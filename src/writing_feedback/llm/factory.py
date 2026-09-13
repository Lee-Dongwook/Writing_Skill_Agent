from writing_feedback.config import Settings
from writing_feedback.llm.base import LLMClient


def create_llm_client(settings: Settings) -> LLMClient:
    """설정의 llm_provider에 맞는 LLM 클라이언트를 만든다."""
    if settings.llm_provider == "groq":
        from writing_feedback.llm.groq_client import GroqClient
        return GroqClient(settings)
    from writing_feedback.llm.client import OllamaClient
    return OllamaClient(settings)
