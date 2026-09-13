import asyncio
import unittest

import httpx
from pydantic import BaseModel

from writing_feedback.config import Settings
from writing_feedback.llm.base import LLMOutputError
from writing_feedback.llm.client import OllamaClient


class Output(BaseModel):
    value: str


class OllamaMetricTest(unittest.TestCase):
    def test_truncation_is_rejected_and_nanoseconds_are_converted(self):
        async def run():
            client = OllamaClient(Settings())
            client._http = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"done": True, "done_reason": "length", "load_duration": 2_000_000_000, "prompt_eval_duration": 500_000_000, "eval_duration": 250_000_000, "prompt_eval_count": 4, "eval_count": 10, "message": {"content": "{}"}})), base_url="http://test")
            with self.assertRaises(LLMOutputError):
                await client.generate(system_prompt="s", user_prompt="u", response_model=Output)
            metric = client.metrics[0]
            self.assertEqual(metric["error_kind"], "output_truncated")
            self.assertEqual(metric["load_duration_seconds"], 2.0)
            self.assertEqual(metric["generation_tokens_per_second"], 40.0)
            await client.aclose()
        asyncio.run(run())
