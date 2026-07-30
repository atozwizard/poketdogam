# Run: uv run python -m unittest tests/test_ui_predevice.py
from __future__ import annotations

import unittest
import warnings
import os
from pathlib import Path
import platform

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated.*",
    category=Warning,
)
from fastapi.testclient import TestClient

from app.config.settings import get_settings
from app.agents.pokedex_agent.tools.tool_local_llm import ROTOM_SYSTEM_PROMPT
from app.main import create_app


PROJECT_ROOT = Path(__file__).resolve().parents[1]


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
        self.assertIn("Local Scan PoC", response.text)
        self.assertIn("/ui/app.js", response.text)
        self.assertIn("/ui/camera-quality.js", response.text)
        self.assertIn('id="cameraInput"', response.text)
        self.assertIn('id="cameraPreview"', response.text)
        self.assertIn('id="startCameraButton"', response.text)
        self.assertIn('id="captureButton"', response.text)
        self.assertNotIn("/ui/assets/rotomu/", response.text)
        self.assertEqual(
            self.client.get("/ui/assets/rotomu/rotom-phone.png").status_code,
            404,
        )

    def test_scan_text_matches_pikachu(self) -> None:
        response = self.client.post(
            "/v1/scan/text",
            json={"ocr_text": "피카추\nHP 60", "filename": "test-fixture.txt"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(len(payload["top_candidates"]), 1)
        self.assertEqual(payload["top_candidates"][0]["pokemon_id"], 25)
        self.assertTrue(payload["requires_user_confirmation"])
        self.assertEqual(payload["ocr_engine"], "fixture_text")
        self.assertNotEqual(payload["dataset_version"], "unknown")
        self.assertGreaterEqual(payload["latency_ms"], 0)
        self.assertEqual(payload["top_candidates"][0]["form_name"], "base")

    def test_manual_search_returns_candidates(self) -> None:
        response = self.client.get("/v1/pokedex/search", params={"query": "피카", "limit": 5})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["matches"][0]["pokemon_id"], 25)
        self.assertLessEqual(len(payload["matches"]), 5)
        self.assertTrue(payload["dataset_version"])

    def test_official_unnumbered_preview_is_searchable_without_invented_dex_number(self) -> None:
        response = self.client.get("/v1/pokedex/search", params={"query": "Browt", "limit": 3})

        self.assertEqual(response.status_code, 200)
        match = response.json()["matches"][0]
        self.assertEqual(match["pokemon_id"], -1000001)
        detail = self.client.get(f"/v1/pokedex/forms/{match['form_id']}").json()
        self.assertEqual(detail["record_status"], "officially_announced_unnumbered")
        self.assertEqual(detail["localization_status"], "ko_name_not_announced")

    def test_pokedex_detail_includes_evolution_and_type_matchups(self) -> None:
        search = self.client.get("/v1/pokedex/search", params={"query": "피카츄", "limit": 1}).json()
        form_id = search["matches"][0]["form_id"]
        response = self.client.get(f"/v1/pokedex/forms/{form_id}")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["generation"], 1)
        self.assertIn("라이츄", {item["to_name"] for item in payload["evolutions"]})
        self.assertIn(
            {"type": "ground", "multiplier": 2.0},
            payload["weaknesses"],
        )
        self.assertTrue(any(item["condition"] for item in payload["evolutions"]))

    def test_chat_exposes_llm_runtime(self) -> None:
        response = self.client.post("/v1/chat", json={"message": "피카츄 알려줘"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["llm_runtime"], "template")
        self.assertIn("피카츄", payload["answer"])

    def test_selected_form_preserves_weakness_facet(self) -> None:
        search = self.client.get("/v1/pokedex/search", params={"query": "리자몽", "limit": 1}).json()
        form_id = search["matches"][0]["form_id"]
        response = self.client.post("/v1/chat", json={"message": "약점", "form_id": form_id})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["facet"], "weakness")
        self.assertIn("바위 ×4", payload["answer"])
        self.assertNotIn("땅", payload["answer"])
        self.assertEqual(payload["llm_model"], "grounded_template")

    def test_selected_form_localizes_resistance_answer(self) -> None:
        search = self.client.get("/v1/pokedex/search", params={"query": "리자몽", "limit": 1}).json()
        form_id = search["matches"][0]["form_id"]
        response = self.client.post("/v1/chat", json={"message": "반감과 무효", "form_id": form_id})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["facet"], "resistance")
        self.assertIn("벌레 ×0.25", payload["answer"])
        self.assertIn("무효는 땅", payload["answer"])
        self.assertNotIn("bug", payload["answer"])
        self.assertEqual(payload["llm_model"], "grounded_template")

    def test_image_upload_never_uses_filename_as_ocr(self) -> None:
        image_path = next((PROJECT_ROOT / "docs" / "rotomu").glob("*.png"))
        with image_path.open("rb") as image:
            response = self.client.post(
                "/v1/scan",
                files={"image": ("피카츄.png", image, "image/png")},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertNotEqual(payload["ocr_engine"], "filename_fallback")
        self.assertFalse(
            payload["top_candidates"]
            and payload["top_candidates"][0]["pokemon_id"] == 25
            and payload["top_candidates"][0]["confidence"] == 1.0
        )

    def test_image_upload_rejects_invalid_content(self) -> None:
        response = self.client.post(
            "/v1/scan",
            files={"image": ("fake.png", b"not an image", "image/png")},
        )

        self.assertEqual(response.status_code, 415)

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

    def test_ui_contains_confirmation_and_quality_log_guards(self) -> None:
        index = self.client.get("/").text
        script = self.client.get("/ui/app.js").text

        self.assertIn('id="searchInput"', index)
        self.assertIn('id="typeMatchups"', index)
        self.assertIn("if (!appState.confirmed)", script)
        self.assertIn("discovered_count", script)
        self.assertIn("poketdogam.qualityEvents", script)
        self.assertIn('"matcher_only"', script)
        self.assertIn("navigator.mediaDevices.getUserMedia", script)
        self.assertIn("captureCameraFrame", script)
        self.assertIn("PoketdogamCameraQuality", script)
        self.assertIn("확률이 아닌 비교 점수", script)
        self.assertTrue(script.rstrip().endswith("loadHealth();"))

    def test_health_and_privacy_delete_contract(self) -> None:
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "ready")
        self.assertIsInstance(health.json()["ocr_engines"], list)
        if platform.system() == "Darwin":
            self.assertIn("vision_macos", health.json()["ocr_engines"])

        chat = self.client.post("/v1/chat", json={"message": "피카츄 알려줘"}).json()
        session_id = chat["session_id"]
        privacy = self.client.get("/v1/privacy/status")
        self.assertEqual(privacy.status_code, 200)
        self.assertFalse(privacy.json()["raw_images_stored"])
        deleted = self.client.delete(f"/v1/sessions/{session_id}")
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(self.client.delete("/v1/sessions/not.valid").status_code, 422)

    def test_fact_answer_cites_the_exact_fact_channel(self) -> None:
        search = self.client.get("/v1/pokedex/search", params={"query": "피카츄", "limit": 1}).json()
        response = self.client.post(
            "/v1/chat",
            json={"message": "약점", "form_id": search["matches"][0]["form_id"]},
        )

        self.assertEqual(response.status_code, 200)
        citation = response.json()["citations"][0]
        self.assertEqual(citation["facet"], "weakness")
        self.assertTrue(citation["passage_id"].startswith("fact:weakness:"))

    def test_voice_status_policy_blocks_official_mimicry(self) -> None:
        response = self.client.get("/v1/voice/status")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["original_ai_voice_allowed"])
        self.assertFalse(payload["official_audio_extraction_allowed"])
        self.assertFalse(payload["official_voice_mimicry_allowed"])

    def test_selected_form_generates_grounded_narration(self) -> None:
        search = self.client.get("/v1/pokedex/search", params={"query": "피카츄", "limit": 1}).json()
        form_id = search["matches"][0]["form_id"]
        response = self.client.post("/v1/voice/narration", json={"form_id": form_id})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["form_id"], form_id)
        self.assertIn("피카츄", payload["narration_text"])
        self.assertIn("전기", payload["narration_text"])
        self.assertIn("땅 2배", payload["narration_text"])
        self.assertIn("라이츄", payload["narration_text"])
        self.assertIn("천둥의돌", payload["narration_text"])
        self.assertIn("알로라 지역", payload["narration_text"])
        self.assertNotIn("라이츄으로", payload["narration_text"])
        self.assertIn("선택한 정확한 폼", payload["narration_text"])

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
