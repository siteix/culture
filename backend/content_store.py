from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from parser import parse_all_sources
from sources import SOURCES


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CONTENT_FILE = DATA_DIR / "content.json"
UPDATE_INTERVAL_SECONDS = 24 * 60 * 60
_refresh_lock = threading.Lock()


def empty_payload() -> dict:
    return {
        "updatedAt": None,
        "items": [],
        "sources": SOURCES,
        "errors": [],
    }


def ensure_content_file() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not CONTENT_FILE.exists():
        write_content(empty_payload())


def read_content() -> dict:
    ensure_content_file()
    try:
        data = json.loads(CONTENT_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return empty_payload()
    data.setdefault("items", [])
    data.setdefault("sources", SOURCES)
    data.setdefault("errors", [])
    return data


def write_content(payload: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CONTENT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def is_stale(payload: dict) -> bool:
    updated_at = payload.get("updatedAt")
    if not updated_at:
        return True
    try:
        updated = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
    except ValueError:
        return True
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - updated > timedelta(seconds=UPDATE_INTERVAL_SECONDS)


def refresh_content(force: bool = False) -> dict:
    with _refresh_lock:
        current = read_content()
        if not force and not is_stale(current):
            return current
        payload = parse_all_sources()
        if payload["items"]:
            write_content(payload)
            return payload
        if current["items"]:
            current["errors"].append({"source": "parser", "error": "Парсер не вернул новых материалов, оставлены прежние данные."})
            return current
        write_content(payload)
        return payload


def start_daily_refresh_thread() -> None:
    def loop():
        while True:
            try:
                refresh_content(force=False)
            except Exception as error:
                print(f"[parser] daily refresh failed: {error}")
            time.sleep(60 * 30)

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
