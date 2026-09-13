"""CLI와 HTTP API가 함께 사용하는 실제 첨삭 실행 경로."""

import time
from collections.abc import Callable

from writing_feedback.agents.evaluation import EvaluationAgent
from writing_feedback.agents.fast_feedback import FastFeedbackAgent
from writing_feedback.agents.feedback import FeedbackAgent
from writing_feedback.agents.passage import PassageAgent
from writing_feedback.config import Settings
from writing_feedback.llm.client import OllamaClient
from writing_feedback.orchestration.state import AgentName, WorkflowState
from writing_feedback.orchestration.supervisor import Supervisor


def build_performance(started: float, state: WorkflowState, calls: list[dict]) -> dict:
    """입·출력 본문 없이 실행 성능만 집계한다."""
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


async def run_workflow(
    state: WorkflowState,
    settings: Settings,
    *,
    on_state_change: Callable[[WorkflowState], None] | None = None,
) -> WorkflowState:
    """요청의 mode에 따라 빠른 또는 상세 Agent를 실행한다."""
    client = OllamaClient(settings)
    started = time.perf_counter()
    try:
        if state.mode.value == "fast":
            handlers = {
                AgentName.FAST: FastFeedbackAgent(
                    client,
                    input_token_budget=settings.fast_input_token_budget,
                    num_predict=settings.fast_num_predict,
                )
            }
        else:
            handlers = {
                AgentName.PASSAGE: PassageAgent(client),
                AgentName.EVALUATION: EvaluationAgent(client),
                AgentName.FEEDBACK: FeedbackAgent(client),
            }
        supervisor = Supervisor(
            handlers=handlers,
            timeout_seconds=settings.llm_timeout_seconds,
            total_timeout_seconds=settings.workflow_timeout_seconds,
            on_state_change=on_state_change,
        )
        result = await supervisor.run(state)
        result.performance = build_performance(started, result, client.metrics)
        return result
    finally:
        await client.aclose()
