#include "sitting_test.h"
#include "menu.h"

// Sitting test deltas
int femurDelta = 0;
int tibiaDelta = 0;

// --------------------------------------------------
// Sitting Test pose
// --------------------------------------------------
void applyTuningPose() {
  // Coxa stays at standing neutral
  servoWriteRaw(0, CH_LF_COXA, coxaRef + TRIM_LF_COXA);
  servoWriteRaw(0, CH_LM_COXA, coxaRef + TRIM_LM_COXA);
  servoWriteRaw(0, CH_LB_COXA, coxaRef + TRIM_LB_COXA);

  servoWriteRaw(1, CH_RF_COXA, coxaRef + TRIM_RF_COXA);
  servoWriteRaw(1, CH_RM_COXA, coxaRef + TRIM_RM_COXA);
  servoWriteRaw(1, CH_RB_COXA, coxaRef + TRIM_RB_COXA);

  // Femur
  // Left upward = positive, downward = negative
  servoWriteRaw(0, CH_LF_FEMUR, femurRef + femurDelta + TRIM_LF_FEMUR);
  servoWriteRaw(0, CH_LM_FEMUR, femurRef + femurDelta + TRIM_LM_FEMUR);
  servoWriteRaw(0, CH_LB_FEMUR, femurRef + femurDelta + TRIM_LB_FEMUR);

  // Right upward = negative, downward = positive
  servoWriteRaw(1, CH_RF_FEMUR, femurRef - femurDelta + TRIM_RF_FEMUR);
  servoWriteRaw(1, CH_RM_FEMUR, femurRef - femurDelta + TRIM_RM_FEMUR);
  servoWriteRaw(1, CH_RB_FEMUR, femurRef - femurDelta + TRIM_RB_FEMUR);

  // Tibia
  // Left inward = positive, outward = negative
  servoWriteRaw(0, CH_LF_TIBIA, tibiaRef + tibiaDelta + TRIM_LF_TIBIA);
  servoWriteRaw(0, CH_LM_TIBIA, tibiaRef + tibiaDelta + TRIM_LM_TIBIA);
  servoWriteRaw(0, CH_LB_TIBIA, tibiaRef + tibiaDelta + TRIM_LB_TIBIA);

  // Right inward = negative, outward = positive
  servoWriteRaw(1, CH_RF_TIBIA, tibiaRef - tibiaDelta + TRIM_RF_TIBIA);
  servoWriteRaw(1, CH_RM_TIBIA, tibiaRef - tibiaDelta + TRIM_RM_TIBIA);
  servoWriteRaw(1, CH_RB_TIBIA, tibiaRef - tibiaDelta + TRIM_RB_TIBIA);
}

void printCurrentPose() {
  Serial.println();
  Serial.println("===== SITTING TEST (MANUAL) =====");
  Serial.print("Femur delta from stand: ");
  Serial.println(femurDelta);
  Serial.print("Tibia delta from stand: ");
  Serial.println(tibiaDelta);

  Serial.println("Actual commanded femur angles:");
  Serial.print("  Left  femurs = ");
  Serial.println(femurRef + femurDelta);
  Serial.print("  Right femurs = ");
  Serial.println(femurRef - femurDelta);

  Serial.println("Actual commanded tibia angles:");
  Serial.print("  Left  tibias = ");
  Serial.println(tibiaRef + tibiaDelta);
  Serial.print("  Right tibias = ");
  Serial.println(tibiaRef - tibiaDelta);

  Serial.println();
  Serial.println("Controls:");
  Serial.println("  Up Arrow    -> Femur downward");
  Serial.println("  Down Arrow  -> Femur upward");
  Serial.println("  Left Arrow  -> Tibia inward");
  Serial.println("  Right Arrow -> Tibia outward");
  Serial.println("  R           -> Reset current test");
  Serial.println("  P           -> Print values");
  Serial.println("  M           -> Back to menu");
  Serial.println("=================================");
  Serial.println();
}

// --------------------------------------------------
// Reset helper
// --------------------------------------------------
void resetSittingTest() {
  femurDelta = 0;
  tibiaDelta = 0;
  applyTuningPose();
}

// --------------------------------------------------
// Sitting Test controls
// --------------------------------------------------
void handleSittingTestControl() {
  if (!Serial.available())
    return;

  char c = Serial.read();

  if (c == 'r' || c == 'R') {
    resetSittingTest();
    printCurrentPose();
    return;
  }

  if (c == 'p' || c == 'P') {
    printCurrentPose();
    return;
  }

  if (c == 'm' || c == 'M') {
    waitForModeChoice();
    return;
  }

  // Arrow keys:
  // Up    = ESC [ A
  // Down  = ESC [ B
  // Right = ESC [ C
  // Left  = ESC [ D
  if (c == 27) {
    while (Serial.available() < 2) {
      delay(1);
    }

    char c1 = Serial.read();
    char c2 = Serial.read();

    if (c1 != '[')
      return;

    switch (c2) {
    case 'A': // Up -> Femur downward
      femurDelta -= STEP_DEGREE;
      applyTuningPose();
      Serial.println("Up Arrow -> Femur downward");
      printCurrentPose();
      break;

    case 'B': // Down -> Femur upward
      femurDelta += STEP_DEGREE;
      applyTuningPose();
      Serial.println("Down Arrow -> Femur upward");
      printCurrentPose();
      break;

    case 'C': // Right -> Tibia outward
      tibiaDelta -= STEP_DEGREE;
      applyTuningPose();
      Serial.println("Right Arrow -> Tibia outward");
      printCurrentPose();
      break;

    case 'D': // Left -> Tibia inward
      tibiaDelta += STEP_DEGREE;
      applyTuningPose();
      Serial.println("Left Arrow -> Tibia inward");
      printCurrentPose();
      break;
    }
  }
}
