"""Vercel Python 함수 진입점. 기존 FastAPI 앱을 Groq·서버리스 설정으로 노출한다."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# 대시보드에서 WRITING_* 값을 따로 지정하면 그 값이 우선한다.
os.environ.setdefault("WRITING_LLM_PROVIDER", "groq")
os.environ.setdefault("WRITING_API_INLINE_RUNS", "true")
# 프론트와 같은 도메인에서 호출하므로 CORS가 필요 없다.
os.environ.setdefault("WRITING_API_CORS_ORIGINS", "")
# vercel.json의 maxDuration(60초) 안에서 끝나도록 시간 예산을 줄인다.
os.environ.setdefault("WRITING_LLM_TIMEOUT_SECONDS", "50")
os.environ.setdefault("WRITING_WORKFLOW_TIMEOUT_SECONDS", "55")

from writing_feedback.api import app  # noqa: E402

__all__ = ["app"]
