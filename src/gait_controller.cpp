#include "gait_controller.h"
#include "config.h"
#include "tripod_gait.h"
#include <Arduino.h>
#include <math.h>

static bool running = false;
static bool done = true;
static GaitCommand currentCommand;
static unsigned long startedAtMs = 0;
static int stepsTarget = 0;
static int stepsDone = 0;

static float clampfLocal(float value, float lo, float hi) {
  if (value < lo) return lo;
  if (value > hi) return hi;
  return value;
}

static void directionVector(GaitCommand& command) {
  switch (command.dir) {
    case GAIT_DIR_FORWARD: command.x = 1.0f; command.y = 0.0f; break;
    case GAIT_DIR_BACKWARD: command.x = -1.0f; command.y = 0.0f; break;
    case GAIT_DIR_LEFT: command.x = 0.0f; command.y = -1.0f; break;
    case GAIT_DIR_RIGHT: command.x = 0.0f; command.y = 1.0f; break;
    case GAIT_DIR_FORWARD_LEFT: command.x = 0.7071f; command.y = -0.7071f; break;
    case GAIT_DIR_FORWARD_RIGHT: command.x = 0.7071f; command.y = 0.7071f; break;
    case GAIT_DIR_BACKWARD_LEFT: command.x = -0.7071f; command.y = -0.7071f; break;
    case GAIT_DIR_BACKWARD_RIGHT: command.x = -0.7071f; command.y = 0.7071f; break;
    case GAIT_DIR_CUSTOM: break;
  }
}

bool gaitStart(GaitCommand command) {
  if (command.invalidDirection || command.invalidNumeric || command.ambiguousBound) return false;
  directionVector(command);

  float mag = sqrtf(command.x * command.x + command.y * command.y);
  if (mag < 0.001f) return false;

  command.speed = clampfLocal(command.speed > 0.0f ? command.speed : GAIT_SPEED_DEFAULT,
                              GAIT_SPEED_MIN, GAIT_SPEED_MAX);
  command.stepLength = clampfLocal(command.stepLength > 0.0f ? command.stepLength : GAIT_STEP_LEN_DEFAULT,
                                   5.0f, GAIT_STEP_LEN_MAX);
  command.stepHeight = clampfLocal(command.stepHeight > 0.0f ? command.stepHeight : GAIT_STEP_HT_DEFAULT,
                                   5.0f, GAIT_STEP_HT_MAX);
  if (command.durationMs > GAIT_DURATION_MS_MAX) command.durationMs = GAIT_DURATION_MS_MAX;
  if (command.steps > GAIT_STEPS_MAX) command.steps = GAIT_STEPS_MAX;
  if (command.distanceCm > GAIT_DISTANCE_CM_MAX) command.distanceCm = GAIT_DISTANCE_CM_MAX;

  stepsTarget = 0;
  stepsDone = 0;
  if (command.bound == MOTION_BOUND_CONTINUOUS) {
    command.bound = MOTION_BOUND_STEPS;
    command.steps = GAIT_STEPS_DEFAULT;
    stepsTarget = constrain(command.steps, 1, GAIT_STEPS_MAX);
  } else if (command.bound == MOTION_BOUND_STEPS) {
    stepsTarget = constrain(command.steps, 1, GAIT_STEPS_MAX);
    command.steps = stepsTarget;
  } else if (command.bound == MOTION_BOUND_DISTANCE_CM) {
    float cycles = command.distanceCm / GAIT_CM_PER_CYCLE_DEFAULT;
    stepsTarget = constrain((int)floorf(cycles + 0.5f), 1, GAIT_STEPS_MAX);
  }

  gaitDirX = command.x;
  gaitDirY = command.y;
  gaitPhaseStep = command.speed;
  gaitStepLength = command.stepLength;
  gaitStepHeight = command.stepHeight;
  currentCommand = command;
  startedAtMs = millis();
  done = false;

  if (!tripodGaitIsRunning()) startTripodGait();
  running = true;
  return true;
}

void gaitUpdate() {
  if (!running) return;
  updateTripodGait();

  if (consumeTripodGaitCycleCompleted()) stepsDone++;

  bool finished = false;
  if (currentCommand.bound == MOTION_BOUND_DURATION_MS) {
    finished = millis() - startedAtMs >= currentCommand.durationMs;
  } else if (currentCommand.bound == MOTION_BOUND_STEPS ||
             currentCommand.bound == MOTION_BOUND_DISTANCE_CM) {
    finished = stepsDone >= stepsTarget;
  }

  if (finished) {
    gaitStopSmooth();
    done = true;
  }
}

void gaitStopSmooth() {
  stopTripodGait();
  running = false;
}

bool gaitIsRunning() {
  return running;
}

bool gaitIsDone() {
  return done;
}

const GaitCommand& gaitCurrentCommand() {
  return currentCommand;
}

const char* gaitDirName(GaitDir dir) {
  switch (dir) {
    case GAIT_DIR_FORWARD: return "forward";
    case GAIT_DIR_BACKWARD: return "backward";
    case GAIT_DIR_LEFT: return "left";
    case GAIT_DIR_RIGHT: return "right";
    case GAIT_DIR_FORWARD_LEFT: return "forward_left";
    case GAIT_DIR_FORWARD_RIGHT: return "forward_right";
    case GAIT_DIR_BACKWARD_LEFT: return "backward_left";
    case GAIT_DIR_BACKWARD_RIGHT: return "backward_right";
    case GAIT_DIR_CUSTOM: return "custom";
  }
  return "unknown";
}

const char* motionBoundName(MotionBoundType bound) {
  switch (bound) {
    case MOTION_BOUND_CONTINUOUS: return "continuous";
    case MOTION_BOUND_DURATION_MS: return "duration_ms";
    case MOTION_BOUND_STEPS: return "steps";
    case MOTION_BOUND_DISTANCE_CM: return "distance_cm";
  }
  return "unknown";
}

int gaitStepsTarget() { return stepsTarget; }
int gaitStepsDone() { return stepsDone; }
unsigned long gaitDurationTargetMs() { return currentCommand.durationMs; }
unsigned long gaitDurationElapsedMs() { return running ? millis() - startedAtMs : 0; }
