#pragma once

#include "types.h"

bool gaitStart(GaitCommand command);
void gaitUpdate();
void gaitStopSmooth();
bool gaitIsRunning();
