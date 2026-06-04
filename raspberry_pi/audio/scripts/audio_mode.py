#!/usr/bin/env python3
"""Switch Hexapod audio hardware between listening and speaker modes."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from typing import Iterable


MIC_POWER_GPIO = 17
AMP_SD_GPIO = 27


def pinctrl_prefix() -> list[str]:
    if os.geteuid() == 0:
        return ["pinctrl"]
    return ["sudo", "pinctrl"]


def run_pinctrl(args: Iterable[str]) -> None:
    cmd = [*pinctrl_prefix(), *args]
    print("+ " + " ".join(cmd))
    subprocess.run(cmd, check=True)


def set_gpio(gpio: int, level: str) -> None:
    run_pinctrl(["set", str(gpio), "op", level])


def get_gpio(gpio: int) -> None:
    run_pinctrl(["get", str(gpio)])


def listen() -> None:
    set_gpio(AMP_SD_GPIO, "dl")
    set_gpio(MIC_POWER_GPIO, "dl")
    print("Audio mode: listen (amp OFF, mics ON)")


def speak() -> None:
    set_gpio(MIC_POWER_GPIO, "dh")
    set_gpio(AMP_SD_GPIO, "dh")
    print("Audio mode: speak (mics OFF, amp ON)")


def off() -> None:
    set_gpio(AMP_SD_GPIO, "dl")
    set_gpio(MIC_POWER_GPIO, "dh")
    print("Audio mode: off (amp OFF, mics OFF)")


def status() -> None:
    get_gpio(MIC_POWER_GPIO)
    get_gpio(AMP_SD_GPIO)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Wrap the GPIO17 mic-power and GPIO27 amp-SD pinctrl commands."
    )
    parser.add_argument(
        "mode",
        choices=("listen", "speak", "off", "status"),
        help=(
            "listen: amp off, mics on; speak: mics off, amp on; "
            "off: both inactive; status: print GPIO17/GPIO27 state"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        if args.mode == "listen":
            listen()
        elif args.mode == "speak":
            speak()
        elif args.mode == "off":
            off()
        elif args.mode == "status":
            status()
        else:
            raise AssertionError(f"unhandled mode: {args.mode}")
    except FileNotFoundError as exc:
        print(f"ERROR: command not found: {exc.filename}", file=sys.stderr)
        return 127
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: pinctrl failed with exit code {exc.returncode}", file=sys.stderr)
        return exc.returncode

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
