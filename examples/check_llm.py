import asyncio

from pydantic import BaseModel, ConfigDict, Field

from writing_feedback.config import Settings
from writing_feedback.llm.base import LLMError
from writing_feedback.llm.client import OllamaClient


class SummaryResult(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    summary: str = Field(
        min_length=1,
        description="지문의 중심 내용을 담은 한국어 한 문장",
    )


async def check_llm() -> None:
    settings = Settings()
    client = OllamaClient(settings)

    try:
        result = await client.generate(
            system_prompt=(
                "당신은 국어 비문학 요약을 돕는 교사입니다. "
                "원문에 없는 내용을 추가하지 말고 "
                "중요한 조건과 한계를 유지하세요."
            ),
            user_prompt=(
                "다음 지문을 한 문장으로 요약하세요.\n\n"
                "도시의 나무는 그늘을 만들어 기온을 낮춘다. "
                "하지만 나무를 심는 것만으로 모든 더위 문제가 "
                "해결되는 것은 아니며, 바람길 확보도 필요하다."
            ),
            response_model=SummaryResult,
        )

        print("로컬 LLM 호출 및 출력 스키마 검증 완료")
        print(result.model_dump_json(indent=2))

    finally:
        await client.aclose()


if __name__ == "__main__":
    try:
        asyncio.run(check_llm())
    except LLMError as exc:
        print(f"실패: {exc}")
        print(f"재시도 가능 여부: {exc.retryable}")
        raise SystemExit(1)
