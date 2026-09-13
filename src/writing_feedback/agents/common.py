from writing_feedback.llm.base import (
    LLMCallError,
    LLMClient,
    LLMOutputError,
    ResponseT,
)
from writing_feedback.orchestration.state import ErrorCode
from writing_feedback.orchestration.supervisor import AgentExecutionError


async def generate_for_agent(
    client: LLMClient,
    *,
    system_prompt: str,
    user_prompt: str,
    response_model: type[ResponseT],
    stage: str = "llm",
    num_predict: int | None = None,
) -> ResponseT:
    try:
        return await client.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=response_model,
            stage=stage,
            num_predict=num_predict,
        )

    except LLMCallError as exc:
        raise AgentExecutionError(
            ErrorCode(exc.error_code) if exc.error_code else ErrorCode.MODEL_CALL_FAILED,
            retryable=exc.retryable,
        ) from exc

    except LLMOutputError as exc:
        raise AgentExecutionError(
            ErrorCode.INVALID_OUTPUT,
            retryable=exc.retryable,
        ) from exc
