from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing_extensions import Self

from writing_feedback.schemas.analysis import SourceEvidence
from writing_feedback.schemas.evaluation import IssueCategory, StudentEvidence


class FastModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class FastIssue(FastModel):
    """단일 호출 첨삭에서 교사가 검토할 핵심 문제 하나."""
    category: IssueCategory
    diagnosis: str = Field(min_length=1, max_length=240)
    source_evidence: list[SourceEvidence] = Field(max_length=2)
    student_evidence: list[StudentEvidence] = Field(max_length=2)

    @model_validator(mode="after")
    def require_applicable_evidence(self) -> Self:
        if self.category in {IssueCategory.OMISSION, IssueCategory.DISTORTION} and not self.source_evidence:
            raise ValueError("누락·왜곡 문제에는 원문 근거가 필요합니다.")
        if self.category in {IssueCategory.DISTORTION, IssueCategory.UNSUPPORTED_CLAIM, IssueCategory.UNNECESSARY_DETAIL, IssueCategory.EXPRESSION} and not self.student_evidence:
            raise ValueError("이 문제 유형에는 학생 글 인용이 필요합니다.")
        return self


class FastFeedbackDraft(FastModel):
    """빠른 경로의 독립 결과. 상세 중간 분석 스키마를 채우지 않는다."""
    passage_summary: str = Field(min_length=1, max_length=360)
    issues: list[FastIssue] = Field(max_length=3)
    student_feedback: str = Field(min_length=1, max_length=420)
