#!/usr/bin/env python3
import json
import sys
from typing import Any

from tools import call_tool, get_tool, list_all


def _print_available() -> None:
    print("Available tools:")
    for tool in list_all():
        status = "implemented" if tool.implemented else "not implemented"
        args = " ".join("<{}>".format(arg) for arg in tool.required_args)
        suffix = " {}".format(args) if args else ""
        print("  {}{}  ({})".format(tool.name, suffix, status))


def _format_value(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if value is None:
        return "null"
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2, sort_keys=True)
    return str(value)


def _print_result(result) -> None:
    payload = result.to_dict()
    print("action:        {}".format(payload["action"]))
    print("ok:            {}".format(str(payload["ok"]).lower()))
    if payload.get("error"):
        print("error:         {}".format(payload["error"]))
    print("spoken_text:   {}".format(payload["spoken_text"]))
    print("display_face:  {}".format(payload["display_face"]))

    data = payload.get("data") or {}
    if data:
        print("data:")
        for key, value in data.items():
            formatted = _format_value(value)
            if "\n" in formatted:
                print("  {}:".format(key))
                for line in formatted.splitlines():
                    print("    {}".format(line))
            else:
                print("  {:<12} {}".format(key + ":", formatted))


def main(argv) -> int:
    if len(argv) < 2:
        print("Usage: python3 test_tools_cli.py <tool_name> [args...]")
        _print_available()
        return 1

    tool_name = argv[1]
    tool = get_tool(tool_name)
    if tool is None:
        print("Unknown tool: {}".format(tool_name))
        _print_available()
        return 1

    provided_args = argv[2:]
    if len(provided_args) < len(tool.required_args):
        print("Missing arguments for {}.".format(tool.name))
        print("Usage: python3 test_tools_cli.py {} {}".format(
            tool.name,
            " ".join("<{}>".format(arg) for arg in tool.required_args),
        ).rstrip())
        return 1

    if len(provided_args) > len(tool.required_args) + len(tool.optional_args):
        print("Too many arguments for {}.".format(tool.name))
        return 1

    kwargs = {}
    arg_names = tool.required_args + tool.optional_args
    for arg_name, value in zip(arg_names, provided_args):
        kwargs[arg_name] = value

    result = call_tool(tool.name, **kwargs)
    _print_result(result)
    return 0 if result.ok else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
