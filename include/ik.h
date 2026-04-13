#pragma once

#include "config.h"
#include "servo_driver.h"
#include <math.h>

// -----------------------------------------
// Leg segment lengths (mm)
// -----------------------------------------
#define LENGTH_COXA     50.0f
#define LENGTH_FEMUR    80.0f
#define LENGTH_TIBIA   120.0f

#define LEG_ZERO_X  130.0f
#define LEG_ZERO_Z -120.0f

struct LegDesc {
    // Hardware
    int8_t  board_coxa,  ch_coxa,  trim_coxa;
    int8_t  board_femur, ch_femur, trim_femur;
    int8_t  board_tibia, ch_tibia, trim_tibia;

    // Kinematics
    float    mountAngle;   // degrees CCW from forward axis
    bool     mirrored;     // true = left side
};

extern const LegDesc LEGS[6];
void legIK(int legIndex, float target_x, float target_y, float target_z);

// Write all 6 legs to a standing pose using IK
void ikStand();