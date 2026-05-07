#include "command_parser.h"
#include "config.h"
#include <Arduino.h>
#include <ArduinoJson.h>
#include <ctype.h>
#include <stdlib.h>
#include <string.h>

static bool equalsIgnoreCase(const char* a, const char* b) {
  if (!a || !b) return false;
  while (*a && *b) {
    if (tolower(*a) != tolower(*b)) return false;
    a++;
    b++;
  }
  return *a == '\0' && *b == '\0';
}

static RobotCommandType commandTypeFromName(const char* name) {
  if (equalsIgnoreCase(name, "ping")) return ROBOT_CMD_PING;
  if (equalsIgnoreCase(name, "status")) return ROBOT_CMD_STATUS;
  if (equalsIgnoreCase(name, "stand")) return ROBOT_CMD_STAND;
  if (equalsIgnoreCase(name, "sit")) return ROBOT_CMD_SIT;
  if (equalsIgnoreCase(name, "stop")) return ROBOT_CMD_STOP;
  if (equalsIgnoreCase(name, "gait")) return ROBOT_CMD_GAIT;
  if (equalsIgnoreCase(name, "rotate")) return ROBOT_CMD_ROTATE;
  if (equalsIgnoreCase(name, "wave")) return ROBOT_CMD_WAVE;
  if (equalsIgnoreCase(name, "body")) return ROBOT_CMD_BODY;
  if (equalsIgnoreCase(name, "gesture")) return ROBOT_CMD_GESTURE;
  return ROBOT_CMD_NONE;
}

static bool parseGaitDir(const char* dir, GaitCommand& out) {
  if (equalsIgnoreCase(dir, "forward")) out.dir = GAIT_DIR_FORWARD;
  else if (equalsIgnoreCase(dir, "backward") || equalsIgnoreCase(dir, "back")) out.dir = GAIT_DIR_BACKWARD;
  else if (equalsIgnoreCase(dir, "left")) out.dir = GAIT_DIR_LEFT;
  else if (equalsIgnoreCase(dir, "right")) out.dir = GAIT_DIR_RIGHT;
  else if (equalsIgnoreCase(dir, "forward_left")) out.dir = GAIT_DIR_FORWARD_LEFT;
  else if (equalsIgnoreCase(dir, "forward_right")) out.dir = GAIT_DIR_FORWARD_RIGHT;
  else if (equalsIgnoreCase(dir, "backward_left") || equalsIgnoreCase(dir, "back_left")) out.dir = GAIT_DIR_BACKWARD_LEFT;
  else if (equalsIgnoreCase(dir, "backward_right") || equalsIgnoreCase(dir, "back_right")) out.dir = GAIT_DIR_BACKWARD_RIGHT;
  else return false;
  return true;
}

static int parseLeg(const char* leg) {
  if (!leg) return 3;
  if (equalsIgnoreCase(leg, "LF")) return 0;
  if (equalsIgnoreCase(leg, "LM")) return 1;
  if (equalsIgnoreCase(leg, "LB")) return 2;
  if (equalsIgnoreCase(leg, "RF")) return 3;
  if (equalsIgnoreCase(leg, "RM")) return 4;
  if (equalsIgnoreCase(leg, "RB")) return 5;
  return atoi(leg);
}

static void copyGestureName(GestureCommand& command, const char* name) {
  if (!name) name = "idle";
  strncpy(command.name, name, sizeof(command.name) - 1);
  command.name[sizeof(command.name) - 1] = '\0';
}

static ParseResult parseJson(const char* line, RobotCommand& out) {
  JsonDocument doc;
  DeserializationError error = deserializeJson(doc, line);
  if (error) return PARSE_MALFORMED;

  const char* cmd = doc["cmd"] | "";
  out.type = commandTypeFromName(cmd);

  if (out.type == ROBOT_CMD_STOP) {
    const char* mode = doc["mode"] | "smooth";
    out.stopMode = equalsIgnoreCase(mode, "emergency") ? STOP_MODE_EMERGENCY : STOP_MODE_SMOOTH;
  } else if (out.type == ROBOT_CMD_GAIT) {
    const char* dir = doc["dir"] | "forward";
    if (!parseGaitDir(dir, out.gait)) {
      out.gait.dir = GAIT_DIR_CUSTOM;
      out.gait.x = doc["x"] | 0.0f;
      out.gait.y = doc["y"] | 0.0f;
    }
    out.gait.speed = doc["speed"] | 0.0f;
    out.gait.stepLength = doc["step_len"] | 0.0f;
    if (out.gait.stepLength <= 0.0f) out.gait.stepLength = doc["stepLength"] | 0.0f;
    out.gait.stepHeight = doc["step_ht"] | 0.0f;
    if (out.gait.stepHeight <= 0.0f) out.gait.stepHeight = doc["stepHeight"] | 0.0f;
  } else if (out.type == ROBOT_CMD_ROTATE) {
    const char* dir = doc["dir"] | "left";
    out.rotate.dir = equalsIgnoreCase(dir, "right") ? LOOP_RIGHT : LOOP_LEFT;
    out.rotate.cycles = doc["cycles"] | 0;
    out.rotate.degrees = doc["degrees"] | 0;
    out.rotate.continuous = doc["continuous"] | false;
  } else if (out.type == ROBOT_CMD_WAVE) {
    const char* leg = doc["leg"] | "RF";
    out.wave.leg = parseLeg(leg);
    out.wave.count = doc["count"] | 2;
  } else if (out.type == ROBOT_CMD_BODY) {
    out.body.x = doc["x"] | 0.0f;
    out.body.y = doc["y"] | 0.0f;
    out.body.z = doc["z"] | 0.0f;
  } else if (out.type == ROBOT_CMD_GESTURE) {
    copyGestureName(out.gesture, doc["name"] | "idle");
    out.gesture.intensity = doc["intensity"] | 0.5f;
  }

  return PARSE_OK;
}

static ParseResult parseText(char* line, RobotCommand& out) {
  char* token = strtok(line, " \t\r\n");
  if (!token) return PARSE_EMPTY;

  out.type = commandTypeFromName(token);

  if (out.type == ROBOT_CMD_GAIT) {
    char* dir = strtok(nullptr, " \t\r\n");
    if (!parseGaitDir(dir ? dir : "forward", out.gait)) return PARSE_MALFORMED;
    char* speed = strtok(nullptr, " \t\r\n");
    if (speed) out.gait.speed = atof(speed);
  } else if (out.type == ROBOT_CMD_ROTATE) {
    char* dir = strtok(nullptr, " \t\r\n");
    out.rotate.dir = equalsIgnoreCase(dir, "right") ? LOOP_RIGHT : LOOP_LEFT;
    char* cycles = strtok(nullptr, " \t\r\n");
    if (cycles) out.rotate.cycles = atoi(cycles);
    else out.rotate.continuous = true;
  } else if (out.type == ROBOT_CMD_WAVE) {
    char* firstArg = strtok(nullptr, " \t\r\n");
    char* secondArg = strtok(nullptr, " \t\r\n");
    if (firstArg) {
      if (isalpha(firstArg[0])) {
        out.wave.leg = parseLeg(firstArg);
        if (secondArg) out.wave.count = atoi(secondArg);
      } else {
        out.wave.count = atoi(firstArg);
      }
    }
  } else if (out.type == ROBOT_CMD_GESTURE) {
    char* name = strtok(nullptr, " \t\r\n");
    copyGestureName(out.gesture, name ? name : "idle");
  }

  return PARSE_OK;
}

ParseResult parseCommand(const char* line, RobotCommand& out) {
  out = RobotCommand();
  if (!line) return PARSE_EMPTY;

  while (*line == ' ' || *line == '\t' || *line == '\r' || *line == '\n') line++;
  if (*line == '\0') return PARSE_EMPTY;

  if (*line == '{') return parseJson(line, out);

  char buffer[96];
  strncpy(buffer, line, sizeof(buffer) - 1);
  buffer[sizeof(buffer) - 1] = '\0';
  return parseText(buffer, out);
}
