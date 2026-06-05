#include "gesture_controller.h"
#include "config.h"
#include "ik.h"
#include "interpolation.h"
#include "poses.h"
#include "servo_driver.h"
#include "util.h"
#include <Arduino.h>
#include <string.h>

enum GestureKind {
  GESTURE_NONE,
  GESTURE_WAVE,
  GESTURE_HAPPY,
  GESTURE_CURIOUS,
  GESTURE_SCARED,
  GESTURE_IDLE,
  GESTURE_SLEEPY,
  GESTURE_LISTENING,
  GESTURE_LEAN,
  GESTURE_LOOK,
  GESTURE_NOD,
  GESTURE_SHAKE,
  GESTURE_BREATHING,
  GESTURE_SWAY
};

static GestureKind kind = GESTURE_NONE;
static bool running = false;
static bool done = true;
static unsigned long startedAt = 0;
static int waveLeg = 3;
static int waveCount = 2;
static float intensity = 0.5f;
static LeanCommand leanCommand;
static LookCommand lookCommand;
static NodShakeCommand nodShakeCommand;
static IdleStyleCommand idleStyleCommand;

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

  if (equalsIgnoreCase(command.name, "happy")) kind = GESTURE_HAPPY;
  else if (equalsIgnoreCase(command.name, "curious")) kind = GESTURE_CURIOUS;
  else if (equalsIgnoreCase(command.name, "scared")) kind = GESTURE_SCARED;
  else if (equalsIgnoreCase(command.name, "sleepy")) kind = GESTURE_SLEEPY;
  else if (equalsIgnoreCase(command.name, "listening")) kind = GESTURE_LISTENING;
  else kind = GESTURE_IDLE;

  running = true;
  done = false;
  startedAt = millis();
  return true;
}

bool leanStart(LeanCommand command) {
  command.amount_mm = constrain(command.amount_mm, 0.0f, LEAN_AMOUNT_MAX_MM);
  command.duration_ms = constrain(command.duration_ms, 1UL, LEAN_DURATION_MAX_MS);
  leanCommand = command;
  kind = GESTURE_LEAN;
  running = true;
  done = false;
  startedAt = millis();
  return true;
}

bool lookStart(LookCommand command) {
  command.duration_ms = constrain(command.duration_ms, 1UL, LOOK_DURATION_MAX_MS);
  lookCommand = command;
  kind = GESTURE_LOOK;
  startedAt = millis();
  done = false;

  if (equalsIgnoreCase(command.dir, "center")) {
    poseStand();
    running = false;
    done = true;
    return true;
  }

  running = true;
  return true;
}

bool nodStart(NodShakeCommand command) {
  command.count = constrain(command.count, 1, NOD_COUNT_MAX);
  nodShakeCommand = command;
  kind = GESTURE_NOD;
  running = true;
  done = false;
  startedAt = millis();
  return true;
}

bool shakeStart(NodShakeCommand command) {
  command.count = constrain(command.count, 1, SHAKE_COUNT_MAX);
  nodShakeCommand = command;
  kind = GESTURE_SHAKE;
  running = true;
  done = false;
  startedAt = millis();
  return true;
}

bool idleStyleStart(IdleStyleCommand command) {
  idleStyleCommand = command;
  kind = equalsIgnoreCase(command.style, "sway") ? GESTURE_SWAY : GESTURE_BREATHING;
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
  } else if (kind == GESTURE_SLEEPY) {
    float y = sinf(seconds * 2.0f) * 6.0f * intensity;
    poseBodyOffset(0.0f, y, -15.0f);
  } else if (kind == GESTURE_LISTENING) {
    float y = sinf(seconds * 3.0f) * 8.0f * intensity;
    poseBodyOffset(24.0f * intensity, y, 0.0f);
  } else {
    float y = sinf(seconds * 4.0f) * 15.0f * intensity;
    poseBodyOffset(0.0f, y, 0.0f);
  }
}

static void updateLean(unsigned long elapsed) {
  if (elapsed >= leanCommand.duration_ms) {
    poseStand();
    running = false;
    done = true;
    return;
  }

  float amount = leanCommand.amount_mm;
  if (equalsIgnoreCase(leanCommand.dir, "right")) poseBodyOffset(0.0f, -amount, 0.0f);
  else if (equalsIgnoreCase(leanCommand.dir, "forward")) poseBodyOffset(amount, 0.0f, 0.0f);
  else if (equalsIgnoreCase(leanCommand.dir, "backward") || equalsIgnoreCase(leanCommand.dir, "back")) poseBodyOffset(-amount, 0.0f, 0.0f);
  else poseBodyOffset(0.0f, amount, 0.0f);
}

static void updateLook(unsigned long elapsed) {
  if (!lookCommand.persistent && elapsed >= lookCommand.duration_ms) {
    poseStand();
    running = false;
    done = true;
    return;
  }

  if (equalsIgnoreCase(lookCommand.dir, "right")) {
    poseBodyOffset(0.0f, -LOOK_BODY_OFFSET_Y, 0.0f);
  } else if (equalsIgnoreCase(lookCommand.dir, "left")) {
    poseBodyOffset(0.0f, LOOK_BODY_OFFSET_Y, 0.0f);
  } else if (equalsIgnoreCase(lookCommand.dir, "up")) {
    poseBodyOffset(LOOK_BODY_OFFSET_X, 0.0f, 0.0f);
  } else if (equalsIgnoreCase(lookCommand.dir, "down")) {
    poseBodyOffset(-LOOK_BODY_OFFSET_X, 0.0f, 0.0f);
  } else {
    poseStand();
  }
}

static void updateNod(unsigned long elapsed) {
  const unsigned long cycleMs = 300;
  unsigned long duration = (unsigned long)nodShakeCommand.count * cycleMs;
  if (elapsed >= duration) {
    poseStand();
    running = false;
    done = true;
    return;
  }

  float phase = (float)elapsed / (float)cycleMs * TWO_PI;
  poseBodyOffset(0.0f, 0.0f, sinf(phase) * 16.0f);
}

static void updateShake(unsigned long elapsed) {
  const unsigned long cycleMs = 250;
  unsigned long duration = (unsigned long)nodShakeCommand.count * cycleMs;
  if (elapsed >= duration) {
    poseStand();
    running = false;
    done = true;
    return;
  }

  float phase = (float)elapsed / (float)cycleMs * TWO_PI;
  poseBodyOffset(0.0f, sinf(phase) * 18.0f, 0.0f);
}

static void updateExpressiveIdle(unsigned long elapsed) {
  float seconds = elapsed / 1000.0f;
  if (kind == GESTURE_SWAY) {
    poseBodyOffset(0.0f, sinf(seconds * TWO_PI / 3.0f) * 10.0f, 0.0f);
  } else {
    poseBodyOffset(0.0f, 0.0f, sinf(seconds * TWO_PI / 2.0f) * 8.0f);
  }
}

void gestureUpdate() {
  if (!running) return;
  unsigned long elapsed = millis() - startedAt;
  if (kind == GESTURE_WAVE) updateWave(elapsed);
  else if (kind == GESTURE_LEAN) updateLean(elapsed);
  else if (kind == GESTURE_LOOK) updateLook(elapsed);
  else if (kind == GESTURE_NOD) updateNod(elapsed);
  else if (kind == GESTURE_SHAKE) updateShake(elapsed);
  else if (kind == GESTURE_BREATHING || kind == GESTURE_SWAY) updateExpressiveIdle(elapsed);
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

const char* gestureCurrentName() {
  switch (kind) {
    case GESTURE_WAVE: return "wave";
    case GESTURE_HAPPY: return "happy";
    case GESTURE_CURIOUS: return "curious";
    case GESTURE_SCARED: return "scared";
    case GESTURE_IDLE: return "idle";
    case GESTURE_SLEEPY: return "sleepy";
    case GESTURE_LISTENING: return "listening";
    case GESTURE_LEAN: return "lean";
    case GESTURE_LOOK: return "look";
    case GESTURE_NOD: return "nod";
    case GESTURE_SHAKE: return "shake";
    case GESTURE_BREATHING: return "breathing";
    case GESTURE_SWAY: return "sway";
    case GESTURE_NONE: break;
  }
  return "";
}
