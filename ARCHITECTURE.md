# Firmware Architecture

This firmware uses a command-driven architecture. The ESP32 owns low-level
motion, timing, IK, and servo control.
A laptop, Raspberry Pi, or AI bridge can send high-level serial commands such as `stand`, `sit`, `gait`, `rotate`, and
`wave`.

For build/upload/test steps, see `command_architecture_guide.txt`.

## Command Flow

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
- raw servo angle writes

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

Rule: motion controllers should advance a small amount per `robotUpdate()` call.
They should not sit in long `delay()` loops.

### Robot Controller

Files:

- `include/robot_controller.h`
- `src/robot_controller.cpp`

Responsibilities:

- own the current `RobotMode`
- stop conflicting motions before starting a new one
- expose a clean API such as `robotCommandStand()` and `robotCommandGait()`
- update active controllers from the main loop

### Protocol

Files:

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
- route commands to `robot_controller`
- return JSON ACK/error/status messages

Preferred command style:

```json
{"cmd":"stand"}
{"cmd":"gait","dir":"forward","speed":0.02}
{"cmd":"stop"}
```

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
  debugMenuUpdate();
  delay(5);
}
```

The important property is that the loop keeps running. Commands like status or
stop should still be handled while a motion is active.

## Adding A New Command

Use this order:

1. Add or extend command data in `include/types.h`.
2. Parse the command in `src/command_parser.cpp`.
3. Route it in `src/command_router.cpp`.
4. Add a robot API function in `robot_controller` if needed.
5. Implement the actual motion in a controller or pose helper.
6. Build with `python3 -m platformio run`.

## Safety Rules

- Keep new motions non-blocking when possible.
- Start with low speeds and small offsets.
- Do not casually edit servo trims, channels, or IK mount angles.
- Stop gait/rotate before applying sit or stand.
- Keep high-level commands semantic. Do not make the host send raw servo angles.
