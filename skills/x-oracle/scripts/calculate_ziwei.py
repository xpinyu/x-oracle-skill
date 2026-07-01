#!/usr/bin/env python3
"""Optionally calculate a Zi Wei chart for X-Oracle.

Preferred dependency:
    pip install purplestar

Fallback dependency:
    pip install iztro-py
"""

from __future__ import annotations

import argparse
import json
import select
import sys
from datetime import datetime
from typing import Any


def load_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.input:
        return json.loads(args.input)
    if args.file:
        with open(args.file, "r", encoding="utf-8") as handle:
            return json.load(handle)

    payload = {
        "birth_date": args.birth_date,
        "birth_time": args.birth_time,
        "gender": args.gender,
        "timezone": args.timezone,
        "birthplace": args.birthplace,
        "longitude": args.longitude,
        "latitude": args.latitude,
        "name": args.name,
    }
    has_cli_birth_input = args.birth_date is not None or args.birth_time is not None
    if has_cli_birth_input:
        return {key: value for key, value in payload.items() if value is not None}

    stdin_has_data = not sys.stdin.isatty() and bool(select.select([sys.stdin], [], [], 0)[0])
    if stdin_has_data:
        stdin_payload = sys.stdin.read().strip()
        if stdin_payload:
            return json.loads(stdin_payload)

    return {key: value for key, value in payload.items() if value is not None}


def normalize_gender(value: Any) -> str:
    text = str(value).lower()
    if text in {"male", "m", "man", "男", "1"}:
        return "male"
    if text in {"female", "f", "woman", "女", "0"}:
        return "female"
    raise ValueError("gender is required for Zi Wei and must be male/female.")


def time_to_iztro_index(value: str) -> int:
    hour = datetime.strptime(value[:5], "%H:%M").hour
    if hour == 23:
        return 0
    return (hour + 1) // 2


def calculate_with_purplestar(payload: dict[str, Any]) -> dict[str, Any]:
    from purplestar.core.chart import generate_chart
    from purplestar.output.json_schema import to_json_schema
    from purplestar.output.plaintext import to_plaintext

    chart = generate_chart(
        gender=normalize_gender(payload.get("gender")),
        solar_date=payload["birth_date"],
        time=payload.get("birth_time"),
        timezone=payload.get("timezone", "Asia/Shanghai"),
        place=payload.get("birthplace"),
        name=payload.get("name"),
        longitude=payload.get("longitude"),
        latitude=payload.get("latitude"),
    )

    return {
        "engine": "purplestar",
        "chart": json.loads(to_json_schema(chart)),
        "plain_text": to_plaintext(chart),
    }


def calculate_with_iztro(payload: dict[str, Any]) -> dict[str, Any]:
    from iztro_py import astro

    gender = "男" if normalize_gender(payload.get("gender")) == "male" else "女"
    time_index = time_to_iztro_index(payload["birth_time"])
    chart = astro.by_solar(payload["birth_date"], time_index, gender)

    if hasattr(chart, "model_dump"):
        chart_payload = chart.model_dump()
    elif hasattr(chart, "dict"):
        chart_payload = chart.dict()
    else:
        chart_payload = str(chart)

    return {
        "engine": "iztro-py",
        "time_index": time_index,
        "chart": chart_payload,
    }


def calculate(payload: dict[str, Any]) -> dict[str, Any]:
    if "birth_date" not in payload or "birth_time" not in payload:
        raise ValueError("birth_date and birth_time are required.")
    if "gender" not in payload:
        raise ValueError("gender is required for Zi Wei.")

    errors = []
    for engine in (calculate_with_purplestar, calculate_with_iztro):
        try:
            return engine(payload)
        except ImportError as exc:
            errors.append(str(exc))
        except Exception as exc:
            errors.append(f"{engine.__name__}: {exc}")

    raise RuntimeError(
        "No Zi Wei engine succeeded. Install `purplestar` or `iztro-py`. "
        + " | ".join(errors)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Calculate an optional Zi Wei chart for X-Oracle.")
    parser.add_argument("--input", help="JSON payload string.")
    parser.add_argument("--file", help="Path to a JSON payload file.")
    parser.add_argument("--birth-date", help="Birth date in YYYY-MM-DD.")
    parser.add_argument("--birth-time", help="Birth time in HH:MM.")
    parser.add_argument("--gender", help="male/female.")
    parser.add_argument("--timezone", default="Asia/Shanghai", help="IANA timezone.")
    parser.add_argument("--birthplace", help="Birthplace label.")
    parser.add_argument("--longitude", type=float, help="Birth longitude, east positive.")
    parser.add_argument("--latitude", type=float, help="Birth latitude.")
    parser.add_argument("--name", help="Optional chart name.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON.")
    args = parser.parse_args()

    try:
        result = calculate(load_payload(args))
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
