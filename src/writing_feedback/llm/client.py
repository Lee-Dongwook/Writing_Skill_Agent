import asyncio
import time
from typing import Any

import httpx
from pydantic import ValidationError

from writing_feedback.config import Settings
from writing_feedback.llm.base import LLMCallError, LLMClient, LLMOutputError, ResponseT


class OllamaClient(LLMClient):
    """Ollama chat client. Metrics never retain prompt or output text."""
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._metrics: list[dict[str, Any]] = []
        self._http = httpx.AsyncClient(base_url=settings.ollama_base_url, timeout=httpx.Timeout(settings.llm_timeout_seconds, connect=10.0), trust_env=False)

    async def generate(self, *, system_prompt: str, user_prompt: str, response_model: type[ResponseT], stage: str = "llm", num_predict: int | None = None) -> ResponseT:
        output_limit = num_predict or self.settings.llm_num_predict
        payload = {
            "model": self.settings.ollama_model, "stream": False, "think": self.settings.llm_think, "keep_alive": "5m",
            "format": response_model.model_json_schema(),
            "messages": [{"role": "system", "content": system_prompt + "\n\nformat으로 제공된 JSON 스키마를 따르는 객체 하나만 출력하세요. 마크다운이나 JSON 밖의 설명은 넣지 마세요."}, {"role": "user", "content": user_prompt}],
            "options": {"num_ctx": self.settings.llm_num_ctx, "num_predict": output_limit, "temperature": self.settings.llm_temperature},
        }
        started, body, outcome, error_kind = time.perf_counter(), None, "error", None
        try:
            try:
                response = await asyncio.wait_for(self._http.post("/api/chat", json=payload), timeout=self.settings.llm_timeout_seconds)
                response.raise_for_status()
            except (asyncio.TimeoutError, httpx.TimeoutException):
                error_kind = "timeout"
                raise LLMCallError("로컬 모델 호출 시간이 초과되었습니다.", retryable=True) from None
            except httpx.HTTPStatusError as exc:
                error_kind = "http_error"
                raise LLMCallError(f"Ollama가 HTTP {exc.response.status_code} 오류를 반환했습니다.", retryable=exc.response.status_code in {408, 429, 500, 502, 503, 504}) from None
            except httpx.RequestError:
                error_kind = "connection_error"
                raise LLMCallError("로컬 Ollama 서버와 통신할 수 없습니다.", retryable=True) from None
            try:
                body = response.json()
            except ValueError:
                error_kind = "response_json_error"
                raise LLMOutputError("Ollama 응답 본문이 올바른 JSON이 아닙니다.", retryable=True) from None
            if not isinstance(body, dict):
                error_kind = "response_shape_error"
                raise LLMOutputError("Ollama 응답 본문이 객체가 아닙니다.", retryable=True)
            if body.get("done") is not True:
                error_kind = "incomplete"
                raise LLMOutputError("Ollama 응답이 완료되지 않았습니다.", retryable=True)
            if body.get("done_reason") == "length":
                error_kind = "output_truncated"
                raise LLMOutputError("출력 토큰 상한에 도달했습니다. 출력을 줄이거나 상한 설정을 조정하세요.", retryable=False)
            message = body.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            if not isinstance(content, str) or not content.strip():
                error_kind = "missing_message" if not isinstance(message, dict) else "empty_output"
                raise LLMOutputError("Ollama 응답에 사용할 수 있는 message.content가 없습니다.", retryable=True)
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

    def _record_metric(self, stage: str, output_limit: int, started: float, outcome: str, error_kind: str | None, body: dict[str, Any] | None) -> None:
        metric: dict[str, Any] = {"stage": stage, "attempt": 1 + sum(item["stage"] == stage for item in self._metrics), "elapsed_seconds": round(time.perf_counter() - started, 3), "outcome": outcome, "error_kind": error_kind, "model": self.settings.ollama_model, "num_ctx": self.settings.llm_num_ctx, "num_predict": output_limit, "temperature": self.settings.llm_temperature, "think": self.settings.llm_think, "load_duration_seconds": None, "prompt_eval_duration_seconds": None, "eval_duration_seconds": None, "prompt_eval_count": None, "eval_count": None, "generation_tokens_per_second": None, "done_reason": None}
        if isinstance(body, dict):
            # Ollama의 *_duration 단위는 나노초이므로 초로 변환한다.
            for key in ("load_duration", "prompt_eval_duration", "eval_duration"):
                value = body.get(key)
                metric[f"{key}_seconds"] = round(value / 1_000_000_000, 6) if isinstance(value, (int, float)) else None
            for key in ("prompt_eval_count", "eval_count"):
                metric[key] = body.get(key) if isinstance(body.get(key), int) else None
            count, seconds = metric.get("eval_count"), metric.get("eval_duration_seconds")
            metric["generation_tokens_per_second"] = round(count / seconds, 3) if isinstance(count, int) and isinstance(seconds, (int, float)) and seconds > 0 else None
            metric["done_reason"] = body.get("done_reason")
        self._metrics.append(metric)

    @property
    def metrics(self) -> list[dict[str, Any]]:
        return list(self._metrics)

    async def aclose(self) -> None:
        await self._http.aclose()
