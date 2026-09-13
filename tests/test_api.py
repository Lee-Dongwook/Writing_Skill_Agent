import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from writing_feedback.api import create_app
from writing_feedback.config import Settings
from writing_feedback.orchestration.state import WorkflowStatus, utc_now
from writing_feedback.schemas.fast_feedback import FastFeedbackDraft


PAYLOAD = {
    "school_level": "elementary", "grade": 5, "task_type": "summary",
    "instruction": "두 문장으로 요약하세요.", "passage": "나무는 그늘을 만든다.",
    "student_text": "나무는 그늘을 만든다.", "mode": "fast",
}


async def fake_run(state, settings, *, on_state_change=None):
    state.status = WorkflowStatus.RUNNING
    if on_state_change:
        on_state_change(state)
    state.fast_feedback = FastFeedbackDraft(
        passage_summary="나무는 그늘을 만든다.", issues=[], student_feedback="핵심 내용을 잘 담았어요."
    )
    state.status = WorkflowStatus.AWAITING_TEACHER_REVIEW
    state.updated_at = utc_now()
    if on_state_change:
        on_state_change(state)
    return state


class ApiTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app(Settings(api_result_ttl_seconds=60))

    def test_create_then_get_completed_result_without_request_text(self):
        with patch("writing_feedback.api.run_workflow", fake_run), TestClient(self.app) as client:
            created = client.post("/api/runs", json=PAYLOAD)
            self.assertEqual(created.status_code, 202)
            result = client.get(f"/api/runs/{created.json()['run_id']}")
        self.assertEqual(result.status_code, 200)
        body = result.json()
        self.assertEqual(body["status"], "awaiting_teacher_review")
        self.assertEqual(body["result"]["fast_feedback"]["issues"], [])
        self.assertNotIn("request", body)

    def test_invalid_grade_is_rejected_before_run_creation(self):
        invalid = {**PAYLOAD, "school_level": "middle", "grade": 4}
        with TestClient(self.app) as client:
            response = client.post("/api/runs", json=invalid)
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
