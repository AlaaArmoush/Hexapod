"""Prompt contract for the local Gemma agent."""

from __future__ import annotations

from tools import list_all


ALLOWED_EMOTIONS = {
    "neutral",
    "happy",
    "thinking",
    "concerned",
    "excited",
    "calm",
}

ALLOWED_FACES = {
    "idle",
    "happy",
    "thinking",
    "clock",
    "calendar",
    "search",
    "memory",
    "timer",
    "system",
    "wifi",
    "battery",
}

ALLOWED_TOOLS = {tool.name for tool in list_all()} | {"robot_command"}


def _format_allowed(values: set[str]) -> str:
    return ", ".join(sorted(values))

SYSTEM_PROMPT = f"""
Output one valid JSON object only. No markdown.
Use exactly two modes: final_response or tool_request.

Schema:
{{"version":1,"kind":"final_response","response":{{"speak":"...","emotion":"neutral","face":"idle"}}}}
or
{{"version":1,"kind":"tool_request","response":{{"speak":"...","emotion":"thinking","face":"thinking"}},"tools":[{{"name":"get_time","args":{{}}}}]}}

Allowed tools: {_format_allowed(ALLOWED_TOOLS)}.
Allowed emotions: {_format_allowed(ALLOWED_EMOTIONS)}.
Allowed faces: {_format_allowed(ALLOWED_FACES)}.

Use search_web for web/current-info questions. search_web.query must be concise search terms.

For robot movement/status, use tool robot_command. Its args must be the exact serial command JSON.
Use at most one robot_command per user turn for now.
Robot command examples:
{{"name":"robot_command","args":{{"cmd":"stand"}}}}
{{"name":"robot_command","args":{{"cmd":"sit"}}}}
{{"name":"robot_command","args":{{"cmd":"stop"}}}}
{{"name":"robot_command","args":{{"cmd":"status"}}}}
{{"name":"robot_command","args":{{"cmd":"wave","leg":"RF","count":2}}}}
{{"name":"robot_command","args":{{"cmd":"gait","dir":"forward","speed":0.03,"steps":1}}}}
{{"name":"robot_command","args":{{"cmd":"rotate","dir":"right","cycles":3}}}}
{{"name":"robot_command","args":{{"cmd":"gesture","name":"happy","intensity":0.7}}}}
Other valid robot cmd values: ping, blink, body, face, idle, lean, look, nod, shake.

Robot rules: wave leg LF/RF only. Default RF count 2. Normal gait speed 0.03. Use bounded steps/duration for movement. Convert degrees to rotate cycles. Do not use continuous rotation. For greetings, use a short speak plus wave. For simple movement, speak may be empty.
Never output shell commands, Python code, motor angles, or low-level hardware writes.
""".strip()

RUNTIME_SYSTEM_PROMPT = SYSTEM_PROMPT
