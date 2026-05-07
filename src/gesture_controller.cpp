#include "gesture_controller.h"
#include "config.h"
#include "ik.h"
#include "interpolation.h"
#include "poses.h"
#include "servo_driver.h"
#include <Arduino.h>
#include <string.h>

enum GestureKind {
  GESTURE_NONE,
  GESTURE_WAVE,
  GESTURE_HAPPY,
  GESTURE_CURIOUS,
  GESTURE_SCARED,
  GESTURE_IDLE
};

static GestureKind kind = GESTURE_NONE;
static bool running = false;
static bool done = true;
static unsigned long startedAt = 0;
static int waveLeg = 3;
static int waveCount = 2;
static float intensity = 0.5f;

static void allButWaveLeg(float x, float y, float z, float waveX, float waveY, float waveZ) {
  for (int i = 0; i < 6; i++) {
    if (i == waveLeg) legIK(i, waveX, waveY, waveZ);
    else legIK(i, x, y, z);
  }
}

static float waveLeanY() {
  return LEGS[waveLeg].mirrored ? 40.0f : -40.0f;
}

bool gestureStart(WaveCommand command) {
  waveLeg = constrain(command.leg, 0, 5);
  waveCount = constrain(command.count, 1, 6);
  kind = GESTURE_WAVE;
  running = true;
  done = false;
  startedAt = millis();
  return true;
}

bool gestureStart(GestureCommand command) {
  intensity = command.intensity;
  if (intensity < 0.0f) intensity = 0.0f;
  if (intensity > 1.0f) intensity = 1.0f;

  if (strcmp(command.name, "happy") == 0) kind = GESTURE_HAPPY;
  else if (strcmp(command.name, "curious") == 0) kind = GESTURE_CURIOUS;
  else if (strcmp(command.name, "scared") == 0) kind = GESTURE_SCARED;
  else kind = GESTURE_IDLE;

  running = true;
  done = false;
  startedAt = millis();
  return true;
}

static void updateWave(unsigned long elapsed) {
  const unsigned long stepPoseMs = 10;
  const unsigned long poseSteps = 21;
  const unsigned long leanMs = poseSteps * stepPoseMs;
  const unsigned long liftMs = poseSteps * stepPoseMs;
  const unsigned long lowerMs = poseSteps * stepPoseMs;
  const unsigned long centerMs = poseSteps * stepPoseMs;
  const unsigned long sweepStepMs = 15;
  const bool leftSide = LEGS[waveLeg].mirrored;
  const int sweepAStart = leftSide ? 83 : 97;
  const int sweepAHigh = leftSide ? 113 : 137;
  const int sweepALow = leftSide ? 43 : 67;
  const int sweepSign = leftSide ? -1 : 1;
  const int sweepStepDeg = 3;
  const int sweepUpSteps = 14;
  const int sweepDownSteps = 24;
  const int sweepReturnSteps = 11;
  const int sweepStepsPerWave = sweepUpSteps + sweepDownSteps + sweepReturnSteps;
  const unsigned long sweepMs = (unsigned long)sweepStepsPerWave * sweepStepMs * waveCount;

  if (elapsed < leanMs) {
    int step = (int)(elapsed / stepPoseMs);
    if (step > 20) step = 20;
    float t = (float)step / 20.0f;
    poseBodyOffset(0.0f, lerp(0.0f, waveLeanY(), t), 0.0f);
    return;
  }

  elapsed -= leanMs;
  if (elapsed < liftMs) {
    int step = (int)(elapsed / stepPoseMs);
    if (step > 20) step = 20;
    float t = (float)step / 20.0f;
    allButWaveLeg(0.0f, waveLeanY(), 0.0f, 0.0f, 0.0f, lerp(0.0f, 100.0f, t));
    return;
  }

  elapsed -= liftMs;
  if (elapsed < sweepMs) {
    allButWaveLeg(0.0f, waveLeanY(), 0.0f, 0.0f, 0.0f, 100.0f);
    const LegDesc& leg = LEGS[waveLeg];
    int step = (int)((elapsed / sweepStepMs) % sweepStepsPerWave);
    int angle = sweepAStart;

    if (step < sweepUpSteps) {
      angle = sweepAStart + sweepSign * step * sweepStepDeg;
      if (!leftSide && angle > sweepAHigh) angle = sweepAHigh;
      if (leftSide && angle < sweepALow) angle = sweepALow;
    } else if (step < sweepUpSteps + sweepDownSteps) {
      int localStep = step - sweepUpSteps;
      angle = (leftSide ? sweepALow : sweepAHigh) - sweepSign * localStep * sweepStepDeg;
      if (!leftSide && angle < sweepALow) angle = sweepALow;
      if (leftSide && angle > sweepAHigh) angle = sweepAHigh;
    } else {
      int localStep = step - sweepUpSteps - sweepDownSteps;
      angle = (leftSide ? sweepAHigh : sweepALow) + sweepSign * localStep * sweepStepDeg;
      if (!leftSide && angle > sweepAStart) angle = sweepAStart;
      if (leftSide && angle < sweepAStart) angle = sweepAStart;
    }

    servoWriteRaw(leg.board_coxa, leg.ch_coxa, angle + leg.trim_coxa);
    return;
  }

  elapsed -= sweepMs;
  if (elapsed < lowerMs) {
    int step = (int)(elapsed / stepPoseMs);
    if (step > 20) step = 20;
    float t = (float)step / 20.0f;
    allButWaveLeg(0.0f, waveLeanY(), 0.0f, 0.0f, 0.0f, lerp(100.0f, 0.0f, t));
    return;
  }

  elapsed -= lowerMs;
  if (elapsed < centerMs) {
    int step = (int)(elapsed / stepPoseMs);
    if (step > 20) step = 20;
    float t = (float)step / 20.0f;
    poseBodyOffset(0.0f, lerp(waveLeanY(), 0.0f, t), 0.0f);
    return;
  }

  poseStand();
  running = false;
  done = true;
}

static void updateNamedGesture(unsigned long elapsed) {
  float seconds = elapsed / 1000.0f;
  if (elapsed > 1400) {
    poseStand();
    running = false;
    done = true;
    return;
  }

  if (kind == GESTURE_HAPPY) {
    float z = sinf(seconds * 12.0f) * 18.0f * intensity;
    poseBodyOffset(0.0f, 0.0f, z);
  } else if (kind == GESTURE_CURIOUS) {
    float x = 35.0f * intensity;
    float y = sinf(seconds * 5.0f) * 10.0f * intensity;
    poseBodyOffset(x, y, 0.0f);
  } else if (kind == GESTURE_SCARED) {
    poseBodyOffset(0.0f, 0.0f, 40.0f * intensity);
  } else {
    float y = sinf(seconds * 4.0f) * 15.0f * intensity;
    poseBodyOffset(0.0f, y, 0.0f);
  }
}

void gestureUpdate() {
  if (!running) return;
  unsigned long elapsed = millis() - startedAt;
  if (kind == GESTURE_WAVE) updateWave(elapsed);
  else updateNamedGesture(elapsed);
}

void gestureStop() {
  poseStand();
  kind = GESTURE_NONE;
  running = false;
  done = true;
}

bool gestureIsRunning() {
  return running;
}

bool gestureIsDone() {
  return done;
}
