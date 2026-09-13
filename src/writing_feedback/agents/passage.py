import json
from importlib.resources import files

from writing_feedback.llm.base import (
    LLMCallError,
    LLMClient,
    LLMOutputError,
)
from writing_feedback.orchestration.state import (
    ErrorCode,
    WorkflowState,
)
from writing_feedback.orchestration.supervisor import AgentExecutionError
from writing_feedback.orchestration.validation import split_passage
from writing_feedback.schemas.analysis import PassageAnalysis


class PassageAgent:
    def __init__(self, client: LLMClient) -> None:
        self.client = client

        self.system_prompt = (
            files("writing_feedback")
            .joinpath("prompts", "passage.md")
            .read_text(encoding="utf-8")
        )

    async def __call__(
        self,
        state: WorkflowState,
    ) -> PassageAnalysis:
        if state.rubric is None:
            raise AgentExecutionError(
                ErrorCode.INTERNAL_ERROR,
                retryable=False,
            )

        paragraphs = split_passage(state.request.passage)

        payload = {
            "school_level": state.request.school_level.value,
            "grade": state.request.grade,
            "task_type": state.request.task_type.value,
            "instruction": state.request.instruction,
            "teacher_guidance": state.request.teacher_guidance,
            "rubric": state.rubric.model_dump(mode="json"),
            "paragraphs": [
                {
                    "paragraph_id": paragraph_id,
                    "text": text,
                }
                for paragraph_id, text in paragraphs.items()
            ],
        }

        try:
            return await self.client.generate(
                system_prompt=self.system_prompt,
                user_prompt=json.dumps(
                    payload,
                    ensure_ascii=False,
                ),
                response_model=PassageAnalysis,
                stage="passage",
            )

        except LLMCallError as exc:
            raise AgentExecutionError(
                ErrorCode.MODEL_CALL_FAILED,
                retryable=exc.retryable,
            ) from exc

        except LLMOutputError as exc:
            raise AgentExecutionError(
                ErrorCode.INVALID_OUTPUT,
                retryable=exc.retryable,
            ) from exc
