"""
VoicePipeline — capture → STT → agent → TTS state machine.

States: IDLE → LISTENING → THINKING → SPEAKING → LISTENING

Usage:
    python -m raspberry_pi.audio.pipeline                              # llama-server on localhost:8080
    python -m raspberry_pi.audio.pipeline --enable-robot --port /dev/ttyUSB0
    python -m raspberry_pi.audio.pipeline --base-url http://HOST:8080
"""
from __future__ import annotations

import argparse
import queue
import sys
import time
from enum import Enum, auto
from pathlib import Path
from typing import Callable


class _State(Enum):
    IDLE = auto()
    LISTENING = auto()
    THINKING = auto()
    SPEAKING = auto()


class VoicePipeline:
    def __init__(
        self,
        agent_fn: Callable[[str], str] | None = None,
        canned=None,
        tts=None,
    ) -> None:
        # agent_fn: None = echo mode (speaks the transcript back)
        self._agent_fn = agent_fn
        self._canned = canned   # CannedLines — lazy-created in start() if None
        self._tts = tts         # PiperTTS — lazy-created in start() if None
        self._state = _State.IDLE
        self._queue: queue.Queue[str] = queue.Queue()
        self._running = False
        self._cap = None
        self._stt = None

    def _on_transcript(self, text: str) -> None:
        if self._state == _State.LISTENING:
            self._state = _State.THINKING
            self._queue.put_nowait(text)

    def _process_transcript(self, text: str) -> None:
        """THINKING → SPEAKING → LISTENING for one transcript."""
        print(f"[pipeline] THINKING: {text!r}", file=sys.stderr)
        self._canned.play("okay")
        time.sleep(0.4)
        response = self._agent_fn(text) if self._agent_fn else text
        self._state = _State.SPEAKING
        print(f"[pipeline] SPEAKING: {response!r}", file=sys.stderr)
        self._tts.say(response)
        self._state = _State.LISTENING
        print("[pipeline] back to LISTENING", file=sys.stderr)

    def start(self) -> None:
        from .capture import AudioCapture
        from .stt import MoonshineSTT
        from .canned import CannedLines
        from .tts import PiperTTS
        from .playback import AudioPlayer

        if self._canned is None:
            player = AudioPlayer()
            self._canned = CannedLines(player=player)
            self._canned.load()
        if self._tts is None:
            self._tts = PiperTTS()

        self._stt = MoonshineSTT(on_final=self._on_transcript)
        self._cap = AudioCapture(on_chunk=self._stt.feed)

        self._stt.start()
        self._cap.start()
        self._running = True
        self._state = _State.LISTENING
        print("[pipeline] LISTENING — speak a command, Ctrl-C to quit", file=sys.stderr)

        try:
            while self._running:
                try:
                    text = self._queue.get(timeout=0.2)
                except queue.Empty:
                    continue
                self._process_transcript(text)
        except KeyboardInterrupt:
            print("\n[pipeline] stopping", file=sys.stderr)
        finally:
            self.stop()

    def stop(self) -> None:
        self._running = False
        if self._stt is not None:
            self._stt.stop()
            self._stt = None
        if self._cap is not None:
            self._cap.stop()
            self._cap = None
        self._state = _State.IDLE


def _build_agent_fn(args: argparse.Namespace) -> Callable[[str], str]:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from agent.agent_loop import AgentLoop
    from agent.llama_client import LlamaClient
    from agent.robot_executor import RobotExecutor
    from agent.tool_executor import execute_tools
    from agent.prompts import SYSTEM_PROMPT

    robot_executor = RobotExecutor(
        port=args.port,
        baudrate=args.baudrate,
        dry_run=not args.enable_robot,
        require_confirmation=False,
    )

    def tool_executor(tool_requests, user_input=""):
        return execute_tools(tool_requests, robot_executor=robot_executor, enable_robot=True)

    client = LlamaClient(base_url=args.base_url, timeout=args.timeout)
    loop = AgentLoop(
        llama_client=client,
        tool_executor=tool_executor,
        system_prompt=SYSTEM_PROMPT,
    )
    return lambda text: loop.run_once(text)["speak"]


def main() -> None:
    parser = argparse.ArgumentParser(description="VoicePipeline — live voice command loop.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080", help="llama-server URL.")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--enable-robot", action="store_true", help="Send validated commands to hardware.")
    parser.add_argument("--port", help="Serial port, e.g. /dev/ttyUSB0.")
    parser.add_argument("--baudrate", type=int, default=115200)
    args = parser.parse_args()

    if args.enable_robot and not args.port:
        parser.error("--enable-robot requires --port")

    VoicePipeline(agent_fn=_build_agent_fn(args)).start()


if __name__ == "__main__":
    main()
