#pragma once

#include "config.h"
#include <Adafruit_PWMServoDriver.h>
#include <Arduino.h>
#include <Wire.h>

// -----------------------------------------
// PWM driver instances (defined in servo_driver.cpp)
// -----------------------------------------
extern Adafruit_PWMServoDriver servoDriver_0; // 0x40 — Left side
extern Adafruit_PWMServoDriver servoDriver_1; // 0x41 — Right side

// -----------------------------------------
// Shared reference angles (defined in servo_driver.cpp)
// All pose writers offset from these before adding their deltas.
// -----------------------------------------
extern int coxaRef;
extern int femurRef;
extern int tibiaRef;

// -----------------------------------------
// API
// -----------------------------------------
void servoWriteRaw(uint8_t board, uint8_t ch, int angle);
void servoNeutral(uint8_t board, uint8_t ch, int trim);
uint8_t pcaAddressForBoard(uint8_t board);
bool pcaBoardPresent(uint8_t board);
uint8_t pcaBoardI2cError(uint8_t board);
void stand();
