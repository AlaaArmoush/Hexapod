#pragma once

#include "types.h"

void cameraHeadInit();
bool cameraHeadStart(CameraPanPos pos);
void cameraHeadUpdate();
void cameraHeadStop();
bool cameraHeadIsRunning();
bool cameraHeadIsDone();
CameraPanPos cameraHeadCurrentPos();
const char* cameraPanPosName(CameraPanPos pos);
