from __future__ import annotations

import os
import warnings
os.environ["ORT_LOGGING_LEVEL"] = "4"                 # FATAL only — suppress C++ warnings/errors
warnings.filterwarnings("ignore", category=UserWarning, module="onnxruntime")

import argparse
import queue
import sys
import time
from enum import Enum, auto
from pathlib import Path
from typing import Callable


class _State(Enum):
    IDLE = auto()
    WAKE_LISTENING = auto()
    LISTENING = auto()
    THINKING = auto()
    SPEAKING = auto()


class VoicePipeline:
    def __init__(
        self,
        agent_fn: Callable[[str], str] | None = None,
        face_fn: Callable[[str], None] | None = None,
        cmd_fn: Callable[[dict], None] | None = None,
        canned=None,
        tts=None,
        use_wake_word: bool = False,
        tracker=None,
    ) -> None:
        self._agent_fn = agent_fn
        self._face_fn = face_fn
        self._cmd_fn = cmd_fn
        self._canned = canned
        self._tts = tts
        self._use_wake_word = use_wake_word
        self._tracker = tracker
        self._state = _State.IDLE
        self._queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self._running = False
        self._cap = None
        self._stt = None
        self._detector = None
        self._spoke_at: float = 0.0

    _POST_SPEAK_COOLDOWN = 1.2
    # Info-tool faces worth keeping on screen briefly after speaking so the user can
    # read them, instead of immediately resetting to the idle/sleep face.
    _LINGER_FACES = {"clock", "calendar", "timer", "reminder", "memory", "battery", "system"}
    _LINGER_HOLD_S = 2.5

    def _is_fast_intent(self, text: str) -> bool:
        try:
            from agent.fast_robot_intent import build_fast_robot_plan
            return build_fast_robot_plan(text) is not None
        except ImportError:
            return False

    def _face(self, name: str) -> None:
        if self._face_fn is not None:
            try:
                self._face_fn(name)
            except Exception:
                pass

    def _on_wakeword(self, model_name: str, score: float, direction: str) -> None:
        if self._state == _State.WAKE_LISTENING:
            self._state = _State.LISTENING  # block re-entry before queue is drained
            self._queue.put_nowait(("wake", direction))

    def _on_transcript(self, text: str) -> None:
        if self._state == _State.LISTENING:
            if time.monotonic() - self._spoke_at < self._POST_SPEAK_COOLDOWN:
                return
            self._state = _State.THINKING
            if self._stt is not None:
                self._stt.pause()
            self._queue.put_nowait(("transcript", text))

    def _start_stt(self) -> None:
        from .audio.capture import AudioCapture
        self._cap = AudioCapture(on_chunk=self._stt.feed)
        self._cap.start()
        self._stt.resume()

    def _stop_stt(self) -> None:
        self._stt.pause()
        if self._cap is not None:
            self._cap.stop()
            self._cap = None

    def _start_detector(self) -> None:
        from .audio.scripts.audio_mode import listen as _audio_listen
        from raspberry_pi.wake_word.detector import WakeWordDetector, WAKEWORD_MODEL_PATH, WAKEWORD_THRESHOLD, AUDIO_DEVICE
        _audio_listen()
        self._detector = WakeWordDetector(
            model_path=WAKEWORD_MODEL_PATH,
            on_wakeword=self._on_wakeword,
            threshold=WAKEWORD_THRESHOLD,
            device=AUDIO_DEVICE,
        )
        self._detector.start()

    def _stop_detector(self) -> None:
        if self._detector is not None:
            self._detector.stop()
            self._detector = None

    # Camera pan position → body rotation needed to face where the camera is looking.
    # Pan center is straight ahead; left positions sit to the body's left, right to its
    # right. Rotation is quantised to 30° cycles, so we round to clean multiples — the
    # ApproachController fine-tunes any residual offset once it sees the person head-on.
    _PAN_TO_BODY_ROTATE = {
        "left": ("left", 60),
        "front_left": ("left", 30),
        "center": (None, 0),
        "front_right": ("right", 30),
        "right": ("right", 60),
    }
    # Pan positions scanned (order) when the wake-direction guess doesn't find anyone.
    _SCAN_PAN_ORDER = ("center", "front_left", "front_right", "left", "right")

    def _handle_wakeword(self, direction: str) -> None:
        print(f"[pipeline] wake word (direction={direction!r})", file=sys.stderr)
        self._stop_detector()
        self._dispatch_direction(direction)

        pan_pos = None
        if self._tracker is not None:
            # Fast path: the camera already panned to the voice-direction guess — if the
            # person is right there, we know which pan position they're at.
            if self._acquire_person(timeout_s=2.0) is not None:
                pan_pos = self._guess_to_pan_pos(direction)
            else:
                # The mic direction is only a coarse guess (and often wrong), so scan the
                # camera across pan positions to actually find the person.
                pan_pos = self._scan_for_person()

        if pan_pos is not None:
            self._greet_and_approach(pan_pos)
            return

        self._start_stt()
        self._face("listening")
        print("[pipeline] LISTENING — speak a command", file=sys.stderr)

    def _greet_and_approach(self, pan_pos: str) -> None:
        import random
        from bridge.bridge_errors import BridgeError
        from bridge.robot_commands import build_camera_center
        from camera.approach import ApproachController, ApproachResult

        # Centre the camera so the approach runs with a straight-ahead view.
        # Body alignment is skipped here — ApproachController corrects lateral offset
        # via rotation during approach, which looks more natural than a pre-turn.
        if self._tracker is not None:
            self._tracker.reset()
        try:
            self._cmd_fn(build_camera_center())
        except Exception:
            pass
        time.sleep(0.6)  # camera recentre + tracker re-lock

        if self._acquire_person(timeout_s=2.0) is None:
            print("[pipeline] lost person after turning — back to WAKE_LISTENING", file=sys.stderr)
            self._start_detector()
            self._state = _State.WAKE_LISTENING
            self._face("idle")
            return

        print("[pipeline] person detected — approaching", file=sys.stderr)
        self._canned.play("approaching")
        self._face("walking")
        try:
            result = ApproachController(self._tracker, self._cmd_fn).run()
        except BridgeError as exc:
            # Serial dropped mid-approach (e.g. servo brownout knocked the ESP32
            # off USB). Abort the approach and recover instead of crashing the
            # whole pipeline — wake word/camera/STT keep working, and the robot
            # path comes back on its own once the port re-enumerates.
            print(f"[pipeline] approach aborted — robot serial lost: {exc}", file=sys.stderr)
            self._start_detector()
            self._state = _State.WAKE_LISTENING
            self._face("idle")
            return
        if result == ApproachResult.ARRIVED:
            self._canned.play(random.choice(["greet_1", "greet_2", "greet_3"]))
            self._face("listening")
            self._start_stt()
            print("[pipeline] ARRIVED — LISTENING", file=sys.stderr)
            return
        self._start_detector()
        self._state = _State.WAKE_LISTENING
        self._face("idle")
        print(f"[pipeline] approach {result.name} — back to WAKE_LISTENING", file=sys.stderr)

    @staticmethod
    def _guess_to_pan_pos(direction: str) -> str:
        """Which pan position _dispatch_direction left the camera at for this guess."""
        if direction == "left":
            return "left"
        if direction == "right":
            return "right"
        return "center"  # front / back (back already rotated the body 180°)

    def _align_body_to_pan(self, pan_pos: str) -> bool:
        """Rotate the body to face the pan position. Returns True if it issued a turn."""
        from bridge.robot_commands import build_rotate
        rot_dir, degrees = self._PAN_TO_BODY_ROTATE.get(pan_pos, (None, 0))
        if rot_dir is None or degrees == 0:
            return False
        print(f"[pipeline] turning body {rot_dir} {degrees}° to face person", file=sys.stderr)
        try:
            self._cmd_fn(build_rotate(dir=rot_dir, degrees=degrees))
            return True
        except Exception as exc:
            print(f"[pipeline] body turn failed (ignored): {exc}", file=sys.stderr)
            return False

    def _scan_for_person(self) -> str | None:
        """Pan the camera across positions and return the one with the best person
        detection, or None if nobody is found. Uses fresh per-frame detection (not the
        smoothed tracker target, which lingers for ~2s and would leak across positions).
        """
        from bridge.robot_commands import build_camera_center, build_camera_pan
        print("[pipeline] no one at the guessed direction — scanning", file=sys.stderr)
        best_pos = None
        best_conf = 0.0
        for pos in self._SCAN_PAN_ORDER:
            try:
                self._cmd_fn(build_camera_pan(pos=pos))
            except Exception:
                continue
            time.sleep(0.5)  # camera servo move + a fresh frame
            frame = self._tracker.provider.grab_frame()
            if frame is None:
                continue
            result = self._tracker.detector.detect(frame, target_label="person")
            if result is not None and result.detected:
                conf = max(d.confidence for d in result.detections)
                if conf > best_conf:
                    best_conf = conf
                    best_pos = pos
        if best_pos is None:
            try:
                self._cmd_fn(build_camera_center())
            except Exception:
                pass
        return best_pos

    def _acquire_person(self, timeout_s: float):
        """Poll the tracker briefly so it can lock on after the camera pans.

        The tracker runs at ~5 FPS, so a single check right after panning usually
        sees target=None. Poll for up to timeout_s and return the first target found.
        """
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            target = self._tracker.target
            if target is not None:
                return target
            time.sleep(0.1)
        return None

    def _dispatch_direction(self, direction: str) -> None:
        if self._cmd_fn is None:
            return
        from bridge.robot_commands import build_camera_pan, build_rotate
        try:
            if direction == "back":
                self._cmd_fn(build_rotate(dir="left", degrees=180))
                self._cmd_fn(build_camera_pan(pos="center"))
            else:
                pan_pos = direction if direction not in ("front", "center") else "center"
                self._cmd_fn(build_camera_pan(pos=pan_pos))
        except Exception as exc:
            print(f"[pipeline] direction command failed (ignored): {exc}", file=sys.stderr)

    def _process_transcript(self, text: str) -> None:
        """THINKING → SPEAKING → WAKE_LISTENING or LISTENING for one transcript."""
        print(f"[pipeline] THINKING: {text!r}", file=sys.stderr)

        if self._tracker is not None:
            from agent.search_intent import match_search_intent
            from camera.detection import resolve_coco_label
            from camera.search import ObjectSearcher
            raw_target = match_search_intent(text)
            if raw_target is not None:
                target_label = resolve_coco_label(raw_target)
                if target_label is not None:
                    self._face("scan")
                    self._tts.say(f"Searching for {raw_target}.")
                    searcher = ObjectSearcher(
                        self._tracker.provider,
                        self._tracker.detector,
                        self._cmd_fn,
                    )
                    try:
                        result = searcher.search(target_label)
                    except Exception as exc:
                        print(f"[pipeline] search failed: {exc}", file=sys.stderr)
                        self._tts.say("Search failed.")
                        self._face("sad")
                        self._spoke_at = time.monotonic()
                        self._finish_speaking()
                        return
                    if result.found:
                        self._tts.say(f"Found it! It's to my {result.position}.")
                        self._face("happy")
                    else:
                        self._tts.say(f"I couldn't find a {raw_target}.")
                        self._face("sad")
                    self._spoke_at = time.monotonic()
                    self._finish_speaking()
                    return

        if not self._is_fast_intent(text):
            self._face("thinking")
        response = self._agent_fn(text) if self._agent_fn else text
        self._state = _State.SPEAKING
        if response:
            print(f"[pipeline] SPEAKING: {response!r}", file=sys.stderr)
            self._tts.say(response)
        self._spoke_at = time.monotonic()

        # Keep info faces (e.g. clock) visible for a moment before resetting to idle —
        # otherwise _finish_speaking wipes them the instant speaking ends. The agent
        # loop already drew these faces *with* their text (e.g. the current time), so we
        # only hold here — re-sending the face would clear the text back to "--:--".
        last_face = getattr(self._agent_fn, "last_face", None)
        if last_face in self._LINGER_FACES:
            time.sleep(self._LINGER_HOLD_S)

        self._finish_speaking(reset_face=not getattr(self._agent_fn, "last_robot_command", False))

    def _finish_speaking(self, reset_face: bool = True) -> None:
        if self._use_wake_word:
            self._stop_stt()
            self._start_detector()
            self._state = _State.WAKE_LISTENING
            # After a robot motion command the firmware couples the face to the posture
            # (sit→sleep, stand→neutral). Forcing "idle" here would stomp that and start
            # the idle-expression rotation, so leave the firmware's face alone.
            if reset_face:
                self._face("idle")
            print("[pipeline] back to WAKE_LISTENING", file=sys.stderr)
        else:
            self._state = _State.LISTENING
            if self._cap is not None:
                self._cap.flush()
            if self._stt is not None:
                self._stt.resume()
            self._face("listening")
            print("[pipeline] back to LISTENING", file=sys.stderr)

    def start(self) -> None:
        from .audio.canned import CannedLines
        from .audio.tts import PiperTTS
        from .audio.playback import AudioPlayer

        if self._canned is None:
            player = AudioPlayer()
            self._canned = CannedLines(player=player)
            self._canned.load()
        if self._tts is None:
            self._tts = PiperTTS()
        if self._stt is None:
            from .audio.stt import MoonshineSTT
            self._stt = MoonshineSTT(on_final=self._on_transcript)
            self._stt.start()
            self._stt.pause()

        self._running = True

        if self._use_wake_word:
            self._start_detector()
            self._state = _State.WAKE_LISTENING
            self._face("idle")
            print("[pipeline] WAKE_LISTENING — say 'Hey Heksah'", file=sys.stderr)
        else:
            self._start_stt()
            self._state = _State.LISTENING
            self._face("listening")
            print("[pipeline] LISTENING — speak a command, Ctrl-C to quit", file=sys.stderr)

        try:
            while self._running:
                try:
                    kind, payload = self._queue.get(timeout=0.2)
                except queue.Empty:
                    continue
                if kind == "wake":
                    self._handle_wakeword(payload)
                else:
                    self._process_transcript(payload)
        except KeyboardInterrupt:
            print("\n[pipeline] stopping", file=sys.stderr)
        finally:
            self.stop()

    def stop(self) -> None:
        self._running = False
        self._stop_stt()
        if self._stt is not None:
            self._stt.stop()
            self._stt = None
        self._stop_detector()
        if self._tracker is not None:
            self._tracker.stop()
            self._tracker.provider.stop()
            self._tracker = None
        self._state = _State.IDLE


def _build_agent_fn(
    args: argparse.Namespace,
) -> tuple[Callable[[str], str], Callable[[str], None], Callable[[dict], None]]:
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
        keep_connected=True,   # persistent serial — no connect/sync overhead per command
    )

    def tool_executor(tool_requests, user_input=""):
        return execute_tools(tool_requests, robot_executor=robot_executor, enable_robot=True, user_input=user_input)

    _PERSISTENT_FACES = {"listening", "idle", "thinking", "walking", "rotating", "waving", "system", "clock", "calendar"}

    def face_executor(face_name: str, display_text: str | None = None) -> None:
        cmd: dict = {"cmd": "face", "name": face_name}
        if face_name in _PERSISTENT_FACES:
            cmd["persistent"] = True
        else:
            cmd["duration_ms"] = 3000
        if display_text:
            cmd["text"] = display_text
        robot_executor.execute_command(cmd)

    def cmd_executor(cmd: dict) -> None:
        robot_executor.execute_command(cmd)

    client = LlamaClient(base_url=args.base_url, timeout=args.timeout)
    loop = AgentLoop(
        llama_client=client,
        tool_executor=tool_executor,
        system_prompt=SYSTEM_PROMPT,
        face_executor=face_executor,
    )

    def agent_fn(text: str) -> str:
        result = loop.run_once(text)
        # Expose the agent's chosen face so the pipeline can hold info faces (clock,
        # calendar, ...) on screen after speaking instead of wiping them to idle.
        agent_fn.last_face = result.get("face")
        # Let the pipeline know a robot motion command ran so it won't reset the face to
        # idle afterwards — the firmware already set the posture-coupled face.
        agent_fn.last_robot_command = any(
            tr.get("name") == "robot_command" and tr.get("ok")
            for tr in result.get("tool_results", [])
        )
        print(f"[agent] result ok={result.get('ok')} kind={result.get('kind')} "
              f"plan_source={result.get('timings',{}).get('plan_source')} "
              f"error={result.get('error')!r}", file=sys.stderr)
        for tr in result.get("tool_results", []):
            print(f"[agent] tool={tr.get('name')} ok={tr.get('ok')} "
                  f"error={tr.get('error')!r} spoken={tr.get('spoken_text')!r} data={tr.get('data')}", file=sys.stderr)
        parts: list[str] = []
        for tr in result.get("tool_results", []):
            spoken = tr.get("spoken_text")
            if spoken and tr.get("name") != "robot_command":
                parts.append(spoken)

        # Robot motion commands skip TTS to keep latency low.
        # Info tools (time, battery, etc.) still need their spoken result.
        if result.get("timings", {}).get("plan_source") == "fast_robot":
            return " ".join(parts)

        if result.get("speak"):
            parts.insert(0, result["speak"])
        return " ".join(parts)

    return agent_fn, face_executor, cmd_executor


def _autodetect_port() -> str | None:
    """Resolve the ESP32 serial port, preferring the stable by-id symlink.

    /dev/serial/by-id/ names survive USB re-enumeration (ttyUSB0 ↔ ttyUSB1),
    so a brownout that drops the chip off the bus won't change the path.
    Falls back to the first /dev/ttyUSB* / /dev/ttyACM* if by-id is unavailable.
    """
    import glob

    by_id = sorted(glob.glob("/dev/serial/by-id/*"))
    if by_id:
        return by_id[0]
    legacy = sorted(glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*"))
    return legacy[0] if legacy else None


def main() -> None:
    parser = argparse.ArgumentParser(description="VoicePipeline — live voice command loop.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080", help="llama-server URL.")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--enable-robot", action="store_true", help="Send validated commands to hardware.")
    parser.add_argument("--port", help="Serial port, e.g. /dev/ttyUSB0.")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--wake-word", action="store_true", help="Require 'Hey Heksah' before each command.")
    parser.add_argument("--enable-camera", action="store_true", help="Enable OAK-D tracker for approach/search.")
    args = parser.parse_args()

    if args.enable_robot and not args.port:
        args.port = _autodetect_port()
        if args.port is None:
            parser.error("--enable-robot: no serial port found — pass --port explicitly")
        print(f"[pipeline] auto-detected robot port: {args.port}", file=sys.stderr)

    agent_fn, face_fn, cmd_fn = _build_agent_fn(args)

    tracker = None
    if args.enable_camera:
        from camera.provider import DepthAICameraProvider
        from camera.host_detector import HostDetector
        from camera.tracker import PersonTracker
        provider = DepthAICameraProvider()
        provider.start()
        tracker = PersonTracker(provider, HostDetector(), fps=5)
        tracker.start()

    VoicePipeline(
        agent_fn=agent_fn, face_fn=face_fn, cmd_fn=cmd_fn,
        use_wake_word=args.wake_word, tracker=tracker,
    ).start()


if __name__ == "__main__":
    main()
