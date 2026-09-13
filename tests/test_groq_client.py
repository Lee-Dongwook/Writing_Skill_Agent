import asyncio
import json
import unittest

import httpx
from pydantic import BaseModel

from writing_feedback.config import Settings
from writing_feedback.llm.base import LLMCallError, LLMOutputError
from writing_feedback.llm.factory import create_llm_client
from writing_feedback.llm.groq_client import GroqClient


class Output(BaseModel):
    value: str


def completion(content, finish_reason="stop"):
    return {"choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": finish_reason}], "usage": {"prompt_tokens": 20, "completion_tokens": 10, "prompt_time": 0.01, "completion_time": 0.25, "queue_time": 0.002}}


def client_with(handler, **overrides) -> GroqClient:
    settings = Settings(llm_provider="groq", GROQ_API_KEY="test-key", **overrides)
    client = GroqClient(settings)
    client._http = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://test", headers=client._http.headers)
    return client


class GroqClientTest(unittest.TestCase):
    def test_factory_selects_provider(self):
        self.assertIsInstance(create_llm_client(Settings(llm_provider="groq", GROQ_API_KEY="k")), GroqClient)
        self.assertNotIsInstance(create_llm_client(Settings(llm_provider="ollama")), GroqClient)

    def test_success_uses_json_schema_and_reasoning_allowance(self):
        seen = {}

        def handler(request):
            seen["auth"] = request.headers["Authorization"]
            seen["body"] = json.loads(request.content)
            return httpx.Response(200, json=completion('{"value": "요약"}'))

        async def run():
            client = client_with(handler)
            result = await client.generate(system_prompt="s", user_prompt="u", response_model=Output, stage="fast", num_predict=512)
            self.assertEqual(result.value, "요약")
            metric = client.metrics[0]
            await client.aclose()
            return metric
        metric = asyncio.run(run())
        self.assertEqual(seen["auth"], "Bearer test-key")
        self.assertEqual(seen["body"]["response_format"]["type"], "json_schema")
        self.assertEqual(seen["body"]["max_completion_tokens"], 512 + 1024)
        self.assertFalse(seen["body"]["include_reasoning"])
        self.assertEqual(metric["outcome"], "success")
        self.assertEqual(metric["generation_tokens_per_second"], 40.0)
        self.assertNotIn("value", json.dumps(metric))

    def test_non_schema_model_uses_json_object_with_schema_in_prompt(self):
        seen = {}

        def handler(request):
            seen["body"] = json.loads(request.content)
            return httpx.Response(200, json=completion('{"value": "x"}'))

        async def run():
            client = client_with(handler, groq_model="llama-3.1-8b-instant")
            await client.generate(system_prompt="s", user_prompt="u", response_model=Output)
            await client.aclose()
        asyncio.run(run())
        self.assertEqual(seen["body"]["response_format"], {"type": "json_object"})
        self.assertIn('"value"', seen["body"]["messages"][0]["content"])
        self.assertNotIn("reasoning_effort", seen["body"])

    def test_errors_map_to_safe_codes(self):
        cases = [
            (httpx.Response(401, json={"error": {"message": "bad key"}}), LLMCallError, "llm_not_configured"),
            (httpx.Response(429, json={"error": {"message": "slow down"}}), LLMCallError, "llm_rate_limited"),
            (httpx.Response(400, json={"error": {"code": "json_validate_failed"}}), LLMOutputError, None),
            (httpx.Response(200, json=completion('{"value": "x"}', finish_reason="length")), LLMOutputError, None),
            (httpx.Response(200, json=completion('{"wrong": 1}')), LLMOutputError, None),
        ]
        for response, error_type, code in cases:
            async def run():
                client = client_with(lambda _: response)
                try:
                    with self.assertRaises(error_type) as ctx:
                        await client.generate(system_prompt="s", user_prompt="u", response_model=Output)
                finally:
                    await client.aclose()
                return ctx.exception
            self.assertEqual(asyncio.run(run()).error_code, code)

    def test_missing_api_key_fails_without_network(self):
        async def run():
            client = GroqClient(Settings(llm_provider="groq", GROQ_API_KEY=None))
            try:
                with self.assertRaises(LLMCallError) as ctx:
                    await client.generate(system_prompt="s", user_prompt="u", response_model=Output)
            finally:
                await client.aclose()
            return ctx.exception
        self.assertEqual(asyncio.run(run()).error_code, "llm_not_configured")


if __name__ == "__main__":
    unittest.main()
