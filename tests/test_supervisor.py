import asyncio
import unittest

from writing_feedback.agents.mock import (
    DEMO_PASSAGE,
    DEMO_STUDENT_TEXT,
    build_mock_rubric,
    mock_evaluation,
    mock_feedback,
    mock_passage,
)
from writing_feedback.orchestration.state import (
    AgentName,
    ErrorCode,
    WorkflowState,
    WorkflowStatus,
)
from writing_feedback.orchestration.supervisor import Supervisor
from writing_feedback.schemas.request import FeedbackRequest


class SupervisorTest(unittest.TestCase):
    def run_workflow(self, overrides=None):
        request = FeedbackRequest(
            school_level="elementary",
            grade=5,
            instruction="지문의 중심 내용을 두 문장으로 요약하세요.",
            passage=DEMO_PASSAGE,
            student_text=DEMO_STUDENT_TEXT,
        )

        handlers = {
            AgentName.PASSAGE: mock_passage,
            AgentName.EVALUATION: mock_evaluation,
            AgentName.FEEDBACK: mock_feedback,
        }
        handlers.update(overrides or {})

        state = WorkflowState(
            request=request,
            rubric=build_mock_rubric(request),
        )

        return asyncio.run(
            Supervisor(handlers=handlers).run(state)
        )

    def test_normal_flow(self):
        result = self.run_workflow()

        self.assertEqual(
            result.status,
            WorkflowStatus.AWAITING_TEACHER_REVIEW,
        )
        self.assertEqual(result.step_count, 3)
        self.assertEqual(result.errors, [])
        self.assertIsNotNone(result.feedback)

    def test_invalid_quote_is_retried_then_rejected(self):
        async def invalid_passage(state):
            output = await mock_passage(state)
            output["central_idea_evidence"][0]["quote"] = (
                "이 문장은 원문에 존재하지 않습니다."
            )
            return output

        result = self.run_workflow({
            AgentName.PASSAGE: invalid_passage,
        })

        self.assertEqual(result.status, WorkflowStatus.FAILED)
        self.assertEqual(result.step_count, 3)
        self.assertEqual(len(result.errors), 3)
        self.assertTrue(all(
            error.code == ErrorCode.EVIDENCE_MISMATCH
            for error in result.errors
        ))
        self.assertIsNone(result.passage_analysis)
        self.assertIsNone(result.evaluation)

    def test_missing_feedback_is_rejected(self):
        async def incomplete_feedback(state):
            output = await mock_feedback(state)
            output["comments"] = []
            return output

        result = self.run_workflow({
            AgentName.FEEDBACK: incomplete_feedback,
        })

        self.assertEqual(result.status, WorkflowStatus.FAILED)
        self.assertEqual(result.step_count, 5)
        self.assertIsNotNone(result.evaluation)
        self.assertIsNone(result.feedback)
        self.assertEqual(
            result.errors[-1].code,
            ErrorCode.EVIDENCE_MISMATCH,
        )


if __name__ == "__main__":
    unittest.main()
