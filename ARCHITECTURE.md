# Firmware Architecture

## Scope

This document covers the ESP32 firmware pipeline from host command input to
robot motion, OLED expression, inverse kinematics, and PCA9685 servo writes.

## Design Invariants

- Host input is semantic intent, not raw hardware control.
- Parsed input is normalized into one `RobotCommand`.
- Routing validates commands before any behavior starts.
- Long-running behavior is state-based and advanced from `loop()`.
- Only the active robot behavior advances during each `robotUpdate()`.
- IK and servo output are owned by firmware-side hardware layers.

## System Flow

Movement commands narrow toward hardware:

```text
+------------------+
| host command     |
+------------------+
  One newline-terminated JSON or text command from the host, bridge,
  or serial monitor.
        |
        v
+------------------+
| serial protocol  |
+------------------+
  `serialProtocolUpdate()` reads bytes, fills `lineBuffer`, and waits
  until a complete line arrives.
        |
        v
+------------------+
| command parser   |
+------------------+
  `parseCommand()` converts JSON or text into one normalized
  `RobotCommand` with typed payload data.
        |
        v
+------------------+
| command router   |
+------------------+
  `routeCommand()` rejects unsafe or invalid input, sends an immediate
  ack/error, and dispatches accepted commands.
        |
        v
+------------------+
| robot controller |
+------------------+
  Owns `RobotMode`, stops conflicting behaviors, starts the requested
  behavior, couples motion to face state, and emits done events.
        |
        v
+---------------------+
| behavior controller |
+---------------------+
  Advances gait, rotate, gesture, sit, body, or camera pan state one
  small step during `robotUpdate()`.
        |
        v
+-------------------+
| pose / gait math  |
+-------------------+
  Produces body offsets or per-leg foot offsets for the current
  behavior frame.
        |
        v
+---------------------+
| inverse kinematics  |
+---------------------+
  `legIK()` converts offsets into coxa, femur, and tibia servo angles
  using leg geometry, mirroring, and trims.
        |
        v
+------------------+
| servo driver     |
+------------------+
  `servoWriteRaw()` clamps angles, converts them to PCA9685 PWM ticks,
  and writes the selected board/channel.
        |
        v
+------------------+
| PCA9685 boards   |
+------------------+
  Output servo pulses for the leg servos and camera pan servo.
```

Display commands use the same command boundary, then split toward the OLED:

```text
+--------------------+
| host command       |
+--------------------+
  One newline-terminated face, blink, look, or behavior command.
        |
        v
+--------------------+
| serial protocol    |
+--------------------+
  Reads the line exactly like movement commands.
        |
        v
+--------------------+
| command parser     |
+--------------------+
  Creates `RobotCommand` data, including `FaceCommand` fields when the
  command directly targets the display.
        |
        v
+--------------------+
| command router     |
+--------------------+
  Validates face names, blink/display intent, and command parameters.
        |
        v
+--------------------+
| display controller |
+--------------------+
  Stores current face, base face, temporary face timing, gaze, text,
  blink state, and custom animation timing.
        |
        v
+--------------------+
| renderer           |
+--------------------+
  `displayUpdate()` advances RoboEyes or draws one custom face frame.
        |
        v
+--------------------+
| SH1107 OLED        |
+--------------------+
  Displays the current expression.
```

Behavior commands often touch both paths. For example, `gait` starts leg motion
through the movement path and also asks the display controller to show the
walking face.

Commands and updates are separate:

```text
command arrival:
  serialProtocolUpdate()
    -> parseCommand()
    -> routeCommand()
    -> start or change controller/display state

runtime update:
  loop()
    -> robotUpdate()
       advances the active controller by one step
    -> displayUpdate()
       advances or restores the current face
```

## Main Loop

`src/main.cpp` is the cooperative scheduler:

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

Each subsystem gets a short turn:

- `serialProtocolUpdate()` reads at most one complete command line and returns.
- `robotUpdate()` advances the active robot mode and returns.
- `displayUpdate()` advances the OLED face state and returns.

Long command handlers and controllers should not contain blocking loops. They
should store state and continue from the next `loop()` pass.

Startup in `setup()` opens serial at `57600`, starts I2C, probes both PCA9685
boards, reinitializes I2C after probing, initializes the servo drivers,
initializes the display, initializes robot state, and emits the ready event:

```json
{"event":"ready","firmware":"hexapod","protocol":1}
```

## Command Boundary

Files:

- `include/types.h`
- `include/serial_protocol.h`
- `src/serial_protocol.cpp`
- `include/command_parser.h`
- `src/command_parser.cpp`
- `include/command_router.h`
- `src/command_router.cpp`

The firmware accepts one command per line. JSON is the preferred host protocol:

```json
{"cmd":"stand"}
{"cmd":"gait","dir":"forward","speed":0.02,"steps":2}
{"cmd":"rotate","dir":"left","cycles":2}
{"cmd":"face","name":"starstruck"}
{"cmd":"look","dir":"left","duration_ms":1200}
{"cmd":"idle","style":"breathing"}
{"cmd":"stop"}
```

Text commands exist for serial monitor use:

```text
gait forward --steps 2 --speed 0.02 --step-len 35 --step-ht 20
rotate left 2
face happy 1000
```

`serial_protocol` frames input. It does not know command semantics.

`command_parser` recognizes JSON or text and fills `RobotCommand`. That struct
is the handoff object for the rest of the firmware. It contains:

- `type`: normalized command enum
- `cmdName`: original command name for errors/status
- validation flags such as `invalidNumeric`
- one typed payload per command family

`command_router` is the safety and dispatch layer. It rejects malformed values,
ambiguous motion bounds, invalid directions, invalid faces, and raw hardware
control fields. Accepted commands either call a `robotCommand...()` function or
directly update the display controller.

Raw hardware fields such as `servo`, `angle`, `pwm`, `board`, `channel`,
`pixel`, and `bitmap` are rejected with `raw_servo_control_not_allowed`.

## Robot Controller

Files:

- `include/robot_controller.h`
- `src/robot_controller.cpp`

The robot controller is the orchestration layer. It owns:

- current `RobotMode`
- last error string
- command start/stop behavior
- behavior completion events
- motion-to-face coupling
- user-visible status assembly

Current modes:

- `idle`
- `standing`
- `sitting`
- `gait`
- `rotating`
- `waving`
- `gesture`
- `body`
- `camera_pan`

Command entry points such as `robotCommandGait()` and `robotCommandRotate()`
start behavior and return quickly. Later, `robotUpdate()` advances whichever
mode is active:

```text
ROBOT_MODE_SITTING    -> poseSitUpdate()
ROBOT_MODE_GAIT       -> gaitUpdate()
ROBOT_MODE_ROTATING   -> rotateUpdate()
ROBOT_MODE_WAVING     -> gestureUpdate()
ROBOT_MODE_GESTURE    -> gestureUpdate()
ROBOT_MODE_CAMERA_PAN -> cameraHeadUpdate() completion check
```

The controller also sets expression state. For example, gait shows a walking
face, rotate shows a rotating face, sitting shows sleepy, and look/nod/shake use
temporary expressive faces.

## Movement Controllers

Movement controllers are small state machines with the same basic shape:

```text
start(command)
  validate, clamp, store state, mark running

update()
  advance one step based on millis(), phase, cycles, or interpolation
  write the current pose
  mark done when complete

stop()
  settle or reset controller state
  clear running
```

### Gait

Files:

- `include/gait_controller.h`
- `src/gait_controller.cpp`
- `include/tripod_gait.h`
- `src/tripod_gait.cpp`

`gait_controller` is the command-level walking wrapper. It maps directions to
X/Y vectors, clamps command values, converts distance into steps, tracks
duration/step/distance bounds, and starts the tripod gait engine.

`tripod_gait` is the per-frame gait engine. It alternates two leg groups,
advances a phase value, calculates swing and stance foot offsets, and calls
`legIK()` for each leg.

### Rotate

Files:

- `include/rotate_controller.h`
- `src/rotate_controller.cpp`
- `src/rotate_loop_test.cpp`

`rotate_controller` wraps the rotate-loop implementation. It validates left or
right direction, supports cycles/degrees/continuous rotation, counts completed
cycles, and stops when the requested bound is reached.

### Gestures

Files:

- `include/gesture_controller.h`
- `src/gesture_controller.cpp`

`gesture_controller` handles wave, named gestures, lean, look, nod, shake, and
idle styles. It uses elapsed time, sine waves, interpolation, and body offsets.
It returns after each update instead of blocking for the whole gesture.

### Poses

Files:

- `include/poses.h`
- `src/poses.cpp`

Pose helpers are the direct posture layer:

- `poseStand()` writes neutral standing through IK.
- `poseSitStart()` begins a sit transition.
- `poseSitUpdate()` advances the sit transition.
- `poseBodyOffset()` applies one body offset to all six legs.

## IK And Servo Output

Files:

- `include/ik.h`
- `src/ik.cpp`
- `include/config.h`
- `include/servo_driver.h`
- `src/servo_driver.cpp`

`ik.cpp` converts body-relative foot targets into servo angles. It owns leg
geometry, mount angles, left/right mirroring, coxa/femur/tibia solving, and
angle clamping.

`solveLegIK()` calculates a solution without touching hardware. `legIK()` solves
the leg, adds trims from `config.h`, and writes the result.

`servo_driver.cpp` owns the final PCA9685 interaction. `servoWriteRaw()` clamps
the requested angle, converts it to PWM ticks, and writes to either the left or
right PCA9685 board.

## Display And Expression

Files:

- `include/display_controller.h`
- `src/display_controller.cpp`
- `lib/RoboEyes/FluxGarage_RoboEyes.h`

The display controller owns the OLED expression state:

- current face
- persistent base face
- temporary face and expiration time
- optional face text
- gaze direction
- blink events
- custom animation timing

Direct face commands can set temporary or persistent faces. Robot behavior can
also set temporary faces through `robot_controller`, so expression follows
motion even when the host only sends a movement command.

`displayUpdate()` checks whether temporary faces have expired, restores the base
face when needed, and advances either RoboEyes or a custom renderer.

## Example: Gait Command

Input:

```text
gait forward --steps 2 --speed 0.02 --step-len 35 --step-ht 20
```

Flow:

1. `serialProtocolUpdate()` reads the line.
2. `parseCommand()` calls the text parser.
3. The parser fills a `RobotCommand` with `type = ROBOT_CMD_GAIT`.
4. `routeCommand()` validates numeric values, direction, and motion bounds.
5. The router calls `robotCommandGait(command.gait)`.
6. `robotCommandGait()` stops conflicting motion if needed.
7. `gaitStart()` clamps and stores gait parameters, sets tripod gait globals,
   and starts the tripod engine.
8. The router sends a gait acknowledgement immediately.
9. Later `loop()` passes call `robotUpdate()`.
10. `robotUpdate()` calls `gaitUpdate()` while mode is `ROBOT_MODE_GAIT`.
11. `gaitUpdate()` calls `updateTripodGait()`.
12. `updateTripodGait()` computes foot offsets and calls `legIK()` for each leg.
13. `legIK()` solves joint angles and calls `servoWriteRaw()`.
14. When the requested steps are complete, gait stops and `robotUpdate()` emits:

```json
{"event":"done","cmd":"gait","state":"standing"}
```

## Example: Face Command

Input:

```json
{"cmd":"face","name":"clock","time":"10:30","duration_ms":5000}
```

Flow:

1. `serialProtocolUpdate()` reads the line.
2. `parseCommand()` calls the JSON parser.
3. The parser fills `RobotCommand` with `type = ROBOT_CMD_FACE`, face name,
   text, and duration.
4. `routeCommand()` validates the face name with `displayParseFaceName()`.
5. The router calls `displaySetFaceText()`.
6. The router calls `displaySetTemporaryFace()`.
7. Later `loop()` passes call `displayUpdate()`.
8. The display controller renders the clock face until the temporary duration
   expires, then restores the base face.

## Status And Events

The firmware responds in compact JSON.

Ready:

```json
{"event":"ready","firmware":"hexapod","protocol":1}
```

ACK:

```json
{"ok":true,"cmd":"stand"}
```

Error:

```json
{"ok":false,"error":"invalid_direction","dir":"sideways"}
```

Done:

```json
{"event":"done","cmd":"gait","state":"standing"}
```

`status` responses are assembled by `robotGetStatus()` and include current mode,
active command, face state, gait progress, rotate progress, camera pan state,
and last error when relevant.

## Safety Model

- Hosts command intent, not servo angles.
- Parser/router code rejects malformed, ambiguous, and unsafe input early.
- Controllers clamp accepted values against `config.h` limits.
- The robot controller stops conflicting behaviors before starting new ones.
- Long behavior remains interruptible because it advances from `loop()`.
- IK centralizes leg geometry, mirroring, and trims.
- Servo writes clamp angles to `0..180`.

This software model does not replace mechanical safety. Power, servo load,
calibration, physical joint limits, and clearances still matter.

## Host-Side Layers

The Python bridge mirrors the firmware boundary by building semantic command
dicts, validating them, sending newline-delimited JSON, and parsing firmware
responses.

Useful files:

- `bridge/robot_commands.py`
- `bridge/serial_robot_bridge.py`
- `bridge/response_parser.py`
- `test_robot_bridge_cli.py`

The local Gemma agent loop treats model output as untrusted data and only allows
validated tool requests. See:

- `docs/LOCAL_GEMMA_AGENT.md`
- `docs/AGENT_OUTPUT_CONTRACT.md`

AI, voice, and host applications should use the bridge or deterministic tool
executor. They should not write raw serial strings or hardware-level fields.

## Legacy Debug Tests

These files preserve manual calibration and debug workflows:

- `src/sitting_test.cpp`
- `src/rotate_test.cpp`
- `src/rotate_loop_test.cpp`
- `src/body_motion_test.cpp`
- `src/tripod_gait.cpp`
- `src/wave.cpp`
- `src/menu.cpp`

Some contain interactive serial handling or waits that are acceptable inside
debug modes. The command protocol is the preferred path for host, Python, and AI
control.

## Adding A New Command

1. Add or extend command data in `include/types.h`.
2. Parse the command in `src/command_parser.cpp`.
3. Route it in `src/command_router.cpp`.
4. Add a robot API in `robot_controller` if it affects mode or motion.
5. Implement long-running behavior as a non-blocking controller.
6. Add display coupling if the command should affect expression.
7. Add host bridge support if the command should be available off-board.
8. Build with `pio run`.

New long-running code should use `millis()` and stored state. It should advance
one pose, phase, or frame per update call and return.

## Adding A New Face

1. Add a `FaceState` value in `include/display_controller.h`.
2. Add the semantic name in `displayFaceName()`.
3. Add parser support in `displayParseFaceName()`.
4. Implement the expression in `applyFace()` or `drawCustomFace()`.
5. If it is custom animated, include it in `isCustomFace()`.
6. Add a serial monitor example.
7. Build with `pio run`.

Prefer semantic face names. Do not add arbitrary host-controlled pixels or
bitmaps unless the safety model is deliberately changed.
