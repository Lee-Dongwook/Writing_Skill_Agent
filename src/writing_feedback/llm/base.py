from abc import ABC, abstractmethod
from typing import Any, TypeVar

from pydantic import BaseModel


ResponseT = TypeVar("ResponseT", bound=BaseModel)


class LLMError(Exception):
    """LLM 호출 또는 응답 처리 오류."""

    def __init__(
        self,
        message: str,
        *,
        retryable: bool,
        error_code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.error_code = error_code


class LLMCallError(LLMError):
    """연결 실패, 시간 초과, HTTP 오류."""


class LLMOutputError(LLMError):
    """불완전한 응답 또는 출력 스키마 검증 실패."""


class LLMClient(ABC):
    @abstractmethod
    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[ResponseT],
        stage: str = "llm",
        num_predict: int | None = None,
    ) -> ResponseT:
        """지정한 Pydantic 모델로 검증된 결과를 반환합니다."""
        raise NotImplementedError

    @property
    def metrics(self) -> list[dict[str, Any]]:
        """내용을 포함하지 않는 호출 성능 메타데이터."""
        return []

    @abstractmethod
    async def aclose(self) -> None:
        """사용 중인 연결 자원을 해제합니다."""
        raise NotImplementedError
