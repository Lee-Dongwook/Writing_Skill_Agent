import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from pydantic import BaseModel, ValidationError

from writing_feedback.orchestration.state import (
    AgentName,
    ErrorCode,
    WorkflowError,
    WorkflowState,
    WorkflowStatus,
    WorkflowMode,
    utc_now,
)
from writing_feedback.schemas.analysis import PassageAnalysis
from writing_feedback.schemas.evaluation import SummaryEvaluation
from writing_feedback.schemas.feedback import FeedbackDraft
from writing_feedback.schemas.fast_feedback import FastFeedbackDraft
from writing_feedback.orchestration.validation import (
    EvidenceValidationError,
    validate_evaluation,
    validate_feedback,
    validate_passage_analysis,
    validate_fast_feedback,
)


# Agent는 상태를 입력받고, 구조화된 결과를 반환합니다.
AgentOutput = BaseModel | dict[str, Any]
AgentHandler = Callable[[WorkflowState], Awaitable[AgentOutput]]


class AgentExecutionError(Exception):
    """Agent가 명시적으로 전달하는 실행 오류."""

    def __init__(
        self,
        code: ErrorCode,
        *,
        retryable: bool = False,
    ) -> None:
        super().__init__(code.value)
        self.code = code
        self.retryable = retryable


class Supervisor:
    def __init__(
        self,
        handlers: Mapping[AgentName, AgentHandler],
        *,
        timeout_seconds: float = 60.0,
        total_timeout_seconds: float | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("호출 제한 시간은 0보다 커야 합니다.")

        self.handlers = dict(handlers)
        self.timeout_seconds = timeout_seconds
        self.total_timeout_seconds = total_timeout_seconds or timeout_seconds

    @staticmethod
    def select_next_agent(
        state: WorkflowState,
    ) -> AgentName | None:
        """필수 선행 결과를 확인하고 다음 작업을 선택합니다."""

        if state.status in {
            WorkflowStatus.AWAITING_TEACHER_REVIEW,
            WorkflowStatus.FAILED,
        }:
            return None

        if state.mode == WorkflowMode.FAST:
            return None if state.fast_feedback is not None else AgentName.FAST

        if state.evaluation is not None and state.passage_analysis is None:
            raise ValueError("지문 분석 없이 평가 결과가 존재합니다.")

        if state.feedback is not None and state.evaluation is None:
            raise ValueError("평가 없이 첨삭 결과가 존재합니다.")

        if state.passage_analysis is None:
            return AgentName.PASSAGE

        if state.evaluation is None:
            return AgentName.EVALUATION

        if state.feedback is None:
            return AgentName.FEEDBACK

        return None

    async def run(self, state: WorkflowState) -> WorkflowState:
        """새 실행을 시작하고 성공 또는 실패 상태까지 진행합니다."""

        self._validate_start(state)

        # 호출자가 전달한 초기 상태는 그대로 보존합니다.
        state = state.model_copy(deep=True)
        state.status = WorkflowStatus.RUNNING
        started = time.perf_counter()
        state.updated_at = utc_now()

        while True:
            agent = self.select_next_agent(state)
            state.next_agent = agent
            state.updated_at = utc_now()

            # 마지막 허용 호출에서 성공한 경우도 정상 종료합니다.
            if agent is None:
                state.status = WorkflowStatus.AWAITING_TEACHER_REVIEW
                state.updated_at = utc_now()
                return state

            if state.step_count >= state.max_steps:
                self._record_error(
                    state,
                    agent=None,
                    code=ErrorCode.STEP_LIMIT_EXCEEDED,
                    retryable=False,
                )
                return state

            remaining = self.total_timeout_seconds - (time.perf_counter() - started)
            if remaining <= 0:
                self._record_error(state, agent=agent, code=ErrorCode.TIME_BUDGET_EXCEEDED, retryable=False)
                return state

            # 재시도를 포함해 실제 호출 직전에 증가시킵니다.
            state.step_count += 1
            state.updated_at = utc_now()

            try:
                # Agent에는 복사본을 전달해 공유 상태 직접 변경을 막습니다.
                output = await asyncio.wait_for(
                    self.handlers[agent](state.model_copy(deep=True)),
                    timeout=min(self.timeout_seconds, remaining),
                )

                self._store_output(state, agent, output)

            except asyncio.TimeoutError:
                self._record_error(
                    state,
                    agent=agent,
                    code=ErrorCode.MODEL_CALL_FAILED,
                    retryable=True,
                )

            except AgentExecutionError as exc:
                self._record_error(
                    state,
                    agent=agent,
                    code=exc.code,
                    retryable=exc.retryable,
                )
                
            except EvidenceValidationError:
                self._record_error(
                    state,
                    agent=agent,
                    code=ErrorCode.EVIDENCE_MISMATCH,
                    retryable=True,
                )

            except ValidationError:
                self._record_error(
                    state,
                    agent=agent,
                    code=ErrorCode.INVALID_OUTPUT,
                    retryable=True,
                )

            except Exception:
                # 예외 원문에는 학생 글이나 인증 정보가 섞일 수 있으므로
                # 공유 상태에는 정해진 오류 요약만 저장합니다.
                self._record_error(
                    state,
                    agent=agent,
                    code=ErrorCode.INTERNAL_ERROR,
                    retryable=False,
                )

            else:
                state.retry_count = 0
                state.updated_at = utc_now()
                continue

            if state.status == WorkflowStatus.FAILED:
                return state

            # 다음 루프에서 실제 재시도를 시작합니다.
            state.retry_count += 1

    def _validate_start(self, state: WorkflowState) -> None:
        if state.status != WorkflowStatus.PENDING:
            raise ValueError("새로운 pending 상태만 실행할 수 있습니다.")

        if (
            state.step_count != 0
            or state.retry_count != 0
            or state.errors
            or state.next_agent is not None
            or state.passage_analysis is not None
            or state.evaluation is not None
            or state.feedback is not None
            or state.fast_feedback is not None
        ):
            raise ValueError("이전 실행 이력이 없는 새 상태가 필요합니다.")

        if state.rubric is None:
            raise ValueError("실행 전에 평가 기준을 설정해야 합니다.")

        required = {AgentName.FAST} if state.mode == WorkflowMode.FAST else {AgentName.PASSAGE, AgentName.EVALUATION, AgentName.FEEDBACK}
        missing = required - set(self.handlers)

        if missing:
            names = ", ".join(sorted(agent.value for agent in missing))
            raise ValueError(f"등록되지 않은 Agent가 있습니다: {names}")

    @staticmethod
    def _store_output(
        state: WorkflowState,
        agent: AgentName,
        output: AgentOutput,
    ) -> None:
        # 모델 객체로 반환해도 다시 데이터로 변환한 후 검증합니다.
        payload = (
            output.model_dump()
            if isinstance(output, BaseModel)
            else output
        )

        if agent == AgentName.PASSAGE:
            result = PassageAnalysis.model_validate(payload)
            validate_passage_analysis(
                state.request,
                result,
            )

            state.passage_analysis = result

        elif agent == AgentName.EVALUATION:
            if state.passage_analysis is None:
                raise AgentExecutionError(
                    ErrorCode.INTERNAL_ERROR,
                    retryable=False,
                )
            result = SummaryEvaluation.model_validate(payload)
            validate_evaluation(
                state.request,
                state.passage_analysis,
                result,
            )
            state.evaluation = result

        elif agent == AgentName.FEEDBACK:
            if state.evaluation is None:
                raise AgentExecutionError(
                    ErrorCode.INTERNAL_ERROR,
                    retryable=False,
                )
            result = FeedbackDraft.model_validate(payload)
            validate_feedback(
                state.evaluation,
                result,
            )

            state.feedback = result

        elif agent == AgentName.FAST:
            result = FastFeedbackDraft.model_validate(payload)
            validate_fast_feedback(state.request, result)
            state.fast_feedback = result

        else:
            raise ValueError(f"지원하지 않는 Agent입니다: {agent}")

    @staticmethod
    def _record_error(
        state: WorkflowState,
        *,
        agent: AgentName | None,
        code: ErrorCode,
        retryable: bool,
    ) -> None:
        messages = {
            ErrorCode.MODEL_CALL_FAILED: "모델 호출에 실패했습니다.",
            ErrorCode.INVALID_OUTPUT: "Agent 출력 형식이 올바르지 않습니다.",
            ErrorCode.EVIDENCE_MISMATCH: "출력의 근거 또는 참조가 일치하지 않습니다.",
            ErrorCode.STEP_LIMIT_EXCEEDED: "전체 호출 횟수 제한을 초과했습니다.",
            ErrorCode.INTERNAL_ERROR: "내부 실행 오류가 발생했습니다.",
            ErrorCode.TIME_BUDGET_EXCEEDED: "전체 실행 시간 예산을 초과했습니다.",
            ErrorCode.INPUT_BUDGET_EXCEEDED: "입력이 빠른 경로의 토큰 예산을 초과했습니다.",
        }

        state.errors.append(
            WorkflowError(
                agent=agent,
                code=code,
                message=messages[code],
                retryable=retryable,
                step=state.step_count,
            )
        )

        can_retry = (
            retryable
            and state.retry_count < state.max_retries
            and state.step_count < state.max_steps
        )

        if not can_retry:
            state.status = WorkflowStatus.FAILED
            state.next_agent = None

        state.updated_at = utc_now()
