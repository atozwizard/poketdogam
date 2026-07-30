from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import httpx
from fastapi import HTTPException
from PIL import Image

from app.agents.pokedex_agent.state import AgentState
from app.api.routes import scan as scan_route
from app.api.routes.scan import _validate_image_dimensions
from app.main import create_app
from scripts.build_local_dex.artifacts import (
    attach_artifact_manifest,
    verify_artifact_manifest,
)
from scripts.build_local_dex.collector import _atomic_copy


def image_bytes(width: int = 64, height: int = 64, mode: str = "RGB") -> bytes:
    output = BytesIO()
    Image.new(mode, (width, height), color=0).save(output, format="PNG")
    return output.getvalue()


class RuntimeSafetyTest(unittest.TestCase):
    def test_decoded_image_dimensions_are_bounded(self) -> None:
        with self.assertRaises(HTTPException) as tiny:
            _validate_image_dimensions(image_bytes(16, 16), "image/png")
        self.assertEqual(tiny.exception.status_code, 422)

        with self.assertRaises(HTTPException) as huge:
            _validate_image_dimensions(image_bytes(8000, 5001, mode="1"), "image/png")
        self.assertEqual(huge.exception.status_code, 413)

    def test_scan_work_does_not_block_health_request(self) -> None:
        async def scenario() -> float:
            transport = httpx.ASGITransport(app=create_app())
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                scan_task = asyncio.create_task(
                    client.post(
                        "/v1/scan",
                        files={"image": ("camera.png", image_bytes(), "image/png")},
                    )
                )
                await asyncio.sleep(0.04)
                started = time.perf_counter()
                health = await client.get("/health/live")
                elapsed = time.perf_counter() - started
                self.assertEqual(health.status_code, 200)
                self.assertEqual((await scan_task).status_code, 200)
                return elapsed

        def slow_scan(*_args, **_kwargs):
            time.sleep(0.3)
            state = AgentState()
            state.dataset_version = "test"
            return state, []

        with patch.object(scan_route.agent, "run_scan", side_effect=slow_scan):
            elapsed = asyncio.run(scenario())
        self.assertLess(elapsed, 0.15)

    def test_security_headers_and_health_contract(self) -> None:
        transport = httpx.ASGITransport(app=create_app())

        async def scenario() -> None:
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/")
                self.assertEqual(response.headers["x-content-type-options"], "nosniff")
                self.assertEqual(response.headers["x-frame-options"], "DENY")
                self.assertEqual(response.headers["permissions-policy"], "camera=(self), microphone=()")
                ready = await client.get("/health/ready")
                self.assertIn("components", ready.json())

        asyncio.run(scenario())

    def test_artifact_manifest_detects_corruption_and_atomic_copy_replaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "dex.sqlite"
            meta = root / "dex.meta.json"
            target = root / "published" / "dex.sqlite"
            artifact.write_bytes(b"verified")
            meta.write_text('{"dataset_version":"test"}', encoding="utf-8")

            attach_artifact_manifest(meta, {"dex.sqlite": artifact})
            self.assertTrue(
                verify_artifact_manifest(meta, {"dex.sqlite": artifact})["valid"]
            )
            _atomic_copy(artifact, target)
            self.assertEqual(target.read_bytes(), b"verified")

            artifact.write_bytes(b"corrupted")
            self.assertFalse(
                verify_artifact_manifest(meta, {"dex.sqlite": artifact})["valid"]
            )


if __name__ == "__main__":
    unittest.main()
