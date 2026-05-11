# Firmware Architecture

This firmware uses a command-driven architecture. The ESP32 owns low-level
timing, motion state, inverse kinematics, OLED expression state, and servo
control. A laptop, Raspberry Pi, or AI bridge sends high-level newline-delimited
serial commands such as `stand`, `gait`, `rotate`, `face`, `look`, `nod`, and
`idle`.

The host should describe intent, not servo angles or raw display pixels. The
firmware translates semantic commands into safe body motion, face animation, IK,
and PCA9685 writes.

## Command Flow

Motion commands follow this path:

```text
Serial line
  -> serial_protocol.cpp
  -> command_parser.cpp
  -> command_router.cpp
  -> robot_controller.cpp
  -> motion controller / pose helper
  -> ik.cpp
  -> servo_driver.cpp
  -> PCA9685 boards
```

Face/display commands follow this path:

```text
Serial line
  -> serial_protocol.cpp
  -> command_parser.cpp
  -> command_router.cpp
  -> display_controller.cpp
  -> Adafruit_SH1107 / RoboEyes / pixel-art drawing
  -> SH1107 OLED
```

Many commands touch both paths. For example, `look`, `nod`, `shake`, `gait`, and
`wave` move the body and also set a matching OLED face.

## Layers

### Hardware

Files:

- `include/config.h`
- `include/servo_driver.h`
- `src/servo_driver.cpp`

Responsibilities:

- I2C pins
- PCA9685 setup constants
- servo channels
- trim offsets
- safe motion/display tuning constants
- raw servo angle writes used internally by low-level code

The host command API should not expose raw servo writes.

### Kinematics

Files:

- `include/ik.h`
- `src/ik.cpp`

Responsibilities:

- leg geometry
- leg mount table
- IK solving
- writing IK results to the servos

`legIK()` solves and writes. `solveLegIK()` solves without writing.

### Poses

Files:

- `include/poses.h`
- `src/poses.cpp`

Responsibilities:

- stand
- sit
- body offset
- simple non-blocking pose transitions

The sit pose uses the same target deltas as the old `sitting` branch global
`sit()` function.

### Motion Controllers

Files:

- `include/gait_controller.h`
- `src/gait_controller.cpp`
- `include/rotate_controller.h`
- `src/rotate_controller.cpp`
- `include/gesture_controller.h`
- `src/gesture_controller.cpp`

Responsibilities:

- start/stop/update motion behaviors
- clamp command parameters
- avoid blocking the serial loop
- wrap older motion code where useful
- implement expressive body motions

`gesture_controller` now owns more than named gestures and wave. It also handles
expressive motions:

- `lean`
- `look`
- `nod`
- `shake`
- `idle breathing`
- `idle sway`
- named gestures such as `happy`, `curious`, `scared`, `sleepy`, and
  `listening`

Rule: motion controllers should advance a small amount per `robotUpdate()` call.
They should not sit in long `delay()` loops.

### Display / Expression Controller

Files:

- `include/display_controller.h`
- `src/display_controller.cpp`
- `lib/RoboEyes/FluxGarage_RoboEyes.h`

Responsibilities:

- initialize the SH1107 OLED
- own persistent and temporary face state
- update RoboEyes non-blockingly from `displayUpdate()`
- draw custom animated pixel-art faces
- parse and expose semantic face names
- support gaze direction and blink events
- restore temporary faces back to the base face

The display controller supports two kinds of expressions:

- RoboEyes-based faces, such as `idle`, `neutral`, `happy`, `curious`,
  `scared`, `sleepy`, `listening`, `walking`, `rotating`, and `waving`
- custom pixel-art faces, such as `error`, `love`, `surprised`, `starstruck`,
  `dizzy`, `confused`, `sad`, `sleep`, `loading`, `alert`, `low_battery`,
  `boop`, and `scan`

Direct expressive face commands are temporary by default. `idle` and `neutral`
are persistent base faces. The host can request persistence with:

```json
{"cmd":"face","name":"surprised","persistent":true}
```

### Robot Controller

Files:

- `include/robot_controller.h`
- `src/robot_controller.cpp`

Responsibilities:

- own the current `RobotMode`
- stop conflicting motions before starting a new one
- expose a clean API such as `robotCommandStand()` and `robotCommandGait()`
- update active controllers from the main loop
- couple robot mode and gesture state to OLED face state

The robot controller is the bridge between motion and expression. Examples:

- idle mode sets the idle face
- standing mode sets the neutral face
- sitting mode sets the sleepy face
- gait uses the walking face while active
- rotate uses the rotating face while active
- wave uses the waving face while active
- gesture names map to matching faces
- `nod`, `shake`, `lean`, and `look` set temporary or persistent expressive
  faces

### Protocol

Files:

- `include/types.h`
- `include/serial_protocol.h`
- `src/serial_protocol.cpp`
- `include/command_parser.h`
- `src/command_parser.cpp`
- `include/command_router.h`
- `src/command_router.cpp`

Responsibilities:

- read newline-terminated serial commands
- parse JSON commands first
- support simple fallback text commands
- validate directions, numeric fields, bounds, and semantic face names
- reject raw servo/display-control fields
- route commands to `robot_controller` and `display_controller`
- return JSON ACK/error/status messages

Preferred command style:

```json
{"cmd":"stand"}
{"cmd":"gait","dir":"forward","speed":0.02,"steps":2}
{"cmd":"face","name":"starstruck"}
{"cmd":"look","dir":"left","duration_ms":1200}
{"cmd":"idle","style":"breathing"}
{"cmd":"stop"}
```

Important command families:

- posture: `stand`, `sit`, `stop`
- locomotion: `gait`, `rotate`
- gestures: `wave`, `gesture`
- expressive body: `lean`, `look`, `nod`, `shake`, `idle` with `style`
- display: `face`, `blink`
- diagnostics: `ping`, `status`

The `status` response includes face state:

```json
{
  "ok": true,
  "cmd": "status",
  "mode": "gesture",
  "active_cmd": "look",
  "gesture": "look",
  "face": "listening",
  "face_temporary": true
}
```

The real response includes additional motion fields for gait, rotate, duration,
steps, distance, and errors.

### Legacy Debug Tests

Files include:

- `src/sitting_test.cpp`
- `src/rotate_test.cpp`
- `src/rotate_loop_test.cpp`
- `src/body_motion_test.cpp`
- `src/tripod_gait.cpp`
- `src/wave.cpp`
- `src/menu.cpp`

These are kept for calibration/debug workflows. The command protocol is the
preferred control path for Python or AI bridge work.

## Main Loop

`src/main.cpp` is intentionally small:

```cpp
void loop() {
  serialProtocolUpdate();
  robotUpdate();
  displayUpdate();
#if ENABLE_DEBUG_MENU
  debugMenuUpdate();
#endif
  delay(5);
}
```

The important property is that the loop keeps running. Commands like `status`
or `stop` should still be handled while a motion or OLED animation is active.

## Adding A New Command

Use this order:

1. Add or extend command data in `include/types.h`.
2. Parse the command in `src/command_parser.cpp`.
3. Route it in `src/command_router.cpp`.
4. Add a robot API function in `robot_controller` if it affects motion or mode.
5. Implement the actual motion in a controller or pose helper.
6. Add or update display coupling in `robot_controller` or
   `display_controller` if the command should affect expression.
7. Add test commands to `tests_serial_monitor.txt`.
8. Build with `pio run`.

## Adding A New Face

Use this order:

1. Add a `FaceState` value in `include/display_controller.h`.
2. Add the semantic name in `displayFaceName()`.
3. Add parser support in `displayParseFaceName()`.
4. Implement the expression in `applyFace()` or `drawCustomFace()`.
5. If it is pixel-art or custom animated, include it in `isCustomFace()`.
6. Add a serial test command to `tests_serial_monitor.txt`.
7. Build with `pio run`.

Prefer semantic face names. Do not add a host command that sends arbitrary
pixels or bitmaps unless the safety model is deliberately changed.