#pragma once

#include "types.h"

enum ParseResult {
  PARSE_OK,
  PARSE_MALFORMED,
  PARSE_EMPTY
};

ParseResult parseCommand(const char* line, RobotCommand& out);
