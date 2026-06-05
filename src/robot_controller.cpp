#include "robot_controller.h"
#include "camera_head_controller.h"
#include "config.h"
#include "display_controller.h"
#include "gait_controller.h"
#include "gesture_controller.h"
#include "poses.h"
#include "rotate_controller.h"
#include "serial_protocol.h"
#include "util.h"
#include <Arduino.h>
#include <string.h>

static RobotMode currentRobotMode = ROBOT_MODE_IDLE;
static char lastError[32] = "";
static const char* activeCameraHeadCmd = "camera_pan";

static float clampBody(float value) {
  if (value < -BODY_OFFSET_MAX) return -BODY_OFFSET_MAX;
  if (value > BODY_OFFSET_MAX) return BODY_OFFSET_MAX;
  return value;
}

static FaceState faceForGesture(const char* name) {
  if (equalsIgnoreCase(name, "happy")) return FACE_HAPPY;
  if (equalsIgnoreCase(name, "curious")) return FACE_CURIOUS;
  if (equalsIgnoreCase(name, "scared")) return FACE_SCARED;
  if (equalsIgnoreCase(name, "sleepy")) return FACE_SLEEPY;
  if (equalsIgnoreCase(name, "listening")) return FACE_LISTENING;
  return FACE_CURIOUS;
}

static const char* activeCmdForGestureName(const char* name) {
  if (equalsIgnoreCase(name, "breathing") || equalsIgnoreCase(name, "sway")) return "idle";
  if (equalsIgnoreCase(name, "lean")) return "lean";
  if (equalsIgnoreCase(name, "look")) return "look";
  if (equalsIgnoreCase(name, "nod")) return "nod";
  if (equalsIgnoreCase(name, "shake")) return "shake";
  return "gesture";
}

static void syncFaceToMode(RobotMode mode) {
  switch (mode) {
    case ROBOT_MODE_IDLE:
      displaySetFace(FACE_IDLE);
      break;
    case ROBOT_MODE_STANDING:
      displaySetFace(FACE_NEUTRAL);
      break;
    case ROBOT_MODE_SITTING:
      displaySetFace(FACE_SLEEPY);
      break;
    case ROBOT_MODE_GAIT:
      displaySetTemporaryFace(FACE_WALKING, 0);
      break;
    case ROBOT_MODE_ROTATING:
      displaySetTemporaryFace(FACE_ROTATING, 0);
      break;
    case ROBOT_MODE_WAVING:
      displaySetTemporaryFace(FACE_WAVING, 0);
      break;
    case ROBOT_MODE_GESTURE:
      break;
    case ROBOT_MODE_BODY:
      displaySetFace(FACE_NEUTRAL);
      break;
    case ROBOT_MODE_CAMERA_PAN:
      displaySetTemporaryFace(FACE_LISTENING, 0);
      break;
  }
}

static void setRobotMode(RobotMode mode) {
  currentRobotMode = mode;
  syncFaceToMode(mode);
}

void robotInit() {
  cameraHeadInit();
  setRobotMode(ROBOT_MODE_IDLE);
}

void robotUpdate() {
  cameraHeadUpdate();
  if (currentRobotMode == ROBOT_MODE_SITTING) {
    if (poseSitUpdate()) setRobotMode(ROBOT_MODE_IDLE);
  } else if (currentRobotMode == ROBOT_MODE_GAIT) {
    gaitUpdate();
    if (!gaitIsRunning() && gaitIsDone()) {
      setRobotMode(ROBOT_MODE_STANDING);
      Serial.println("{\"event\":\"done\",\"cmd\":\"gait\",\"state\":\"standing\"}");
    }
  } else if (currentRobotMode == ROBOT_MODE_ROTATING) {
    rotateUpdate();
    if (!rotateIsRunning()) {
      setRobotMode(ROBOT_MODE_STANDING);
      if (rotateIsDone()) Serial.println("{\"event\":\"done\",\"cmd\":\"rotate\",\"state\":\"standing\"}");
    }
  } else if (currentRobotMode == ROBOT_MODE_WAVING || currentRobotMode == ROBOT_MODE_GESTURE) {
    gestureUpdate();
    if (gestureIsDone()) {
      const char* doneCmd = currentRobotMode == ROBOT_MODE_WAVING ? "wave" : activeCmdForGestureName(gestureCurrentName());
      setRobotMode(ROBOT_MODE_STANDING);
      Serial.print("{\"event\":\"done\",\"cmd\":\"");
      Serial.print(doneCmd && doneCmd[0] ? doneCmd : "gesture");
      Serial.println("\",\"state\":\"standing\"}");
    }
  } else if (currentRobotMode == ROBOT_MODE_CAMERA_PAN) {
    if (!cameraHeadIsRunning() && cameraHeadIsDone()) {
      setRobotMode(ROBOT_MODE_STANDING);
      Serial.print("{\"event\":\"done\",\"cmd\":\"");
      Serial.print(activeCameraHeadCmd);
      Serial.print("\",\"pos\":\"");
      Serial.print(cameraPanPosName(cameraHeadCurrentPos()));
      Serial.println("\",\"state\":\"standing\"}");
    }
  }
}

bool robotCommandStand() {
  robotCommandStop();
  poseStand();
  setRobotMode(ROBOT_MODE_STANDING);
  return true;
}

bool robotCommandSit() {
  robotCommandStop();
  poseSitStart();
  setRobotMode(ROBOT_MODE_SITTING);
  return true;
}

bool robotCommandStop() {
  gaitStopSmooth();
  rotateStop();
  gestureStop();
  cameraHeadStop();
  setRobotMode(ROBOT_MODE_IDLE);
  return true;
}

bool robotCommandGait(GaitCommand command) {
  if (currentRobotMode != ROBOT_MODE_GAIT) robotCommandStop();
  if (!gaitStart(command)) return false;
  setRobotMode(ROBOT_MODE_GAIT);
  return true;
}

bool robotCommandRotate(RotateCommand command) {
  robotCommandStop();
  if (!rotateStart(command)) return false;
  setRobotMode(ROBOT_MODE_ROTATING);
  return true;
}

bool robotCommandWave(WaveCommand command) {
  robotCommandStop();
  if (!gestureStart(command)) return false;
  setRobotMode(ROBOT_MODE_WAVING);
  return true;
}

bool robotCommandBody(BodyCommand command) {
  robotCommandStop();
  poseBodyOffset(clampBody(command.x), clampBody(command.y), clampBody(command.z));
  setRobotMode(ROBOT_MODE_BODY);
  return true;
}

bool robotCommandGesture(GestureCommand command) {
  robotCommandStop();
  if (!gestureStart(command)) return false;
  currentRobotMode = ROBOT_MODE_GESTURE;
  displaySetTemporaryFace(faceForGesture(command.name), 1600);
  return true;
}

bool robotCommandLean(LeanCommand command) {
  robotCommandStop();
  command.amount_mm = constrain(command.amount_mm, 0.0f, LEAN_AMOUNT_MAX_MM);
  command.duration_ms = constrain(command.duration_ms, 1UL, LEAN_DURATION_MAX_MS);
  if (!leanStart(command)) return false;
  currentRobotMode = ROBOT_MODE_GESTURE;
  displaySetTemporaryFace(FACE_CURIOUS, command.duration_ms + 200);
  return true;
}

bool robotCommandLook(LookCommand command) {
  robotCommandStop();
  command.duration_ms = constrain(command.duration_ms, 1UL, LOOK_DURATION_MAX_MS);
  if (!lookStart(command)) return false;
  if (equalsIgnoreCase(command.dir, "center")) {
    setRobotMode(ROBOT_MODE_STANDING);
    displayCenterGaze();
  } else {
    currentRobotMode = ROBOT_MODE_GESTURE;
    if (command.persistent) displaySetFace(FACE_LISTENING);
    else displaySetTemporaryFace(FACE_LISTENING, command.duration_ms);
    displaySetGaze(command.dir);
  }
  return true;
}

bool robotCommandNod(NodShakeCommand command) {
  robotCommandStop();
  command.count = constrain(command.count, 1, NOD_COUNT_MAX);
  if (!nodStart(command)) return false;
  currentRobotMode = ROBOT_MODE_GESTURE;
  displaySetTemporaryFace(FACE_LISTENING, (unsigned long)command.count * 300UL + 200UL);
  return true;
}

bool robotCommandShake(NodShakeCommand command) {
  robotCommandStop();
  command.count = constrain(command.count, 1, SHAKE_COUNT_MAX);
  if (!shakeStart(command)) return false;
  currentRobotMode = ROBOT_MODE_GESTURE;
  displaySetTemporaryFace(FACE_SCARED, (unsigned long)command.count * 250UL + 200UL);
  return true;
}

bool robotCommandIdleStyle(IdleStyleCommand command) {
  robotCommandStop();
  if (!idleStyleStart(command)) return false;
  currentRobotMode = ROBOT_MODE_GESTURE;
  displaySetFace(FACE_IDLE);
  return true;
}

bool robotCommandCameraPan(CameraPanCommand command, const char* cmdName) {
  robotCommandStop();
  activeCameraHeadCmd = cmdName ? cmdName : "camera_pan";
  if (!cameraHeadStart(command.pos)) return false;
  currentRobotMode = ROBOT_MODE_CAMERA_PAN;
  displaySetTemporaryFace(FACE_LISTENING, 0);
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
  status.face = displayFaceName(displayGetCurrentFace());
  status.faceTemporary = displayIsTemporaryFace();
  status.headPanPosition = cameraPanPosName(cameraHeadCurrentPos());
  status.headPanRunning = cameraHeadIsRunning();

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
    status.gesture = gestureCurrentName();
    if (currentRobotMode == ROBOT_MODE_WAVING) status.activeCmd = "wave";
    else status.activeCmd = activeCmdForGestureName(status.gesture);
  } else if (cameraHeadIsRunning()) {
    status.activeCmd = "camera_pan";
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
    case ROBOT_MODE_CAMERA_PAN: return "camera_pan";
  }
  return "unknown";
}

void robotSetLastError(const char* error) {
  if (!error) error = "";
  strncpy(lastError, error, sizeof(lastError) - 1);
  lastError[sizeof(lastError) - 1] = '\0';
}
