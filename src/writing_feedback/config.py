from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="WRITING_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 로컬 개발은 Ollama, 배포(Vercel)는 외부 Groq API를 사용합니다.
    llm_provider: Literal["ollama", "groq"] = "ollama"

    # Vercel 대시보드에는 접두사 없는 GROQ_API_KEY로 등록합니다.
    groq_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("GROQ_API_KEY", "WRITING_GROQ_API_KEY"),
    )
    # 스키마 강제(json_schema)를 지원하는 모델을 기본값으로 둡니다.
    groq_model: str = Field(default="openai/gpt-oss-20b", min_length=1)
    groq_reasoning_effort: Literal["low", "medium", "high"] = "low"
    # 추론 모델은 추론 토큰도 출력 상한을 소모하므로 단계별 상한에 더한다.
    groq_reasoning_token_allowance: int = Field(default=1024, ge=0)

    ollama_base_url: Literal[
        "http://127.0.0.1:11434",
        "http://localhost:11434",
    ] = "http://127.0.0.1:11434"

    ollama_model: str = Field(
        default="qwen3:4b",
        min_length=1,
    )

    llm_timeout_seconds: float = Field(
        default=180.0,
        gt=0,
        allow_inf_nan=False,
    )

    llm_num_ctx: int = Field(
        default=4096,
        ge=1024,
    )

    llm_num_predict: int = Field(
        default=2048,
        ge=1,
    )

    llm_temperature: float = Field(
        default=0.1,
        ge=0,
        le=2,
        allow_inf_nan=False,
    )

    llm_think: bool = False

    # 빠른 첨삭은 짧은 교사 검토 초안만 생성하므로, 상세 경로의 출력
    # 상한(2048) 대신 작은 상한을 사용한다.
    fast_num_predict: int = Field(default=512, ge=64)
    fast_input_token_budget: int = Field(default=3000, ge=256)
    workflow_timeout_seconds: float = Field(default=120.0, gt=0)
    api_max_concurrent_runs: int = Field(default=1, ge=1, le=1)
    api_queue_limit: int = Field(default=8, ge=1, le=100)
    api_result_ttl_seconds: int = Field(default=3600, ge=60)
    api_cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    # 서버리스에서는 응답 후 백그라운드 작업과 메모리 저장소를 보장할 수 없으므로
    # POST 요청 안에서 첨삭을 끝내고 결과를 바로 반환한다.
    api_inline_runs: bool = False

    @property
    def model_name(self) -> str:
        return self.groq_model if self.llm_provider == "groq" else self.ollama_model

    @property
    def api_cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.api_cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_token_limits(self) -> Self:
        if self.llm_num_predict >= self.llm_num_ctx:
            raise ValueError(
                "출력 토큰 상한은 전체 컨텍스트보다 작아야 합니다."
            )

        return self
