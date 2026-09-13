from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="WRITING_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 현재 단계에서는 로컬 Ollama 서버를 사용합니다.
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
        default=8192,
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

    @model_validator(mode="after")
    def validate_token_limits(self) -> Self:
        if self.llm_num_predict >= self.llm_num_ctx:
            raise ValueError(
                "출력 토큰 상한은 전체 컨텍스트보다 작아야 합니다."
            )

        return self
