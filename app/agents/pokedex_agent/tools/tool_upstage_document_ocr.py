# Run: python app/agents/pokedex_agent/tools/tool_upstage_document_ocr.py
from app.config.settings import get_settings


def extract_document_text(image_bytes: bytes, filename: str) -> dict[str, object]:
    settings = get_settings()
    if not image_bytes:
        return {"text": "", "blocks": [], "provider": "upstage_document_ocr"}
    return {
        "text": f"OCR pending for {filename}",
        "blocks": [],
        "provider": "upstage_document_ocr",
        "configured": bool(settings.upstage_api_key),
        "bytes": len(image_bytes),
    }


def main() -> None:
    print(extract_document_text(b"demo", "sample.png"))


if __name__ == "__main__":
    main()
