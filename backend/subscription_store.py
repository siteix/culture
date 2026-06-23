from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path

from scheduler import compute_next_run


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DATA_FILE = DATA_DIR / "subscriptions.json"

ALLOWED_FREQUENCIES = {"daily", "weekly", "hourly"}
ALLOWED_SECTIONS = {"world", "events", "calls"}
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class ValidationError(Exception):
    pass


def ensure_store() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        DATA_FILE.write_text("[]\n", encoding="utf-8")


def read_subscriptions() -> list[dict]:
    ensure_store()
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def write_subscriptions(items: list[dict]) -> None:
    ensure_store()
    DATA_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate(input_data: dict) -> dict:
    errors: list[str] = []
    email = str(input_data.get("email", "")).strip().lower()
    frequency = str(input_data.get("frequency", "daily"))
    time_value = str(input_data.get("time", "09:00"))
    sections = input_data.get("sections", [])
    interval_hours = int(input_data.get("intervalHours") or 0)

    if not EMAIL_RE.match(email):
        errors.append("Укажите корректный email")

    if frequency not in ALLOWED_FREQUENCIES:
        errors.append("Выберите корректную периодичность")

    if not TIME_RE.match(time_value):
        errors.append("Укажите время в формате HH:MM")

    if frequency == "hourly" and interval_hours not in {3, 6, 12}:
        errors.append("Интервал должен быть 3, 6 или 12 часов")

    clean_sections = [section for section in sections if section in ALLOWED_SECTIONS]
    if not clean_sections:
        errors.append("Выберите хотя бы один раздел сводки")

    if errors:
        raise ValidationError(". ".join(errors))

    return {
        "email": email,
        "frequency": frequency,
        "time": time_value,
        "weekday": str(input_data.get("weekday", "monday")),
        "intervalHours": interval_hours,
        "city": str(input_data.get("city", "")),
        "sections": clean_sections,
    }


def create_subscription(input_data: dict) -> dict:
    payload = validate(input_data)
    now = datetime.now()
    subscription = {
        "id": str(uuid.uuid4()),
        "status": "active",
        **payload,
        "createdAt": now.isoformat(timespec="seconds"),
    }
    subscription["nextRunAt"] = compute_next_run(subscription, now).isoformat(timespec="seconds")

    items = read_subscriptions()
    items.append(subscription)
    write_subscriptions(items)
    return subscription
