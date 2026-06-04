# Agent Output Contract

This document describes the JSON format that the local Gemma agent is expected
to return.

The model does not get to control hardware directly. It can only return one
validated JSON object. The Python agent then parses that object, checks it
against this contract, rejects unsafe content, and only then runs any requested
tool.

## Output Rules

The model must return:

- one JSON object
- no markdown
- no extra text before or after the JSON
- `version` equal to `1`
- `kind` equal to either `final_response` or `tool_request`
- a `response` object containing `speak`, `emotion`, and `face`

The parser can strip a simple markdown code fence, but the prompt still tells
the model to output plain JSON only.

## Mode: final_response

Use this when the model can answer directly without a tool.

```json
{
  "version": 1,
  "kind": "final_response",
  "response": {
    "speak": "Hello. I am ready.",
    "emotion": "neutral",
    "face": "idle"
  }
}
```

`response.speak` must be a non-empty string and must be 240 characters or
fewer. It must not contain code backticks.

## Mode: tool_request

Use this when the model needs a deterministic tool.

```json
{
  "version": 1,
  "kind": "tool_request",
  "response": {
    "speak": "Checking the time.",
    "emotion": "thinking",
    "face": "clock"
  },
  "tools": [
    {
      "name": "get_time",
      "args": {}
    }
  ]
}
```

The `tools` field must be a list. Each item must be an object with a known
`name`. Tool arguments must match the executor rules in `agent/tool_executor.py`.

## Robot Command Tool

Robot requests use the same `tool_request` mode with the `robot_command` tool.

```json
{
  "version": 1,
  "kind": "tool_request",
  "response": {
    "speak": "Waving.",
    "emotion": "happy",
    "face": "happy"
  },
  "tools": [
    {
      "name": "robot_command",
      "args": {
        "cmd": "wave",
        "leg": "RF",
        "count": 2
      }
    }
  ]
}
```

The robot command arguments are not sent straight to serial. They are compiled
through `agent/robot_command.py` and `bridge/robot_commands.py` first. In normal
CLI use, the command is dry-run validated. Real sending requires
`--enable-robot` and an explicit serial port.

## Allowed Emotions

Emotions are agent-side response labels. They are used by the Python agent
contract, not by the ESP32 firmware command parser.

```text
calm
concerned
excited
happy
neutral
thinking
```

## Allowed Faces

The contract imports allowed faces from `agent/response_contract.py`. These are
the canonical face names supported by the firmware display controller.

```text
alert
battery
blinking
boop
calendar
camera
clock
confused
curious
dizzy
error
happy
idle
listening
loading
love
low_battery
memory
microphone
neutral
reminder
rotating
sad
scan
scared
search
sleep
sleepy
speaking
starstruck
success
surprised
system
thinking
timer
walking
waving
wifi
```

## Allowed Tools

The contract imports allowed tool names from `agent/response_contract.py`.

```text
battery_status
camera_status
capture_image
check_clearance
depth_probe
describe_scene
detect_object
detect_person
explain_capability
forget_memory
get_date
get_time
local_file_lookup
mic_status
network_status
observe_scene
read_project_note
recall_memory
remember_fact
robot_command
search_web
set_reminder
set_timer
system_status
tell_joke
voice_direction_estimate
```

Implemented tool names may run normally. Registered but not currently
implemented tool names may be accepted by validation, then return
`not_implemented` during tool execution.

## Rejected Output

The validator rejects:

- unknown top-level fields
- unsupported `version`
- unsupported `kind`
- missing or invalid `response`
- empty or too-long `response.speak`
- code backticks in `response.speak`
- unsupported `emotion`
- unsupported `face`
- non-list `tools`
- unknown tool names
- unsafe strings anywhere in the JSON object

Unsafe strings include:

```text
arbitrary_json
eval
exec
file_read
file_write
i2c_write
pca_write
python
raw_oled
raw_pixels
raw_servo
serial_write
servo
set_servo
shell
```

Robot commands have an additional safety pass in `agent/robot_command.py` before
they can become serial JSON.
