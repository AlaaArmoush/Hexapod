from typing import Any

from .base import ToolResult
from .storage import data_path, read_json_object, write_json


MEMORY_FILE = "memory.json"


def _memory_path():
    return data_path(MEMORY_FILE)


def _invalid_key(action: str) -> ToolResult:
    return ToolResult(
        ok=False,
        action=action,
        spoken_text="I need a memory key for that.",
        display_face="memory",
        error="invalid_key",
    )


def remember_fact(key: str, value: Any) -> ToolResult:
    key = str(key).strip()
    if not key:
        return _invalid_key("remember_fact")

    memory = read_json_object(_memory_path())
    memory[key] = value
    write_json(_memory_path(), memory)

    return ToolResult(
        ok=True,
        action="remember_fact",
        spoken_text="I will remember {}.".format(key),
        data={"key": key, "value": value},
        display_face="memory",
    )


def recall_memory(key: str) -> ToolResult:
    key = str(key).strip()
    if not key:
        return _invalid_key("recall_memory")

    memory = read_json_object(_memory_path())
    if key not in memory:
        return ToolResult(
            ok=False,
            action="recall_memory",
            spoken_text="I do not have a memory for {}.".format(key),
            data={"key": key},
            display_face="memory",
            error="key_not_found",
        )

    return ToolResult(
        ok=True,
        action="recall_memory",
        spoken_text="{} is {}.".format(key, memory[key]),
        data={"key": key, "value": memory[key]},
        display_face="memory",
    )


def forget_memory(key: str) -> ToolResult:
    key = str(key).strip()
    if not key:
        return _invalid_key("forget_memory")

    memory = read_json_object(_memory_path())
    if key not in memory:
        return ToolResult(
            ok=False,
            action="forget_memory",
            spoken_text="I do not have a memory for {}.".format(key),
            data={"key": key},
            display_face="memory",
            error="key_not_found",
        )

    value = memory.pop(key)
    write_json(_memory_path(), memory)

    return ToolResult(
        ok=True,
        action="forget_memory",
        spoken_text="I forgot {}.".format(key),
        data={"key": key, "value": value},
        display_face="memory",
    )
