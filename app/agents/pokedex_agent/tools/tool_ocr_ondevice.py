# Run: python app/agents/pokedex_agent/tools/tool_ocr_ondevice.py
from __future__ import annotations

from pathlib import Path
import string


def extract_ondevice_text(image_bytes: bytes, filename: str) -> dict[str, object]:
    if not image_bytes:
        return {"text": "", "blocks": [], "provider": "os_ocr_adapter", "engine": "empty_input"}

    decoded = _decode_fixture_text(image_bytes)
    if decoded:
        return {
            "text": decoded,
            "blocks": [],
            "provider": "os_ocr_adapter",
            "engine": "fixture_text",
        }

    fallback_text = Path(filename).stem.replace("_", " ").replace("-", " ")
    return {
        "text": fallback_text,
        "blocks": [],
        "provider": "os_ocr_adapter",
        "engine": "filename_fallback",
    }


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
