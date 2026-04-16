#pragma once

#include "ik.h"

// Current body offset applied to all 6 legs
extern float bodyX;  // forward/back  (mm)
extern float bodyY;  // left/right    (mm)
extern float bodyZ;  // up/down       (mm)

void applyBodyOffset();
void printBodyMotionPose();
void resetBodyMotionTest();
void handleBodyMotionTestControl();