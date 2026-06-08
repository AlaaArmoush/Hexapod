#!/usr/bin/env python3
"""Terminal entry point for the local Hexapod agent."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent.agent_loop import AgentLoop
from agent.llama_client import LlamaClient
from agent.prompts import SYSTEM_PROMPT
from agent.robot_executor import RobotExecutor
from agent.tool_executor import execute_tools


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local Hexapod Gemma agent.")
    parser.add_argument("--once", help="Ask one question and exit.")
    parser.add_argument("--mock-llm", action="store_true", help="Use a hardcoded model response.")
    parser.add_argument("--verbose", action="store_true", help="Print raw model JSON.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080", help="llama-server base URL.")
    parser.add_argument("--timeout", type=int, default=30, help="llama-server request timeout.")
    parser.add_argument("--temperature", type=float, default=0, help="Model sampling temperature.")
    parser.add_argument("--max-tokens", type=int, default=60, help="Maximum tokens for model JSON output.")
    parser.add_argument(
        "--json-response-format",
        action="store_true",
        help="Ask llama-server to enforce JSON mode. Off by default because it can be slower or flaky on some local models.",
    )
    parser.add_argument(
        "--dump-prompt",
        action="store_true",
        help="Print the active system prompt and exit.",
    )
    parser.add_argument(
        "--full-prompt",
        action="store_true",
        help="Use the full unified prompt explicitly. The default runtime prompt is the same contract.",
    )
    parser.add_argument("--no-tools", action="store_true", help="Validate tool requests without executing tools.")
    parser.add_argument(
        "--no-robot",
        action="store_true",
        help="Disable robot_command handling even when tools are enabled.",
    )
    parser.add_argument(
        "--robot-dry-run",
        action="store_true",
        help="Validate robot commands and print the exact serial JSON without opening serial.",
    )
    parser.add_argument(
        "--enable-robot",
        action="store_true",
        help="Allow validated robot commands to be sent to hardware.",
    )
    parser.add_argument("--port", help="Serial port for real robot mode, for example /dev/ttyUSB0.")
    parser.add_argument("--baudrate", type=int, default=115200, help="Robot serial baudrate.")
    parser.add_argument(
        "--yes",
        "--no-confirm",
        action="store_true",
        dest="yes",
        help="Skip movement confirmation in real robot mode.",
    )
    parser.add_argument(
        "--no-fast-robot",
        action="store_true",
        help="Disable deterministic shortcuts for simple robot movement commands.",
    )
    parser.add_argument(
        "--robot-sync",
        choices=["ping", "none"],
        default="ping",
        help="Serial startup sync mode. Use none only for diagnosing reset/sync latency.",
    )
    parser.add_argument(
        "--keep-robot-open",
        action="store_true",
        help="Keep the serial port open across turns. Interactive mode does this by default.",
    )
    parser.add_argument(
        "--summarize-tool-results",
        action="store_true",
        help="Ask the model to rewrite successful tool results as one short sentence.",
    )
    return parser


def _print_result(result: dict, verbose: bool = False) -> None:
    print("Agent: {}".format(result["speak"]))
    if verbose and result.get("timings"):
        print("Timing: {}".format(_format_timings(result["timings"])))

    if not result["ok"]:
        if result.get("error"):
            print("Error: {}".format(result["error"]))
        return

    for tool_result in result.get("tool_results", []):
        prefix = "Tool" if tool_result.get("ok") else "Tool error"
        name = tool_result.get("name", "unknown")
        spoken = tool_result.get("spoken_text") or tool_result.get("error") or ""
        print("{} [{}]: {}".format(prefix, name, spoken))
        if name == "robot_command":
            data = tool_result.get("data", {})
            serial_json = data.get("serial_json")
            if serial_json:
                mode = "DRY-RUN" if data.get("dry_run") else "SEND"
                print("Robot JSON [{}]: {}".format(mode, serial_json))
            if verbose and data.get("timings"):
                print("Robot timing: {}".format(_format_timings(data["timings"])))
        elif name == "camera_status":
            data = tool_result.get("data", {})
            if data:
                print(
                    "Camera: connected={} running={} device={} stereo={}".format(
                        data.get("connected"),
                        data.get("pipeline_running"),
                        data.get("device_id"),
                        data.get("stereo_available"),
                    )
                )
        elif name == "capture_image":
            data = tool_result.get("data", {})
            path = data.get("path")
            if path:
                print("Image path: {}".format(path))
                print(
                    "Image: {}x{} age_ms={}".format(
                        data.get("width"),
                        data.get("height"),
                        data.get("age_ms"),
                    )
                )


def _format_timings(timings: dict) -> str:
    parts = []
    for key in (
        "plan_source",
        "model_s",
        "parse_s",
        "validate_s",
        "tools_s",
        "summarize_s",
        "total_s",
        "robot_connect_s",
        "robot_connect_reused",
        "robot_sync_s",
        "robot_sync_skipped",
        "robot_send_s",
        "robot_ack_s",
    ):
        if key not in timings:
            continue
        value = timings[key]
        if isinstance(value, float):
            parts.append("{}={:.3f}s".format(key, value))
        else:
            parts.append("{}={}".format(key, value))
    return " ".join(parts)


def _build_loop(args: argparse.Namespace):
    client = None if args.mock_llm else LlamaClient(base_url=args.base_url, timeout=args.timeout)
    robot_executor = _build_robot_executor(args)

    def tool_executor(tool_requests, user_input: str = ""):
        return execute_tools(
            tool_requests,
            robot_executor=robot_executor,
            enable_robot=not args.no_robot,
        )

    return AgentLoop(
        llama_client=client,
        mock_llm=args.mock_llm,
        verbose=args.verbose,
        enable_tools=not args.no_tools,
        tool_executor=tool_executor,
        summarize_tool_results=args.summarize_tool_results,
        system_prompt=SYSTEM_PROMPT if args.full_prompt else None,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        json_response_format=args.json_response_format,
        fast_robot_shortcuts=not args.no_fast_robot,
    ), client, robot_executor


def _build_robot_executor(args: argparse.Namespace) -> RobotExecutor:
    if args.enable_robot and not args.port:
        raise SystemExit("--enable-robot requires --port, for example --port /dev/ttyUSB0")

    dry_run = not args.enable_robot or args.robot_dry_run
    return RobotExecutor(
        port=args.port,
        baudrate=args.baudrate,
        dry_run=dry_run,
        require_confirmation=not args.yes,
        confirm_callback=_confirm_robot_command,
        sync_robot=args.robot_sync != "none",
        keep_connected=bool(args.keep_robot_open or args.once is None),
    )


def _confirm_robot_command(command: dict) -> bool:
    answer = input("Send robot command {}? [y/N] ".format(command)).strip().lower()
    return answer in {"y", "yes"}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.dump_prompt:
        print(SYSTEM_PROMPT)
        return 0
    loop, client, robot_executor = _build_loop(args)

    try:
        if args.once is not None:
            result = loop.run_once(args.once)
            _print_result(result, verbose=args.verbose)
            return 0 if result["ok"] else 2

        # Interactive loop: warm up the KV cache once before the first user turn.
        if client is not None:
            if args.verbose:
                print("[warming up KV cache...]")
            system_prompt = SYSTEM_PROMPT if args.full_prompt else loop.system_prompt
            client.warmup(system_prompt)

        print("Hexapod Agent - type your message, or Ctrl+C to quit.")
        while True:
            user_input = input("\nYou: ").strip()
            if not user_input:
                continue
            print("[thinking...]")
            result = loop.run_once(user_input)
            _print_result(result, verbose=args.verbose)
    except (KeyboardInterrupt, EOFError):
        print("\nGoodbye.")
        return 0
    finally:
        robot_executor.close()


if __name__ == "__main__":
    raise SystemExit(main())
