#include "command_parser.h"
#include "config.h"
#include "util.h"
#include <Arduino.h>
#include <ArduinoJson.h>
#include <stdlib.h>
#include <string.h>

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
  if (equalsIgnoreCase(name, "face")) return ROBOT_CMD_FACE;
  if (equalsIgnoreCase(name, "blink")) return ROBOT_CMD_BLINK;
  if (equalsIgnoreCase(name, "lean")) return ROBOT_CMD_LEAN;
  if (equalsIgnoreCase(name, "look")) return ROBOT_CMD_LOOK;
  if (equalsIgnoreCase(name, "nod")) return ROBOT_CMD_NOD;
  if (equalsIgnoreCase(name, "shake")) return ROBOT_CMD_SHAKE;
  if (equalsIgnoreCase(name, "idle")) return ROBOT_CMD_IDLE_STYLE;
  if (equalsIgnoreCase(name, "camera_pan")) return ROBOT_CMD_CAMERA_PAN;
  if (equalsIgnoreCase(name, "camera_center")) return ROBOT_CMD_CAMERA_PAN;
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

static void copyFaceName(FaceCommand& command, const char* name) {
  if (!name) name = "idle";
  strncpy(command.name, name, sizeof(command.name) - 1);
  command.name[sizeof(command.name) - 1] = '\0';
}

static void copyFaceText(FaceCommand& command, const char* text) {
  if (!text) {
    command.text[0] = '\0';
    command.hasText = false;
    return;
  }
  strncpy(command.text, text, sizeof(command.text) - 1);
  command.text[sizeof(command.text) - 1] = '\0';
  command.hasText = command.text[0] != '\0';
}

static bool isLeanDirection(const char* dir) {
  return equalsIgnoreCase(dir, "left") || equalsIgnoreCase(dir, "right") ||
         equalsIgnoreCase(dir, "forward") || equalsIgnoreCase(dir, "backward") ||
         equalsIgnoreCase(dir, "back");
}

static bool isLookDirection(const char* dir) {
  return equalsIgnoreCase(dir, "left") || equalsIgnoreCase(dir, "right") ||
         equalsIgnoreCase(dir, "up") || equalsIgnoreCase(dir, "down") ||
         equalsIgnoreCase(dir, "center");
}

static bool isIdleStyle(const char* style) {
  return equalsIgnoreCase(style, "breathing") || equalsIgnoreCase(style, "sway");
}

static bool parseCameraPanPos(const char* pos, CameraPanCommand& out) {
  if (equalsIgnoreCase(pos, "left")) out.pos = CAM_PAN_LEFT;
  else if (equalsIgnoreCase(pos, "front_left") || equalsIgnoreCase(pos, "slight_left")) out.pos = CAM_PAN_FRONT_LEFT;
  else if (equalsIgnoreCase(pos, "center")) out.pos = CAM_PAN_CENTER;
  else if (equalsIgnoreCase(pos, "front_right") || equalsIgnoreCase(pos, "slight_right")) out.pos = CAM_PAN_FRONT_RIGHT;
  else if (equalsIgnoreCase(pos, "right")) out.pos = CAM_PAN_RIGHT;
  else return false;
  return true;
}

static bool hasRawServoField(JsonDocument& doc) {
  return !doc["servo"].isNull() ||
         !doc["angle"].isNull() ||
         !doc["pwm"].isNull() ||
         !doc["board"].isNull() ||
         !doc["channel"].isNull() ||
         !doc["pixel"].isNull() ||
         !doc["bitmap"].isNull() ||
         !doc["raw"].isNull();
}

static bool invalidNumber(JsonDocument& doc, const char* key) {
  if (doc[key].isNull()) return false;
  return !(doc[key].is<int>() || doc[key].is<float>() || doc[key].is<double>());
}

static bool parseTextFloat(const char* value, float& out) {
  if (!value || value[0] == '\0') return false;
  char* end = nullptr;
  float parsed = strtof(value, &end);
  if (end == value || *end != '\0') return false;
  out = parsed;
  return true;
}

static bool parseTextInt(const char* value, int& out) {
  if (!value || value[0] == '\0') return false;
  char* end = nullptr;
  long parsed = strtol(value, &end, 10);
  if (end == value || *end != '\0') return false;
  out = (int)parsed;
  return true;
}

static bool parseTextUnsignedLong(const char* value, unsigned long& out) {
  if (!value || value[0] == '\0') return false;
  char* end = nullptr;
  unsigned long parsed = strtoul(value, &end, 10);
  if (end == value || *end != '\0') return false;
  out = parsed;
  return true;
}

static bool tokenLooksFloat(const char* value) {
  if (!value) return false;
  while (*value) {
    if (*value == '.') return true;
    value++;
  }
  return false;
}

static ParseResult parseJson(const char* line, RobotCommand& out) {
  JsonDocument doc;
  DeserializationError error = deserializeJson(doc, line);
  if (error) return PARSE_MALFORMED;

  const char* cmd = doc["cmd"] | "";
  strncpy(out.cmdName, cmd, sizeof(out.cmdName) - 1);
  out.cmdName[sizeof(out.cmdName) - 1] = '\0';
  out.type = commandTypeFromName(cmd);
  if (equalsIgnoreCase(cmd, "idle") && doc["style"].isNull()) {
    out.type = ROBOT_CMD_NONE;
  }
  out.rawServoControl = hasRawServoField(doc);

  if (out.type == ROBOT_CMD_GAIT) {
    const char* dir = doc["dir"] | "forward";
    strncpy(out.gait.dirName, dir, sizeof(out.gait.dirName) - 1);
    out.gait.dirName[sizeof(out.gait.dirName) - 1] = '\0';
    if (!parseGaitDir(dir, out.gait)) {
      out.gait.invalidDirection = true;
    }
    int boundCount = 0;
    if (!doc["duration_ms"].isNull()) { out.gait.bound = MOTION_BOUND_DURATION_MS; boundCount++; }
    if (!doc["steps"].isNull()) { out.gait.bound = MOTION_BOUND_STEPS; boundCount++; }
    if (!doc["distance_cm"].isNull()) { out.gait.bound = MOTION_BOUND_DISTANCE_CM; boundCount++; }
    out.gait.ambiguousBound = boundCount > 1;

    out.gait.invalidNumeric =
      invalidNumber(doc, "speed") || invalidNumber(doc, "step_len") ||
      invalidNumber(doc, "stepLength") || invalidNumber(doc, "step_ht") ||
      invalidNumber(doc, "stepHeight") || invalidNumber(doc, "duration_ms") ||
      invalidNumber(doc, "steps") || invalidNumber(doc, "distance_cm");
    out.gait.speed = doc["speed"] | 0.0f;
    out.gait.stepLength = doc["step_len"] | 0.0f;
    if (out.gait.stepLength <= 0.0f) out.gait.stepLength = doc["stepLength"] | 0.0f;
    out.gait.stepHeight = doc["step_ht"] | 0.0f;
    if (out.gait.stepHeight <= 0.0f) out.gait.stepHeight = doc["stepHeight"] | 0.0f;
    out.gait.durationMs = doc["duration_ms"] | 0UL;
    out.gait.steps = doc["steps"] | 0;
    out.gait.distanceCm = doc["distance_cm"] | 0.0f;
    if ((out.gait.bound == MOTION_BOUND_DURATION_MS && out.gait.durationMs == 0) ||
        (out.gait.bound == MOTION_BOUND_STEPS && out.gait.steps <= 0) ||
        (out.gait.bound == MOTION_BOUND_DISTANCE_CM && out.gait.distanceCm <= 0.0f) ||
        out.gait.speed < 0.0f || out.gait.stepLength < 0.0f || out.gait.stepHeight < 0.0f) {
      out.gait.invalidNumeric = true;
    }
  } else if (out.type == ROBOT_CMD_ROTATE) {
    const char* dir = doc["dir"] | "left";
    strncpy(out.rotate.dirName, dir, sizeof(out.rotate.dirName) - 1);
    out.rotate.dirName[sizeof(out.rotate.dirName) - 1] = '\0';
    if (equalsIgnoreCase(dir, "right")) out.rotate.dir = LOOP_RIGHT;
    else if (equalsIgnoreCase(dir, "left")) out.rotate.dir = LOOP_LEFT;
    else out.rotate.invalidDirection = true;

    int boundCount = 0;
    if (!doc["cycles"].isNull()) boundCount++;
    if (!doc["degrees"].isNull()) boundCount++;
    if (!doc["continuous"].isNull()) boundCount++;
    out.rotate.ambiguousBound = boundCount > 1;
    out.rotate.invalidNumeric = invalidNumber(doc, "cycles") || invalidNumber(doc, "degrees");
    out.rotate.cycles = doc["cycles"] | 0;
    out.rotate.degrees = doc["degrees"] | 0;
    out.rotate.continuous = doc["continuous"] | false;
    if (out.rotate.cycles < 0 || out.rotate.degrees < 0) out.rotate.invalidNumeric = true;
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
    if (invalidNumber(doc, "intensity")) out.gesture.intensity = 0.5f;
  } else if (out.type == ROBOT_CMD_FACE) {
    copyFaceName(out.face, doc["name"] | "idle");
    const char* faceText = doc["text"] | (const char*)nullptr;
    if (!faceText && equalsIgnoreCase(out.face.name, "clock")) faceText = doc["time"] | (const char*)nullptr;
    if (!faceText && equalsIgnoreCase(out.face.name, "calendar")) faceText = doc["date"] | (const char*)nullptr;
    copyFaceText(out.face, faceText);
    out.face.invalidFace = invalidNumber(doc, "duration_ms");
    out.face.duration_ms = doc["duration_ms"] | FACE_COMMAND_DURATION_MS;
    out.face.persistent = doc["persistent"] | false;
    if (out.face.duration_ms == 0) out.face.invalidFace = true;
  } else if (out.type == ROBOT_CMD_BLINK) {
    // No parameters.
  } else if (out.type == ROBOT_CMD_LEAN) {
    const char* dir = doc["dir"] | "left";
    strncpy(out.lean.dir, dir, sizeof(out.lean.dir) - 1);
    out.lean.dir[sizeof(out.lean.dir) - 1] = '\0';
    out.lean.invalidDirection = !isLeanDirection(dir);
    out.lean.invalidNumeric = invalidNumber(doc, "amount_mm") || invalidNumber(doc, "duration_ms");
    out.lean.amount_mm = doc["amount_mm"] | 20.0f;
    out.lean.duration_ms = doc["duration_ms"] | 400UL;
    if (out.lean.amount_mm < 0.0f || out.lean.duration_ms == 0) out.lean.invalidNumeric = true;
  } else if (out.type == ROBOT_CMD_LOOK) {
    const char* dir = doc["dir"] | "center";
    strncpy(out.look.dir, dir, sizeof(out.look.dir) - 1);
    out.look.dir[sizeof(out.look.dir) - 1] = '\0';
    out.look.invalidDirection = !isLookDirection(dir);
    out.look.invalidNumeric = invalidNumber(doc, "duration_ms");
    out.look.duration_ms = doc["duration_ms"] | LOOK_DURATION_DEFAULT_MS;
    out.look.persistent = doc["persistent"] | false;
    if (out.look.duration_ms == 0) out.look.invalidNumeric = true;
  } else if (out.type == ROBOT_CMD_NOD || out.type == ROBOT_CMD_SHAKE) {
    out.nodShake.invalidNumeric = invalidNumber(doc, "count");
    out.nodShake.count = doc["count"] | 2;
    if (out.nodShake.count <= 0) out.nodShake.invalidNumeric = true;
  } else if (out.type == ROBOT_CMD_IDLE_STYLE) {
    const char* style = doc["style"] | "breathing";
    strncpy(out.idleStyle.style, style, sizeof(out.idleStyle.style) - 1);
    out.idleStyle.style[sizeof(out.idleStyle.style) - 1] = '\0';
    out.idleStyle.invalidStyle = !isIdleStyle(style);
  } else if (out.type == ROBOT_CMD_CAMERA_PAN) {
    const char* pos = doc["pos"] | "center";
    strncpy(out.cameraPan.posName, pos, sizeof(out.cameraPan.posName) - 1);
    out.cameraPan.posName[sizeof(out.cameraPan.posName) - 1] = '\0';
    out.cameraPan.invalidPos = !parseCameraPanPos(pos, out.cameraPan);
    out.cameraPan.invalidNumeric = invalidNumber(doc, "offset");
    out.cameraPan.offsetDeg = doc["offset"] | 0;
  }

  out.invalidNumeric = out.gait.invalidNumeric || out.rotate.invalidNumeric ||
                       out.lean.invalidNumeric || out.look.invalidNumeric ||
                       out.nodShake.invalidNumeric ||
                       out.face.invalidFace ||
                       out.cameraPan.invalidNumeric;

  return PARSE_OK;
}

static ParseResult parseText(char* line, RobotCommand& out) {
  char* token = strtok(line, " \t\r\n");
  if (!token) return PARSE_EMPTY;

  out.type = commandTypeFromName(token);
  strncpy(out.cmdName, token, sizeof(out.cmdName) - 1);
  out.cmdName[sizeof(out.cmdName) - 1] = '\0';

  if (out.type == ROBOT_CMD_GAIT) {
    char* dir = strtok(nullptr, " \t\r\n");
    strncpy(out.gait.dirName, dir ? dir : "forward", sizeof(out.gait.dirName) - 1);
    out.gait.dirName[sizeof(out.gait.dirName) - 1] = '\0';
    if (!parseGaitDir(dir ? dir : "forward", out.gait)) return PARSE_MALFORMED;
    bool sawBound = false;

    char* arg = strtok(nullptr, " \t\r\n");
    while (arg) {
      if (equalsIgnoreCase(arg, "--speed")) {
        char* value = strtok(nullptr, " \t\r\n");
        if (!parseTextFloat(value, out.gait.speed)) out.gait.invalidNumeric = true;
      } else if (equalsIgnoreCase(arg, "--steps")) {
        char* value = strtok(nullptr, " \t\r\n");
        int steps = 0;
        if (!parseTextInt(value, steps)) out.gait.invalidNumeric = true;
        out.gait.steps = steps;
        out.gait.bound = MOTION_BOUND_STEPS;
        if (sawBound) out.gait.ambiguousBound = true;
        sawBound = true;
      } else if (equalsIgnoreCase(arg, "--duration-ms")) {
        char* value = strtok(nullptr, " \t\r\n");
        unsigned long durationMs = 0;
        if (!parseTextUnsignedLong(value, durationMs)) out.gait.invalidNumeric = true;
        out.gait.durationMs = durationMs;
        out.gait.bound = MOTION_BOUND_DURATION_MS;
        if (sawBound) out.gait.ambiguousBound = true;
        sawBound = true;
      } else if (equalsIgnoreCase(arg, "--distance-cm")) {
        char* value = strtok(nullptr, " \t\r\n");
        float distanceCm = 0.0f;
        if (!parseTextFloat(value, distanceCm)) out.gait.invalidNumeric = true;
        out.gait.distanceCm = distanceCm;
        out.gait.bound = MOTION_BOUND_DISTANCE_CM;
        if (sawBound) out.gait.ambiguousBound = true;
        sawBound = true;
      } else if (equalsIgnoreCase(arg, "--step-len")) {
        char* value = strtok(nullptr, " \t\r\n");
        if (!parseTextFloat(value, out.gait.stepLength)) out.gait.invalidNumeric = true;
      } else if (equalsIgnoreCase(arg, "--step-ht")) {
        char* value = strtok(nullptr, " \t\r\n");
        if (!parseTextFloat(value, out.gait.stepHeight)) out.gait.invalidNumeric = true;
      } else if (arg[0] == '-') {
        out.gait.invalidNumeric = true;
      } else if (tokenLooksFloat(arg)) {
        if (!parseTextFloat(arg, out.gait.speed)) out.gait.invalidNumeric = true;
      } else {
        int steps = 0;
        if (!parseTextInt(arg, steps)) out.gait.invalidNumeric = true;
        out.gait.steps = steps;
        out.gait.bound = MOTION_BOUND_STEPS;
        if (sawBound) out.gait.ambiguousBound = true;
        sawBound = true;
      }
      arg = strtok(nullptr, " \t\r\n");
    }

    if ((out.gait.bound == MOTION_BOUND_DURATION_MS && out.gait.durationMs == 0) ||
        (out.gait.bound == MOTION_BOUND_STEPS && out.gait.steps <= 0) ||
        (out.gait.bound == MOTION_BOUND_DISTANCE_CM && out.gait.distanceCm <= 0.0f) ||
        out.gait.speed < 0.0f || out.gait.stepLength < 0.0f || out.gait.stepHeight < 0.0f) {
      out.gait.invalidNumeric = true;
    }
  } else if (out.type == ROBOT_CMD_ROTATE) {
    char* dir = strtok(nullptr, " \t\r\n");
    strncpy(out.rotate.dirName, dir ? dir : "left", sizeof(out.rotate.dirName) - 1);
    out.rotate.dirName[sizeof(out.rotate.dirName) - 1] = '\0';
    out.rotate.dir = equalsIgnoreCase(dir, "right") ? LOOP_RIGHT : LOOP_LEFT;
    char* cycles = strtok(nullptr, " \t\r\n");
    if (cycles) {
      if (equalsIgnoreCase(cycles, "--continuous")) out.rotate.continuous = true;
      else if (!parseTextInt(cycles, out.rotate.cycles)) out.rotate.invalidNumeric = true;
    } else {
      out.rotate.cycles = ROTATE_CYCLES_DEFAULT;
    }
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
  } else if (out.type == ROBOT_CMD_FACE) {
    char* name = strtok(nullptr, " \t\r\n");
    copyFaceName(out.face, name ? name : "idle");
    char* duration = strtok(nullptr, " \t\r\n");
    if (duration) out.face.duration_ms = strtoul(duration, nullptr, 10);
    if (out.face.duration_ms == 0) out.face.invalidFace = true;
  } else if (out.type == ROBOT_CMD_LEAN) {
    char* dir = strtok(nullptr, " \t\r\n");
    strncpy(out.lean.dir, dir ? dir : "left", sizeof(out.lean.dir) - 1);
    out.lean.dir[sizeof(out.lean.dir) - 1] = '\0';
    out.lean.invalidDirection = !isLeanDirection(out.lean.dir);
    char* amount = strtok(nullptr, " \t\r\n");
    char* duration = strtok(nullptr, " \t\r\n");
    if (amount) out.lean.amount_mm = atof(amount);
    if (duration) out.lean.duration_ms = strtoul(duration, nullptr, 10);
    if (out.lean.amount_mm < 0.0f || out.lean.duration_ms == 0) out.lean.invalidNumeric = true;
  } else if (out.type == ROBOT_CMD_LOOK) {
    char* dir = strtok(nullptr, " \t\r\n");
    strncpy(out.look.dir, dir ? dir : "center", sizeof(out.look.dir) - 1);
    out.look.dir[sizeof(out.look.dir) - 1] = '\0';
    out.look.invalidDirection = !isLookDirection(out.look.dir);
    char* duration = strtok(nullptr, " \t\r\n");
    if (duration) out.look.duration_ms = strtoul(duration, nullptr, 10);
    if (out.look.duration_ms == 0) out.look.invalidNumeric = true;
  } else if (out.type == ROBOT_CMD_NOD || out.type == ROBOT_CMD_SHAKE) {
    char* count = strtok(nullptr, " \t\r\n");
    if (count) out.nodShake.count = atoi(count);
    if (out.nodShake.count <= 0) out.nodShake.invalidNumeric = true;
  } else if (out.type == ROBOT_CMD_IDLE_STYLE) {
    char* style = strtok(nullptr, " \t\r\n");
    strncpy(out.idleStyle.style, style ? style : "breathing", sizeof(out.idleStyle.style) - 1);
    out.idleStyle.style[sizeof(out.idleStyle.style) - 1] = '\0';
    out.idleStyle.invalidStyle = !isIdleStyle(out.idleStyle.style);
  } else if (out.type == ROBOT_CMD_CAMERA_PAN) {
    char* pos = equalsIgnoreCase(out.cmdName, "camera_center") ? nullptr : strtok(nullptr, " \t\r\n");
    char* offset = strtok(nullptr, " \t\r\n");
    if (pos && equalsIgnoreCase(pos, "--offset")) {
      pos = nullptr;
      if (!offset) offset = strtok(nullptr, " \t\r\n");
    }
    strncpy(out.cameraPan.posName, pos ? pos : "center", sizeof(out.cameraPan.posName) - 1);
    out.cameraPan.posName[sizeof(out.cameraPan.posName) - 1] = '\0';
    out.cameraPan.invalidPos = !parseCameraPanPos(out.cameraPan.posName, out.cameraPan);
    if (offset) {
      if (equalsIgnoreCase(offset, "--offset")) offset = strtok(nullptr, " \t\r\n");
      if (!parseTextInt(offset, out.cameraPan.offsetDeg)) out.cameraPan.invalidNumeric = true;
    }
  }

  out.invalidNumeric = out.gait.invalidNumeric || out.rotate.invalidNumeric ||
                       out.lean.invalidNumeric || out.look.invalidNumeric ||
                       out.nodShake.invalidNumeric || out.face.invalidFace ||
                       out.cameraPan.invalidNumeric;

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
