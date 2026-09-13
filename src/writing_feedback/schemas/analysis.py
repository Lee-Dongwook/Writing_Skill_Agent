from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing_extensions import Self


class AnalysisModel(BaseModel):
    """지문 분석 결과의 공통 설정."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class SourceEvidence(AnalysisModel):
    """분석을 뒷받침하는 원문 인용."""

    paragraph_id: int = Field(
        strict=True,
        ge=1,
        description="원문 문단 번호. 1부터 시작",
    )

    quote: str = Field(
        min_length=1,
        description="해당 문단에서 그대로 가져온 연속된 원문 구절",
    )


class KeyPoint(AnalysisModel):
    """지문에서 전달하는 핵심 내용."""

    point_id: str = Field(
        pattern=r"^K[1-9][0-9]*$",
        description="핵심 내용 식별자. 예: K1",
    )

    content: str = Field(
        min_length=1,
        description="핵심 내용을 설명하는 문장",
    )

    essential_for_summary: bool = Field(
        strict=True,
        description="학년과 과제 지시문을 고려한 요약 필수 여부",
    )

    evidence: list[SourceEvidence] = Field(
        min_length=1,
        description="핵심 내용의 원문 근거",
    )


class ParagraphAnalysis(AnalysisModel):
    """문단별 요지와 글 전체에서의 역할."""

    paragraph_id: int = Field(
        strict=True,
        ge=1,
    )

    main_idea: str = Field(
        min_length=1,
        description="문단의 중심 내용",
    )

    role: str = Field(
        min_length=1,
        description="글 전체에서의 역할. 예: 개념 정의, 원인 설명, 한계 제시",
    )

    evidence: list[SourceEvidence] = Field(
        min_length=1,
    )

    @model_validator(mode="after")
    def validate_evidence_paragraph(self) -> Self:
        if any(
            item.paragraph_id != self.paragraph_id
            for item in self.evidence
        ):
            raise ValueError(
                "문단 분석의 근거는 해당 문단을 참조해야 합니다."
            )

        return self


class KeyConcept(AnalysisModel):
    """원문에 등장하는 주요 개념."""

    term: str = Field(
        min_length=1,
    )

    explanation: str = Field(
        min_length=1,
        description="외부 지식이 아닌 지문 맥락에 따른 개념 설명",
    )

    evidence: list[SourceEvidence] = Field(
        min_length=1,
    )


class RelationType(str, Enum):
    CAUSE_EFFECT = "cause_effect"
    CONTRAST = "contrast"
    CONDITION = "condition"
    PROBLEM_SOLUTION = "problem_solution"
    EXAMPLE = "example"
    ELABORATION = "elaboration"
    LIMITATION = "limitation"
    SEQUENCE = "sequence"


class LogicalRelation(AnalysisModel):
    """핵심 내용 사이의 논리 관계."""

    source_point_id: str = Field(
        pattern=r"^K[1-9][0-9]*$",
    )

    target_point_id: str = Field(
        pattern=r"^K[1-9][0-9]*$",
    )

    relation_type: RelationType

    explanation: str = Field(
        min_length=1,
        description="두 핵심 내용이 어떻게 연결되는지 설명",
    )

    evidence: list[SourceEvidence] = Field(
        min_length=1,
    )


class PassageAnalysis(AnalysisModel):
    """지문 분석 Agent의 최종 출력."""

    topic: str = Field(
        min_length=1,
        description="글이 다루는 주제",
    )

    central_idea: str = Field(
        min_length=1,
        description="글 전체에서 전달하는 중심 내용",
    )

    central_idea_evidence: list[SourceEvidence] = Field(
        min_length=1,
    )

    paragraphs: list[ParagraphAnalysis] = Field(
        min_length=1,
    )

    key_points: list[KeyPoint] = Field(
        min_length=1,
    )

    # 해당 항목이 없는 지문도 빈 배열로 명시하도록 필수 필드로 둡니다.
    concepts: list[KeyConcept]

    relations: list[LogicalRelation]

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        paragraph_ids = [
            paragraph.paragraph_id
            for paragraph in self.paragraphs
        ]

        if len(paragraph_ids) != len(set(paragraph_ids)):
            raise ValueError("문단 번호가 중복되었습니다.")

        point_ids = [
            point.point_id
            for point in self.key_points
        ]

        if len(point_ids) != len(set(point_ids)):
            raise ValueError("핵심 내용 식별자가 중복되었습니다.")

        known_paragraph_ids = set(paragraph_ids)
        known_point_ids = set(point_ids)

        evidence_groups = [
            self.central_idea_evidence,
            *(paragraph.evidence for paragraph in self.paragraphs),
            *(point.evidence for point in self.key_points),
            *(concept.evidence for concept in self.concepts),
            *(relation.evidence for relation in self.relations),
        ]

        for evidence_group in evidence_groups:
            for evidence in evidence_group:
                if evidence.paragraph_id not in known_paragraph_ids:
                    raise ValueError(
                        "존재하지 않는 문단을 참조했습니다: "
                        f"{evidence.paragraph_id}"
                    )

        for relation in self.relations:
            if relation.source_point_id not in known_point_ids:
                raise ValueError(
                    "존재하지 않는 핵심 내용을 참조했습니다: "
                    f"{relation.source_point_id}"
                )

            if relation.target_point_id not in known_point_ids:
                raise ValueError(
                    "존재하지 않는 핵심 내용을 참조했습니다: "
                    f"{relation.target_point_id}"
                )

            if relation.source_point_id == relation.target_point_id:
                raise ValueError(
                    "논리 관계의 출발점과 도착점은 달라야 합니다."
                )

        return self
