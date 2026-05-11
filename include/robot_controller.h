#pragma once

#include "types.h"

void robotInit();
void robotUpdate();
bool robotCommandStand();
bool robotCommandSit();
bool robotCommandStop(StopMode mode);
bool robotCommandGait(GaitCommand command);
bool robotCommandRotate(RotateCommand command);
bool robotCommandWave(WaveCommand command);
bool robotCommandBody(BodyCommand command);
bool robotCommandGesture(GestureCommand command);
bool robotCommandLean(LeanCommand command);
bool robotCommandLook(LookCommand command);
bool robotCommandNod(NodShakeCommand command);
bool robotCommandShake(NodShakeCommand command);
bool robotCommandIdleStyle(IdleStyleCommand command);
RobotStatus robotGetStatus();
const char* robotModeName(RobotMode mode);
void robotSetLastError(const char* error);
