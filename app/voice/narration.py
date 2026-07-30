from __future__ import annotations

from typing import Any


TYPE_LABELS = {
    "normal": "노말",
    "fire": "불꽃",
    "water": "물",
    "electric": "전기",
    "grass": "풀",
    "ice": "얼음",
    "fighting": "격투",
    "poison": "독",
    "ground": "땅",
    "flying": "비행",
    "psychic": "에스퍼",
    "bug": "벌레",
    "rock": "바위",
    "ghost": "고스트",
    "dragon": "드래곤",
    "dark": "악",
    "steel": "강철",
    "fairy": "페어리",
}

ITEM_LABELS = {
    "thunder-stone": "천둥의돌",
    "fire-stone": "불꽃의돌",
    "water-stone": "물의돌",
    "leaf-stone": "리프의돌",
    "moon-stone": "달의돌",
    "sun-stone": "태양의돌",
    "shiny-stone": "빛의돌",
    "dusk-stone": "어둠의돌",
    "dawn-stone": "각성의돌",
    "ice-stone": "얼음의돌",
    "kings-rock": "왕의징표석",
    "metal-coat": "금속코트",
}

REGION_LABELS = {
    "alola": "알로라",
    "galar": "가라르",
    "hisui": "히스이",
    "paldea": "팔데아",
}


def build_narration(detail: dict[str, Any]) -> str:
    """Build a deterministic Korean script only from the selected form's facts."""
    name = str(detail.get("name_ko") or detail.get("name_en") or "선택한 포켓몬")
    form_name = str(detail.get("form_name") or "base")
    form_suffix = "" if form_name == "base" else f" {form_name} 폼"
    types = [
        TYPE_LABELS.get(str(item), str(item))
        for item in detail.get("types", [])
        if item
    ]

    sentences = [f"{name}{form_suffix} 정보를 읽는다-로."]
    if types:
        sentences.append(f"타입은 {'과 '.join(types)} 타입이다.")

    weaknesses = detail.get("weaknesses") or []
    if weaknesses:
        labels = [
            f"{TYPE_LABELS.get(str(item.get('type')), str(item.get('type')))} {_multiplier_label(item.get('multiplier'))}"
            for item in weaknesses[:5]
        ]
        sentences.append(f"약점은 {', '.join(labels)}다.")
    else:
        sentences.append("확인된 약점 정보가 없다.")

    evolutions = detail.get("evolutions") or []
    if evolutions:
        summaries = [_evolution_label(item, name) for item in evolutions[:3]]
        sentences.append(f"진화 정보는 다음과 같다. {'; '.join(summaries)}.")
    else:
        sentences.append("현재 데이터에는 연결된 진화 정보가 없다.")

    stats = detail.get("stats") or {}
    if stats.get("bst") is not None:
        sentences.append(f"종족값 합계는 {int(stats['bst'])}이다.")
    sentences.append("화면에서 선택한 정확한 폼 기준이다-로.")
    return " ".join(sentences)


def _multiplier_label(value: object) -> str:
    try:
        multiplier = float(value)
    except (TypeError, ValueError):
        return "상성 미확인"
    if multiplier.is_integer():
        return f"{int(multiplier)}배"
    return f"{multiplier:g}배"


def _evolution_label(item: dict[str, Any], selected_name: str) -> str:
    from_name = str(item.get("from_name") or selected_name)
    to_name = str(item.get("to_name") or "다음 포켓몬")
    condition = item.get("condition")
    trigger = ""
    if isinstance(condition, dict):
        trigger = _condition_summary(condition)
    if not trigger:
        trigger = _trigger_summary(str(item.get("trigger_value") or item.get("trigger_type") or ""))
    destination = f"{to_name}{_direction_particle(to_name)}"
    if trigger:
        return f"{from_name}에서 {destination}, 조건은 {trigger}"
    return f"{from_name}에서 {destination} 진화"


def _condition_summary(condition: dict[str, Any]) -> str:
    parts: list[str] = []
    region = condition.get("region")
    if region:
        parts.append(f"{REGION_LABELS.get(str(region), _plain_slug(region))} 지역")
    item = condition.get("item")
    if item:
        parts.append(f"{_item_label(item)} 사용")
    held_item = condition.get("held_item")
    if held_item:
        parts.append(f"{_item_label(held_item)} 지니기")
    if condition.get("min_level"):
        parts.append(f"레벨 {condition['min_level']} 이상")
    if condition.get("min_happiness"):
        parts.append(f"친밀도 {condition['min_happiness']} 이상")
    if condition.get("time_of_day"):
        parts.append(f"{_plain_slug(condition['time_of_day'])} 시간대")
    if condition.get("known_move"):
        parts.append(f"{_plain_slug(condition['known_move'])} 습득")
    if condition.get("known_move_type"):
        move_type = TYPE_LABELS.get(str(condition["known_move_type"]), _plain_slug(condition["known_move_type"]))
        parts.append(f"{move_type} 타입 기술 습득")
    if condition.get("location"):
        parts.append(f"{_plain_slug(condition['location'])} 장소")
    return ", ".join(parts[:3])


def _trigger_summary(trigger: str) -> str:
    labels = {
        "level-up": "레벨업",
        "trade": "통신교환",
        "use-item": "진화 도구 사용",
        "shed": "특수 분화",
        "spin": "회전",
        "tower-of-darkness": "악의 탑 수련",
        "tower-of-waters": "물의 탑 수련",
    }
    if trigger in ITEM_LABELS:
        return f"{ITEM_LABELS[trigger]} 사용"
    return labels.get(trigger, _plain_slug(trigger))


def _item_label(value: object) -> str:
    slug = str(value)
    return ITEM_LABELS.get(slug, _plain_slug(slug))


def _plain_slug(value: object) -> str:
    return str(value).replace("-", " ")


def _direction_particle(value: str) -> str:
    if not value:
        return "으로"
    last = value[-1]
    if "가" <= last <= "힣":
        jongseong = (ord(last) - ord("가")) % 28
        return "으로" if jongseong not in (0, 8) else "로"
    return "로"
