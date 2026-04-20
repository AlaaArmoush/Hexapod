#include "wave.h"
#include "menu.h"
#include <Arduino.h>

#define WAVE_LEG 3 // RF leg

static float lerpf(float a, float b, float t) {
    return a + (b - a) * t;
}

void playWaveAnimation() {
    Serial.println("Starting wave animation...");
    
    // 1. Lean body left (move feet right -> target_y = -40)
    for (int step = 0; step <= 20; step++) {
        float y = lerpf(0.0f, -40.0f, (float)step / 20.0f);
        for (int i = 0; i < 6; i++) {
            legIK(i, 0.0f, y, 0.0f);
        }
        delay(10);
    }
    
    // 2. Raise RF leg
    // Z goes up to 100, X stays at 0
    for (int step = 0; step <= 20; step++) {
        float z = lerpf(0.0f, 100.0f, (float)step / 20.0f);
        float x = lerpf(0.0f, 0.0f, (float)step / 20.0f);
        for (int i = 0; i < 6; i++) {
            if (i == WAVE_LEG) {
                legIK(i, x, 0.0f, z);
            } else {
                legIK(i, 0.0f, -40.0f, 0.0f);
            }
        }
        delay(10);
    }
    
    // 3. Wave by sweeping coxa 
    const LegDesc& rf = LEGS[WAVE_LEG];
    int baseCoxaAngle = 97; // Approx angle from IK at (40, 0, 100)
    int waveCount = 2;
    
    for (int w = 0; w < waveCount; w++) {
        for (int a = baseCoxaAngle; a <= baseCoxaAngle + 40; a += 3) {
            servoWriteRaw(rf.board_coxa, rf.ch_coxa, a + rf.trim_coxa);
            delay(15); 
        }
        for (int a = baseCoxaAngle + 40; a >= baseCoxaAngle - 30; a -= 3) {
            servoWriteRaw(rf.board_coxa, rf.ch_coxa, a + rf.trim_coxa);
            delay(15); 
        }
        for (int a = baseCoxaAngle - 30; a <= baseCoxaAngle; a += 3) {
            servoWriteRaw(rf.board_coxa, rf.ch_coxa, a + rf.trim_coxa);
            delay(15); 
        }
    }
    
    // 4. Put leg down
    for (int step = 0; step <= 20; step++) {
        float z = lerpf(100.0f, 0.0f, (float)step / 20.0f);
        float x = lerpf(0.0f, 0.0f, (float)step / 20.0f);
        for (int i = 0; i < 6; i++) {
            if (i == WAVE_LEG) {
                legIK(i, x, 0.0f, z);
            } else {
                legIK(i, 0.0f, -40.0f, 0.0f);
            }
        }
        delay(10);
    }
    
    // 5. Center body
    for (int step = 0; step <= 20; step++) {
        float y = lerpf(-40.0f, 0.0f, (float)step / 20.0f);
        for (int i = 0; i < 6; i++) {
            legIK(i, 0.0f, y, 0.0f);
        }
        delay(10);
    }
    
    Serial.println("Wave complete.");
}

void printWaveState() {
    Serial.println();
    Serial.println("===== WAVE =====");
    Serial.println("  W -> Play Wave Animation");
    Serial.println("  M -> Back to menu");
    Serial.println("================");
    Serial.println();
}

void handleWaveControl() {
    if (!Serial.available()) return;
    char c = Serial.read();

    if (c == 'w' || c == 'W') { 
        playWaveAnimation(); 
        return; 
    }
    if (c == 'm' || c == 'M') { 
        waitForModeChoice(); 
        return; 
    }
}
