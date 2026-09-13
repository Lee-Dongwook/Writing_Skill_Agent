from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing_extensions import Self

from writing_feedback.schemas.analysis import SourceEvidence


class EvaluationModel(BaseModel):
    """학생 글 평가 결과의 공통 설정."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class CoverageStatus(str, Enum):
    ACCURATE = "accurate"      # 핵심 의미를 정확하게 반영
    PARTIAL = "partial"        # 일부만 반영
    MISSING = "missing"        # 반영되지 않음
    DISTORTED = "distorted"    # 의미를 왜곡해서 반영


class IssueCategory(str, Enum):
    OMISSION = "omission"
    DISTORTION = "distortion"
    UNSUPPORTED_CLAIM = "unsupported_claim"
    UNNECESSARY_DETAIL = "unnecessary_detail"
    ORGANIZATION = "organization"
    EXPRESSION = "expression"


class Severity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class StudentEvidence(EvaluationModel):
    """평가 대상이 되는 학생 글의 실제 구절."""

    quote: str = Field(
        min_length=1,
        description="학생 글에서 그대로 가져온 연속된 구절",
    )


class KeyPointCoverage(EvaluationModel):
    """지문의 핵심 내용이 학생 글에 반영된 정도."""

    point_id: str = Field(
        pattern=r"^K[1-9][0-9]*$",
        description="지문 분석 결과의 핵심 내용 식별자",
    )

    status: CoverageStatus

    reason: str = Field(
        min_length=1,
        description="반영 상태를 이렇게 판단한 이유",
    )

    student_evidence: list[StudentEvidence] = Field(
        description="학생 글의 관련 구절. 누락된 경우 빈 배열",
    )

    @model_validator(mode="after")
    def validate_student_evidence(self) -> Self:
        if self.status == CoverageStatus.MISSING:
            if self.student_evidence:
                raise ValueError(
                    "누락된 핵심 내용에는 학생 글 인용을 넣을 수 없습니다."
                )
        elif not self.student_evidence:
            raise ValueError(
                "반영된 핵심 내용에는 학생 글의 근거 구절이 필요합니다."
            )

        return self


class EvaluationIssue(EvaluationModel):
    """교사가 검토할 개별 평가 문제."""

    issue_id: str = Field(
        pattern=r"^I[1-9][0-9]*$",
        description="문제 식별자. 예: I1",
    )

    category: IssueCategory

    severity: Severity = Field(
        description="학년과 과제 기준에 따른 문제의 중요도",
    )

    diagnosis: str = Field(
        min_length=1,
        description="무엇이 문제인지 설명하는 교사용 진단",
    )

    reasoning: str = Field(
        min_length=1,
        description="원문·학생 글·과제 기준에 근거한 간결한 판단 이유",
    )

    related_point_ids: list[str] = Field(
        description="관련 핵심 내용 식별자. 직접 관련이 없으면 빈 배열",
    )

    source_evidence: list[SourceEvidence] = Field(
        description="원문 근거. 표현·구성 문제 등은 빈 배열 가능",
    )

    student_evidence: list[StudentEvidence] = Field(
        description="학생 글의 문제 구절. 누락 문제 등은 빈 배열 가능",
    )

    @model_validator(mode="after")
    def validate_issue_evidence(self) -> Self:
        source_required = {
            IssueCategory.OMISSION,
            IssueCategory.DISTORTION,
        }

        if self.category in source_required and not self.source_evidence:
            raise ValueError(
                "핵심 누락·의미 왜곡 문제에는 원문 근거가 필요합니다."
            )

        student_required = {
            IssueCategory.DISTORTION,
            IssueCategory.UNSUPPORTED_CLAIM,
            IssueCategory.UNNECESSARY_DETAIL,
            IssueCategory.EXPRESSION,
        }

        if self.category in student_required and not self.student_evidence:
            raise ValueError(
                "해당 문제 유형에는 학생 글의 근거 구절이 필요합니다."
            )

        if len(self.related_point_ids) != len(set(self.related_point_ids)):
            raise ValueError("관련 핵심 내용 식별자가 중복되었습니다.")

        return self


class SummaryEvaluation(EvaluationModel):
    """요약 평가 Agent의 최종 출력."""

    overall_assessment: str = Field(
        min_length=1,
        description="이해 정확성·핵심 반영·구성·표현에 대한 교사용 총평",
    )

    key_point_coverage: list[KeyPointCoverage] = Field(
        min_length=1,
        description="지문 분석에서 추출한 모든 핵심 내용의 반영 상태",
    )

    issues: list[EvaluationIssue] = Field(
        description="첨삭이 필요한 문제 목록. 문제가 없으면 빈 배열",
    )

    @model_validator(mode="after")
    def validate_identifiers(self) -> Self:
        point_ids = [
            coverage.point_id
            for coverage in self.key_point_coverage
        ]

        if len(point_ids) != len(set(point_ids)):
            raise ValueError("핵심 내용 반영 평가가 중복되었습니다.")

        issue_ids = [
            issue.issue_id
            for issue in self.issues
        ]

        if len(issue_ids) != len(set(issue_ids)):
            raise ValueError("문제 식별자가 중복되었습니다.")

        known_point_ids = set(point_ids)

        for issue in self.issues:
            for point_id in issue.related_point_ids:
                if point_id not in known_point_ids:
                    raise ValueError(
                        "반영 평가에 없는 핵심 내용을 참조했습니다: "
                        f"{point_id}"
                    )

        return self
