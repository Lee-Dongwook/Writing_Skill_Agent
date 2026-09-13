import asyncio
import json
import time
from typing import Any

import httpx
from pydantic import ValidationError

from writing_feedback.config import Settings
from writing_feedback.llm.base import LLMCallError, LLMClient, LLMOutputError, ResponseT


GROQ_BASE_URL = "https://api.groq.com/openai/v1"
# Groq에서 json_schema 구조화 출력을 지원하는 모델 계열. 그 외 모델은 json_object로 요청한다.
JSON_SCHEMA_MODEL_PREFIXES = ("openai/gpt-oss", "qwen/")


class GroqClient(LLMClient):
    """Groq(OpenAI 호환) chat client. Metrics never retain prompt or output text."""
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._metrics: list[dict[str, Any]] = []
        api_key = settings.groq_api_key.get_secret_value() if settings.groq_api_key else ""
        self._http = httpx.AsyncClient(
            base_url=GROQ_BASE_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=httpx.Timeout(settings.llm_timeout_seconds, connect=10.0),
        )

    @property
    def _is_reasoning_model(self) -> bool:
        return self.settings.groq_model.startswith("openai/gpt-oss")

    def _payload(self, system_prompt: str, user_prompt: str, response_model: type[ResponseT], max_tokens: int) -> dict[str, Any]:
        schema = response_model.model_json_schema()
        if self.settings.groq_model.startswith(JSON_SCHEMA_MODEL_PREFIXES):
            response_format: dict[str, Any] = {"type": "json_schema", "json_schema": {"name": response_model.__name__, "strict": False, "schema": schema}}
            instruction = "\n\n제공된 JSON 스키마를 따르는 객체 하나만 출력하세요. 마크다운이나 JSON 밖의 설명은 넣지 마세요."
        else:
            # json_object 모드는 문법만 보장하므로 스키마를 프롬프트에 직접 제시한다.
            response_format = {"type": "json_object"}
            instruction = "\n\n다음 JSON 스키마를 따르는 객체 하나만 출력하세요. 마크다운이나 JSON 밖의 설명은 넣지 마세요.\n" + json.dumps(schema, ensure_ascii=False)
        payload: dict[str, Any] = {
            "model": self.settings.groq_model, "stream": False,
            "messages": [{"role": "system", "content": system_prompt + instruction}, {"role": "user", "content": user_prompt}],
            "temperature": self.settings.llm_temperature, "max_completion_tokens": max_tokens,
            "response_format": response_format,
        }
        if self._is_reasoning_model:
            payload["reasoning_effort"] = self.settings.groq_reasoning_effort
            payload["include_reasoning"] = False
        return payload

    async def generate(self, *, system_prompt: str, user_prompt: str, response_model: type[ResponseT], stage: str = "llm", num_predict: int | None = None) -> ResponseT:
        output_limit = num_predict or self.settings.llm_num_predict
        if self._is_reasoning_model:
            output_limit += self.settings.groq_reasoning_token_allowance
        started, body, outcome, error_kind = time.perf_counter(), None, "error", None
        try:
            if self.settings.groq_api_key is None:
                error_kind = "not_configured"
                raise LLMCallError("GROQ_API_KEY 환경 변수가 설정되지 않았습니다.", retryable=False, error_code="llm_not_configured")
            payload = self._payload(system_prompt, user_prompt, response_model, output_limit)
            try:
                response = await asyncio.wait_for(self._http.post("/chat/completions", json=payload), timeout=self.settings.llm_timeout_seconds)
                response.raise_for_status()
            except (asyncio.TimeoutError, httpx.TimeoutException):
                error_kind = "timeout"
                raise LLMCallError("외부 모델 호출 시간이 초과되었습니다.", retryable=True) from None
            except httpx.HTTPStatusError as exc:
                error_kind = f"http_{exc.response.status_code}"
                self._raise_for_status(exc.response)
            except httpx.RequestError:
                error_kind = "connection_error"
                raise LLMCallError("Groq API와 통신할 수 없습니다.", retryable=True) from None
            try:
                body = response.json()
            except ValueError:
                error_kind = "response_json_error"
                raise LLMOutputError("Groq 응답 본문이 올바른 JSON이 아닙니다.", retryable=True) from None
            choices = body.get("choices") if isinstance(body, dict) else None
            choice = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else None
            if choice is None:
                error_kind = "response_shape_error"
                raise LLMOutputError("Groq 응답에 choices가 없습니다.", retryable=True)
            if choice.get("finish_reason") == "length":
                error_kind = "output_truncated"
                raise LLMOutputError("출력 토큰 상한에 도달했습니다. 출력을 줄이거나 상한 설정을 조정하세요.", retryable=False)
            message = choice.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            if not isinstance(content, str) or not content.strip():
                error_kind = "missing_message" if not isinstance(message, dict) else "empty_output"
                raise LLMOutputError("Groq 응답에 사용할 수 있는 message.content가 없습니다.", retryable=True)
            try:
                result = response_model.model_validate_json(content)
            except ValidationError:
                error_kind = "schema_validation_error"
                raise LLMOutputError("모델 출력이 요청한 JSON 스키마 또는 검증 규칙과 일치하지 않습니다.", retryable=True) from None
            outcome = "success"
            return result
        except asyncio.CancelledError:
            # Supervisor의 전체 시간 예산이 하위 HTTP 호출을 취소한 경우다.
            error_kind = "cancelled_by_time_budget"
            raise
        finally:
            self._record_metric(stage, output_limit, started, outcome, error_kind, body)

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        status_code = response.status_code
        try:
            error = response.json().get("error") or {}
        except (ValueError, AttributeError):
            error = {}
        code = error.get("code") if isinstance(error, dict) else None
        if status_code == 400 and code == "json_validate_failed":
            # Groq가 JSON 모드 출력 검증에 실패한 경우다.
            raise LLMOutputError("모델 출력이 JSON 형식 검증에 실패했습니다.", retryable=True) from None
        if status_code in {401, 403}:
            raise LLMCallError("Groq API 키가 유효하지 않거나 권한이 없습니다.", retryable=False, error_code="llm_not_configured") from None
        if status_code == 404 or code == "model_not_found":
            raise LLMCallError("요청한 Groq 모델을 찾을 수 없습니다.", retryable=False, error_code="model_not_installed") from None
        if status_code == 429:
            raise LLMCallError("Groq API 사용량 한도에 도달했습니다.", retryable=True, error_code="llm_rate_limited") from None
        raise LLMCallError(f"Groq API가 HTTP {status_code} 오류를 반환했습니다.", retryable=status_code in {408, 500, 502, 503, 504}) from None

    def _record_metric(self, stage: str, output_limit: int, started: float, outcome: str, error_kind: str | None, body: dict[str, Any] | None) -> None:
        metric: dict[str, Any] = {"stage": stage, "attempt": 1 + sum(item["stage"] == stage for item in self._metrics), "elapsed_seconds": round(time.perf_counter() - started, 3), "outcome": outcome, "error_kind": error_kind, "provider": "groq", "model": self.settings.groq_model, "num_predict": output_limit, "temperature": self.settings.llm_temperature, "queue_time_seconds": None, "prompt_eval_duration_seconds": None, "eval_duration_seconds": None, "prompt_eval_count": None, "eval_count": None, "generation_tokens_per_second": None, "done_reason": None}
        if isinstance(body, dict):
            usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
            # Groq usage의 *_time 단위는 초다. Ollama 메트릭과 같은 키 이름으로 맞춘다.
            for source, target in (("queue_time", "queue_time_seconds"), ("prompt_time", "prompt_eval_duration_seconds"), ("completion_time", "eval_duration_seconds")):
                value = usage.get(source)
                metric[target] = round(value, 6) if isinstance(value, (int, float)) else None
            for source, target in (("prompt_tokens", "prompt_eval_count"), ("completion_tokens", "eval_count")):
                metric[target] = usage.get(source) if isinstance(usage.get(source), int) else None
            count, seconds = metric["eval_count"], metric["eval_duration_seconds"]
            metric["generation_tokens_per_second"] = round(count / seconds, 3) if isinstance(count, int) and isinstance(seconds, (int, float)) and seconds > 0 else None
            choices = body.get("choices")
            if isinstance(choices, list) and choices and isinstance(choices[0], dict):
                metric["done_reason"] = choices[0].get("finish_reason")
        self._metrics.append(metric)

    @property
    def metrics(self) -> list[dict[str, Any]]:
        return list(self._metrics)

    async def aclose(self) -> None:
        await self._http.aclose()
