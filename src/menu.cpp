#include "menu.h"
#include "body_motion_test.h"
#include "rotate_loop_test.h"
#include "rotate_test.h"
#include "sitting_test.h"
#include "tripod_gait.h"
#include "wave.h"
#include <Arduino.h>

TestMode currentMode = MODE_NONE;

void printMenu() {
  Serial.println();
  Serial.println("===== TEST MENU =====");
  Serial.println("1 -> Sitting Test (Manual)");
  Serial.println("2 -> Rotate Test (Manual)");
  Serial.println("3 -> Rotate Loop Test (Auto)");
  Serial.println("4 -> Body Motion Test (IK)");
  Serial.println("5 -> Tripod Gait (IK)");
  Serial.println("6 -> Wave");
  Serial.println("=====================");
  Serial.println();
}

void waitForModeChoice() {
  currentMode = MODE_NONE;
  printMenu();

  while (true) {
    if (Serial.available()) {
      char c = Serial.read();

      if (c == '1') {
        currentMode = MODE_SITTING_TEST;
        resetSittingTest();
        Serial.println("Selected: Sitting Test (Manual)");
        printCurrentPose();
        return;
      }

      if (c == '2') {
        currentMode = MODE_ROTATE_TEST;
        resetRotateTest();
        Serial.println("Selected: Rotate Test (Manual)");
        printRotatePose();
        return;
      }

      if (c == '3') {
        currentMode = MODE_ROTATE_LOOP_TEST;
        resetRotateLoopTest();
        Serial.println("Selected: Rotate Loop Test (Auto)");
        printRotateLoopPose();
        return;
      }

      if (c == '4') {
        currentMode = MODE_BODY_MOTION_TEST;
        resetBodyMotionTest();
        Serial.println("Selected: Body Motion Test (IK)");
        printBodyMotionPose();
        return;
      }

      if (c == '5') {
        currentMode = MODE_TRIPOD_GAIT;
        resetTripodGait();
        Serial.println("Selected: Tripod Gait (IK)");
        printTripodGaitState();
        return;
      }

      if (c == '6') {
        currentMode = MODE_WAVE;
        Serial.println("Selected: Wave");
        printWaveState();
        return;
      }
    }
    delay(10);
  }
}

#if ENABLE_DEBUG_MENU
void debugMenuUpdate() {
  if (currentMode == MODE_SITTING_TEST) handleSittingTestControl();
  else if (currentMode == MODE_ROTATE_TEST) handleRotateTestControl();
  else if (currentMode == MODE_ROTATE_LOOP_TEST) handleRotateLoopTestControl();
  else if (currentMode == MODE_BODY_MOTION_TEST) handleBodyMotionTestControl();
  else if (currentMode == MODE_TRIPOD_GAIT) handleTripodGaitControl();
  else if (currentMode == MODE_WAVE) handleWaveControl();
}
#endif
