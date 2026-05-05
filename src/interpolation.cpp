#include "interpolation.h"

float lerp(float a, float b, float t) {
  return a + (b - a) * t;
}

float easeInOut(float t) {
  if (t < 0.0f) return 0.0f;
  if (t > 1.0f) return 1.0f;
  return t * t * (3.0f - 2.0f * t);
}

int moveTowardI(int currentValue, int targetValue, int stepValue) {
  if (stepValue < 1) stepValue = 1;
  if (currentValue < targetValue) {
    currentValue += stepValue;
    if (currentValue > targetValue) currentValue = targetValue;
  } else if (currentValue > targetValue) {
    currentValue -= stepValue;
    if (currentValue < targetValue) currentValue = targetValue;
  }
  return currentValue;
}

float moveTowardF(float currentValue, float targetValue, float stepValue) {
  if (stepValue <= 0.0f) return targetValue;
  if (currentValue < targetValue) {
    currentValue += stepValue;
    if (currentValue > targetValue) currentValue = targetValue;
  } else if (currentValue > targetValue) {
    currentValue -= stepValue;
    if (currentValue < targetValue) currentValue = targetValue;
  }
  return currentValue;
}
