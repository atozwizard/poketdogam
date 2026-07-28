# Run: uv run python -m unittest tests/test_ui_predevice.py
from __future__ import annotations

import unittest
import warnings
import os

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated.*",
    category=Warning,
)
from fastapi.testclient import TestClient

from app.config.settings import get_settings
from app.agents.pokedex_agent.tools.tool_local_llm import ROTOM_SYSTEM_PROMPT
from app.main import create_app


class PreDeviceUITest(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_llm_provider = os.environ.get("LOCAL_LLM_PROVIDER")
        os.environ["LOCAL_LLM_PROVIDER"] = "template"
        get_settings.cache_clear()
        self.client = TestClient(create_app())

    def tearDown(self) -> None:
        if self.previous_llm_provider is None:
            os.environ.pop("LOCAL_LLM_PROVIDER", None)
        else:
            os.environ["LOCAL_LLM_PROVIDER"] = self.previous_llm_provider
        get_settings.cache_clear()

    def test_index_serves_rotom_ui(self) -> None:
        response = self.client.get("/")
        head_response = self.client.head("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(head_response.status_code, 200)
        self.assertIn("Rotom Dex OS", response.text)
        self.assertIn("/ui/app.js", response.text)

    def test_scan_text_matches_pikachu(self) -> None:
        response = self.client.post(
            "/v1/scan/text",
            json={"ocr_text": "피카추\nHP 60", "filename": "test-fixture.txt"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(len(payload["top_candidates"]), 1)
        self.assertEqual(payload["top_candidates"][0]["pokemon_id"], 25)
        self.assertFalse(payload["requires_user_confirmation"])

    def test_chat_exposes_llm_runtime(self) -> None:
        response = self.client.post("/v1/chat", json={"message": "피카츄 알려줘"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["llm_runtime"], "template")
        self.assertIn("피카츄", payload["answer"])

    def test_chat_stream_emits_sse_events(self) -> None:
        response = self.client.post("/v1/chat/stream", json={"message": "피카츄 알려줘"})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("text/event-stream"))
        self.assertIn('"event": "delta"', response.text)
        self.assertIn('"event": "done"', response.text)
        self.assertIn("피카츄", response.text)

    def test_rotom_prompt_has_persona_and_safety_boundary(self) -> None:
        self.assertIn("Rotom Dex OS", ROTOM_SYSTEM_PROMPT)
        self.assertIn("배경 시놉시스", ROTOM_SYSTEM_PROMPT)
        self.assertIn("공식 대사", ROTOM_SYSTEM_PROMPT)
        self.assertIn("FACTS", ROTOM_SYSTEM_PROMPT)

    def test_voice_status_policy_blocks_official_mimicry(self) -> None:
        response = self.client.get("/v1/voice/status")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["original_ai_voice_allowed"])
        self.assertTrue(payload["official_audio_extraction_allowed"])
        self.assertTrue(payload["official_voice_mimicry_allowed"])

    def test_voice_preview_contract(self) -> None:
        response = self.client.post(
            "/v1/voice/preview",
            json={"text": "분석 완료다-로.", "style": "machine_pulse", "pitch": 1.2, "speed": 1.1},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["runtime"], "browser_speech_synthesis")
        self.assertEqual(payload["style"], "machine_pulse")
        self.assertIn("분석 완료", payload["preview_text"])


if __name__ == "__main__":
    unittest.main()
