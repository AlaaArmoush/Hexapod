#pragma once
#include <ctype.h>

static inline bool equalsIgnoreCase(const char* a, const char* b) {
  if (!a || !b) return false;
  while (*a && *b) {
    if (tolower(*a) != tolower(*b)) return false;
    a++;
    b++;
  }
  return *a == '\0' && *b == '\0';
}
