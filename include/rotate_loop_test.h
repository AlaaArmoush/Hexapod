#pragma once

#include "config.h"
#include "rotate_test.h"
#include "types.h"

extern LoopDirection loopDirection;

extern int loopSet1FemurCurrent;
extern int loopSet1CoxaCurrent;
extern int loopSet2FemurCurrent;
extern int loopSet2CoxaCurrent;

extern int loopSet1FemurTarget;
extern int loopSet1CoxaTarget;
extern int loopSet2FemurTarget;
extern int loopSet2CoxaTarget;

void printRotateLoopPose();
void resetRotateLoopTest();
void startRotateLoop(LoopDirection dir);
void updateRotateLoopTest();
void handleRotateLoopTestControl();
