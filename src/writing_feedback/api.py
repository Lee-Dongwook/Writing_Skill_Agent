"""로컬 개발용 비동기 작업 API. 단일 프로세스 메모리 저장소를 사용한다."""

import asyncio
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Literal

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from writing_feedback.config import Settings
from writing_feedback.orchestration.state import (
    ErrorCode,
    WorkflowError,
    WorkflowMode,
    WorkflowState,
    WorkflowStatus,
    utc_now,
)
from writing_feedback.rubrics.loader import RubricLoadError, load_rubric
from writing_feedback.schemas.request import FeedbackRequest, SchoolLevel, TaskType
from writing_feedback.service import run_workflow


class RunCreateRequest(FeedbackRequest):
    """브라우저가 보내는 요청 계약. mock은 HTTP API에서 지원하지 않는다."""
    mode: WorkflowMode = WorkflowMode.FAST


class RunCreated(BaseModel):
    run_id: str
    status: Literal["pending"]


class RunView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str
    status: WorkflowStatus
    stage: str | None
    errors: list[WorkflowError]
    result: dict | None = None
    performance: dict | None = None


class RunRecord:
    def __init__(self, state: WorkflowState) -> None:
        self.state = state
        self.completed_at: float | None = None


class RunStore:
    """로컬 개발 전용: 재시작 시 유실되고 완료 결과는 TTL 뒤 정리된다."""
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.records: dict[str, RunRecord] = {}
        self.gate = asyncio.Semaphore(settings.api_max_concurrent_runs)

    def cleanup(self) -> None:
        threshold = time.monotonic() - self.settings.api_result_ttl_seconds
        for run_id, record in list(self.records.items()):
            if record.completed_at is not None and record.completed_at < threshold:
                del self.records[run_id]

    def active_count(self) -> int:
        return sum(record.state.status in {WorkflowStatus.PENDING, WorkflowStatus.RUNNING} for record in self.records.values())

    def create(self, state: WorkflowState) -> RunRecord:
        self.cleanup()
        if self.active_count() >= self.settings.api_queue_limit:
            raise QueueFullError
        record = RunRecord(state)
        self.records[state.run_id] = record
        return record

    def get(self, run_id: str) -> RunRecord | None:
        self.cleanup()
        return self.records.get(run_id)

    async def execute(self, record: RunRecord) -> None:
        async with self.gate:
            # 대기 중에도 이미 작업이 정리/취소될 수 있는 확장 가능성을 남긴다.
            if record.state.status != WorkflowStatus.PENDING:
                return

            def update(state: WorkflowState) -> None:
                record.state = state

            try:
                record.state = await execute_safely(record.state, self.settings, on_state_change=update)
            finally:
                record.completed_at = time.monotonic()


async def execute_safely(state: WorkflowState, settings: Settings, *, on_state_change=None) -> WorkflowState:
    try:
        return await run_workflow(state, settings, on_state_change=on_state_change)
    except Exception:
        # 프롬프트·학생 글·예외 원문을 로그나 응답에 넣지 않는다.
        state.status = WorkflowStatus.FAILED
        state.errors.append(WorkflowError(
            agent=None, code=ErrorCode.INTERNAL_ERROR,
            message="서버가 첨삭 작업을 완료하지 못했습니다.", retryable=False,
            step=state.step_count,
        ))
        state.updated_at = utc_now()
        return state


class QueueFullError(Exception):
    pass


def public_view(state: WorkflowState) -> RunView:
    stage = state.next_agent.value if state.status == WorkflowStatus.RUNNING and state.next_agent else None
    result = None
    if state.status == WorkflowStatus.AWAITING_TEACHER_REVIEW:
        # 요청 원문은 다시 보내지 않는다. 결과와 성능 메타데이터만 노출한다.
        result = {
            "mode": state.mode.value,
            "fast_feedback": state.fast_feedback.model_dump(mode="json") if state.fast_feedback else None,
            "passage_analysis": state.passage_analysis.model_dump(mode="json") if state.passage_analysis else None,
            "evaluation": state.evaluation.model_dump(mode="json") if state.evaluation else None,
            "feedback": state.feedback.model_dump(mode="json") if state.feedback else None,
        }
    return RunView(
        run_id=state.run_id, status=state.status, stage=stage, errors=state.errors,
        result=result, performance=state.performance or None,
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    store = RunStore(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield

    app = FastAPI(title="Writing Feedback Local API", version="0.1.0", lifespan=lifespan)
    app.state.run_store = store
    origins = settings.api_cors_origins_list
    if origins:
        app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

    @app.get("/api/health")
    async def health() -> dict:
        return {"status": "ok", "provider": settings.llm_provider, "model": settings.model_name}

    @app.post("/api/runs", response_model=RunCreated | RunView, status_code=status.HTTP_202_ACCEPTED)
    async def create_run(payload: RunCreateRequest, request: Request, response: Response) -> RunCreated | RunView:
        try:
            rubric = load_rubric(payload)
        except RubricLoadError as exc:
            raise HTTPException(status_code=503, detail={"code": "rubric_configuration_error", "message": "평가 기준 설정을 확인하세요."}) from exc
        state = WorkflowState(request=FeedbackRequest.model_validate(payload.model_dump(exclude={"mode"})), rubric=rubric, mode=payload.mode, max_retries=0)
        if settings.api_inline_runs:
            # 서버리스 배포: 요청 안에서 끝낸 완료/실패 상태를 200으로 바로 반환한다.
            response.status_code = status.HTTP_200_OK
            return public_view(await execute_safely(state, settings))
        try:
            record = store.create(state)
        except QueueFullError:
            raise HTTPException(status_code=429, detail={"code": "queue_full", "message": "로컬 첨삭 대기열이 가득 찼습니다. 잠시 후 명시적으로 다시 실행하세요."}) from None
        request.app.state.background_tasks = getattr(request.app.state, "background_tasks", set())
        task = asyncio.create_task(store.execute(record))
        request.app.state.background_tasks.add(task)
        task.add_done_callback(request.app.state.background_tasks.discard)
        return RunCreated(run_id=state.run_id, status="pending")

    @app.get("/api/runs/{run_id}", response_model=RunView)
    async def get_run(run_id: str) -> RunView:
        record = store.get(run_id)
        if record is None:
            raise HTTPException(status_code=404, detail={"code": "run_not_found", "message": "실행을 찾을 수 없습니다. 서버 재시작 또는 결과 보존 시간 만료일 수 있습니다."})
        return public_view(record.state)

    return app


app = create_app()


def run() -> None:
    import uvicorn
    uvicorn.run("writing_feedback.api:app", host="127.0.0.1", port=8000, reload=False)
