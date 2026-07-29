# Run: python app/agents/pokedex_agent/tools/tool_ocr_ondevice.py
from __future__ import annotations

from pathlib import Path
import platform
import shutil
import string
import subprocess
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parents[4]
MACOS_VISION_SCRIPT = PROJECT_ROOT / "scripts" / "ocr_macos_vision.swift"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".heic", ".heif", ".tif", ".tiff"}
OCR_TIMEOUT_SECONDS = 12


def available_ocr_engines() -> list[str]:
    engines = []
    if platform.system() == "Darwin" and shutil.which("swift") and MACOS_VISION_SCRIPT.exists():
        engines.append("vision_macos")
    if shutil.which("tesseract"):
        engines.append("tesseract_local")
    return engines


def extract_ondevice_text(
    image_bytes: bytes,
    filename: str,
    content_type: str | None = None,
) -> dict[str, object]:
    if not image_bytes:
        return {"text": "", "blocks": [], "provider": "os_ocr_adapter", "engine": "empty_input"}

    suffix = Path(filename).suffix.lower()
    if _is_fixture_input(suffix, content_type):
        decoded = _decode_fixture_text(image_bytes)
        if not decoded:
            return {
                "text": "",
                "blocks": [],
                "provider": "fixture_text",
                "engine": "fixture_text_invalid",
            }
        return {
            "text": decoded,
            "blocks": [],
            "provider": "fixture_text",
            "engine": "fixture_text",
        }

    if suffix not in IMAGE_SUFFIXES:
        return {"text": "", "blocks": [], "provider": "os_ocr_adapter", "engine": "unsupported_image"}

    backend_results = []
    if platform.system() == "Darwin" and shutil.which("swift") and MACOS_VISION_SCRIPT.exists():
        backend_results.append(("vision_macos", _run_ocr_command(image_bytes, suffix, ["swift", str(MACOS_VISION_SCRIPT)])))

    tesseract = shutil.which("tesseract")
    if tesseract:
        backend_results.append(
            (
                "tesseract_local",
                _run_ocr_command(
                    image_bytes,
                    suffix,
                    [tesseract, "{image}", "stdout", "-l", "kor+eng+jpn", "--psm", "6"],
                ),
            )
        )

    for engine, text in backend_results:
        if text:
            return {
                "text": text,
                "blocks": [],
                "provider": "os_ocr_adapter",
                "engine": engine,
            }

    if backend_results:
        return {
            "text": "",
            "blocks": [],
            "provider": "os_ocr_adapter",
            "engine": f"{backend_results[0][0]}_empty",
        }
    return {"text": "", "blocks": [], "provider": "os_ocr_adapter", "engine": "ocr_unavailable"}


def _is_fixture_input(suffix: str, content_type: str | None) -> bool:
    return suffix in {".txt", ".jsonl"} or (content_type or "").lower().startswith("text/")


def _run_ocr_command(image_bytes: bytes, suffix: str, command: list[str]) -> str:
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix) as image_file:
            image_file.write(image_bytes)
            image_file.flush()
            resolved = [part.replace("{image}", image_file.name) for part in command]
            if "{image}" not in command:
                resolved.append(image_file.name)
            result = subprocess.run(
                resolved,
                capture_output=True,
                check=False,
                timeout=OCR_TIMEOUT_SECONDS,
            )
    except (OSError, subprocess.SubprocessError):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.decode("utf-8", errors="replace").strip()


def _decode_fixture_text(image_bytes: bytes) -> str:
    try:
        decoded = image_bytes.decode("utf-8").strip()
    except UnicodeDecodeError:
        return ""
    if not decoded:
        return ""

    printable = sum(1 for char in decoded if char in string.printable or ord(char) > 127)
    if printable / max(len(decoded), 1) < 0.85:
        return ""
    return decoded


def main() -> None:
    print(extract_ondevice_text("피카추\nHP 60".encode(), "fixture.txt"))


if __name__ == "__main__":
    main()
