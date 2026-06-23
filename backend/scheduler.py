from __future__ import annotations

from datetime import datetime, timedelta


WEEKDAY_INDEX = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def _parse_time(value: str) -> tuple[int, int]:
    try:
        hours, minutes = value.split(":", 1)
        return int(hours), int(minutes)
    except (AttributeError, ValueError):
        return 9, 0


def compute_next_run(subscription: dict, now: datetime | None = None) -> datetime:
    now = now or datetime.now()
    hours, minutes = _parse_time(subscription.get("time", "09:00"))

    if subscription.get("frequency") == "hourly":
        interval = int(subscription.get("intervalHours") or 6)
        next_run = now + timedelta(hours=interval)
        return next_run.replace(minute=minutes, second=0, microsecond=0)

    next_run = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)

    if subscription.get("frequency") == "daily":
        if next_run <= now:
            next_run += timedelta(days=1)
        return next_run

    if subscription.get("frequency") == "weekly":
        target = WEEKDAY_INDEX.get(subscription.get("weekday"), 0)
        delta_days = (target - next_run.weekday()) % 7
        next_run += timedelta(days=delta_days)
        if next_run <= now:
            next_run += timedelta(days=7)
        return next_run

    return next_run


def build_digest_job_payload(subscription: dict) -> dict:
    return {
        "subscriptionId": subscription["id"],
        "email": subscription["email"],
        "sections": subscription["sections"],
        "city": subscription.get("city", ""),
        "nextRunAt": subscription["nextRunAt"],
        "template": "culture-digest-v1",
    }


def enqueue_digest(subscription: dict) -> dict:
    # Production connection point:
    # send build_digest_job_payload(subscription) to Celery/RQ/SQS,
    # then use an SMTP provider such as Mailgun, SendGrid, UniSender or direct SMTP.
    return build_digest_job_payload(subscription)
