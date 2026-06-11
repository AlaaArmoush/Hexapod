from datetime import datetime

from .base import ToolResult


def get_time() -> ToolResult:
    now = datetime.now().astimezone()
    spoken_hour = now.strftime("%I").lstrip("0") or "0"
    spoken_time = "{}:{}".format(spoken_hour, now.strftime("%M %p"))
    timezone = now.tzname()

    return ToolResult(
        ok=True,
        action="get_time",
        spoken_text="It is {}.".format(spoken_time),
        data={
            "time": now.strftime("%H:%M:%S"),
            "hour": now.hour,
            "minute": now.minute,
            "second": now.second,
            "timezone": timezone,
        },
        display_face="clock",
        display_text=now.strftime("%H:%M"),
    )


def get_date() -> ToolResult:
    now = datetime.now().astimezone()
    spoken_text = "Today is {} {}, {}.".format(now.strftime("%B"), now.day, now.year)

    return ToolResult(
        ok=True,
        action="get_date",
        spoken_text=spoken_text,
        data={
            "date": now.date().isoformat(),
            "weekday": now.strftime("%A"),
            "day": now.day,
            "month": now.month,
            "year": now.year,
        },
        display_face="calendar",
        display_text=now.strftime("%a %b %d"),
    )
