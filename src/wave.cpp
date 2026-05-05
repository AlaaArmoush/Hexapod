#include "wave.h"
#include "gesture_controller.h"
#include "menu.h"
#include <Arduino.h>

void playWaveAnimation() {
    WaveCommand command;
    command.leg = 3;
    command.count = 2;
    gestureStart(command);
    Serial.println("Wave started.");
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
    gestureUpdate();

    if (!Serial.available()) return;
    char c = Serial.read();

    if (c == 'w' || c == 'W') {
        playWaveAnimation();
        return;
    }
    if (c == 'm' || c == 'M') {
        gestureStop();
        return;
    }
}
