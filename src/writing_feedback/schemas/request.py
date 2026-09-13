from enum import Enum
from typing_extensions import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

class SchoolLevel(str, Enum):
    ELEMENTARY = "elementary"
    MIDDLE = "middle"
    HIGH = "high"

class TaskType(str, Enum):
    SUMMARY = "summary"

MAX_GRADE_BY_SCHOOL_LEVEL: dict[SchoolLevel, int] = {
    SchoolLevel.ELEMENTARY : 6,
    SchoolLevel.MIDDLE: 3,
    SchoolLevel.HIGH: 3,
}

class FeedbackRequest(BaseModel):

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    school_level: SchoolLevel = Field(
        description="학교급: elementary, middle, high",
    )

    grade: int = Field(
        strict=True,
        ge=1,
        le=6,
        description="학교 내 학년: 초등 1~6, 중등·고등 1~3",
    )

    task_type: TaskType = Field(
        default=TaskType.SUMMARY,
        description="과제 유형",
    )

    instruction: str = Field(
        min_length=1,
        max_length=5_000,
        description="교사가 제시한 과제 지시문",
    )

    passage: str = Field(
        min_length=1,
        max_length=50_000,
        description="학생이 읽은 원문 지문",
    )

    student_text: str = Field(
        min_length=1,
        max_length=20_000,
        description="학생이 작성한 글",
    )

    teacher_guidance: str | None = Field(
        default=None,
        min_length=1,
        max_length=5_000,
        description="교사가 지정한 추가 평가 기준 또는 지도 방향",
    )

    @model_validator(mode="after")
    def validate_grade_for_school_level(self) -> Self:
        max_grade = MAX_GRADE_BY_SCHOOL_LEVEL[self.school_level]

        if self.grade > max_grade:
            raise ValueError(
                f"{self.school_level.value}의 학년은 "
                f"1~{max_grade} 사이여야 합니다."
            )

        return self
