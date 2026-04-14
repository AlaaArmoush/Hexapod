#include "body_motion_test.h"
#include "menu.h"
#include <Arduino.h>

float bodyX = 0.0f;
float bodyY = 0.0f;
float bodyZ = 0.0f;

#define BODY_STEP_MM 5.0f   // mm per keypress

void applyBodyOffset() {
    for (int i = 0; i < 6; i++) {
        legIK(i, bodyX, bodyY, bodyZ);
    }
}

void printBodyMotionPose() {
    Serial.println();
    Serial.println("===== BODY MOTION TEST (IK) =====");
    Serial.print("X (fwd/back) : "); Serial.println(bodyX);
    Serial.print("Y (left/right): "); Serial.println(bodyY);
    Serial.print("Z (up/down)  : "); Serial.println(bodyZ);
    Serial.println();
    Serial.println("Controls:");
    Serial.println("  Up/Down Arrow -> X forward/back");
    Serial.println("  Left/Right Arrow -> Y left/right");
    Serial.println("  W / S         -> Z up / down");
    Serial.println("  R             -> Reset");
    Serial.println("  P             -> Print values");
    Serial.println("  M             -> Back to menu");
    Serial.println("=================================");
    Serial.println();
}

void resetBodyMotionTest() {
    bodyX = 0.0f;
    bodyY = 0.0f;
    bodyZ = 0.0f;
    applyBodyOffset();
}

void handleBodyMotionTestControl() {
    if (!Serial.available()) return;

    char c = Serial.read();

    if (c == 'r' || c == 'R') {
        resetBodyMotionTest();
        printBodyMotionPose();
        return;
    }

    if (c == 'p' || c == 'P') {
        printBodyMotionPose();
        return;
    }

    if (c == 'm' || c == 'M') {
        resetBodyMotionTest();
        waitForModeChoice();
        return;
    }

    // Z axis: W = up, S = down
    if (c == 'w' || c == 'W') {
        bodyZ -= BODY_STEP_MM;
        applyBodyOffset();
        Serial.println("Z up");
        printBodyMotionPose();
        return;
    }

    if (c == 's' || c == 'S') {
        bodyZ += BODY_STEP_MM;
        applyBodyOffset();
        Serial.println("Z down");
        printBodyMotionPose();
        return;
    }

    // Arrow keys: X and Y
    if (c == 27) {
        while (Serial.available() < 2) delay(1);
        char c1 = Serial.read();
        char c2 = Serial.read();
        if (c1 != '[') return;

        switch (c2) {
            case 'A': // Up -> X forward
                bodyX += BODY_STEP_MM;
                applyBodyOffset();
                Serial.println("X forward");
                printBodyMotionPose();
                break;

            case 'B': // Down -> X back
                bodyX -= BODY_STEP_MM;
                applyBodyOffset();
                Serial.println("X back");
                printBodyMotionPose();
                break;

            case 'C': // Right -> Y right
                bodyY += BODY_STEP_MM;
                applyBodyOffset();
                Serial.println("Y right");
                printBodyMotionPose();
                break;

            case 'D': // Left -> Y left
                bodyY -= BODY_STEP_MM;
                applyBodyOffset();
                Serial.println("Y left");
                printBodyMotionPose();
                break;
        }
    }
}