#include "robot_controller.h"
#include "config.h"
#include "gait_controller.h"
#include "gesture_controller.h"
#include "poses.h"
#include "rotate_controller.h"
#include "serial_protocol.h"
#include <Arduino.h>
#include <string.h>

static RobotMode currentRobotMode = ROBOT_MODE_IDLE;
static char lastError[32] = "";

static float clampBody(float value) {
  if (value < -BODY_OFFSET_MAX) return -BODY_OFFSET_MAX;
  if (value > BODY_OFFSET_MAX) return BODY_OFFSET_MAX;
  return value;
}

void robotInit() {
  currentRobotMode = ROBOT_MODE_IDLE;
}

void robotUpdate() {
  if (currentRobotMode == ROBOT_MODE_SITTING) {
    if (poseSitUpdate()) currentRobotMode = ROBOT_MODE_IDLE;
  } else if (currentRobotMode == ROBOT_MODE_GAIT) {
    gaitUpdate();
    if (!gaitIsRunning() && gaitIsDone()) {
      currentRobotMode = ROBOT_MODE_STANDING;
      Serial.println("{\"event\":\"done\",\"cmd\":\"gait\",\"state\":\"standing\"}");
    }
  } else if (currentRobotMode == ROBOT_MODE_ROTATING) {
    rotateUpdate();
    if (!rotateIsRunning()) {
      currentRobotMode = ROBOT_MODE_STANDING;
      if (rotateIsDone()) Serial.println("{\"event\":\"done\",\"cmd\":\"rotate\",\"state\":\"standing\"}");
    }
  } else if (currentRobotMode == ROBOT_MODE_WAVING || currentRobotMode == ROBOT_MODE_GESTURE) {
    gestureUpdate();
    if (gestureIsDone()) currentRobotMode = ROBOT_MODE_STANDING;
  }
}

bool robotCommandStand() {
  robotCommandStop(STOP_MODE_SMOOTH);
  poseStand();
  currentRobotMode = ROBOT_MODE_STANDING;
  return true;
}

bool robotCommandSit() {
  robotCommandStop(STOP_MODE_SMOOTH);
  poseSitStart();
  currentRobotMode = ROBOT_MODE_SITTING;
  return true;
}

bool robotCommandStop(StopMode mode) {
  (void)mode;
  gaitStopSmooth();
  rotateStop();
  gestureStop();
  currentRobotMode = ROBOT_MODE_IDLE;
  return true;
}

bool robotCommandGait(GaitCommand command) {
  if (currentRobotMode != ROBOT_MODE_GAIT) robotCommandStop(STOP_MODE_SMOOTH);
  if (!gaitStart(command)) return false;
  currentRobotMode = ROBOT_MODE_GAIT;
  return true;
}

bool robotCommandRotate(RotateCommand command) {
  robotCommandStop(STOP_MODE_SMOOTH);
  if (!rotateStart(command)) return false;
  currentRobotMode = ROBOT_MODE_ROTATING;
  return true;
}

bool robotCommandWave(WaveCommand command) {
  robotCommandStop(STOP_MODE_SMOOTH);
  if (!gestureStart(command)) return false;
  currentRobotMode = ROBOT_MODE_WAVING;
  return true;
}

bool robotCommandBody(BodyCommand command) {
  robotCommandStop(STOP_MODE_SMOOTH);
  poseBodyOffset(clampBody(command.x), clampBody(command.y), clampBody(command.z));
  currentRobotMode = ROBOT_MODE_BODY;
  return true;
}

bool robotCommandGesture(GestureCommand command) {
  robotCommandStop(STOP_MODE_SMOOTH);
  if (!gestureStart(command)) return false;
  currentRobotMode = ROBOT_MODE_GESTURE;
  return true;
}

RobotStatus robotGetStatus() {
  RobotStatus status;
  status.mode = currentRobotMode;
  status.gaitRunning = gaitIsRunning();
  status.rotateRunning = rotateIsRunning();
  status.gestureRunning = gestureIsRunning();
  status.interruptible = true;
  status.lastError = lastError;

  if (status.gaitRunning) {
    const GaitCommand& command = gaitCurrentCommand();
    status.activeCmd = "gait";
    status.dir = gaitDirName(command.dir);
    status.speed = command.speed;
    status.bound = motionBoundName(command.bound);
    status.stepsTarget = gaitStepsTarget();
    status.stepsDone = gaitStepsDone();
    status.durationTargetMs = gaitDurationTargetMs();
    status.durationElapsedMs = gaitDurationElapsedMs();
    status.distanceTargetCm = command.distanceCm;
  } else if (status.rotateRunning) {
    const RotateCommand& command = rotateCurrentCommand();
    status.activeCmd = "rotate";
    status.dir = command.dir == LOOP_RIGHT ? "right" : "left";
    status.bound = command.continuous ? "continuous" : "cycles";
    status.rotateCyclesTarget = rotateCyclesTarget();
    status.rotateCyclesDone = rotateCyclesDone();
    status.rotateContinuous = command.continuous;
  } else if (status.gestureRunning) {
    status.activeCmd = currentRobotMode == ROBOT_MODE_WAVING ? "wave" : "gesture";
  } else {
    status.activeCmd = "";
    status.bound = "none";
  }
  return status;
}

const char* robotModeName(RobotMode mode) {
  switch (mode) {
    case ROBOT_MODE_IDLE: return "idle";
    case ROBOT_MODE_STANDING: return "standing";
    case ROBOT_MODE_SITTING: return "sitting";
    case ROBOT_MODE_GAIT: return "gait";
    case ROBOT_MODE_ROTATING: return "rotating";
    case ROBOT_MODE_WAVING: return "waving";
    case ROBOT_MODE_GESTURE: return "gesture";
    case ROBOT_MODE_BODY: return "body";
  }
  return "unknown";
}

void robotSetLastError(const char* error) {
  if (!error) error = "";
  strncpy(lastError, error, sizeof(lastError) - 1);
  lastError[sizeof(lastError) - 1] = '\0';
}
