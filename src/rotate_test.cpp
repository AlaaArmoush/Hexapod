#include "rotate_test.h"
#include "menu.h"
#include "sitting_test.h" // for tibiaRef

// Rotate manual test deltas
int set1FemurDelta = 0;
int set1CoxaDelta = 0;
int set2FemurDelta = 0;
int set2CoxaDelta = 0;

// --------------------------------------------------
// Shared rotate pose writer
//
// Set 1: Right Middle, Left Front, Left Back
// Set 2: Left Middle, Right Front, Right Back
//
// Coxa: clockwise positive, counter-clockwise negative
// --------------------------------------------------
void applyRotatePoseValues(int s1Femur, int s1Coxa, int s2Femur, int s2Coxa) {
  // Keep all tibias at standing reference
  servoWriteRaw(0, CH_LF_TIBIA, tibiaRef + TRIM_LF_TIBIA);
  servoWriteRaw(0, CH_LM_TIBIA, tibiaRef + TRIM_LM_TIBIA);
  servoWriteRaw(0, CH_LB_TIBIA, tibiaRef + TRIM_LB_TIBIA);

  servoWriteRaw(1, CH_RF_TIBIA, tibiaRef + TRIM_RF_TIBIA);
  servoWriteRaw(1, CH_RM_TIBIA, tibiaRef + TRIM_RM_TIBIA);
  servoWriteRaw(1, CH_RB_TIBIA, tibiaRef + TRIM_RB_TIBIA);

  // ---------- SET 1 ----------
  // Right Middle, Left Front, Left Back

  // Coxa
  servoWriteRaw(1, CH_RM_COXA, coxaRef + s1Coxa + TRIM_RM_COXA);
  servoWriteRaw(0, CH_LF_COXA, coxaRef + s1Coxa + TRIM_LF_COXA);
  servoWriteRaw(0, CH_LB_COXA, coxaRef + s1Coxa + TRIM_LB_COXA);

  // Femur
  // Left femur: downward negative / upward positive
  servoWriteRaw(0, CH_LF_FEMUR, femurRef + s1Femur + TRIM_LF_FEMUR);
  servoWriteRaw(0, CH_LB_FEMUR, femurRef + s1Femur + TRIM_LB_FEMUR);

  // Right femur: downward positive / upward negative
  servoWriteRaw(1, CH_RM_FEMUR, femurRef - s1Femur + TRIM_RM_FEMUR);

  // ---------- SET 2 ----------
  // Left Middle, Right Front, Right Back

  // Coxa
  servoWriteRaw(0, CH_LM_COXA, coxaRef + s2Coxa + TRIM_LM_COXA);
  servoWriteRaw(1, CH_RF_COXA, coxaRef + s2Coxa + TRIM_RF_COXA);
  servoWriteRaw(1, CH_RB_COXA, coxaRef + s2Coxa + TRIM_RB_COXA);

  // Femur
  // Left femur: downward negative / upward positive
  servoWriteRaw(0, CH_LM_FEMUR, femurRef + s2Femur + TRIM_LM_FEMUR);

  // Right femur: downward positive / upward negative
  servoWriteRaw(1, CH_RF_FEMUR, femurRef - s2Femur + TRIM_RF_FEMUR);
  servoWriteRaw(1, CH_RB_FEMUR, femurRef - s2Femur + TRIM_RB_FEMUR);
}

void applyRotateTestPose() {
  applyRotatePoseValues(set1FemurDelta, set1CoxaDelta, set2FemurDelta,
                        set2CoxaDelta);
}

void printRotatePose() {
  Serial.println();
  Serial.println("===== ROTATE TEST (MANUAL) =====");
  Serial.print("Set 1 Femur Delta: ");
  Serial.println(set1FemurDelta);
  Serial.print("Set 1 Coxa Delta : ");
  Serial.println(set1CoxaDelta);

  Serial.print("Set 2 Femur Delta: ");
  Serial.println(set2FemurDelta);
  Serial.print("Set 2 Coxa Delta : ");
  Serial.println(set2CoxaDelta);

  Serial.println();
  Serial.println("Set 1 = Right Middle, Left Front, Left Back");
  Serial.println("  Up Arrow    -> Femur upward");
  Serial.println("  Down Arrow  -> Femur downward");
  Serial.println("  Left Arrow  -> Coxa counter-clockwise");
  Serial.println("  Right Arrow -> Coxa clockwise");

  Serial.println();
  Serial.println("Set 2 = Left Middle, Right Front, Right Back");
  Serial.println("  W -> Femur downward");
  Serial.println("  S -> Femur upward");
  Serial.println("  A -> Coxa counter-clockwise");
  Serial.println("  D -> Coxa clockwise");

  Serial.println();
  Serial.println("Other:");
  Serial.println("  R -> Reset current test");
  Serial.println("  P -> Print values");
  Serial.println("  M -> Back to menu");
  Serial.println("===============================");
  Serial.println();
}

// --------------------------------------------------
// Reset helper
// --------------------------------------------------
void resetRotateTest() {
  set1FemurDelta = 0;
  set1CoxaDelta = 0;
  set2FemurDelta = 0;
  set2CoxaDelta = 0;
  applyRotateTestPose();
}

// --------------------------------------------------
// Rotate Test controls
// --------------------------------------------------
void handleRotateTestControl() {
  if (!Serial.available())
    return;

  char c = Serial.read();

  if (c == 'r' || c == 'R') {
    resetRotateTest();
    printRotatePose();
    return;
  }

  if (c == 'p' || c == 'P') {
    printRotatePose();
    return;
  }

  if (c == 'm' || c == 'M') {
    waitForModeChoice();
    return;
  }

  // Set 2: W/S = femur, A/D = coxa
  if (c == 'w' || c == 'W') {
    set2FemurDelta -= STEP_DEGREE; // downward
    applyRotateTestPose();
    Serial.println("Set 2 -> Femur downward");
    printRotatePose();
    return;
  }

  if (c == 's' || c == 'S') {
    set2FemurDelta += STEP_DEGREE; // upward
    applyRotateTestPose();
    Serial.println("Set 2 -> Femur upward");
    printRotatePose();
    return;
  }

  if (c == 'a' || c == 'A') {
    set2CoxaDelta -= STEP_DEGREE; // counter-clockwise
    applyRotateTestPose();
    Serial.println("Set 2 -> Coxa counter-clockwise");
    printRotatePose();
    return;
  }

  if (c == 'd' || c == 'D') {
    set2CoxaDelta += STEP_DEGREE; // clockwise
    applyRotateTestPose();
    Serial.println("Set 2 -> Coxa clockwise");
    printRotatePose();
    return;
  }

  // Set 1: arrows
  if (c == 27) {
    while (Serial.available() < 2) {
      delay(1);
    }

    char c1 = Serial.read();
    char c2 = Serial.read();

    if (c1 != '[')
      return;

    switch (c2) {
    case 'A': // Up -> Femur upward
      set1FemurDelta += STEP_DEGREE;
      applyRotateTestPose();
      Serial.println("Set 1 -> Femur upward");
      printRotatePose();
      break;

    case 'B': // Down -> Femur downward
      set1FemurDelta -= STEP_DEGREE;
      applyRotateTestPose();
      Serial.println("Set 1 -> Femur downward");
      printRotatePose();
      break;

    case 'C': // Right -> Coxa clockwise
      set1CoxaDelta += STEP_DEGREE;
      applyRotateTestPose();
      Serial.println("Set 1 -> Coxa clockwise");
      printRotatePose();
      break;

    case 'D': // Left -> Coxa counter-clockwise
      set1CoxaDelta -= STEP_DEGREE;
      applyRotateTestPose();
      Serial.println("Set 1 -> Coxa counter-clockwise");
      printRotatePose();
      break;
    }
  }
}
