# Firmware Architecture

This firmware is the onboard nervous system for the hexapod. The host computer
speaks in intent - stand, gait, rotate, look, nod, blink, idle - and the ESP32
turns that intent into coordinated motion, expression, inverse kinematics, and
PCA9685 servo writes.

The most important architectural rule is that the robot stays alive to new
input while it is moving. A gait, gesture, sit transition, rotate cycle, or OLED
animation must not monopolize the CPU. Long behaviors are represented as small
state machines that advance a little on each pass through `loop()`.

The host should never send raw servo angles or display pixels during normal
operation. It describes what the robot should do, and the firmware owns the
translation into safe hardware-level action.

The current host side also includes a local Gemma agent loop. That layer is
allowed to propose only validated JSON outputs and deterministic tool calls. It
does not bypass the Python bridge or the firmware command parser.

## System Shape

At a high level, the firmware is split into five cooperating domains:

- protocol: receive, parse, validate, and acknowledge host commands
- orchestration: own robot mode and decide which behavior is active
- behavior controllers: advance gait, rotate, sit, body, and expressive motions
- presentation: maintain persistent and temporary OLED face state
- hardware: solve IK, apply trims, and write PCA9685 PWM outputs

The flow deliberately narrows as it approaches hardware:

```text
host intent
  -> serial protocol
  -> parser
  -> router
  -> robot controller
  -> behavior controller / pose helper
  -> inverse kinematics
  -> servo driver
  -> PCA9685 boards
  -> servos
```

Face and expression commands take a parallel path:

```text
host intent
  -> serial protocol
  -> parser
  -> router / robot controller
  -> display controller
  -> RoboEyes or custom pixel-art renderer
  -> SH1107 OLED
```

Many commands intentionally touch both paths. `gait` moves the legs and switches
the face to `walking`. `rotate` uses `rotating`. `look`, `nod`, `shake`, `wave`,
and named gestures combine body motion with a matching temporary expression.

## Non-Blocking Core

`src/main.cpp` is intentionally small because it is the scheduler for the whole
robot:

```cpp
void loop() {
  serialProtocolUpdate();
  robotUpdate();

  static unsigned long lastDisplayUpdateMs = 0;
  unsigned long now = millis();
  unsigned long displayInterval = gaitIsRunning()
      ? OLED_GAIT_FRAME_INTERVAL_MS
      : OLED_FRAME_INTERVAL_MS;
  if (now - lastDisplayUpdateMs >= displayInterval) {
    lastDisplayUpdateMs = now;
    displayUpdate();
  }

#if ENABLE_DEBUG_MENU
  debugMenuUpdate();
#endif
  delay(5);
}
```

This loop has three contracts:

- `serialProtocolUpdate()` must keep accepting newline-delimited commands.
- `robotUpdate()` must advance only the active behavior and then return.
- `displayUpdate()` must draw one frame or service RoboEyes and then return.

This is cooperative multitasking. There is no RTOS task scheduler here. Each
controller carries its own state, timestamps, phase counters, and completion
flags. The global `loop()` gives each subsystem a short turn.

That design makes these interactions possible:

- `status` can be requested while a gait is walking.
- `stop` can interrupt a rotate or gesture.
- temporary faces can expire while motion continues.
- OLED updates can be throttled during gait so I2C display traffic does not
  compete too aggressively with servo timing.
- long motions report `done` events only after their controller reaches a
  natural completion point.

Short startup delays and the tiny `delay(5)` at the end of `loop()` are allowed.
Long command handlers and behavior controllers should not contain blocking
`delay()` loops.

## Startup

Startup is owned by `setup()` in `src/main.cpp`:

1. Open serial at `115200`.
2. Bring up I2C on `I2C_SDA` / `I2C_SCL`.
3. Probe the left and right PCA9685 boards.
4. Reinitialize I2C after probing, because the ESP32 I2C peripheral can lock
   after a NACK.
5. Initialize both PCA9685 servo drivers.
6. Initialize the OLED display controller.
7. Initialize robot mode state.
8. Send the serial protocol `ready` event.
9. Optionally stand on boot if `AUTO_STAND_ON_BOOT` is enabled.

The current PlatformIO target is `esp32dev` using the Arduino framework.

## Protocol Boundary

Files:

- `include/types.h`
- `include/serial_protocol.h`
- `src/serial_protocol.cpp`
- `include/command_parser.h`
- `src/command_parser.cpp`
- `include/command_router.h`
- `src/command_router.cpp`

The protocol layer is the border between the host and the robot. It reads one
newline-terminated command at a time into a fixed-size buffer, parses JSON first,
falls back to simple text commands, and returns JSON responses.

Accepted command families:

- posture: `stand`, `sit`, `stop`
- locomotion: `gait`, `rotate`
- direct body pose: `body`
- gestures: `wave`, `gesture`
- expressive body: `lean`, `look`, `nod`, `shake`, `idle`
- display: `face`, `blink`
- diagnostics: `ping`, `status`

Preferred command style:

```json
{"cmd":"stand"}
{"cmd":"gait","dir":"forward","speed":0.02,"steps":2}
{"cmd":"rotate","dir":"left","cycles":2}
{"cmd":"face","name":"starstruck"}
{"cmd":"look","dir":"left","duration_ms":1200}
{"cmd":"idle","style":"breathing"}
{"cmd":"stop"}
```

The parser validates:

- command names
- directions
- numeric bounds
- mutually exclusive motion bounds such as `steps` versus `duration_ms`
- semantic face names
- raw hardware control attempts

Raw servo control is explicitly rejected with `raw_servo_control_not_allowed`.
That is a safety and architecture decision: high-level commands are stable,
hardware mappings and trims are internal.

## Host Python Bridge

Files:

- `bridge/bridge_errors.py`
- `bridge/response_parser.py`
- `bridge/robot_commands.py`
- `bridge/serial_robot_bridge.py`
- `test_robot_bridge_cli.py`

The Python bridge is the supported host-side entry point for programs running
on a Raspberry Pi or Linux laptop. It does not plan behavior and it does not
own hardware details. Its job is to build validated semantic command dicts,
send compact newline-terminated JSON over USB serial, and parse firmware JSON
lines back into structured Python responses.

This bridge preserves the same safety boundary as the firmware:

- command builders expose semantic actions such as `stand`, `gait`, `rotate`,
  `face`, and `look`
- local validation rejects invalid directions, ambiguous motion bounds, and
  unsafe parameter ranges before serial write
- `send_command()` rejects raw hardware fields even if a caller bypasses the
  builders
- non-JSON debug text from the firmware is parsed as a harmless raw line

The CLI in `test_robot_bridge_cli.py` is primarily for smoke testing and manual
operation. `--dry-run` validates and prints the exact JSON without opening a
serial port; hardware runs wait for the firmware `ready` event before sending.

LLM or voice layers should call `SerialRobotBridge` methods or a deterministic
executor built on top of them. They should not write directly to serial and
should not construct raw JSON strings themselves.

## Local Gemma Agent Loop

Files:

- `scripts/run_agent_cli.py`
- `agent/llama_client.py`
- `agent/prompts.py`
- `agent/response_contract.py`
- `agent/agent_plan.py`
- `agent/agent_validator.py`
- `agent/tool_executor.py`
- `agent/robot_command.py`
- `agent/robot_executor.py`
- `docs/LOCAL_GEMMA_AGENT.md`
- `docs/AGENT_OUTPUT_CONTRACT.md`

The local agent loop is the current AI layer for typed interaction. It sends a
system prompt and user text to a locally running Gemma model through
`llama-server`, then treats the model response as untrusted data.

The accepted model output is one JSON object with one of two modes:

- `final_response`: speak directly to the user without running a tool
- `tool_request`: request one or more known deterministic tools

The safety path is deliberately narrow:

```text
typed input
  -> run_agent_cli.py
  -> AgentLoop
  -> LlamaClient
  -> parse_agent_plan()
  -> validate_agent_plan()
  -> execute_tools()
  -> deterministic tool result
```

Robot requests are represented as a `robot_command` tool request. Those
arguments are compiled through `agent/robot_command.py`, which reuses the bridge
command builders in `bridge/robot_commands.py`. In default CLI mode,
`RobotExecutor` dry-runs the command and prints the compact serial JSON instead
of opening a serial port.

Real robot execution requires all of these:

- `--enable-robot`
- an explicit `--port`
- confirmation for movement unless `--yes` is passed
- successful validation by the agent output contract
- successful validation by the bridge command builders

This gives the AI layer two boundaries before hardware:

1. The model may only produce the documented agent JSON contract.
2. A robot command must still compile into the existing semantic serial
   protocol before `SerialRobotBridge` can send it.

The agent validator rejects unsafe strings such as raw servo control, shell or
Python execution, direct serial writes, I2C/PCA writes, raw OLED pixels, and
arbitrary file access. This mirrors the firmware boundary: the model can express
intent, but it cannot write hardware-level commands.

## Robot Controller

Files:

- `include/robot_controller.h`
- `src/robot_controller.cpp`

The robot controller is the conductor. It owns the current `RobotMode`, stops
conflicting behaviors before starting a new one, updates the active controller,
and couples motion state to face state.

Robot modes:

- `idle`
- `standing`
- `sitting`
- `gait`
- `rotating`
- `waving`
- `gesture`
- `body`

Only the active mode is advanced in `robotUpdate()`. For example, gait mode calls
`gaitUpdate()`, rotate mode calls `rotateUpdate()`, and gesture mode calls
`gestureUpdate()`. When a controller reports completion, the robot returns to
standing and emits a `done` event where appropriate.

The controller also owns expression coupling:

- idle mode sets `idle`
- standing mode sets `neutral`
- sitting mode sets `sleepy`
- gait uses temporary `walking`
- rotate uses temporary `rotating`
- wave uses temporary `waving`
- named gestures choose matching faces such as `happy`, `curious`, `scared`,
  `sleepy`, and `listening`
- `look`, `nod`, `shake`, and `lean` use short-lived expressive faces unless the
  command explicitly asks for persistence

This layer is also where user-visible status is assembled. `robotGetStatus()`
reports mode, active command, gait progress, rotate progress, gesture name,
current face, temporary-face state, interruptibility, and the last error string.

## Motion Controllers

Files:

- `include/gait_controller.h`
- `src/gait_controller.cpp`
- `include/rotate_controller.h`
- `src/rotate_controller.cpp`
- `include/gesture_controller.h`
- `src/gesture_controller.cpp`

Controllers are small state machines. Their shape is consistent:

```text
start(command)
  -> validate and clamp parameters
  -> store command/state
  -> mark running

update()
  -> advance one step based on millis(), phase, or cycle counters
  -> write the current pose
  -> mark done when complete

stop()
  -> return to a safe pose or neutral controller state
  -> clear running
```

### Gait

`gait_controller` wraps the tripod gait engine in `src/tripod_gait.cpp`.

Responsibilities:

- map named directions to normalized X/Y vectors
- clamp speed, step length, step height, duration, steps, and distance
- support continuous, duration-bound, step-bound, and distance-bound walking
- count completed tripod cycles
- stop smoothly when the requested bound is reached

The lower-level tripod gait advances phase on each update, alternates lift
groups, computes foot offsets, and calls `legIK()` for each leg.

### Rotate

`rotate_controller` wraps the older rotate-loop implementation. It accepts left
or right rotation, supports continuous rotation, converts degrees into rough
cycle counts, tracks completed cycles, and stops once the target is reached.

### Gestures And Expressive Body Motion

`gesture_controller` handles both explicit gestures and subtle body language:

- `wave`
- named gestures: `happy`, `curious`, `scared`, `sleepy`, `listening`, `idle`
- `lean`
- `look`
- `nod`
- `shake`
- idle `breathing`
- idle `sway`

These motions use elapsed time, sine waves, interpolation steps, and IK body
offsets instead of blocking waits. A gesture may run for 300 ms or indefinitely,
but it still gives control back to `loop()` on every update.

## Poses

Files:

- `include/poses.h`
- `src/poses.cpp`

Pose helpers are the simplest motion layer:

- `poseStand()` writes a neutral IK standing pose.
- `poseSitStart()` begins a sit transition.
- `poseSitUpdate()` advances the sit transition using `LOOP_UPDATE_MS` and
  `SIT_INTERP_STEP`.
- `poseBodyOffset()` applies the same body offset to all six legs through IK.

The sit pose keeps compatibility with the old sitting branch by using the same
femur and tibia target deltas.

## Kinematics

Files:

- `include/ik.h`
- `src/ik.cpp`

The IK layer turns body-relative foot offsets into servo angles. It owns:

- leg geometry
- leg mount descriptors
- mirrored left/right conventions
- coxa, femur, and tibia angle calculation
- clamping to the 0-180 degree servo range

`solveLegIK()` calculates a solution without writing hardware. `legIK()`
calculates and writes the solution to the appropriate PCA9685 channels with
per-joint trims applied.

## Servo Hardware

Files:

- `include/config.h`
- `include/servo_driver.h`
- `src/servo_driver.cpp`

The hardware layer owns the physical mapping:

- I2C pins and clock
- PCA9685 addresses
- servo PWM frequency
- channel assignments for all 18 joints
- reference angles
- trim offsets
- raw PWM conversion
- PCA board presence checks

`servoWriteRaw()` is intentionally low-level. It clamps angles, converts degrees
to PCA9685 PWM ticks using the configured baseline, and writes to the selected
board. Normal host commands should reach it only through poses, controllers, or
IK.

## Display And Expression

Files:

- `include/display_controller.h`
- `src/display_controller.cpp`
- `lib/RoboEyes/FluxGarage_RoboEyes.h`

The display controller owns the SH1107 OLED and the robot's visible emotional
state. It supports two rendering families:

- RoboEyes faces: `idle`, `neutral`, `happy`, `curious`, `scared`, `sleepy`,
  `listening`, `walking`, `rotating`, `waving`
- custom pixel-art faces: `error`, `love`, `surprised`, `starstruck`, `dizzy`,
  `confused`, `sad`, `sleep`, `loading`, `alert`, `low_battery`, `boop`,
  `scan`, `clock`, `calendar`, `search`, `camera`, `memory`, `timer`,
  `reminder`, `battery`, `system`, `wifi`, `microphone`, `speaking`, and
  `success`

The controller tracks:

- current face
- persistent base face
- temporary face state
- temporary face expiration time
- optional face text
- gaze direction
- blink events
- custom animation frame timing

Direct `face` commands are temporary by default. `idle` and `neutral` are
persistent base faces, and any face can be made persistent with:

```json
{"cmd":"face","name":"surprised","persistent":true}
```

`displayUpdate()` is non-blocking. Temporary faces expire by comparing
`millis()` against their start time. Custom faces redraw at their own frame
interval. RoboEyes is allowed to advance one frame when called.

## Status And Events

The firmware speaks back in compact JSON.

Ready event:

```json
{"event":"ready","firmware":"hexapod","protocol":1}
```

Simple ACK:

```json
{"ok":true,"cmd":"stand"}
```

Error:

```json
{"ok":false,"error":"invalid_direction","value":"sideways"}
```

Representative status response:

```json
{
  "ok": true,
  "cmd": "status",
  "mode": "gesture",
  "active_cmd": "look",
  "gesture": "look",
  "face": "listening",
  "face_temporary": true,
  "interruptible": true
}
```

When a bounded motion finishes, the robot emits a `done` event:

```json
{"event":"done","cmd":"gait","state":"standing"}
```

The real `status` response includes additional motion fields for gait, rotate,
duration, steps, distance, and errors when they are relevant.

## Safety Model

The firmware's safety model is simple and strict:

- hosts command intent, not servo angles
- parsers reject malformed and unsafe fields early
- controllers clamp accepted parameters against `config.h` limits
- the robot controller stops conflicting behaviors before starting a new one
- servo writes are clamped to 0-180 degrees
- IK applies trim offsets in one central place
- long behaviors must stay interruptible through the main loop

This does not replace mechanical safety. Power, servo load, joint limits,
calibration, and physical clearances still matter. The architecture only makes
the software path predictable and easier to reason about.

## Legacy Debug Tests

Files include:

- `src/sitting_test.cpp`
- `src/rotate_test.cpp`
- `src/rotate_loop_test.cpp`
- `src/body_motion_test.cpp`
- `src/tripod_gait.cpp`
- `src/wave.cpp`
- `src/menu.cpp`

These files preserve calibration and debug workflows. They may contain older
interactive loops and small waits that are acceptable in test modes. The command
protocol is the preferred control path for host, Python, or AI bridge work.

## Timing Rules For New Code

When adding behavior, follow these rules:

1. Command parsing may validate and store intent, but it should not move the
   robot.
2. Routing may start a behavior, but it should not run the full behavior.
3. Controllers should expose `start`, `update`, `stop`, `isRunning`, and
   `isDone` style APIs when the behavior lasts longer than one loop pass.
4. Use `millis()` and stored timestamps for timing.
5. Advance one pose, phase, or frame per `update()` call.
6. Return quickly so serial input and stop/status commands remain responsive.
7. Emit `done` from the orchestration layer when a behavior completes.

Blocking code belongs only in deliberate diagnostics, startup pauses, or tiny
hardware-settle points.

## Adding A New Command

Use this order:

1. Add or extend command data in `include/types.h`.
2. Parse the command in `src/command_parser.cpp`.
3. Route it in `src/command_router.cpp`.
4. Add a robot API function in `robot_controller` if it affects motion or mode.
5. Implement long-running motion in a controller with non-blocking `update()`.
6. Add display coupling in `robot_controller` or `display_controller` if the
   command should affect expression.
7. Add serial monitor examples or hardware notes for the new command.
8. Build with `pio run`.

## Adding A New Face

Use this order:

1. Add a `FaceState` value in `include/display_controller.h`.
2. Add the semantic name in `displayFaceName()`.
3. Add parser support in `displayParseFaceName()`.
4. Implement the expression in `applyFace()` or `drawCustomFace()`.
5. If it is pixel-art or custom animated, include it in `isCustomFace()`.
6. Add a serial monitor example.
7. Build with `pio run`.

Prefer semantic face names. Do not add a host command that sends arbitrary
pixels or bitmaps unless the safety model is deliberately changed.
