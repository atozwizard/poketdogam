# Run: python app/agents/pokedex_agent/tools/tool_local_llm.py
from __future__ import annotations

import json
from pathlib import Path
import re
import sys
from collections.abc import Iterator
from typing import Any

import httpx


PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agents.pokedex_agent.prompts.rotom import build_system_prompt
from app.config.settings import get_settings


THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def generate_local_answer(message: str, detail: dict[str, Any], template_answer: str) -> dict[str, str]:
    settings = get_settings()
    if settings.local_llm_provider != "ollama":
        return {
            "runtime": "template",
            "model": "template",
            "answer": template_answer,
            "error": "",
        }

    prompt = _build_prompt(message, detail, template_answer)
    system_prompt = build_system_prompt(
        grounded=True,
        context=str(
            {
                "name_ko": detail.get("name_ko"),
                "name_en": detail.get("name_en"),
                "generation": detail.get("generation"),
                "types": detail.get("types"),
                "height_m": detail.get("height_m"),
                "weight_kg": detail.get("weight_kg"),
                "stats": detail.get("stats"),
                "form_name": detail.get("form_name"),
            }
        ),
        safe_template=template_answer,
    )
    try:
        response = httpx.post(
            f"{settings.ollama_base_url.rstrip('/')}/api/chat",
            json={
                "model": settings.local_llm_model,
                "stream": False,
                "think": False,
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {"role": "user", "content": prompt},
                ],
                "options": {
                    "temperature": 0.35,
                    "top_p": 0.9,
                    "num_predict": 180,
                },
            },
            timeout=settings.local_llm_timeout,
        )
        response.raise_for_status()
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        return {
            "runtime": "fallback_template",
            "model": settings.local_llm_model,
            "answer": template_answer,
            "error": str(exc),
        }

    payload = response.json()
    message = payload.get("message") if isinstance(payload, dict) else {}
    answer = _clean_answer(str(message.get("content", "") if isinstance(message, dict) else ""))
    if not answer or _is_suspicious_answer(answer, message=prompt):
        return {
            "runtime": "fallback_template",
            "model": settings.local_llm_model,
            "answer": template_answer,
            "error": "empty_or_suspicious_response",
        }

    return {
        "runtime": "ollama",
        "model": settings.local_llm_model,
        "answer": answer,
        "error": "",
    }


def stream_local_answer(message: str, detail: dict[str, Any], template_answer: str) -> Iterator[dict[str, str]]:
    settings = get_settings()
    if settings.local_llm_provider != "ollama":
        yield {"event": "meta", "runtime": "template", "model": "template"}
        yield {"event": "delta", "text": template_answer}
        yield {"event": "done", "answer": template_answer, "runtime": "template", "model": "template"}
        return

    prompt = _build_prompt(message, detail, template_answer)
    system_prompt = build_system_prompt(
        grounded=True,
        context=str(
            {
                "name_ko": detail.get("name_ko"),
                "name_en": detail.get("name_en"),
                "generation": detail.get("generation"),
                "types": detail.get("types"),
                "height_m": detail.get("height_m"),
                "weight_kg": detail.get("weight_kg"),
                "stats": detail.get("stats"),
                "form_name": detail.get("form_name"),
            }
        ),
        safe_template=template_answer,
    )
    chunks: list[str] = []
    try:
        with httpx.stream(
            "POST",
            f"{settings.ollama_base_url.rstrip('/')}/api/chat",
            json={
                "model": settings.local_llm_model,
                "stream": True,
                "think": False,
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {"role": "user", "content": prompt},
                ],
                "options": {
                    "temperature": 0.35,
                    "top_p": 0.9,
                    "num_predict": 180,
                },
            },
            timeout=settings.local_llm_timeout,
        ) as response:
            response.raise_for_status()
            yield {"event": "meta", "runtime": "ollama", "model": settings.local_llm_model}
            for line in response.iter_lines():
                if not line:
                    continue
                payload = json.loads(line)
                payload_message = payload.get("message") if isinstance(payload, dict) else {}
                delta = str(payload_message.get("content", "") if isinstance(payload_message, dict) else "")
                if delta:
                    chunks.append(delta)
                    yield {"event": "delta", "text": delta}
                if isinstance(payload, dict) and payload.get("done"):
                    break
    except (httpx.HTTPError, httpx.TimeoutException, json.JSONDecodeError) as exc:
        yield {"event": "meta", "runtime": "fallback_template", "model": settings.local_llm_model}
        yield {"event": "replace", "text": template_answer}
        yield {
            "event": "done",
            "answer": template_answer,
            "runtime": "fallback_template",
            "model": settings.local_llm_model,
            "error": str(exc),
        }
        return

    answer = _clean_answer("".join(chunks))
    if not answer or _is_suspicious_answer(answer, message=prompt):
        yield {"event": "meta", "runtime": "fallback_template", "model": settings.local_llm_model}
        yield {"event": "replace", "text": template_answer}
        yield {
            "event": "done",
            "answer": template_answer,
            "runtime": "fallback_template",
            "model": settings.local_llm_model,
            "error": "empty_or_suspicious_response",
        }
        return

    if answer != "".join(chunks).strip():
        yield {"event": "replace", "text": answer}
    yield {"event": "done", "answer": answer, "runtime": "ollama", "model": settings.local_llm_model}


def _build_prompt(message: str, detail: dict[str, Any], template_answer: str) -> str:
    facts = {
        "name_ko": detail.get("name_ko"),
        "name_en": detail.get("name_en"),
        "generation": detail.get("generation"),
        "types": detail.get("types"),
        "height_m": detail.get("height_m"),
        "weight_kg": detail.get("weight_kg"),
        "stats": detail.get("stats"),
        "form_name": detail.get("form_name"),
    }
    return (
        "Rotom Dex OS 말투로 한국어 1~4문장만 답하라. 질문이 단순하면 1문장으로 끝내라. "
        "자연스러울 때만 어미 '-로'를 쓰고, '-로'를 공백으로 따로 붙이지 말라. "
        "USER_QUESTION을 반복하지 말라. SAFE_TEMPLATE/FACTS에 있는 사실만 더 자연스럽게 말하라. "
        "FACTS에 없는 애니메이션 설정, 성격, 기술, 세계관 설명은 추가하지 말라.\n\n"
        f"USER_QUESTION: {message}\n"
        f"FACTS: {facts}\n"
        f"SAFE_TEMPLATE: {template_answer}\n"
        "ANSWER:"
    )


def _clean_answer(answer: str) -> str:
    cleaned = THINK_RE.sub("", answer).strip()
    cleaned = cleaned.replace("ANSWER:", "").strip()
    cleaned = re.sub(r"\n+\s*-로\s*$", "", cleaned).strip()
    cleaned = re.sub(r"\s+[-–—]\s*로[-–—]?\s*$", "", cleaned).strip()
    return cleaned


def _is_suspicious_answer(answer: str, message: str) -> bool:
    if re.search(r"[\u4e00-\u9fff]", answer):
        return True
    if len(answer) > 320:
        return True
    banned_tokens = ["USER_QUESTION", "SAFE_TEMPLATE", "FACTS", "ANSWER:"]
    if any(token in answer for token in banned_tokens):
        return True
    if "알려줘" in answer or "말투로" in answer:
        return True
    question_text = re.sub(r"\s+", " ", message).strip()
    return bool(question_text and question_text[:24] in answer)


def main() -> None:
    detail = {
        "name_ko": "피카츄",
        "name_en": "Pikachu",
        "generation": 1,
        "types": ["electric"],
        "stats": {"bst": 320},
    }
    print(generate_local_answer("피카츄 알려줘", detail, "피카츄는 1세대 포켓몬이고 타입은 electric입니다."))


if __name__ == "__main__":
    main()
