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
  const unsigned long leanMs = 250;
  const unsigned long liftMs = 250;
  const unsigned long sweepMs = 260UL * waveCount;
  const unsigned long lowerMs = 250;
  const unsigned long centerMs = 250;

  if (elapsed < leanMs) {
    float t = easeInOut((float)elapsed / (float)leanMs);
    poseBodyOffset(0.0f, lerp(0.0f, -40.0f, t), 0.0f);
    return;
  }

  elapsed -= leanMs;
  if (elapsed < liftMs) {
    float t = easeInOut((float)elapsed / (float)liftMs);
    allButWaveLeg(0.0f, -40.0f, 0.0f, 0.0f, 0.0f, lerp(0.0f, 80.0f, t));
    return;
  }

  elapsed -= liftMs;
  if (elapsed < sweepMs) {
    allButWaveLeg(0.0f, -40.0f, 0.0f, 0.0f, 0.0f, 80.0f);
    const LegDesc& leg = LEGS[waveLeg];
    float phase = (float)(elapsed % 260UL) / 260.0f;
    float angle = 97.0f + sinf(phase * 6.2831853f) * 35.0f;
    servoWriteRaw(leg.board_coxa, leg.ch_coxa, (int)angle + leg.trim_coxa);
    return;
  }

  elapsed -= sweepMs;
  if (elapsed < lowerMs) {
    float t = easeInOut((float)elapsed / (float)lowerMs);
    allButWaveLeg(0.0f, -40.0f, 0.0f, 0.0f, 0.0f, lerp(80.0f, 0.0f, t));
    return;
  }

  elapsed -= lowerMs;
  if (elapsed < centerMs) {
    float t = easeInOut((float)elapsed / (float)centerMs);
    poseBodyOffset(0.0f, lerp(-40.0f, 0.0f, t), 0.0f);
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
