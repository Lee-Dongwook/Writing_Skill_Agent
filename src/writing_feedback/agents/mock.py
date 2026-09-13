from typing import Any

from writing_feedback.orchestration.state import (
    ResolvedRubric,
    RubricCriterion,
    WorkflowState,
)
from writing_feedback.schemas.request import (
    FeedbackRequest,
    SchoolLevel,
)


DEMO_PASSAGE = (
    "도시의 나무는 여름철 기온을 낮추는 데 도움을 준다. "
    "나뭇잎이 햇빛을 가려 그늘을 만들고, "
    "잎에서 물이 증발할 때 주변의 열을 흡수하기 때문이다. "
    "하지만 나무를 심는 것만으로 모든 도시의 더위 문제가 "
    "해결되는 것은 아니다. "
    "바람이 통하는 길을 확보하고 건물의 배치를 고려하는 노력도 "
    "함께 필요하다."
)

DEMO_STUDENT_TEXT = (
    "도시의 나무는 그늘을 만들어 기온을 낮춘다. "
    "그래서 나무를 많이 심으면 도시의 더위 문제를 "
    "모두 해결할 수 있다."
)

SHADE_QUOTE = "나뭇잎이 햇빛을 가려 그늘을 만들고"
EVAPORATION_QUOTE = (
    "잎에서 물이 증발할 때 주변의 열을 흡수하기 때문이다."
)
LIMITATION_QUOTE = (
    "하지만 나무를 심는 것만으로 모든 도시의 더위 문제가 "
    "해결되는 것은 아니다."
)
STUDENT_ERROR_QUOTE = (
    "그래서 나무를 많이 심으면 도시의 더위 문제를 "
    "모두 해결할 수 있다."
)


def ensure_demo_request(request: FeedbackRequest) -> None:
    """고정 예제 결과를 다른 글에 적용하지 않도록 제한합니다."""

    if (
        request.passage != DEMO_PASSAGE
        or request.student_text != DEMO_STUDENT_TEXT
    ):
        raise ValueError(
            "mock 모드는 기본 '도시의 나무' 예제만 지원합니다."
        )


def source(quote: str) -> dict[str, Any]:
    return {
        "paragraph_id": 1,
        "quote": quote,
    }


def build_mock_rubric(request: FeedbackRequest) -> ResolvedRubric:
    guidance_by_level = {
        SchoolLevel.ELEMENTARY: "쉬운 낱말과 짧은 질문으로 안내합니다.",
        SchoolLevel.MIDDLE: "핵심 내용과 논리 관계를 확인하도록 안내합니다.",
        SchoolLevel.HIGH: "논지와 조건·한계를 정밀하게 검토하도록 안내합니다.",
    }

    return ResolvedRubric(
        rubric_id=(
            f"mock-summary-{request.school_level.value}-{request.grade}"
        ),
        version="0.1.0",
        criteria=[
            RubricCriterion(
                criterion_id="meaning_accuracy",
                description="원문의 핵심 의미를 정확하게 전달하는지 확인",
                expectation=(
                    "이번 실행 확인용 예제에서는 나무의 냉각 효과와 "
                    "그 한계를 함께 반영하는지 확인합니다."
                ),
            )
        ],
        feedback_guidance=guidance_by_level[request.school_level],
    )


async def mock_passage(state: WorkflowState) -> dict[str, Any]:
    ensure_demo_request(state.request)

    return {
        "topic": "도시 나무의 냉각 효과와 한계",
        "central_idea": (
            "나무는 도시의 기온을 낮추지만 "
            "더위 문제를 해결하려면 다른 노력도 필요하다."
        ),
        "central_idea_evidence": [
            source("도시의 나무는 여름철 기온을 낮추는 데 도움을 준다."),
            source(LIMITATION_QUOTE),
        ],
        "paragraphs": [
            {
                "paragraph_id": 1,
                "main_idea": "나무의 냉각 원리와 추가 대책의 필요성",
                "role": "효과 설명과 한계 제시",
                "evidence": [source(LIMITATION_QUOTE)],
            }
        ],
        "key_points": [
            {
                "point_id": "K1",
                "content": "나무는 그늘을 만들어 기온을 낮춘다.",
                "essential_for_summary": True,
                "evidence": [source(SHADE_QUOTE)],
            },
            {
                "point_id": "K2",
                "content": "잎에서 물이 증발할 때 주변의 열을 흡수한다.",
                "essential_for_summary": False,
                "evidence": [source(EVAPORATION_QUOTE)],
            },
            {
                "point_id": "K3",
                "content": "나무만으로 도시의 더위 문제를 모두 해결할 수 없다.",
                "essential_for_summary": True,
                "evidence": [source(LIMITATION_QUOTE)],
            },
        ],
        "concepts": [],
        "relations": [
            {
                "source_point_id": "K1",
                "target_point_id": "K3",
                "relation_type": "limitation",
                "explanation": (
                    "나무의 냉각 효과가 더위 문제 전체의 해결을 뜻하지는 않는다."
                ),
                "evidence": [source(LIMITATION_QUOTE)],
            }
        ],
    }


async def mock_evaluation(state: WorkflowState) -> dict[str, Any]:
    ensure_demo_request(state.request)

    if state.passage_analysis is None:
        raise ValueError("지문 분석 결과가 필요합니다.")

    return {
        "overall_assessment": (
            "그늘의 냉각 효과는 반영했지만 나무의 효과를 과도하게 일반화했습니다."
        ),
        "key_point_coverage": [
            {
                "point_id": "K1",
                "status": "accurate",
                "reason": "그늘을 통해 기온이 낮아진다는 의미를 반영했습니다.",
                "student_evidence": [
                    {"quote": "도시의 나무는 그늘을 만들어 기온을 낮춘다."}
                ],
            },
            {
                "point_id": "K2",
                "status": "missing",
                "reason": "증발에 의한 냉각 설명은 포함하지 않았습니다.",
                "student_evidence": [],
            },
            {
                "point_id": "K3",
                "status": "distorted",
                "reason": "원문에 제시된 한계와 반대되는 내용을 썼습니다.",
                "student_evidence": [{"quote": STUDENT_ERROR_QUOTE}],
            },
        ],
        "issues": [
            {
                "issue_id": "I1",
                "category": "distortion",
                "severity": "high",
                "diagnosis": "나무의 냉각 효과를 모든 더위 문제의 해결로 확대했습니다.",
                "reasoning": (
                    "원문은 나무만으로 해결할 수 없다고 설명하지만 "
                    "학생 글은 모두 해결할 수 있다고 서술했습니다."
                ),
                "related_point_ids": ["K3"],
                "source_evidence": [source(LIMITATION_QUOTE)],
                "student_evidence": [{"quote": STUDENT_ERROR_QUOTE}],
            }
        ],
    }


async def mock_feedback(state: WorkflowState) -> dict[str, Any]:
    ensure_demo_request(state.request)

    if state.evaluation is None:
        raise ValueError("평가 결과가 필요합니다.")

    return {
        "teacher_summary": (
            "나무의 효과와 한계를 구분하도록 지도할 필요가 있습니다."
        ),
        "student_summary": (
            "나무가 그늘을 만든다는 내용을 잘 담았어요. "
            "두 번째 문장도 원문과 같은 뜻인지 확인해 보세요."
        ),
        "comments": [
            {
                "issue_id": "I1",
                "teacher_note": (
                    "원문의 '해결되는 것은 아니다'와 "
                    "학생 글의 '모두 해결할 수 있다'를 비교하게 합니다."
                ),
                "student_feedback": (
                    "더위를 줄이는 데 도움이 된다는 것과 "
                    "더위 문제를 모두 해결한다는 것은 뜻이 달라요."
                ),
                "revision_question": (
                    "글쓴이는 나무를 심는 것 외에 어떤 노력도 필요하다고 했나요?"
                ),
                "revision_example": (
                    "하지만 도시의 더위 문제를 해결하려면 "
                    "바람길을 확보하고 건물의 배치도 고려해야 한다."
                ),
            }
        ],
    }
