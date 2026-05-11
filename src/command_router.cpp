#include "command_router.h"
#include "gait_controller.h"
#include "robot_controller.h"
#include "rotate_controller.h"
#include "serial_protocol.h"
#include <Arduino.h>

static const char* commandName(RobotCommandType type) {
  switch (type) {
    case ROBOT_CMD_PING: return "ping";
    case ROBOT_CMD_STATUS: return "status";
    case ROBOT_CMD_STAND: return "stand";
    case ROBOT_CMD_SIT: return "sit";
    case ROBOT_CMD_STOP: return "stop";
    case ROBOT_CMD_GAIT: return "gait";
    case ROBOT_CMD_ROTATE: return "rotate";
    case ROBOT_CMD_WAVE: return "wave";
    case ROBOT_CMD_BODY: return "body";
    case ROBOT_CMD_GESTURE: return "gesture";
    case ROBOT_CMD_NONE: return "unknown";
  }
  return "unknown";
}

static void sendStatus() {
  RobotStatus status = robotGetStatus();
  Serial.print("{\"ok\":true,\"cmd\":\"status\",\"mode\":\"");
  Serial.print(robotModeName(status.mode));
  Serial.print("\",\"active_cmd\":\"");
  Serial.print(status.activeCmd);
  Serial.print("\",\"dir\":\"");
  Serial.print(status.dir);
  Serial.print("\",\"speed\":");
  Serial.print(status.speed, 3);
  Serial.print(",\"bound\":\"");
  Serial.print(status.bound);
  Serial.print("\",\"steps_target\":");
  Serial.print(status.stepsTarget);
  Serial.print(",\"steps_done\":");
  Serial.print(status.stepsDone);
  Serial.print(",\"duration_target_ms\":");
  Serial.print(status.durationTargetMs);
  Serial.print(",\"duration_elapsed_ms\":");
  Serial.print(status.durationElapsedMs);
  Serial.print(",\"distance_target_cm\":");
  Serial.print(status.distanceTargetCm, 1);
  Serial.print(",\"rotate_cycles_target\":");
  Serial.print(status.rotateCyclesTarget);
  Serial.print(",\"rotate_cycles_done\":");
  Serial.print(status.rotateCyclesDone);
  Serial.print(",\"rotate_continuous\":");
  Serial.print(status.rotateContinuous ? "true" : "false");
  Serial.print(",\"interruptible\":");
  Serial.print(status.interruptible ? "true" : "false");
  Serial.print(",\"last_error\":\"");
  Serial.print(status.lastError);
  Serial.print("\"");
  Serial.println("}");
}

static void sendError(const char* error) {
  robotSetLastError(error);
  serialSendError(error);
}

static void sendUnknownCommand(const RobotCommand& command) {
  robotSetLastError("unknown_command");
  Serial.print("{\"ok\":false,\"error\":\"unknown_command\",\"cmd\":\"");
  Serial.print(command.cmdName);
  Serial.println("\"}");
}

static void sendInvalidDirection(const char* dir) {
  robotSetLastError("invalid_direction");
  Serial.print("{\"ok\":false,\"error\":\"invalid_direction\",\"dir\":\"");
  Serial.print(dir ? dir : "");
  Serial.println("\"}");
}

static void sendGaitAck(const GaitCommand& command) {
  Serial.print("{\"ok\":true,\"cmd\":\"gait\",\"state\":\"walking\",\"bound\":\"");
  Serial.print(motionBoundName(command.bound));
  Serial.print("\"");
  if (command.bound == MOTION_BOUND_DURATION_MS) {
    Serial.print(",\"duration_ms\":");
    Serial.print(gaitDurationTargetMs());
  } else if (command.bound == MOTION_BOUND_STEPS) {
    Serial.print(",\"steps\":");
    Serial.print(gaitStepsTarget());
  } else if (command.bound == MOTION_BOUND_DISTANCE_CM) {
    Serial.print(",\"distance_cm\":");
    Serial.print(command.distanceCm, 1);
    Serial.print(",\"estimated_steps\":");
    Serial.print(gaitStepsTarget());
  }
  Serial.println("}");
}

static void sendRotateAck(const RotateCommand& command) {
  Serial.print("{\"ok\":true,\"cmd\":\"rotate\",\"state\":\"rotating\",\"dir\":\"");
  Serial.print(command.dir == LOOP_RIGHT ? "right" : "left");
  Serial.print("\"");
  if (command.continuous) {
    Serial.print(",\"bound\":\"continuous\"");
  } else {
    Serial.print(",\"bound\":\"cycles\",\"cycles\":");
    Serial.print(rotateCyclesTarget());
  }
  Serial.println("}");
}

void routeCommand(const RobotCommand& command) {
  bool ok = false;

  if (command.rawServoControl) {
    sendError("raw_servo_control_not_allowed");
    return;
  }
  if (command.invalidNumeric) {
    sendError("invalid_numeric_parameter");
    return;
  }

  switch (command.type) {
    case ROBOT_CMD_PING:
      serialSendOk("ping");
      return;
    case ROBOT_CMD_STATUS:
      sendStatus();
      return;
    case ROBOT_CMD_STAND:
      ok = robotCommandStand();
      break;
    case ROBOT_CMD_SIT:
      ok = robotCommandSit();
      break;
    case ROBOT_CMD_STOP:
      ok = robotCommandStop(command.stopMode);
      break;
    case ROBOT_CMD_GAIT:
      if (command.gait.ambiguousBound) {
        sendError("ambiguous_gait_bound");
        return;
      }
      if (command.gait.invalidDirection) {
        sendInvalidDirection(command.gait.dirName);
        return;
      }
      ok = robotCommandGait(command.gait);
      if (ok) {
        robotSetLastError("");
        sendGaitAck(gaitCurrentCommand());
        return;
      }
      break;
    case ROBOT_CMD_ROTATE:
      if (command.rotate.ambiguousBound) {
        sendError("ambiguous_rotate_bound");
        return;
      }
      if (command.rotate.invalidDirection) {
        sendInvalidDirection(command.rotate.dirName);
        return;
      }
      ok = robotCommandRotate(command.rotate);
      if (ok) {
        robotSetLastError("");
        sendRotateAck(rotateCurrentCommand());
        return;
      }
      break;
    case ROBOT_CMD_WAVE:
      ok = robotCommandWave(command.wave);
      break;
    case ROBOT_CMD_BODY:
      ok = robotCommandBody(command.body);
      break;
    case ROBOT_CMD_GESTURE:
      ok = robotCommandGesture(command.gesture);
      break;
    case ROBOT_CMD_NONE:
      sendUnknownCommand(command);
      return;
  }

  if (ok) {
    robotSetLastError("");
    serialSendOk(commandName(command.type));
  } else {
    sendError("invalid_numeric_parameter");
  }
}
