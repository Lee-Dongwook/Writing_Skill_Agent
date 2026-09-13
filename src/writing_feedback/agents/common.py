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
) -> ResponseT:
    try:
        return await client.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=response_model,
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
