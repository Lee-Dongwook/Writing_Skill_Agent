import json
import math
from importlib.resources import files

from writing_feedback.agents.common import generate_for_agent
from writing_feedback.llm.base import LLMClient
from writing_feedback.orchestration.state import ErrorCode, WorkflowState
from writing_feedback.orchestration.supervisor import AgentExecutionError
from writing_feedback.orchestration.validation import split_passage
from writing_feedback.schemas.fast_feedback import FastFeedbackDraft


def estimate_korean_tokens(text: str) -> int:
    """토크나이저가 없을 때의 보수적 추정치(한국어도 고려, 정확한 값 아님)."""
    return math.ceil(len(text.replace(" ", "")) / 1.5) + len(text.split())


class FastFeedbackAgent:
    def __init__(self, client: LLMClient, *, input_token_budget: int, num_predict: int) -> None:
        self.client, self.input_token_budget, self.num_predict = client, input_token_budget, num_predict
        self.system_prompt = files("writing_feedback").joinpath("prompts", "fast_feedback.md").read_text(encoding="utf-8")

    async def __call__(self, state: WorkflowState) -> FastFeedbackDraft:
        if state.rubric is None:
            raise AgentExecutionError(ErrorCode.INTERNAL_ERROR, retryable=False)
        payload = {
            "school_level": state.request.school_level.value, "grade": state.request.grade,
            "task_type": state.request.task_type.value,
            "instruction": state.request.instruction, "teacher_guidance": state.request.teacher_guidance,
            "rubric": {"criteria": state.rubric.criteria, "feedback_guidance": state.rubric.feedback_guidance},
            "paragraphs": [{"paragraph_id": i, "text": text} for i, text in split_passage(state.request.passage).items()],
            "student_text": state.request.student_text,
        }
        user_prompt = json.dumps(payload, ensure_ascii=False, default=lambda item: item.model_dump(mode="json"))
        estimated = estimate_korean_tokens(self.system_prompt + user_prompt) + self.num_predict
        if estimated > self.input_token_budget + self.num_predict:
            raise AgentExecutionError(ErrorCode.INPUT_BUDGET_EXCEEDED, retryable=False)
        return await generate_for_agent(self.client, system_prompt=self.system_prompt, user_prompt=user_prompt, response_model=FastFeedbackDraft, stage="fast", num_predict=self.num_predict)
