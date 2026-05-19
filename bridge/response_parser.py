import json
from typing import Any


ParsedResponse = dict[str, str | dict[str, Any] | bool | None]


def parse_line(raw_bytes: bytes | str) -> ParsedResponse | None:
    if isinstance(raw_bytes, bytes):
        text = raw_bytes.decode("utf-8", errors="replace").strip()
    else:
        text = raw_bytes.strip()

    if text == "":
        return None

    result: ParsedResponse = {
        "raw": text,
        "json": None,
        "ok": None,
        "event": None,
        "error": None,
        "cmd": None,
    }

    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return result

    if not isinstance(obj, dict):
        return result

    result["json"] = obj
    result["ok"] = obj.get("ok")
    result["event"] = obj.get("event")
    result["error"] = obj.get("error")
    result["cmd"] = obj.get("cmd")
    return result
