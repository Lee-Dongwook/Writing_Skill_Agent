from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from writing_feedback.schemas.analysis import PassageAnalysis
from writing_feedback.schemas.evaluation import SummaryEvaluation
from writing_feedback.schemas.feedback import FeedbackDraft
from writing_feedback.schemas.request import FeedbackRequest


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StateModel(BaseModel):
    """실행 상태 모델의 공통 설정."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
    )


class AgentName(str, Enum):
    PASSAGE = "passage"
    EVALUATION = "evaluation"
    FEEDBACK = "feedback"


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_TEACHER_REVIEW = "awaiting_teacher_review"
    FAILED = "failed"


class ErrorCode(str, Enum):
    MODEL_CALL_FAILED = "model_call_failed"
    INVALID_OUTPUT = "invalid_output"
    EVIDENCE_MISMATCH = "evidence_mismatch"
    STEP_LIMIT_EXCEEDED = "step_limit_exceeded"
    INTERNAL_ERROR = "internal_error"


class WorkflowError(StateModel):
    """실행 중 발생한 오류 기록."""

    agent: AgentName | None = Field(
        description="오류 발생 에이전트. Supervisor 자체 오류는 None",
    )

    code: ErrorCode

    message: str = Field(
        min_length=1,
        description="원문·학생 글·API 키를 포함하지 않는 오류 요약",
    )

    retryable: bool = Field(
        strict=True,
        description="재시도 가능한 오류인지 여부",
    )

    step: int = Field(
        strict=True,
        ge=0,
        description="오류 발생 시점의 전체 에이전트 호출 횟수",
    )

    occurred_at: datetime = Field(
        default_factory=utc_now,
    )


class RubricCriterion(StateModel):
    """이번 실행에 적용할 평가 기준 한 항목."""

    criterion_id: str = Field(
        min_length=1,
        description="평가 기준 식별자",
    )

    description: str = Field(
        min_length=1,
        description="무엇을 평가할지에 대한 설명",
    )

    expectation: str = Field(
        min_length=1,
        description="해당 학교급·학년에서 기대하는 수행 수준",
    )


class ResolvedRubric(StateModel):
    """학교급·학년·과제에 맞춰 선택한 평가 기준."""

    rubric_id: str = Field(
        min_length=1,
    )

    version: str = Field(
        min_length=1,
        description="평가 기준 버전. 예: 0.1.0",
    )

    criteria: list[RubricCriterion] = Field(
        min_length=1,
    )

    feedback_guidance: str = Field(
        min_length=1,
        description="피드백의 어휘 수준·말투·지도 방식",
    )


class WorkflowState(StateModel):
    """한 번의 첨삭 실행에 대한 공유 상태."""

    run_id: str = Field(
        default_factory=lambda: str(uuid4()),
    )

    request: FeedbackRequest

    rubric: ResolvedRubric | None = None

    passage_analysis: PassageAnalysis | None = None
    evaluation: SummaryEvaluation | None = None
    feedback: FeedbackDraft | None = None

    status: WorkflowStatus = WorkflowStatus.PENDING
    next_agent: AgentName | None = None

    step_count: int = Field(
        default=0,
        strict=True,
        ge=0,
        description="재시도를 포함한 전체 에이전트 호출 횟수",
    )

    retry_count: int = Field(
        default=0,
        strict=True,
        ge=0,
        description="현재 단계에서 시작한 추가 시도 횟수",
    )

    max_steps: int = Field(
        default=9,
        strict=True,
        ge=1,
        description="한 실행에서 허용할 전체 에이전트 호출 상한",
    )

    max_retries: int = Field(
        default=2,
        strict=True,
        ge=0,
        description="단계별 최초 호출 이후 허용할 추가 시도 횟수",
    )

    errors: list[WorkflowError] = Field(
        default_factory=list,
    )

    created_at: datetime = Field(
        default_factory=utc_now,
    )

    updated_at: datetime = Field(
        default_factory=utc_now,
    )
