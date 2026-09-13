from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing_extensions import Self


class FeedbackModel(BaseModel):
    """첨삭 결과의 공통 설정."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class FeedbackComment(FeedbackModel):
    """평가 문제 하나에 대한 첨삭 초안."""

    issue_id: str = Field(
        pattern=r"^I[1-9][0-9]*$",
        description="평가 결과의 문제 식별자",
    )

    teacher_note: str = Field(
        min_length=1,
        description="교사가 지도할 때 참고할 설명과 지도 방향",
    )

    student_feedback: str = Field(
        min_length=1,
        description="학년에 맞는 표현으로 작성한 학생용 피드백",
    )

    revision_question: str = Field(
        min_length=1,
        description="학생이 원문을 다시 살피고 스스로 수정하도록 돕는 질문",
    )

    revision_example: str | None = Field(
        min_length=1,
        description=(
            "교사가 선택적으로 제공할 부분 수정 예시. "
            "적절한 예시가 없으면 null"
        ),
    )


class FeedbackDraft(FeedbackModel):
    """첨삭 Agent가 생성하는 교사 검토용 초안."""

    teacher_summary: str = Field(
        min_length=1,
        description="학생 글의 특징과 우선 지도 사항을 정리한 교사용 총평",
    )

    student_summary: str = Field(
        min_length=1,
        description="학생에게 전달할 전체 피드백",
    )

    comments: list[FeedbackComment] = Field(
        description="평가 문제별 첨삭. 문제가 없으면 빈 배열",
    )

    @model_validator(mode="after")
    def validate_unique_issue_ids(self) -> Self:
        issue_ids = [
            comment.issue_id
            for comment in self.comments
        ]

        if len(issue_ids) != len(set(issue_ids)):
            raise ValueError(
                "같은 평가 문제에 대한 첨삭이 중복되었습니다."
            )

        return self
