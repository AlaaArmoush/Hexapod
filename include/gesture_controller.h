#pragma once

#include "types.h"

bool gestureStart(WaveCommand command);
bool gestureStart(GestureCommand command);
bool leanStart(LeanCommand command);
bool lookStart(LookCommand command);
bool nodStart(NodShakeCommand command);
bool shakeStart(NodShakeCommand command);
bool idleStyleStart(IdleStyleCommand command);
void gestureUpdate();
void gestureStop();
bool gestureIsRunning();
bool gestureIsDone();
const char* gestureCurrentName();
