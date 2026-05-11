#pragma once

#include "types.h"

bool rotateStart(RotateCommand command);
void rotateUpdate();
void rotateStop();
bool rotateIsRunning();
bool rotateIsDone();
const RotateCommand& rotateCurrentCommand();
int rotateCyclesTarget();
int rotateCyclesDone();
