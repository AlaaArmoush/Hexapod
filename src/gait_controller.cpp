#include "gait_controller.h"
#include "config.h"
#include "tripod_gait.h"
#include <Arduino.h>
#include <math.h>

static bool running = false;

static float clampfLocal(float value, float lo, float hi) {
  if (value < lo) return lo;
  if (value > hi) return hi;
  return value;
}

static void directionVector(GaitCommand& command) {
  switch (command.dir) {
    case GAIT_DIR_FORWARD: command.x = 1.0f; command.y = 0.0f; break;
    case GAIT_DIR_BACKWARD: command.x = -1.0f; command.y = 0.0f; break;
    case GAIT_DIR_LEFT: command.x = 0.0f; command.y = 1.0f; break;
    case GAIT_DIR_RIGHT: command.x = 0.0f; command.y = -1.0f; break;
    case GAIT_DIR_FORWARD_LEFT: command.x = 0.7071f; command.y = 0.7071f; break;
    case GAIT_DIR_FORWARD_RIGHT: command.x = 0.7071f; command.y = -0.7071f; break;
    case GAIT_DIR_BACKWARD_LEFT: command.x = -0.7071f; command.y = 0.7071f; break;
    case GAIT_DIR_BACKWARD_RIGHT: command.x = -0.7071f; command.y = -0.7071f; break;
    case GAIT_DIR_CUSTOM: break;
  }
}

bool gaitStart(GaitCommand command) {
  directionVector(command);

  float mag = sqrtf(command.x * command.x + command.y * command.y);
  if (mag < 0.001f) return false;

  gaitDirX = command.x;
  gaitDirY = command.y;
  gaitPhaseStep = clampfLocal(command.speed > 0.0f ? command.speed : GAIT_SPEED_DEFAULT,
                              GAIT_SPEED_MIN, GAIT_SPEED_MAX);
  gaitStepLength = clampfLocal(command.stepLength > 0.0f ? command.stepLength : GAIT_STEP_LEN_DEFAULT,
                               5.0f, GAIT_STEP_LEN_MAX);
  gaitStepHeight = clampfLocal(command.stepHeight > 0.0f ? command.stepHeight : GAIT_STEP_HT_DEFAULT,
                               5.0f, GAIT_STEP_HT_MAX);

  startTripodGait();
  running = true;
  return true;
}

void gaitUpdate() {
  updateTripodGait();
}

void gaitStopSmooth() {
  stopTripodGait();
  running = false;
}

bool gaitIsRunning() {
  return running;
}
