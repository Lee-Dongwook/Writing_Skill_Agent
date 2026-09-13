from importlib.resources import files
from typing import Annotated

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)
from typing_extensions import Self

from writing_feedback.orchestration.state import (
    ResolvedRubric,
    RubricCriterion,
)
from writing_feedback.schemas.request import (
    FeedbackRequest,
    MAX_GRADE_BY_SCHOOL_LEVEL,
    SchoolLevel,
    TaskType,
)


NonEmptyText = Annotated[str, Field(min_length=1)]
GradeNumber = Annotated[int, Field(strict=True, ge=1, le=6)]


class RubricLoadError(ValueError):
    """평가 기준 로딩 또는 설정 검증 실패."""


class RubricDefinition(BaseModel):
    """YAML 파일의 구조."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    rubric_id: NonEmptyText
    version: NonEmptyText

    school_level: SchoolLevel
    task_type: TaskType

    criteria: list[RubricCriterion] = Field(min_length=1)

    grade_expectations: dict[GradeNumber, NonEmptyText]

    feedback_guidance: NonEmptyText

    @model_validator(mode="after")
    def validate_definition(self) -> Self:
        criterion_ids = [
            criterion.criterion_id
            for criterion in self.criteria
        ]

        if len(criterion_ids) != len(set(criterion_ids)):
            raise ValueError("평가 기준 ID가 중복되었습니다.")

        max_grade = MAX_GRADE_BY_SCHOOL_LEVEL[self.school_level]
        expected_grades = set(range(1, max_grade + 1))

        if set(self.grade_expectations) != expected_grades:
            raise ValueError(
                "학교급에 해당하는 모든 학년의 기준이 필요합니다."
            )

        return self


def load_rubric(request: FeedbackRequest) -> ResolvedRubric:
    filename = f"{request.school_level.value}.yaml"

    resource = files(
        "writing_feedback.rubrics"
    ).joinpath(filename)

    try:
        raw = resource.read_text(encoding="utf-8")
        payload = yaml.safe_load(raw)
        definition = RubricDefinition.model_validate(payload)

    except (OSError, UnicodeError, yaml.YAMLError, ValidationError) as exc:
        raise RubricLoadError(
            f"평가 기준 파일을 읽거나 검증할 수 없습니다: {filename}"
        ) from exc

    if definition.school_level != request.school_level:
        raise RubricLoadError(
            "평가 기준 파일의 학교급이 요청과 일치하지 않습니다."
        )

    if definition.task_type != request.task_type:
        raise RubricLoadError(
            "평가 기준 파일의 과제 유형이 요청과 일치하지 않습니다."
        )

    grade_expectation = definition.grade_expectations[request.grade]

    criteria = [
        RubricCriterion(
            criterion_id=criterion.criterion_id,
            description=criterion.description,
            expectation=(
                f"{criterion.expectation}\n"
                f"학년별 적용 수준: {grade_expectation}"
            ),
        )
        for criterion in definition.criteria
    ]

    return ResolvedRubric(
        rubric_id=f"{definition.rubric_id}-grade-{request.grade}",
        version=definition.version,
        criteria=criteria,
        feedback_guidance=definition.feedback_guidance,
    )
