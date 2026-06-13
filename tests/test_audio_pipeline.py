"""
Unit tests for VoicePipeline state machine — no hardware required.

All audio components (CannedLines, PiperTTS) are replaced with lightweight
fakes that record calls without touching GPIO, aplay, or Piper.
"""
from __future__ import annotations

import queue
import unittest

from camera.detection import DetectionResult, ObjectDetection
from camera.tracker import PersonTracker
from raspberry_pi.pipeline import VoicePipeline, _State


def _det(label="person", conf=0.9, x=0.0, y=0.0, area=0.1, dist=None):
    return ObjectDetection(
        label=label,
        confidence=conf,
        frame_position_x=x,
        frame_position_y=y,
        bbox_area=area,
        distance_m=dist,
    )


def _result(*detections):
    return DetectionResult(target_label="person", detections=list(detections), frame_age_ms=10)


class _MockCanned:
    def __init__(self):
        self.plays: list[str] = []

    def play(self, key: str) -> None:
        self.plays.append(key)

    def load(self) -> None:
        pass


class _MockTTS:
    def __init__(self):
        self.said: list[str] = []
        # Tracks pipeline state at the time each say() is called.
        self.state_at_say: list[_State] = []

    def bind(self, pipeline: VoicePipeline) -> "_MockTTS":
        self._pipeline = pipeline
        return self

    def say(self, text: str, player=None) -> None:
        if hasattr(self, "_pipeline"):
            self.state_at_say.append(self._pipeline._state)
        self.said.append(text)


def _make_pipeline(agent_fn=None):
    canned = _MockCanned()
    tts = _MockTTS()
    p = VoicePipeline(agent_fn=agent_fn, canned=canned, tts=tts)
    tts.bind(p)
    return p, canned, tts


class _SweepProvider:
    def __init__(self, frames):
        self._frames = iter(frames)

    def grab_frame(self):
        try:
            return next(self._frames)
        except StopIteration:
            return None


class _SweepDetector:
    def __init__(self, results):
        self._results = iter(results)
        self.calls = 0

    def detect(self, frame, target_label=None):
        self.calls += 1
        try:
            return next(self._results)
        except StopIteration:
            return _result()


class _SweepTracker:
    def __init__(self, provider, detector):
        self.provider = provider
        self.detector = detector

    def pick_for_direction(self, detections, direction):
        return PersonTracker.pick_for_direction(detections, direction)


class TestVoicePipelineStateMachine(unittest.TestCase):
    def test_echo_mode_speaks_transcript(self):
        p, canned, tts = _make_pipeline()
        p._process_transcript("hello robot")
        self.assertEqual(tts.said, ["hello robot"])

    def test_agent_called_before_tts(self):
        order = []

        def agent(text):
            order.append(("agent", text))
            return "ok"

        class TrackingTTS(_MockTTS):
            def say(self, text, player=None):
                order.append(("tts", text))
                super().say(text, player)

        p, _, _ = _make_pipeline(agent_fn=agent)
        p._tts = TrackingTTS()
        p._process_transcript("walk forward")

        self.assertEqual(order[0], ("agent", "walk forward"))
        self.assertEqual(order[1], ("tts", "ok"))

    def test_agent_called_with_full_transcript(self):
        agent_calls: list[str] = []

        def agent(text):
            agent_calls.append(text)
            return "agent reply"

        p, canned, tts = _make_pipeline(agent_fn=agent)
        p._process_transcript("walk forward")

        self.assertEqual(agent_calls, ["walk forward"])
        self.assertEqual(tts.said, ["agent reply"])

    def test_speaking_state_during_tts(self):
        p, canned, tts = _make_pipeline()
        p._process_transcript("hi")
        self.assertEqual(tts.state_at_say, [_State.SPEAKING])

    def test_returns_to_listening_after_processing(self):
        p, canned, tts = _make_pipeline()
        p._state = _State.THINKING
        p._process_transcript("stand up")
        self.assertEqual(p._state, _State.LISTENING)

    def test_on_transcript_ignored_when_not_listening(self):
        p, canned, tts = _make_pipeline()
        for busy_state in (_State.THINKING, _State.SPEAKING, _State.IDLE):
            p._state = busy_state
            p._on_transcript("ignored")
            self.assertTrue(p._queue.empty(), f"queue should be empty in state {busy_state}")

    def test_on_transcript_queued_when_listening(self):
        p, canned, tts = _make_pipeline()
        p._state = _State.LISTENING
        p._on_transcript("queued phrase")
        self.assertFalse(p._queue.empty())
        self.assertEqual(p._queue.get_nowait(), ("transcript", "queued phrase"))
        self.assertEqual(p._state, _State.THINKING)

    def test_on_transcript_transitions_to_thinking(self):
        p, canned, tts = _make_pipeline()
        p._state = _State.LISTENING
        p._on_transcript("stand")
        self.assertEqual(p._state, _State.THINKING)

    def test_no_filler_played_by_process_transcript(self):
        p, canned, tts = _make_pipeline()
        p._process_transcript("anything")
        self.assertEqual(canned.plays, [])

    def test_agent_response_is_what_tts_speaks(self):
        p, canned, tts = _make_pipeline(agent_fn=lambda _: "synthesized reply")
        p._process_transcript("some command")
        self.assertEqual(tts.said, ["synthesized reply"])

    def test_scan_for_person_starts_on_wake_direction_and_stops_at_first_detection(self):
        commands = []
        detector = _SweepDetector([_result(_det(x=0.6))])
        tracker = _SweepTracker(_SweepProvider([object()]), detector)
        p = VoicePipeline(cmd_fn=commands.append, tracker=tracker)
        p._SWEEP_STEP_SETTLE_S = 0.0

        pos = p._scan_for_person("right")

        self.assertEqual(pos, "right")
        self.assertEqual(detector.calls, 1)
        self.assertEqual(commands, [{"cmd": "camera_pan", "pos": "center", "offset": -75}])

    def test_scan_for_person_recenters_when_sweep_finds_nobody(self):
        commands = []
        detector = _SweepDetector([_result()] * 20)
        tracker = _SweepTracker(_SweepProvider([object()] * 20), detector)
        p = VoicePipeline(cmd_fn=commands.append, tracker=tracker)
        p._SWEEP_STEP_SETTLE_S = 0.0

        pos = p._scan_for_person("front")

        self.assertIsNone(pos)
        self.assertEqual(commands[-1], {"cmd": "camera_center"})

    def test_look_up_for_conversation_uses_persistent_up_posture(self):
        commands = []
        p = VoicePipeline(cmd_fn=commands.append)

        p._look_up_for_conversation()

        self.assertEqual(commands, [{"cmd": "look", "dir": "up", "persistent": True}])

    def test_look_up_for_conversation_ignores_command_failure(self):
        def fail(_cmd):
            raise RuntimeError("serial unavailable")

        p = VoicePipeline(cmd_fn=fail)

        p._look_up_for_conversation()


if __name__ == "__main__":
    unittest.main()
