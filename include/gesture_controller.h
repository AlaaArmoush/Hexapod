#pragma once

#include "types.h"

bool gestureStart(WaveCommand command);
bool gestureStart(GestureCommand command);
void gestureUpdate();
void gestureStop();
bool gestureIsRunning();
bool gestureIsDone();
