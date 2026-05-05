#include "rotate_controller.h"
#include "config.h"
#include "rotate_loop_test.h"
#include <Arduino.h>

static bool running = false;
static bool done = true;
static bool continuous = false;
static int targetCycles = 0;
static int cyclesCompleted = 0;

bool rotateStart(RotateCommand command) {
  if (command.dir != LOOP_LEFT && command.dir != LOOP_RIGHT) return false;

  if (command.degrees > 0) {
    command.cycles = (command.degrees + 29) / 30;
  }
  if (command.continuous || command.cycles <= 0) {
    continuous = true;
    targetCycles = 0;
  } else {
    continuous = false;
    targetCycles = constrain(command.cycles, 1, ROTATE_CYCLES_MAX);
  }

  cyclesCompleted = 0;
  done = false;
  running = true;
  startRotateLoop(command.dir);
  return true;
}

void rotateUpdate() {
  if (!running) return;

  updateRotateLoopTest();
  if (consumeRotateLoopCycleCompleted()) {
    cyclesCompleted++;
    if (!continuous && cyclesCompleted >= targetCycles) {
      rotateStop();
      done = true;
    }
  }
}

void rotateStop() {
  loopDirection = LOOP_STOPPED;
  updateRotateLoopTest();
  resetRotateLoopTest();
  running = false;
}

bool rotateIsRunning() {
  return running;
}

bool rotateIsDone() {
  return done;
}
