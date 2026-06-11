# Local Gemma Agent Loop

This document explains the current local AI loop for the Hexapod project.

The goal of this layer is to let typed user input go through a local Gemma
model, safely turn the model output into a validated JSON plan, and then either
reply directly or run deterministic tools.

By default, this does not move the robot.

## Current Flow

```text
You type a request
  |
  v
scripts/run_agent_cli.py
  - reads CLI flags
  - creates AgentLoop
  - configures tool and robot execution mode
  |
  v
AgentLoop
  - checks fast_robot_intent.py for unambiguous single-word commands
    (stand, sit, stop, wave, ping, status, simple movement phrases → skip LLM)
  - checks search_intent.py for object search phrases
    ("find the ...", "search for ...", "where is ..." → ObjectSearcher, skip LLM)
  - otherwise calls build_prompt() to select the smallest correct
    prompt section (robot / camera / general tools / full fallback)
  - sends prompt + user text to local Gemma
  - receives raw model text
  |
  v
agent/agent_plan.py
  - strips simple code fences if needed
  - extracts exactly one JSON object
  |
  v
agent/agent_validator.py
  - checks version, kind, response, face, emotion, and tools
  - rejects unsafe strings before any tool runs
  |
  +-----------------------------+
  |                             |
  v                             v
final_response              tool_request
  |                             |
  |                             v
  |                         agent/tool_executor.py
  |                             - validates tool args
  |                             - runs deterministic tools
  |                             - dry-runs or explicitly sends robot commands
  |                             |
  +-------------+---------------+
                |
                v
terminal output
```

For robot-related requests, the model may request the `robot_command` tool.
That command is revalidated through the existing Python bridge command builders
before it can become serial JSON.

Normal default behavior is dry-run validation only.

## Main Files

| Area | Files |
|---|---|
| CLI entry point | `scripts/run_agent_cli.py` |
| Agent loop | `agent/agent_loop.py` |
| Local model client | `agent/llama_client.py` |
| Prompt contract | `agent/prompts.py`, `docs/AGENT_OUTPUT_CONTRACT.md` |
| Fast intent shortcuts | `agent/fast_robot_intent.py` |
| Model JSON parser | `agent/agent_plan.py` |
| Plan validator | `agent/agent_validator.py` |
| Tool executor | `agent/tool_executor.py` |
| Robot command validation | `agent/robot_command.py` |
| Robot execution/dry-run | `agent/robot_executor.py` |
| Deterministic tools | `tools/` |
| Serial bridge | `bridge/` |

## Start llama-server

Start the local model server manually before using the real agent mode:

```bash
llama-server -m ~/models/gemma4/gemma-4-E2B-it-Q8_0.gguf \
  -c 2048 \
  --reasoning off \
  --temp 0.2 \
  --top-k 20 \
  --top-p 0.9 \
  --n-predict 100 \
  -t 8 \
  --host 127.0.0.1 \
  --port 8080
```

The agent expects an OpenAI-compatible chat endpoint at:

```text
http://127.0.0.1:8080/v1/chat/completions
```

## Run The CLI

From the repository root:

```bash
python3 scripts/run_agent_cli.py
```

Ask one question and exit:

```bash
python3 scripts/run_agent_cli.py --once "what time is it?"
```

Use mock mode without starting llama-server:

```bash
python3 scripts/run_agent_cli.py --mock-llm --once "hello"
```

Print the active system prompt:

```bash
python3 scripts/run_agent_cli.py --dump-prompt
```

Print raw model JSON while debugging:

```bash
python3 scripts/run_agent_cli.py --verbose --once "search for hexapod robot"
```

## Tool Behavior

The model is only allowed to request known tools. The current implemented tools
include:

```text
get_time
get_date
search_web
remember_fact
recall_memory
forget_memory
system_status
network_status
battery_status
set_timer
set_reminder
robot_command
```

Camera tools (`capture_image`, `camera_status`, `depth_probe`, `check_clearance`,
`observe_scene`, `detect_person`, `detect_object`) are fully implemented via the
OAK-D DepthAI pipeline. Microphone tools are not yet implemented.

## Robot Commands

Robot requests go through the `robot_command` tool.

Example dry-run:

```bash
python3 scripts/run_agent_cli.py --once "wave with the right front leg"
```

In default mode, robot commands are validated and printed as serial JSON, but
they are not sent to the ESP32.

The robot command path is:

```text
model tool request
  -> agent/tool_executor.py
  -> agent/robot_command.py
  -> bridge/robot_commands.py
  -> agent/robot_executor.py
  -> dry-run result or explicit SerialRobotBridge send
```

The validator rejects low-level or unsafe requests such as raw servo control,
PCA writes, shell commands, Python code, and arbitrary file operations.

## Real Hardware Mode

Real robot movement requires explicit opt-in:

```bash
python3 scripts/run_agent_cli.py \
  --enable-robot \
  --port /dev/ttyUSB0 \
  --once "stand"
```

Movement commands ask for confirmation unless `--yes` is passed:

```bash
python3 scripts/run_agent_cli.py \
  --enable-robot \
  --port /dev/ttyUSB0 \
  --yes \
  --once "wave with the right front leg"
```

Use this carefully. The software validation helps keep the command path
predictable, but it does not replace physical safety checks.

## Useful Flags

| Flag | Purpose |
|---|---|
| `--once "..."` | Run one user request and exit |
| `--mock-llm` | Use a hardcoded model response instead of llama-server |
| `--verbose` | Print the raw model output |
| `--base-url URL` | Use a different llama-server URL |
| `--timeout N` | Set llama-server request timeout |
| `--no-tools` | Validate tool requests without executing tools |
| `--no-robot` | Disable robot command handling |
| `--robot-dry-run` | Force robot command dry-run mode |
| `--enable-robot` | Allow validated commands to be sent to hardware |
| `--port PATH` | Serial port for real robot mode |
| `--yes` | Skip movement confirmation in real robot mode |
| `--summarize-tool-results` | Ask the model to rewrite successful tool results |

## Automated Tests

Run the Python tests:

```bash
python3 -m pytest tests/ -v
```

The automated tests do not require:

- a running llama-server
- a connected ESP32
- a real serial port
- a real camera
- a real microphone

Hardware checks are separate manual tests and should use `--enable-robot` only
when the robot is physically ready.
