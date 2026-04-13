#pragma once

#include "config.h"
#include "servo_driver.h"

// -----------------------------------------
// State (defined in rotate_test.cpp)
// -----------------------------------------
extern int set1FemurDelta;
extern int set1CoxaDelta;
extern int set2FemurDelta;
extern int set2CoxaDelta;

// -----------------------------------------
// API
// -----------------------------------------

// Shared pose writer used by both manual and loop tests.
//
// Set 1: Right Middle, Left Front, Left Back
// Set 2: Left Middle, Right Front, Right Back
//
// Coxa: clockwise positive, counter-clockwise negative
void applyRotatePoseValues(int s1Femur, int s1Coxa, int s2Femur, int s2Coxa);

void applyRotateTestPose();
void printRotatePose();
void resetRotateTest();
void handleRotateTestControl();
