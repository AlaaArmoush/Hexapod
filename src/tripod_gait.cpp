#include "tripod_gait.h"
#include "menu.h"
#include <Arduino.h>
#include <math.h>

// -----------------------------------------
// Leg groups for tripod gait
//   Group A: LF(0), RM(4), LB(2)
//   Group B: RF(3), LM(1), RB(5)
//
// When Group A swings → Group B is stance (pushes body forward)
// Then swap.
// -----------------------------------------
static const int GROUP_A[3] = {0, 4, 2};
static const int GROUP_B[3] = {1, 5, 3};

// -----------------------------------------
// Tunable parameters
// -----------------------------------------
float gaitStepLength = 30.0f;   // mm
float gaitStepHeight = 25.0f;   // mm (positive = foot lifts up)
float gaitPhaseStep  = 0.02f;   // phase advance per update (1.0 = full half-cycle done)
                                 // at LOOP_UPDATE_MS=5ms → full step ≈ 50 updates → 250ms

float gaitDirX = 1.0f;
float gaitDirY = 0.0f;

// -----------------------------------------
// Internal state
// -----------------------------------------
static float gaitPhase   = 0.0f; // 0.0 → 1.0 within each half-cycle
static int   liftGroup   = 0;    // 0 = Group A swings, 1 = Group B swings
static bool  gaitRunning = false;

static unsigned long lastGaitUpdate = 0;
#define GAIT_UPDATE_MS 5

// -----------------------------------------
// Helpers
// -----------------------------------------
static float lerpf(float a, float b, float t) {
    return a + (b - a) * t;
}

static bool isGroupA(int legIndex) {
    for (int i = 0; i < 3; i++)
        if (GROUP_A[i] == legIndex) return true;
    return false;
}


// -----------------------------------------
// Core gait update — called every loop tick
// -----------------------------------------
void updateTripodGait() {
    if (!gaitRunning) return;

    unsigned long now = millis();
    if (now - lastGaitUpdate < GAIT_UPDATE_MS) return;
    lastGaitUpdate = now;

    // Normalize direction vector
    float mag = sqrtf(gaitDirX * gaitDirX + gaitDirY * gaitDirY);
    float nx = (mag > 0.001f) ? gaitDirX / mag : 1.0f;
    float ny = (mag > 0.001f) ? gaitDirY / mag : 0.0f;

    // Advance phase
    gaitPhase += gaitPhaseStep;
    if (gaitPhase >= 1.0f) {
        gaitPhase = 0.0f;
        liftGroup = 1 - liftGroup;  // swap swing group
    }

    // Update each leg
    for (int i = 0; i < 6; i++) {
        bool isSwing = (liftGroup == 0) ? isGroupA(i) : !isGroupA(i);

        float scalar;  // +1 at start, -1 at end for swing; opposite for stance
        float footZ;

        if (isSwing) {
            // Foot swings from +stepLength ahead → plants -stepLength behind
            scalar = lerpf(+1.0f, -1.0f, gaitPhase);
            footZ  = sinf(gaitPhase * M_PI) * gaitStepHeight;
        } else {
            // Foot pushes body: from -stepLength → +stepLength
            scalar = lerpf(-1.0f, +1.0f, gaitPhase);
            footZ  = 0.0f;
        }

        // Apply directional vector to the step length
        float footX = nx * scalar * gaitStepLength;
        float footY = ny * scalar * gaitStepLength;

        legIK(i, footX, footY, footZ);
    }
}

// -----------------------------------------
// Control
// -----------------------------------------
void resetTripodGait() {
    gaitRunning = false;
    gaitPhase   = 0.0f;
    liftGroup   = 0;
    gaitDirX    = 1.0f;
    gaitDirY    = 0.0f;
    for (int i = 0; i < 6; i++) {
        legIK(i, 0.0f, 0.0f, 0.0f);
    }
}

void startTripodGait() {
    gaitPhase   = 0.0f;
    liftGroup   = 0;
    gaitRunning = true;
    lastGaitUpdate = millis();
}

void stopTripodGait() {
    gaitRunning = false;
    // Settle all feet back to neutral
    for (int i = 0; i < 6; i++) {
        legIK(i, 0.0f, 0.0f, 0.0f);
    }
}

void printTripodGaitState() {
    Serial.println();
    Serial.println("===== TRIPOD GAIT =====");
    Serial.print("Running     : "); Serial.println(gaitRunning ? "YES" : "NO");
    Serial.print("Lift group  : "); Serial.println(liftGroup == 0 ? "A (LF,RM,LB)" : "B (LM,RB,RF)");
    Serial.print("Phase       : "); Serial.println(gaitPhase, 2);
    Serial.print("Direction X : "); Serial.println(gaitDirX, 2);
    Serial.print("Direction Y : "); Serial.println(gaitDirY, 2);
    Serial.print("Step length : "); Serial.print(gaitStepLength); Serial.println(" mm");
    Serial.print("Step height : "); Serial.print(gaitStepHeight); Serial.println(" mm");
    Serial.print("Speed       : "); Serial.println(gaitPhaseStep, 3);
    Serial.println();
    Serial.println("Controls (while gait runs):");
    Serial.println("  G           -> Start gait");
    Serial.println("  X           -> Stop gait");
    Serial.println("  Arrow Up    -> Direction: forward  (+X)");
    Serial.println("  Arrow Down  -> Direction: backward (-X)");
    Serial.println("  Arrow Left  -> Direction: left     (+Y)");
    Serial.println("  Arrow Right -> Direction: right    (-Y)");
    Serial.println("  W / S       -> Step height up / down (5mm)");
    Serial.println("  + / -       -> Step length up / down (5mm)");
    Serial.println("  F / V       -> Speed up / down");
    Serial.println("  R           -> Reset");
    Serial.println("  P           -> Print state");
    Serial.println("  M           -> Back to menu");
    Serial.println("=======================");
    Serial.println();
}
void handleTripodGaitControl() {
    // Always run gait update regardless of serial input
    updateTripodGait();

    if (!Serial.available()) return;
    char c = Serial.read();

    if (c == 'g' || c == 'G') { startTripodGait(); Serial.println("Gait STARTED"); return; }
    if (c == 'x' || c == 'X') { stopTripodGait();  Serial.println("Gait STOPPED"); return; }

    if (c == 'r' || c == 'R') { resetTripodGait(); printTripodGaitState(); return; }
    if (c == 'p' || c == 'P') { printTripodGaitState(); return; }
    if (c == 'm' || c == 'M') { resetTripodGait(); waitForModeChoice(); return; }

    // Step length
    if (c == '+' || c == '=') {
        gaitStepLength += 5.0f;
        Serial.print("Step length: "); Serial.println(gaitStepLength);
        return;
    }
    if (c == '-') {
        gaitStepLength = max(5.0f, gaitStepLength - 5.0f);
        Serial.print("Step length: "); Serial.println(gaitStepLength);
        return;
    }

    // Step height
    if (c == 'w' || c == 'W') {
        gaitStepHeight += 5.0f;
        Serial.print("Step height: "); Serial.println(gaitStepHeight);
        return;
    }
    if (c == 's' || c == 'S') {
        gaitStepHeight = max(5.0f, gaitStepHeight - 5.0f);
        Serial.print("Step height: "); Serial.println(gaitStepHeight);
        return;
    }

    // Speed
    if (c == 'f' || c == 'F') {
        gaitPhaseStep = min(0.1f, gaitPhaseStep + 0.005f);
        Serial.print("Speed: "); Serial.println(gaitPhaseStep, 3);
        return;
    }
    if (c == 'v' || c == 'V') {
        gaitPhaseStep = max(0.005f, gaitPhaseStep - 0.005f);
        Serial.print("Speed: "); Serial.println(gaitPhaseStep, 3);
        return;
    }

    // Direction via arrow keys
    if (c == 27) {
        while (Serial.available() < 2) delay(1);
        char c1 = Serial.read();
        char c2 = Serial.read();
        if (c1 != '[') return;

        switch (c2) {
            case 'A': gaitDirX =  1.0f; gaitDirY =  0.0f; Serial.println("Dir: FORWARD");  break;
            case 'B': gaitDirX = -1.0f; gaitDirY =  0.0f; Serial.println("Dir: BACKWARD"); break;
            case 'C': gaitDirX =  0.0f; gaitDirY =  1.0f; Serial.println("Dir: LEFT");     break;
            case 'D': gaitDirX =  0.0f; gaitDirY = -1.0f; Serial.println("Dir: RIGHT");    break;
        }
    }
}