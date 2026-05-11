from datetime import datetime, timedelta
from typing import Any, Dict, List

from .base import ToolResult
from .storage import data_path, read_json, write_json


TIMERS_FILE = "timers.json"
REMINDERS_FILE = "reminders.json"


def _read_list(filename: str) -> List[Dict[str, Any]]:
    value = read_json(data_path(filename), [])
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _format_duration(seconds: int) -> str:
    if seconds % 3600 == 0 and seconds >= 3600:
        count = seconds // 3600
        unit = "hour" if count == 1 else "hours"
    elif seconds % 60 == 0 and seconds >= 60:
        count = seconds // 60
        unit = "minute" if count == 1 else "minutes"
    else:
        count = seconds
        unit = "second" if count == 1 else "seconds"
    return "{} {}".format(count, unit)


def _parse_reminder_datetime(datetime_str: str) -> datetime:
    value = datetime_str.strip()
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        pass

    for pattern in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M"):
        try:
            return datetime.strptime(value, pattern)
        except ValueError:
            continue

    raise ValueError("invalid datetime")


def set_timer(label: str, duration_seconds: int) -> ToolResult:
    label = str(label).strip()
    try:
        duration = int(duration_seconds)
    except (TypeError, ValueError):
        duration = 0

    if not label:
        return ToolResult(
            ok=False,
            action="set_timer",
            spoken_text="I need a timer label.",
            display_face="timer",
            error="invalid_label",
        )

    if duration <= 0:
        return ToolResult(
            ok=False,
            action="set_timer",
            spoken_text="Timer duration must be greater than zero.",
            data={"label": label, "duration_seconds": duration_seconds},
            display_face="timer",
            error="invalid_duration",
        )

    created_at = datetime.now().astimezone()
    fires_at = created_at + timedelta(seconds=duration)
    entry = {
        "label": label,
        "duration_s": duration,
        "created_at": created_at.isoformat(timespec="seconds"),
        "fires_at": fires_at.isoformat(timespec="seconds"),
    }

    timers = _read_list(TIMERS_FILE)
    timers.append(entry)
    write_json(data_path(TIMERS_FILE), timers)

    return ToolResult(
        ok=True,
        action="set_timer",
        spoken_text="Timer set for {}.".format(_format_duration(duration)),
        data=entry,
        display_face="timer",
    )


def set_reminder(label: str, datetime_str: str) -> ToolResult:
    label = str(label).strip()
    if not label:
        return ToolResult(
            ok=False,
            action="set_reminder",
            spoken_text="I need a reminder label.",
            display_face="reminder",
            error="invalid_label",
        )

    try:
        remind_at = _parse_reminder_datetime(str(datetime_str))
    except ValueError:
        return ToolResult(
            ok=False,
            action="set_reminder",
            spoken_text="I could not understand that reminder time.",
            data={"label": label, "datetime_str": datetime_str},
            display_face="reminder",
            error="invalid_datetime",
        )

    entry = {
        "label": label,
        "remind_at": remind_at.isoformat(timespec="seconds"),
    }

    reminders = _read_list(REMINDERS_FILE)
    reminders.append(entry)
    write_json(data_path(REMINDERS_FILE), reminders)

    return ToolResult(
        ok=True,
        action="set_reminder",
        spoken_text="Reminder set for {}.".format(label),
        data=entry,
        display_face="reminder",
    )
