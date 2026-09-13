import asyncio
import unittest

from writing_feedback.agents.fast_feedback import FastFeedbackAgent
from writing_feedback.agents.mock import DEMO_PASSAGE, build_mock_rubric
from writing_feedback.llm.base import LLMOutputError
from writing_feedback.orchestration.state import AgentName, ErrorCode, WorkflowMode, WorkflowState, WorkflowStatus
from writing_feedback.orchestration.supervisor import Supervisor
from writing_feedback.schemas.fast_feedback import FastFeedbackDraft
from writing_feedback.schemas.request import FeedbackRequest


def request() -> FeedbackRequest:
    return FeedbackRequest(school_level="elementary", grade=5, instruction="두 문장으로 요약하세요.", passage=DEMO_PASSAGE, student_text="도시의 나무는 그늘을 만들어 기온을 낮춘다.")


def state(**kwargs) -> WorkflowState:
    item = request()
    return WorkflowState(request=item, rubric=build_mock_rubric(item), mode=WorkflowMode.FAST, **kwargs)


class FakeClient:
    def __init__(self, output): self.output, self.calls = output, 0
    async def generate(self, **kwargs):
        self.calls += 1
        return self.output


class FastPathTest(unittest.TestCase):
    def run_fast(self, handler, **kwargs):
        return asyncio.run(Supervisor({AgentName.FAST: handler}, timeout_seconds=kwargs.pop("timeout", 1), total_timeout_seconds=kwargs.pop("total", 1)).run(state(**kwargs)))

    def test_normal_fast_path_calls_llm_once(self):
        client = FakeClient(FastFeedbackDraft(passage_summary="나무는 더위를 줄이는 데 도움을 주지만 다른 노력도 필요하다.", issues=[], student_feedback="핵심 내용을 잘 담았어요."))
        result = self.run_fast(FastFeedbackAgent(client, input_token_budget=3000, num_predict=128))
        self.assertEqual(result.status, WorkflowStatus.AWAITING_TEACHER_REVIEW)
        self.assertEqual(result.step_count, 1)
        self.assertEqual(client.calls, 1)
        self.assertEqual(result.fast_feedback.issues, [])

    def test_false_quote_and_wrong_paragraph_are_rejected(self):
        async def false_quote(_):
            return {"passage_summary": "요약", "student_feedback": "확인하세요.", "issues": [{"category": "omission", "diagnosis": "한계가 빠졌습니다.", "source_evidence": [{"paragraph_id": 2, "quote": "없는 인용"}], "student_evidence": []}]}
        result = self.run_fast(false_quote)
        self.assertEqual(result.status, WorkflowStatus.FAILED)
        self.assertEqual(result.errors[-1].code, ErrorCode.EVIDENCE_MISMATCH)

    def test_retry_and_total_budget(self):
        calls = 0
        async def slow(_):
            nonlocal calls
            calls += 1
            await asyncio.sleep(.04)
        result = self.run_fast(slow, max_retries=1, timeout=.2, total=.02)
        self.assertEqual(result.status, WorkflowStatus.FAILED)
        self.assertEqual(calls, 1)
        self.assertEqual(result.errors[-1].code, ErrorCode.TIME_BUDGET_EXCEEDED)

    def test_per_call_timeout_is_retried_once(self):
        calls = 0
        async def flaky(_):
            nonlocal calls
            calls += 1
            if calls == 1:
                await asyncio.sleep(.03)
            return {"passage_summary": "요약", "issues": [], "student_feedback": "잘했어요."}
        result = self.run_fast(flaky, max_retries=1, timeout=.01, total=.2)
        self.assertEqual(result.status, WorkflowStatus.AWAITING_TEACHER_REVIEW)
        self.assertEqual(result.step_count, 2)
        self.assertEqual(calls, 2)

    def test_input_budget_is_explicit_failure(self):
        client = FakeClient(None)
        result = self.run_fast(FastFeedbackAgent(client, input_token_budget=1, num_predict=64))
        self.assertEqual(result.status, WorkflowStatus.FAILED)
        self.assertEqual(result.errors[-1].code, ErrorCode.INPUT_BUDGET_EXCEEDED)
        self.assertEqual(client.calls, 0)


if __name__ == "__main__":
    unittest.main()
