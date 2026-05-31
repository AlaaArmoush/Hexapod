#include "rotate_loop_test.h"
#include "menu.h"
#include "interpolation.h"

// Rotate loop current values
int loopSet1FemurCurrent = 0;
int loopSet1CoxaCurrent = 0;
int loopSet2FemurCurrent = 0;
int loopSet2CoxaCurrent = 0;

// Rotate loop target values
int loopSet1FemurTarget = 0;
int loopSet1CoxaTarget = 0;
int loopSet2FemurTarget = 0;
int loopSet2CoxaTarget = 0;

LoopDirection loopDirection = LOOP_STOPPED;

// Loop internal state
static int loopPhase = 0;
static unsigned long lastLoopUpdate = 0;
static unsigned long phaseReachedAt = 0;
static bool phaseSettled = false;
static bool loopCycleCompleted = false;

// --------------------------------------------------
// Rotate Loop Test (Auto)
// --------------------------------------------------
void printRotateLoopPose() {
  Serial.println();
  Serial.println("===== ROTATE LOOP TEST (AUTO) =====");
  Serial.print("Direction: ");
  if (loopDirection == LOOP_LEFT)
    Serial.println("LEFT");
  else if (loopDirection == LOOP_RIGHT)
    Serial.println("RIGHT");
  else
    Serial.println("STOPPED");

  Serial.print("Phase: ");
  Serial.println(loopPhase);

  Serial.print("Current Set1 Femur/Coxa: ");
  Serial.print(loopSet1FemurCurrent);
  Serial.print(" / ");
  Serial.println(loopSet1CoxaCurrent);

  Serial.print("Current Set2 Femur/Coxa: ");
  Serial.print(loopSet2FemurCurrent);
  Serial.print(" / ");
  Serial.println(loopSet2CoxaCurrent);

  Serial.println();
  Serial.println("Controls:");
  Serial.println("  L -> Start rotate LEFT loop");
  Serial.println("  Q -> Start rotate RIGHT loop");
  Serial.println("  X -> Stop loop where it is");
  Serial.println("  R -> Reset current test");
  Serial.println("  P -> Print values");
  Serial.println("  M -> Back to menu");
  Serial.println("==================================");
  Serial.println();
}

void resetRotateLoopTest() {
  loopDirection = LOOP_STOPPED;
  loopPhase = 0;
  phaseSettled = false;
  phaseReachedAt = 0;
  loopCycleCompleted = false;

  loopSet1FemurCurrent = 0;
  loopSet1CoxaCurrent = 0;
  loopSet2FemurCurrent = 0;
  loopSet2CoxaCurrent = 0;

  loopSet1FemurTarget = 0;
  loopSet1CoxaTarget = 0;
  loopSet2FemurTarget = 0;
  loopSet2CoxaTarget = 0;

  applyRotatePoseValues(loopSet1FemurCurrent, loopSet1CoxaCurrent,
                        loopSet2FemurCurrent, loopSet2CoxaCurrent);
}

// right middle set 1, left middle set 2

void setRotateLoopTargetsLeft(int phase) {
  // Based on your tested left-rotation sequence, completed into a loop
  switch (phase) {
  case 0: // Step 1
    // S2 femur +15
    loopSet1FemurTarget = 0;
    loopSet1CoxaTarget = 0;
    loopSet2FemurTarget = 15;
    loopSet2CoxaTarget = 0;
    break;

  case 1: // Step 2
    // S2 coxa -30, S1 coxa +30
    loopSet1FemurTarget = 0;
    loopSet1CoxaTarget = 30;
    loopSet2FemurTarget = 15;
    loopSet2CoxaTarget = -30;
    break;

  case 2: // Step 3
    // S2 coxa back to 0, keep S1 loaded
    loopSet1FemurTarget = 15;
    loopSet1CoxaTarget = 30;
    loopSet2FemurTarget = 0;
    loopSet2CoxaTarget = -30;
    break;

  case 3: // Step 3
    // S2 coxa back to 0, keep S1 loaded
    loopSet1FemurTarget = 15;
    loopSet1CoxaTarget = 0;
    loopSet2FemurTarget = 0;
    loopSet2CoxaTarget = 0;
    break;

  case 4: // Step 4
    // Lift S1 and swing it opposite
    loopSet1FemurTarget = 0;
    loopSet1CoxaTarget = 0;
    loopSet2FemurTarget = 0;
    loopSet2CoxaTarget = 0;
    break;
  }
}

void setRotateLoopTargetsRight(int phase) {
  // Mirror of left rotation by flipping coxa signs
  switch (phase) {
  case 0:
    loopSet1FemurTarget = 0;
    loopSet1CoxaTarget = 0;
    loopSet2FemurTarget = 15;
    loopSet2CoxaTarget = 0;
    break;

  case 1: 
    loopSet1FemurTarget = 0;
    loopSet1CoxaTarget = -30;
    loopSet2FemurTarget = 15;
    loopSet2CoxaTarget = 30;
    break;

  case 2: 
    loopSet1FemurTarget = 15;
    loopSet1CoxaTarget = -30;
    loopSet2FemurTarget = 0;
    loopSet2CoxaTarget = 30;
    break;

  case 3: 
    loopSet1FemurTarget = 15;
    loopSet1CoxaTarget = 0;
    loopSet2FemurTarget = 0;
    loopSet2CoxaTarget = 0;
    break;

  case 4: 
    loopSet1FemurTarget = 0;
    loopSet1CoxaTarget = 0;
    loopSet2FemurTarget = 0;
    loopSet2CoxaTarget = 0;
    break;
  }
}

static bool loopTargetsReached() {
  return loopSet1FemurCurrent == loopSet1FemurTarget &&
         loopSet1CoxaCurrent == loopSet1CoxaTarget &&
         loopSet2FemurCurrent == loopSet2FemurTarget &&
         loopSet2CoxaCurrent == loopSet2CoxaTarget;
}

void startRotateLoop(LoopDirection dir) {
  loopDirection = dir;
  loopPhase = 0;
  phaseSettled = false;
  phaseReachedAt = 0;
  loopCycleCompleted = false;

  if (dir == LOOP_LEFT)
    setRotateLoopTargetsLeft(loopPhase);
  else if (dir == LOOP_RIGHT)
    setRotateLoopTargetsRight(loopPhase);
}

void updateRotateLoopTest() {
  unsigned long now = millis();
  if (now - lastLoopUpdate < ROTATE_LOOP_UPDATE_MS)
    return;
  lastLoopUpdate = now;

  if (loopDirection == LOOP_STOPPED) {
    applyRotatePoseValues(loopSet1FemurCurrent, loopSet1CoxaCurrent,
                          loopSet2FemurCurrent, loopSet2CoxaCurrent);
    return;
  }

  // Smooth interpolation toward target
  loopSet1FemurCurrent =
      moveTowardI(loopSet1FemurCurrent, loopSet1FemurTarget, LOOP_INTERP_STEP);
  loopSet1CoxaCurrent =
      moveTowardI(loopSet1CoxaCurrent, loopSet1CoxaTarget, LOOP_INTERP_STEP);
  loopSet2FemurCurrent =
      moveTowardI(loopSet2FemurCurrent, loopSet2FemurTarget, LOOP_INTERP_STEP);
  loopSet2CoxaCurrent =
      moveTowardI(loopSet2CoxaCurrent, loopSet2CoxaTarget, LOOP_INTERP_STEP);

  applyRotatePoseValues(loopSet1FemurCurrent, loopSet1CoxaCurrent,
                        loopSet2FemurCurrent, loopSet2CoxaCurrent);

  if (loopTargetsReached()) {
    if (!phaseSettled) {
      phaseSettled = true;
      phaseReachedAt = now;
    } else if (now - phaseReachedAt >= LOOP_HOLD_MS) {
      loopPhase++;
      if (loopPhase > 4) {
        loopPhase = 0;
        loopCycleCompleted = true;
      }

      if (loopDirection == LOOP_LEFT)
        setRotateLoopTargetsLeft(loopPhase);
      else if (loopDirection == LOOP_RIGHT)
        setRotateLoopTargetsRight(loopPhase);

      phaseSettled = false;
    }
  } else {
    phaseSettled = false;
  }
}

bool consumeRotateLoopCycleCompleted() {
  bool completed = loopCycleCompleted;
  loopCycleCompleted = false;
  return completed;
}

// --------------------------------------------------
// Rotate Loop Test controls
// --------------------------------------------------
void handleRotateLoopTestControl() {
  if (Serial.available()) {
    char c = Serial.read();

    if (c == 'r' || c == 'R') {
      resetRotateLoopTest();
      printRotateLoopPose();
      return;
    }

    if (c == 'p' || c == 'P') {
      printRotateLoopPose();
      return;
    }

    if (c == 'm' || c == 'M') {
      resetRotateLoopTest();
      return;
    }

    if (c == 'l' || c == 'L') {
      startRotateLoop(LOOP_LEFT);
      Serial.println("Rotate Loop -> LEFT");
      printRotateLoopPose();
      return;
    }

    if (c == 'q' || c == 'Q') {
      startRotateLoop(LOOP_RIGHT);
      Serial.println("Rotate Loop -> RIGHT");
      printRotateLoopPose();
      return;
    }

    if (c == 'x' || c == 'X') {
      loopDirection = LOOP_STOPPED;
      Serial.println("Rotate Loop -> STOP");
      printRotateLoopPose();
      return;
    }
  }

  updateRotateLoopTest();
}
