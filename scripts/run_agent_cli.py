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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local Hexapod Gemma agent.")
    parser.add_argument("--once", help="Ask one question and exit.")
    parser.add_argument("--mock-llm", action="store_true", help="Use a hardcoded model response.")
    parser.add_argument("--verbose", action="store_true", help="Print raw model JSON.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080", help="llama-server base URL.")
    parser.add_argument("--timeout", type=int, default=30, help="llama-server request timeout.")
    parser.add_argument("--temperature", type=float, default=0.2, help="Model sampling temperature.")
    parser.add_argument("--max-tokens", type=int, default=160, help="Maximum tokens for model JSON output.")
    parser.add_argument(
        "--full-prompt",
        action="store_true",
        help="Use the longer six-example prompt instead of the compact runtime prompt.",
    )
    parser.add_argument("--no-tools", action="store_true", help="Validate tool requests without executing tools.")
    parser.add_argument(
        "--summarize-tool-results",
        action="store_true",
        help="Ask the model to rewrite successful tool results as one short sentence.",
    )
    return parser


def _print_result(result: dict) -> None:
    print("Agent: {}".format(result["speak"]))

    if not result["ok"]:
        if result.get("error"):
            print("Error: {}".format(result["error"]))
        return

    for tool_result in result.get("tool_results", []):
        prefix = "Tool" if tool_result.get("ok") else "Tool error"
        name = tool_result.get("name", "unknown")
        spoken = tool_result.get("spoken_text") or tool_result.get("error") or ""
        print("{} [{}]: {}".format(prefix, name, spoken))


def _build_loop(args: argparse.Namespace) -> AgentLoop:
    client = None if args.mock_llm else LlamaClient(base_url=args.base_url, timeout=args.timeout)
    return AgentLoop(
        llama_client=client,
        mock_llm=args.mock_llm,
        verbose=args.verbose,
        enable_tools=not args.no_tools,
        summarize_tool_results=args.summarize_tool_results,
        system_prompt=SYSTEM_PROMPT if args.full_prompt else None,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    loop = _build_loop(args)

    if args.once is not None:
        result = loop.run_once(args.once)
        _print_result(result)
        return 0 if result["ok"] else 2

    print("Hexapod Agent - type your message, or Ctrl+C to quit.")
    try:
        while True:
            user_input = input("\nYou: ").strip()
            if not user_input:
                continue
            print("[thinking...]")
            result = loop.run_once(user_input)
            _print_result(result)
    except (KeyboardInterrupt, EOFError):
        print("\nGoodbye.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
