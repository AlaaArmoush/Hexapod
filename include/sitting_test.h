#pragma once

#include "config.h"
#include "servo_driver.h"

extern int femurDelta;
extern int tibiaDelta;

void applyTuningPose();
void printCurrentPose();
void resetSittingTest();
void handleSittingTestControl();
