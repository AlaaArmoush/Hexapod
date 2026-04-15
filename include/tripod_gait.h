#pragma once

#include "ik.h"

extern float gaitStepLength;  // mm, forward reach per half-cycle
extern float gaitStepHeight;  // mm, how high foot lifts during swing
extern float gaitPhaseStep;   // how fast phase advances per update (speed)
extern float gaitDirX;
extern float gaitDirY;

void resetTripodGait();
void startTripodGait();
void stopTripodGait();
void updateTripodGait();
void printTripodGaitState();
void handleTripodGaitControl();