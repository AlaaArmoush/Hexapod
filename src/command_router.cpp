#include "command_router.h"
#include "robot_controller.h"
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
  Serial.print("\",\"gait\":");
  Serial.print(status.gaitRunning ? "true" : "false");
  Serial.print(",\"rotate\":");
  Serial.print(status.rotateRunning ? "true" : "false");
  Serial.print(",\"gesture\":");
  Serial.print(status.gestureRunning ? "true" : "false");
  Serial.println("}");
}

void routeCommand(const RobotCommand& command) {
  bool ok = false;

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
      ok = robotCommandGait(command.gait);
      break;
    case ROBOT_CMD_ROTATE:
      ok = robotCommandRotate(command.rotate);
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
      serialSendError("unknown_command");
      return;
  }

  if (ok) serialSendOk(commandName(command.type));
  else serialSendError("invalid_params");
}
