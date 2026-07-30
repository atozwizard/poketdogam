# Run: python scripts/build_local_dex/build_aliases.py
from __future__ import annotations

from pathlib import Path
from pprint import pprint
import sys
from uuid import NAMESPACE_URL, uuid5


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agents.pokedex_agent.matching import normalize_match_text


def build_alias_rows(forms: list[dict[str, object]], built_at: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for form in forms:
        form_id = str(form["form_id"])
        aliases = _aliases_for_form(form)
        for locale, alias_text, source in aliases:
            alias_norm = normalize_match_text(alias_text)
            if not alias_norm:
                continue
            unique_key = (form_id, alias_norm)
            if unique_key in seen:
                continue
            seen.add(unique_key)
            rows.append(
                {
                    "alias_id": str(uuid5(NAMESPACE_URL, f"poketdogam:alias:{form_id}:{alias_norm}")),
                    "form_id": form_id,
                    "locale": locale,
                    "alias_text": alias_text,
                    "alias_norm": alias_norm,
                    "source": source,
                    "updated_at": built_at,
                }
            )
    return rows


def _aliases_for_form(form: dict[str, object]) -> list[tuple[str, str, str]]:
    names = form["names"]
    assert isinstance(names, dict)
    form_name = str(form["form_name"])
    aliases: list[tuple[str, str, str]] = []
    name_source = str(form.get("source") or "pokeapi")

    for locale in ("ko", "en", "ja"):
        value = names.get(locale)
        if isinstance(value, str) and value:
            aliases.append((locale, value, name_source))

    if form_name != "base":
        ko_name = str(names.get("ko") or "")
        en_name = str(names.get("en") or "")
        aliases.extend(
            [
                ("ko", f"{ko_name} {form_name}", "manual"),
                ("en", f"{form_name} {en_name}", "manual"),
                ("en", f"{en_name} {form_name}", "manual"),
            ]
        )

    for alias in form.get("aliases", []):
        if isinstance(alias, str):
            aliases.append(("ocr", alias, "manual"))

    return aliases


def main() -> None:
    sample = [
        {
            "form_id": "demo",
            "form_name": "base",
            "names": {"ko": "피카츄", "en": "Pikachu", "ja": "ピカチュウ"},
            "aliases": ["피카추"],
        }
    ]
    pprint(build_alias_rows(sample, "2026-07-28T00:00:00+09:00"))


if __name__ == "__main__":
    main()
