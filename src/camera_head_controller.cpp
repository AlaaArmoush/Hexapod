#include "camera_head_controller.h"
#include "config.h"
#include "servo_driver.h"
#include <Arduino.h>

static CameraPanPos currentPos = CAM_PAN_CENTER;
static CameraPanPos targetPos = CAM_PAN_CENTER;
static int currentDeg = CAMERA_PAN_CENTER_DEG;
static int targetDeg = CAMERA_PAN_CENTER_DEG;
static bool running = false;
static bool done = false;
static unsigned long lastUpdateMs = 0;

static int clampCameraDeg(int deg) {
  if (deg < CAMERA_SERVO_MIN_DEG) return CAMERA_SERVO_MIN_DEG;
  if (deg > CAMERA_SERVO_MAX_DEG) return CAMERA_SERVO_MAX_DEG;
  return deg;
}

static int degreeForPos(CameraPanPos pos) {
  switch (pos) {
    case CAM_PAN_LEFT: return CAMERA_PAN_LEFT_DEG;
    case CAM_PAN_FRONT_LEFT: return CAMERA_PAN_FRONT_LEFT_DEG;
    case CAM_PAN_CENTER: return CAMERA_PAN_CENTER_DEG;
    case CAM_PAN_FRONT_RIGHT: return CAMERA_PAN_FRONT_RIGHT_DEG;
    case CAM_PAN_RIGHT: return CAMERA_PAN_RIGHT_DEG;
  }
  return CAMERA_PAN_CENTER_DEG;
}

const char* cameraPanPosName(CameraPanPos pos) {
  switch (pos) {
    case CAM_PAN_LEFT: return "left";
    case CAM_PAN_FRONT_LEFT: return "front_left";
    case CAM_PAN_CENTER: return "center";
    case CAM_PAN_FRONT_RIGHT: return "front_right";
    case CAM_PAN_RIGHT: return "right";
  }
  return "center";
}

void cameraHeadInit() {
  currentPos = CAM_PAN_CENTER;
  targetPos = CAM_PAN_CENTER;
  currentDeg = clampCameraDeg(CAMERA_PAN_CENTER_DEG);
  targetDeg = currentDeg;
  running = false;
  done = false;
  lastUpdateMs = 0;
  servoWriteRaw(CAMERA_SERVO_BOARD, CAMERA_SERVO_CHANNEL, currentDeg + CAMERA_SERVO_TRIM);
}

bool cameraHeadStart(CameraPanPos pos, int offsetDeg) {
  targetPos = pos;
  targetDeg = clampCameraDeg(degreeForPos(pos) + offsetDeg);
  done = false;
  if (currentDeg == targetDeg) {
    currentPos = targetPos;
    running = false;
    done = true;
    return true;
  }
  running = true;
  lastUpdateMs = 0;
  return true;
}

void cameraHeadUpdate() {
  if (!running) return;

  unsigned long now = millis();
  if (lastUpdateMs != 0 && now - lastUpdateMs < CAMERA_SERVO_UPDATE_MS) return;
  lastUpdateMs = now;

  int delta = targetDeg - currentDeg;
  if (delta == 0) {
    currentPos = targetPos;
    running = false;
    done = true;
    return;
  }

  int step = CAMERA_SERVO_SLEW_DEG_PER_UPDATE;
  if (abs(delta) <= step) currentDeg = targetDeg;
  else currentDeg += delta > 0 ? step : -step;

  currentDeg = clampCameraDeg(currentDeg);
  servoWriteRaw(CAMERA_SERVO_BOARD, CAMERA_SERVO_CHANNEL, currentDeg + CAMERA_SERVO_TRIM);

  if (currentDeg == targetDeg) {
    currentPos = targetPos;
    running = false;
    done = true;
  }
}

void cameraHeadStop() {
  running = false;
  done = false;
}

bool cameraHeadIsRunning() {
  return running;
}

bool cameraHeadIsDone() {
  return done;
}

CameraPanPos cameraHeadCurrentPos() {
  return currentPos;
}
