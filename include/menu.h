#pragma once

#include "config.h"
#include "types.h"

extern TestMode currentMode;

void printMenu();
void waitForModeChoice();

#if ENABLE_DEBUG_MENU
void debugMenuUpdate();
#else
inline void debugMenuUpdate() {}
#endif
