#include "robot_controller.h"
#include "config.h"
#include "gait_controller.h"
#include "gesture_controller.h"
#include "poses.h"
#include "rotate_controller.h"

static RobotMode currentRobotMode = ROBOT_MODE_IDLE;

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
  } else if (currentRobotMode == ROBOT_MODE_ROTATING) {
    rotateUpdate();
    if (!rotateIsRunning()) currentRobotMode = ROBOT_MODE_IDLE;
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
  robotCommandStop(STOP_MODE_SMOOTH);
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
