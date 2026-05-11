#pragma once

#include "types.h"

bool gaitStart(GaitCommand command);
void gaitUpdate();
void gaitStopSmooth();
bool gaitIsRunning();
bool gaitIsDone();
const GaitCommand& gaitCurrentCommand();
const char* gaitDirName(GaitDir dir);
const char* motionBoundName(MotionBoundType bound);
int gaitStepsTarget();
int gaitStepsDone();
unsigned long gaitDurationTargetMs();
unsigned long gaitDurationElapsedMs();
