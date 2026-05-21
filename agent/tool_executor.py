"""Execute deterministic tools requested by a validated agent plan."""

from __future__ import annotations

from typing import Any

from tools import ToolResult, call_tool, get_tool


FACE_HINTS = {
    "get_time": "clock",
    "get_date": "calendar",
    "search_web": "search",
    "remember_fact": "memory",
    "recall_memory": "memory",
    "forget_memory": "memory",
    "set_timer": "timer",
    "system_status": "system",
    "network_status": "wifi",
    "battery_status": "battery",
}

NO_ARG_TOOLS = {"get_time", "get_date", "system_status", "network_status", "battery_status"}
FUTURE_TOOLS = {
    "capture_image",
    "describe_scene",
    "detect_person",
    "detect_object",
    "mic_status",
    "voice_direction_estimate",
    "camera_status",
    "tell_joke",
    "local_file_lookup",
    "read_project_note",
    "explain_capability",
}


def execute_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate, execute, and normalize a list of tool requests."""

    results = []
    for request in tools:
        if not isinstance(request, dict):
            results.append(_error_result("unknown", "invalid_tool_request", "Tool request must be an object."))
            continue

        name = str(request.get("name", "")).strip()
        args = request.get("args", {})
        if not isinstance(args, dict):
            results.append(_error_result(name, "invalid_args", "Tool args must be an object."))
            continue

        error = _validate_tool_args(name, args)
        if error is not None:
            results.append(_error_result(name, error, _message_for_error(error), args))
            continue

        if name in FUTURE_TOOLS:
            results.append(_error_result(name, "not_implemented", "This capability is not yet available.", args))
            continue

        tool = get_tool(name)
        if tool is None:
            results.append(_error_result(name, "unknown_tool", "I do not know that tool yet.", args))
            continue

        try:
            result = call_tool(name, **_tool_call_args(name, args))
        except Exception as exc:  # Tool failures should not crash the agent loop.
            results.append(_error_result(name, "tool_exception", str(exc), args))
            continue

        results.append(_normalize_tool_result(name, result))

    return results


def _validate_tool_args(name: str, args: dict[str, Any]) -> str | None:
    if name in NO_ARG_TOOLS:
        if args:
            return "unexpected_args"
        return None

    if name == "search_web":
        query = args.get("query")
        if not isinstance(query, str) or not query.strip():
            return "missing_query"
        if len(query) > 200:
            return "query_too_long"
        return None

    if name == "remember_fact":
        key = args.get("key")
        value = args.get("value")
        if not isinstance(key, str) or not key.strip():
            return "missing_key"
        if not isinstance(value, str) or not value.strip():
            return "missing_value"
        if len(key) > 50:
            return "key_too_long"
        if len(value) > 500:
            return "value_too_long"
        return None

    if name in {"recall_memory", "forget_memory"}:
        key = args.get("key")
        if not isinstance(key, str) or not key.strip():
            return "missing_key"
        return None

    if name == "set_timer":
        duration = args.get("duration_seconds")
        if not isinstance(duration, int) or isinstance(duration, bool):
            return "invalid_duration"
        if duration < 1 or duration > 86400:
            return "invalid_duration"
        return None

    if name == "set_reminder":
        reminder_text = args.get("reminder_text")
        if not isinstance(reminder_text, str) or not reminder_text.strip():
            return "missing_reminder_text"
        if len(reminder_text) > 200:
            return "reminder_text_too_long"
        return None

    if name in FUTURE_TOOLS:
        return None

    if get_tool(name) is None:
        return "unknown_tool"

    return None


def _tool_call_args(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name == "set_timer":
        return {
            "label": str(args.get("label", "timer")),
            "duration_seconds": args["duration_seconds"],
        }
    if name == "set_reminder":
        return {
            "label": args["reminder_text"],
            "datetime_str": str(args.get("datetime_str", "")),
        }
    return args


def _normalize_tool_result(name: str, result: ToolResult) -> dict[str, Any]:
    return {
        "ok": result.ok,
        "name": name,
        "spoken_text": result.spoken_text,
        "data": dict(result.data),
        "display_face": result.display_face or FACE_HINTS.get(name, "thinking"),
        "error": result.error,
    }


def _error_result(
    name: str,
    error: str,
    spoken_text: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "name": name,
        "spoken_text": spoken_text,
        "data": dict(data or {}),
        "display_face": FACE_HINTS.get(name, "thinking"),
        "error": error,
    }


def _message_for_error(error: str) -> str:
    messages = {
        "unexpected_args": "That tool does not take arguments.",
        "missing_query": "I need a search query for that.",
        "query_too_long": "That search query is too long.",
        "missing_key": "I need a memory key for that.",
        "missing_value": "I need a memory value for that.",
        "key_too_long": "That memory key is too long.",
        "value_too_long": "That memory value is too long.",
        "invalid_duration": "Timer duration must be between 1 and 86400 seconds.",
        "missing_reminder_text": "I need reminder text for that.",
        "reminder_text_too_long": "That reminder text is too long.",
        "unknown_tool": "I do not know that tool yet.",
    }
    return messages.get(error, "I could not run that tool.")

