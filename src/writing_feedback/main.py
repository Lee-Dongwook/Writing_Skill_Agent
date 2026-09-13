import argparse
import asyncio
import json
import time
from pathlib import Path

from pydantic import ValidationError

from writing_feedback.agents.mock import (
    ensure_demo_request,
    mock_evaluation,
    mock_feedback,
    mock_passage,
)
from writing_feedback.agents.passage import PassageAgent
from writing_feedback.agents.evaluation import EvaluationAgent
from writing_feedback.agents.feedback import FeedbackAgent
from writing_feedback.agents.fast_feedback import FastFeedbackAgent
from writing_feedback.config import Settings
from writing_feedback.llm.base import LLMError
from writing_feedback.llm.client import OllamaClient
from writing_feedback.orchestration.state import (
    AgentName,
    WorkflowState,
    WorkflowStatus,
    WorkflowMode,
)
from writing_feedback.orchestration.supervisor import (
    AgentExecutionError,
    Supervisor,
)
from writing_feedback.orchestration.validation import (
    EvidenceValidationError,
    validate_passage_analysis,
)
from writing_feedback.rubrics.loader import (
    RubricLoadError,
    load_rubric,
)
from writing_feedback.schemas.analysis import PassageAnalysis
from writing_feedback.schemas.request import FeedbackRequest


def build_performance(started: float, state: WorkflowState, calls: list[dict]) -> dict:
    """호출 본문 없이 CLI 결과에 포함할 실행·단계별 집계."""
    stages: dict[str, dict] = {}
    for call in calls:
        item = stages.setdefault(call["stage"], {"call_count": 0, "elapsed_seconds": 0.0})
        item["call_count"] += 1
        item["elapsed_seconds"] = round(item["elapsed_seconds"] + call["elapsed_seconds"], 3)
    return {
        "total_seconds": round(time.perf_counter() - started, 3),
        "stage_summary": stages,
        "calls": calls,
        "status": state.status.value,
        "error_codes": [error.code.value for error in state.errors],
    }


async def run_passage_only(
    state: WorkflowState,
    settings: Settings,
) -> PassageAnalysis:
    client = OllamaClient(settings)

    try:
        agent = PassageAgent(client)
        result = await agent(state)

        validate_passage_analysis(
            state.request,
            result,
        )

        return result

    finally:
        await client.aclose()

async def run_local_workflow(
    state: WorkflowState,
    settings: Settings,
) -> WorkflowState:
    client = OllamaClient(settings)
    started = time.perf_counter()

    try:
        supervisor = Supervisor(
            handlers={
                AgentName.PASSAGE: PassageAgent(client),
                AgentName.EVALUATION: EvaluationAgent(client),
                AgentName.FEEDBACK: FeedbackAgent(client),
            },
            timeout_seconds=settings.llm_timeout_seconds,
            total_timeout_seconds=settings.workflow_timeout_seconds,
        )

        result = await supervisor.run(state)
        result.performance = build_performance(started, result, client.metrics)
        return result

    finally:
        await client.aclose()

async def run_fast_workflow(state: WorkflowState, settings: Settings) -> WorkflowState:
    client = OllamaClient(settings)
    started = time.perf_counter()
    try:
        supervisor = Supervisor(
            handlers={AgentName.FAST: FastFeedbackAgent(client, input_token_budget=settings.fast_input_token_budget, num_predict=settings.fast_num_predict)},
            timeout_seconds=settings.llm_timeout_seconds,
            total_timeout_seconds=settings.workflow_timeout_seconds,
        )
        result = await supervisor.run(state)
        result.performance = build_performance(started, result, client.metrics)
        return result
    finally:
        await client.aclose()

def main() -> None:
    parser = argparse.ArgumentParser(
        description="국어 비문학 요약문 첨삭 에이전트",
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="첨삭 요청 JSON 파일 경로",
    )

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--mock",
        action="store_true",
        help="기본 예제 전용 고정 데이터로 전체 흐름 실행",
    )
    mode.add_argument(
        "--passage-only",
        action="store_true",
        help="로컬 LLM으로 지문 분석과 근거 검증 실행",
    )
    mode.add_argument(
        "--local",
        action="store_true",
        help="로컬 LLM 빠른 단일 호출 첨삭 실행(기본 권장)",
    )
    mode.add_argument(
        "--detailed",
        action="store_true",
        help="로컬 LLM 3단계 상세 분석·평가·첨삭 실행",
    )

    args = parser.parse_args()

    try:
        payload = json.loads(
            args.input.read_text(encoding="utf-8"),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        parser.error(f"입력 파일을 읽을 수 없습니다: {exc}")

    try:
        request = FeedbackRequest.model_validate(payload)
    except ValidationError as exc:
        messages = []

        for error in exc.errors(include_input=False):
            location = ".".join(
                str(part) for part in error["loc"]
            ) or "request"

            messages.append(f"- {location}: {error['msg']}")

        parser.error(
            "입력값 검증에 실패했습니다.\n"
            + "\n".join(messages)
        )

    try:
        rubric = load_rubric(request)
    except RubricLoadError as exc:
        parser.error(str(exc))

    state = WorkflowState(
        request=request,
        rubric=rubric,
        max_retries=0,
    )

    if args.mock:
        try:
            ensure_demo_request(request)
        except ValueError as exc:
            parser.error(str(exc))

        supervisor = Supervisor(
            handlers={
                AgentName.PASSAGE: mock_passage,
                AgentName.EVALUATION: mock_evaluation,
                AgentName.FEEDBACK: mock_feedback,
            }
        )

        result = asyncio.run(supervisor.run(state))

        print("[MOCK] 실행 확인용 고정 결과입니다.")
        print(result.model_dump_json(indent=2))

        if result.status == WorkflowStatus.FAILED:
            raise SystemExit(1)

        return

    try:
        settings = Settings()
    except ValidationError:
        parser.error(".env 또는 환경 변수의 설정값을 확인하세요.")

    if args.local or args.detailed:
        state.mode = WorkflowMode.FAST if args.local else WorkflowMode.DETAILED
        print(
            f"[LOCAL] {settings.ollama_model}로 {'빠른 단일 호출' if args.local else '상세 3단계'} 첨삭 실행 중...",
            flush=True,
        )

        result = asyncio.run(
            run_fast_workflow(state, settings) if args.local else run_local_workflow(state, settings)
        )

        if result.status == WorkflowStatus.FAILED:
            print("첨삭 실행이 실패했습니다.")
        else:
            print("첨삭 초안 생성 완료 — 교사 검토 대기")

        print(result.model_dump_json(indent=2))

        if result.status == WorkflowStatus.FAILED:
            raise SystemExit(1)

        return

    print(
        f"[LOCAL] {settings.ollama_model}로 지문 분석 중...",
        flush=True,
    )

    try:
        analysis = asyncio.run(
            run_passage_only(state, settings)
        )

    except AgentExecutionError as exc:
        print(f"지문 분석 실패: {exc.code.value}")

        # Client가 만든 안전한 오류 요약만 표시합니다.
        cause = exc.__cause__
        if isinstance(cause, LLMError):
            print(f"원인: {cause}")

        print(f"재시도 가능 여부: {exc.retryable}")
        raise SystemExit(1)

    except EvidenceValidationError as exc:
        print(f"원문 근거 검증 실패: {exc}")
        raise SystemExit(1)

    print("지문 분석 및 원문 근거 검증 완료")
    print(analysis.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
