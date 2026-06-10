"""
Unit tests for VoicePipeline state machine — no hardware required.

All audio components (CannedLines, PiperTTS) are replaced with lightweight
fakes that record calls without touching GPIO, aplay, or Piper.
"""
from __future__ import annotations

import queue
import unittest

from raspberry_pi.pipeline import VoicePipeline, _State


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
        self.assertEqual(p._queue.get_nowait(), "queued phrase")
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


if __name__ == "__main__":
    unittest.main()
