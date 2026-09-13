import re

from writing_feedback.schemas.analysis import (
    PassageAnalysis,
    SourceEvidence,
)
from writing_feedback.schemas.evaluation import SummaryEvaluation
from writing_feedback.schemas.feedback import FeedbackDraft
from writing_feedback.schemas.fast_feedback import FastFeedbackDraft
from writing_feedback.schemas.request import FeedbackRequest


class EvidenceValidationError(ValueError):
    """원문 근거 또는 단계 간 참조 검증 실패."""


def split_passage(passage: str) -> dict[int, str]:
    """빈 줄을 기준으로 문단을 나누고 1부터 번호를 부여합니다."""

    normalized = passage.replace("\r\n", "\n").replace("\r", "\n")

    paragraphs = [
        part.strip()
        for part in re.split(r"\n[ \t]*\n", normalized)
        if part.strip()
    ]

    return {
        index: paragraph
        for index, paragraph in enumerate(paragraphs, start=1)
    }


def validate_source_evidence(
    evidence: SourceEvidence,
    paragraphs: dict[int, str],
) -> None:
    paragraph = paragraphs.get(evidence.paragraph_id)

    if paragraph is None:
        raise EvidenceValidationError(
            "원문에 없는 문단을 참조했습니다."
        )

    if evidence.quote not in paragraph:
        raise EvidenceValidationError(
            "인용문이 지정한 원문 문단에 존재하지 않습니다."
        )


def validate_student_quote(
    quote: str,
    student_text: str,
) -> None:
    if quote not in student_text:
        raise EvidenceValidationError(
            "인용문이 학생 글에 존재하지 않습니다."
        )


def validate_passage_analysis(
    request: FeedbackRequest,
    analysis: PassageAnalysis,
) -> None:
    paragraphs = split_passage(request.passage)

    actual_ids = {
        paragraph.paragraph_id
        for paragraph in analysis.paragraphs
    }

    if actual_ids != set(paragraphs):
        raise EvidenceValidationError(
            "분석한 문단 목록이 원문 문단 목록과 일치하지 않습니다."
        )

    evidence_groups = [
        analysis.central_idea_evidence,
        *(item.evidence for item in analysis.paragraphs),
        *(item.evidence for item in analysis.key_points),
        *(item.evidence for item in analysis.concepts),
        *(item.evidence for item in analysis.relations),
    ]

    for group in evidence_groups:
        for evidence in group:
            validate_source_evidence(evidence, paragraphs)


def validate_evaluation(
    request: FeedbackRequest,
    analysis: PassageAnalysis,
    evaluation: SummaryEvaluation,
) -> None:
    expected_point_ids = {
        point.point_id
        for point in analysis.key_points
    }

    evaluated_point_ids = {
        coverage.point_id
        for coverage in evaluation.key_point_coverage
    }

    if evaluated_point_ids != expected_point_ids:
        raise EvidenceValidationError(
            "평가한 핵심 내용 목록이 지문 분석 결과와 일치하지 않습니다."
        )

    paragraphs = split_passage(request.passage)

    for coverage in evaluation.key_point_coverage:
        for evidence in coverage.student_evidence:
            validate_student_quote(
                evidence.quote,
                request.student_text,
            )

    for issue in evaluation.issues:
        if not set(issue.related_point_ids).issubset(expected_point_ids):
            raise EvidenceValidationError(
                "평가 문제가 지문 분석에 없는 핵심 내용을 참조했습니다."
            )

        for evidence in issue.source_evidence:
            validate_source_evidence(evidence, paragraphs)

        for evidence in issue.student_evidence:
            validate_student_quote(
                evidence.quote,
                request.student_text,
            )


def validate_feedback(
    evaluation: SummaryEvaluation,
    feedback: FeedbackDraft,
) -> None:
    expected_issue_ids = {
        issue.issue_id
        for issue in evaluation.issues
    }

    feedback_issue_ids = {
        comment.issue_id
        for comment in feedback.comments
    }

    if feedback_issue_ids != expected_issue_ids:
        raise EvidenceValidationError(
            "첨삭 대상 문제 목록이 평가 결과와 일치하지 않습니다."
        )


def validate_fast_feedback(request: FeedbackRequest, feedback: FastFeedbackDraft) -> None:
    paragraphs = split_passage(request.passage)
    for issue in feedback.issues:
        for evidence in issue.source_evidence:
            validate_source_evidence(evidence, paragraphs)
        for evidence in issue.student_evidence:
            validate_student_quote(evidence.quote, request.student_text)
