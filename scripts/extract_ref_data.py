# Run: python scripts/extract_ref_data.py
from __future__ import annotations

import html
import json
import re
from pathlib import Path
from urllib.parse import urlparse

import requests


SOURCE_FILE = Path("docs/ideation/source_guide.md")
OUTPUT_DIR = Path("docs/ref_data")


URL_PATTERN = re.compile(r"https?://[^\s\]\)\>,]+")
TAG_RE = re.compile(r"<[^>]+>")
SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
MULTI_NEWLINE_RE = re.compile(r"\n{3,}")
WS_RE = re.compile(r"[ \t]{2,}")

UI_KEYWORDS = [
    "ui",
    "ux",
    "interface",
    "menu",
    "screen",
    "layout",
    "button",
    "navigation",
    "hud",
    "icon",
    "visual",
    "디자인",
    "화면",
    "인터페이스",
    "버튼",
    "메뉴",
    "내비",
]


def extract_urls(text: str) -> list[str]:
    urls = URL_PATTERN.findall(text)
    deduped: list[str] = []
    seen: set[str] = set()
    for url in urls:
        cleaned = url.rstrip(".,;)]}>\"'")
        if cleaned not in seen:
            seen.add(cleaned)
            deduped.append(cleaned)
    return deduped


def slugify_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower().replace("www.", "")
    path = parsed.path.strip("/").replace("/", "_")
    if not path:
        path = "root"
    base = f"{host}__{path}"
    base = re.sub(r"[^a-zA-Z0-9._-]+", "-", base).strip("-")
    return base[:120]


def html_to_text(raw_html: str) -> str:
    no_script = SCRIPT_STYLE_RE.sub(" ", raw_html)
    no_tags = TAG_RE.sub(" ", no_script)
    decoded = html.unescape(no_tags)
    cleaned = WS_RE.sub(" ", decoded)
    lines = [line.strip() for line in cleaned.splitlines()]
    lines = [line for line in lines if line]
    text = "\n".join(lines)
    return MULTI_NEWLINE_RE.sub("\n\n", text).strip()


def extract_ui_lines(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    out: list[str] = []
    for line in lines:
        lowered = line.lower()
        if any(keyword in lowered for keyword in UI_KEYWORDS):
            out.append(line)
    deduped: list[str] = []
    seen: set[str] = set()
    for line in out:
        if line not in seen:
            seen.add(line)
            deduped.append(line)
    return deduped


def main() -> None:
    if not SOURCE_FILE.exists():
        raise FileNotFoundError(f"Missing source guide: {SOURCE_FILE}")

    src_text = SOURCE_FILE.read_text(encoding="utf-8")
    urls = extract_urls(src_text)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    summary: list[dict[str, str | int]] = []
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            )
        }
    )

    for idx, url in enumerate(urls, start=1):
        slug = slugify_url(url)
        text_path = OUTPUT_DIR / f"{idx:03d}_{slug}.txt"
        ui_path = OUTPUT_DIR / f"{idx:03d}_UI_REF_{slug}.txt"

        status = "ok"
        note = ""
        body_text = ""
        ui_lines: list[str] = []

        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
            body_text = html_to_text(resp.text)
            if not body_text:
                status = "empty_text"
                note = "No extractable text."
            ui_lines = extract_ui_lines(body_text)
        except Exception as exc:
            status = "error"
            note = str(exc)
            body_text = ""

        header = f"URL: {url}\nSTATUS: {status}\n\n"
        text_path.write_text(header + body_text, encoding="utf-8")

        if ui_lines:
            ui_content = header + "\n".join(ui_lines)
            ui_path.write_text(ui_content, encoding="utf-8")

        summary.append(
            {
                "index": idx,
                "url": url,
                "status": status,
                "output_file": str(text_path).replace("\\", "/"),
                "ui_file": str(ui_path).replace("\\", "/") if ui_lines else "",
                "ui_line_count": len(ui_lines),
                "note": note,
            }
        )

    (OUTPUT_DIR / "REF_SUMMARY.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    ok_count = sum(1 for item in summary if item["status"] == "ok")
    print(f"Processed {len(summary)} URLs, ok={ok_count}, output={OUTPUT_DIR}")


if __name__ == "__main__":
    main()
