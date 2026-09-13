import asyncio
import json

import httpx
from pydantic import ValidationError

from writing_feedback.config import Settings
from writing_feedback.llm.base import (
    LLMCallError,
    LLMClient,
    LLMOutputError,
    ResponseT,
)


class OllamaClient(LLMClient):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

        self._http = httpx.AsyncClient(
            base_url=settings.ollama_base_url,
            timeout=httpx.Timeout(
                settings.llm_timeout_seconds,
                connect=10.0,
            ),
            trust_env=False,
        )

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[ResponseT],
    ) -> ResponseT:
        schema = response_model.model_json_schema()

        schema_text = json.dumps(
            schema,
            ensure_ascii=False,
        )

        payload = {
            "model": self.settings.ollama_model,
            "stream": False,
            "think": self.settings.llm_think,
            "keep_alive": "5m",
            "format": schema,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        f"{system_prompt}\n\n"
                        "출력은 아래 JSON 스키마를 따르는 객체 하나로 작성하세요.\n"
                        "마크다운 코드 블록이나 JSON 밖의 설명은 넣지 마세요.\n"
                        f"{schema_text}"
                    ),
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            "options": {
                "num_ctx": self.settings.llm_num_ctx,
                "num_predict": self.settings.llm_num_predict,
                "temperature": self.settings.llm_temperature,
            },
        }

        try:
            response = await asyncio.wait_for(
                self._http.post("/api/chat", json=payload),
                timeout=self.settings.llm_timeout_seconds,
            )

            response.raise_for_status()

        except (asyncio.TimeoutError, httpx.TimeoutException):
            raise LLMCallError(
                "로컬 모델 호출 시간이 초과되었습니다.",
                retryable=True,
            ) from None

        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code

            raise LLMCallError(
                f"Ollama가 HTTP {status} 오류를 반환했습니다.",
                retryable=status in {408, 429, 500, 502, 503, 504},
            ) from None

        except httpx.RequestError:
            raise LLMCallError(
                "로컬 Ollama 서버와 통신할 수 없습니다.",
                retryable=True,
            ) from None

        try:
            body = response.json()
        except ValueError:
            raise LLMOutputError(
                "Ollama 응답 본문이 올바른 JSON이 아닙니다.",
                retryable=True,
            ) from None

        if not isinstance(body, dict):
            raise LLMOutputError(
                "Ollama 응답 본문이 객체가 아닙니다.",
                retryable=True,
            )

        if body.get("done") is not True:
            raise LLMOutputError(
                "Ollama 응답이 완료되지 않았습니다.",
                retryable=True,
            )

        if body.get("done_reason") == "length":
            raise LLMOutputError(
                "출력 토큰 상한에 도달했습니다. "
                "출력을 줄이거나 상한 설정을 조정하세요.",
                retryable=False,
            )

        message = body.get("message")

        if not isinstance(message, dict):
            raise LLMOutputError(
                "Ollama 응답에 message 객체가 없습니다.",
                retryable=True,
            )

        content = message.get("content")

        if not isinstance(content, str) or not content.strip():
            raise LLMOutputError(
                "모델이 비어 있는 응답을 반환했습니다.",
                retryable=True,
            )

        try:
            return response_model.model_validate_json(content)
        except ValidationError:
            raise LLMOutputError(
                "모델 출력이 요청한 JSON 스키마 또는 검증 규칙과 "
                "일치하지 않습니다.",
                retryable=True,
            ) from None

    async def aclose(self) -> None:
        await self._http.aclose()
