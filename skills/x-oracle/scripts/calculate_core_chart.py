#!/usr/bin/env python3
"""Calculate the X-Oracle core chart as structured JSON.

Required dependency:
    pip install lunar_python
"""

from __future__ import annotations

import argparse
import json
import math
import select
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

try:
    from lunar_python import Solar
except ImportError as exc:
    raise SystemExit(
        "Missing dependency: lunar_python. Install with `pip install lunar_python`."
    ) from exc


STEM_ELEMENTS = {
    "甲": "wood",
    "乙": "wood",
    "丙": "fire",
    "丁": "fire",
    "戊": "earth",
    "己": "earth",
    "庚": "metal",
    "辛": "metal",
    "壬": "water",
    "癸": "water",
}

STEM_POLARITY = {
    "甲": "yang",
    "乙": "yin",
    "丙": "yang",
    "丁": "yin",
    "戊": "yang",
    "己": "yin",
    "庚": "yang",
    "辛": "yin",
    "壬": "yang",
    "癸": "yin",
}

BRANCH_ELEMENTS = {
    "子": "water",
    "丑": "earth",
    "寅": "wood",
    "卯": "wood",
    "辰": "earth",
    "巳": "fire",
    "午": "fire",
    "未": "earth",
    "申": "metal",
    "酉": "metal",
    "戌": "earth",
    "亥": "water",
}

HIDDEN_STEMS = {
    "子": ["癸"],
    "丑": ["己", "癸", "辛"],
    "寅": ["甲", "丙", "戊"],
    "卯": ["乙"],
    "辰": ["戊", "乙", "癸"],
    "巳": ["丙", "戊", "庚"],
    "午": ["丁", "己"],
    "未": ["己", "丁", "乙"],
    "申": ["庚", "壬", "戊"],
    "酉": ["辛"],
    "戌": ["戊", "辛", "丁"],
    "亥": ["壬", "甲"],
}

ELEMENT_GENERATES = {
    "wood": "fire",
    "fire": "earth",
    "earth": "metal",
    "metal": "water",
    "water": "wood",
}

ELEMENT_CONTROLS = {
    "wood": "earth",
    "earth": "water",
    "water": "fire",
    "fire": "metal",
    "metal": "wood",
}

RELATIONSHIP_PAIRS = {
    "six_clash": [("子", "午"), ("丑", "未"), ("寅", "申"), ("卯", "酉"), ("辰", "戌"), ("巳", "亥")],
    "six_combine": [("子", "丑"), ("寅", "亥"), ("卯", "戌"), ("辰", "酉"), ("巳", "申"), ("午", "未")],
    "six_harm": [("子", "未"), ("丑", "午"), ("寅", "巳"), ("卯", "辰"), ("申", "亥"), ("酉", "戌")],
}

THREE_PUNISHMENTS = [
    ("寅", "巳", "申"),
    ("丑", "未", "戌"),
]

SELF_PUNISHMENTS = {"辰", "午", "酉", "亥"}


@dataclass
class BirthInput:
    birth_date: str
    birth_time: str
    calendar: str = "gregorian"
    timezone: str = "Asia/Shanghai"
    gender: str | None = None
    birthplace: str | None = None
    longitude: float | None = None
    time_precision: str = "minute"
    focus: str | None = None


def call_value(obj: Any, name: str, default: Any = None) -> Any:
    value = getattr(obj, name, default)
    if callable(value):
        return value()
    return value


def parse_input(raw: dict[str, Any]) -> BirthInput:
    if "birth_date" not in raw or "birth_time" not in raw:
        raise ValueError("birth_date and birth_time are required.")

    return BirthInput(
        birth_date=str(raw["birth_date"]),
        birth_time=str(raw["birth_time"]),
        calendar=str(raw.get("calendar", "gregorian")).lower(),
        timezone=str(raw.get("timezone", "Asia/Shanghai")),
        gender=raw.get("gender"),
        birthplace=raw.get("birthplace"),
        longitude=float(raw["longitude"]) if raw.get("longitude") is not None else None,
        time_precision=str(raw.get("time_precision", "minute")),
        focus=raw.get("focus"),
    )


def parse_local_datetime(data: BirthInput) -> datetime:
    try:
        date_part = datetime.strptime(data.birth_date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("birth_date must use YYYY-MM-DD.") from exc

    time_formats = ["%H:%M", "%H:%M:%S"]
    parsed_time = None
    for fmt in time_formats:
        try:
            parsed_time = datetime.strptime(data.birth_time, fmt).time()
            break
        except ValueError:
            continue
    if parsed_time is None:
        raise ValueError("birth_time must use HH:MM or HH:MM:SS.")

    try:
        zone = ZoneInfo(data.timezone)
    except Exception as exc:
        raise ValueError(f"Invalid timezone: {data.timezone}") from exc

    return datetime.combine(date_part, parsed_time, tzinfo=zone)


def equation_of_time_minutes(dt: datetime) -> float:
    day = dt.timetuple().tm_yday
    angle = 2 * math.pi * (day - 81) / 364
    return 9.87 * math.sin(2 * angle) - 7.53 * math.cos(angle) - 1.5 * math.sin(angle)


def true_solar_time(dt: datetime, longitude: float | None) -> tuple[datetime, dict[str, Any]]:
    if longitude is None:
        return dt, {
            "applied": False,
            "reason": "longitude_missing",
            "confidence_note": "No true solar time correction was applied.",
        }

    offset_hours = dt.utcoffset().total_seconds() / 3600 if dt.utcoffset() else 8
    standard_meridian = offset_hours * 15
    longitude_correction = (longitude - standard_meridian) * 4
    eot = equation_of_time_minutes(dt)
    total_minutes = longitude_correction + eot
    corrected = dt + timedelta(minutes=total_minutes)

    return corrected, {
        "applied": True,
        "longitude": longitude,
        "standard_meridian": standard_meridian,
        "longitude_correction_minutes": round(longitude_correction, 2),
        "equation_of_time_minutes": round(eot, 2),
        "total_correction_minutes": round(total_minutes, 2),
        "corrected_local_time": corrected.isoformat(),
    }


def ten_god(day_stem: str, target_stem: str) -> str:
    day_element = STEM_ELEMENTS[day_stem]
    target_element = STEM_ELEMENTS[target_stem]
    same_polarity = STEM_POLARITY[day_stem] == STEM_POLARITY[target_stem]

    if target_element == day_element:
        return "friend" if same_polarity else "rob_wealth"
    if ELEMENT_GENERATES[day_element] == target_element:
        return "eating_god" if same_polarity else "hurting_officer"
    if ELEMENT_CONTROLS[day_element] == target_element:
        return "indirect_wealth" if same_polarity else "direct_wealth"
    if ELEMENT_CONTROLS[target_element] == day_element:
        return "seven_killing" if same_polarity else "direct_officer"
    if ELEMENT_GENERATES[target_element] == day_element:
        return "indirect_resource" if same_polarity else "direct_resource"
    return "unknown"


def collect_pillars(eight_char: Any) -> list[dict[str, Any]]:
    specs = [
        ("year", "getYear", "getYearGan", "getYearZhi"),
        ("month", "getMonth", "getMonthGan", "getMonthZhi"),
        ("day", "getDay", "getDayGan", "getDayZhi"),
        ("hour", "getTime", "getTimeGan", "getTimeZhi"),
    ]

    pillars = []
    for label, pillar_method, stem_method, branch_method in specs:
        stem = call_value(eight_char, stem_method)
        branch = call_value(eight_char, branch_method)
        pillars.append(
            {
                "label": label,
                "pillar": call_value(eight_char, pillar_method),
                "stem": stem,
                "branch": branch,
                "stem_element": STEM_ELEMENTS.get(stem),
                "stem_polarity": STEM_POLARITY.get(stem),
                "branch_element": BRANCH_ELEMENTS.get(branch),
                "hidden_stems": [
                    {
                        "stem": hidden,
                        "element": STEM_ELEMENTS[hidden],
                        "polarity": STEM_POLARITY[hidden],
                    }
                    for hidden in HIDDEN_STEMS.get(branch, [])
                ],
            }
        )
    return pillars


def add_ten_gods(pillars: list[dict[str, Any]]) -> None:
    day_stem = next(p["stem"] for p in pillars if p["label"] == "day")
    for pillar in pillars:
        pillar["ten_god_stem"] = ten_god(day_stem, pillar["stem"])
        for hidden in pillar["hidden_stems"]:
            hidden["ten_god"] = ten_god(day_stem, hidden["stem"])


def element_distribution(pillars: list[dict[str, Any]]) -> dict[str, Any]:
    weighted = Counter()
    visible = Counter()
    hidden = Counter()

    for pillar in pillars:
        stem_element = pillar["stem_element"]
        branch_element = pillar["branch_element"]
        visible[stem_element] += 1
        visible[branch_element] += 1
        weighted[stem_element] += 1.0
        weighted[branch_element] += 0.7
        hidden_stems = pillar["hidden_stems"]
        for index, hidden_stem in enumerate(hidden_stems):
            weight = [0.3, 0.2, 0.1][index] if index < 3 else 0.05
            element = hidden_stem["element"]
            hidden[element] += 1
            weighted[element] += weight

    all_elements = ["wood", "fire", "earth", "metal", "water"]
    return {
        "weighted": {element: round(weighted[element], 2) for element in all_elements},
        "visible_count": {element: visible[element] for element in all_elements},
        "hidden_count": {element: hidden[element] for element in all_elements},
        "strongest": max(all_elements, key=lambda item: weighted[item]),
        "weakest": min(all_elements, key=lambda item: weighted[item]),
    }


def detect_relationships(branches: list[str]) -> dict[str, Any]:
    branch_set = set(branches)
    result: dict[str, Any] = {}

    for name, pairs in RELATIONSHIP_PAIRS.items():
        result[name] = [
            {"branches": list(pair)}
            for pair in pairs
            if pair[0] in branch_set and pair[1] in branch_set
        ]

    result["three_punishment"] = [
        {"branches": list(group)}
        for group in THREE_PUNISHMENTS
        if all(branch in branch_set for branch in group)
    ]
    counts = Counter(branches)
    result["self_punishment"] = [
        {"branch": branch}
        for branch in SELF_PUNISHMENTS
        if counts[branch] >= 2
    ]
    return result


def time_confidence(dt: datetime, solar_info: dict[str, Any], precision: str) -> dict[str, Any]:
    hour = dt.hour
    minute = dt.minute
    minutes_since_midnight = hour * 60 + minute
    branch_boundaries = [23 * 60, 1 * 60, 3 * 60, 5 * 60, 7 * 60, 9 * 60, 11 * 60, 13 * 60, 15 * 60, 17 * 60, 19 * 60, 21 * 60]
    distances = [abs(minutes_since_midnight - boundary) for boundary in branch_boundaries]
    distances.append(abs(minutes_since_midnight + 24 * 60 - 23 * 60))
    near_boundary = min(distances) <= 30

    notes = []
    if near_boundary:
        notes.append("Birth time is within 30 minutes of a time-branch boundary.")
    if not solar_info.get("applied"):
        notes.append("True solar time was not applied.")
    if precision not in {"minute", "exact"}:
        notes.append(f"Birth time precision is marked as {precision}.")

    return {
        "level": "low" if near_boundary or precision in {"unknown", "approximate"} else "medium" if notes else "high",
        "near_time_branch_boundary": near_boundary,
        "notes": notes,
    }


def build_chart(data: BirthInput) -> dict[str, Any]:
    if data.calendar not in {"gregorian", "solar"}:
        raise ValueError("Only gregorian/solar input is currently supported by this script.")

    local_dt = parse_local_datetime(data)
    corrected_dt, solar_info = true_solar_time(local_dt, data.longitude)

    solar = Solar.fromYmdHms(
        corrected_dt.year,
        corrected_dt.month,
        corrected_dt.day,
        corrected_dt.hour,
        corrected_dt.minute,
        corrected_dt.second,
    )
    lunar = call_value(solar, "getLunar")
    eight_char = call_value(lunar, "getEightChar")

    pillars = collect_pillars(eight_char)
    add_ten_gods(pillars)
    branches = [pillar["branch"] for pillar in pillars]
    day_stem = next(pillar["stem"] for pillar in pillars if pillar["label"] == "day")

    chart = {
        "input": data.__dict__,
        "normalized_time": {
            "local_time": local_dt.isoformat(),
            "calculation_time": corrected_dt.isoformat(),
            "calendar": data.calendar,
            "timezone": data.timezone,
        },
        "solar_time": solar_info,
        "lunar": {
            "year": call_value(lunar, "getYear", None),
            "month": call_value(lunar, "getMonth", None),
            "day": call_value(lunar, "getDay", None),
            "date_string": call_value(lunar, "toString", None),
            "full_string": call_value(lunar, "toFullString", None),
        },
        "core_chart": {
            "pillars": pillars,
            "pillar_string": " ".join(pillar["pillar"] for pillar in pillars),
            "day_master": {
                "stem": day_stem,
                "element": STEM_ELEMENTS[day_stem],
                "polarity": STEM_POLARITY[day_stem],
            },
            "element_distribution": element_distribution(pillars),
            "branch_relationships": detect_relationships(branches),
        },
        "confidence": time_confidence(corrected_dt, solar_info, data.time_precision),
        "notes": [
            "X-Oracle default reports should state BaZi evidence directly and explain the classical reasoning.",
            "Use this JSON as evidence, not as a deterministic verdict.",
        ],
    }

    try:
        yun = None
        if callable(getattr(eight_char, "getYun", None)) and data.gender is not None:
            gender_value = 1 if str(data.gender).lower() in {"male", "m", "男", "1"} else 0
            yun = eight_char.getYun(gender_value)
        if yun is not None:
            chart["luck_cycle"] = {
                "available": True,
                "start_year": call_value(yun, "getStartYear", None),
                "start_month": call_value(yun, "getStartMonth", None),
                "start_day": call_value(yun, "getStartDay", None),
                "start_solar": str(call_value(yun, "getStartSolar", "")),
            }
    except Exception as exc:
        chart["luck_cycle"] = {"available": False, "error": str(exc)}

    return chart


def load_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.input:
        return json.loads(args.input)
    if args.file:
        with open(args.file, "r", encoding="utf-8") as handle:
            return json.load(handle)

    cli_payload = {
        "birth_date": args.birth_date,
        "birth_time": args.birth_time,
        "calendar": args.calendar,
        "timezone": args.timezone,
        "gender": args.gender,
        "birthplace": args.birthplace,
        "longitude": args.longitude,
        "time_precision": args.time_precision,
        "focus": args.focus,
    }
    has_cli_birth_input = args.birth_date is not None or args.birth_time is not None
    if has_cli_birth_input:
        return {key: value for key, value in cli_payload.items() if value is not None}

    stdin_has_data = not sys.stdin.isatty() and bool(select.select([sys.stdin], [], [], 0)[0])
    if stdin_has_data:
        stdin_payload = sys.stdin.read().strip()
        if stdin_payload:
            return json.loads(stdin_payload)

    return {key: value for key, value in cli_payload.items() if value is not None}


def main() -> int:
    parser = argparse.ArgumentParser(description="Calculate an X-Oracle core chart.")
    parser.add_argument("--input", help="JSON payload string.")
    parser.add_argument("--file", help="Path to a JSON payload file.")
    parser.add_argument("--birth-date", help="Birth date in YYYY-MM-DD.")
    parser.add_argument("--birth-time", help="Birth time in HH:MM.")
    parser.add_argument("--calendar", default="gregorian", help="Calendar type. Default: gregorian.")
    parser.add_argument("--timezone", default="Asia/Shanghai", help="IANA timezone. Default: Asia/Shanghai.")
    parser.add_argument("--gender", help="Gender for luck-cycle direction.")
    parser.add_argument("--birthplace", help="Birthplace label.")
    parser.add_argument("--longitude", type=float, help="Birth longitude, east positive.")
    parser.add_argument("--time-precision", default="minute", help="minute, exact, approximate, branch, or unknown.")
    parser.add_argument("--focus", help="Optional focus area.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON.")
    args = parser.parse_args()

    try:
        data = parse_input(load_payload(args))
        chart = build_chart(data)
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1

    print(json.dumps(chart, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
