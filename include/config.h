#pragma once

// I2C & PWM
#define I2C_SDA 21
#define I2C_SCL 22
#define SERVO_FREQ 50

#define SERVO_BASELINE 100
#define STEP_DEGREE 5

// Smooth loop tuning
#define LOOP_INTERP_STEP 1 // degrees per update
#define LOOP_UPDATE_MS 5  // update interval
#define LOOP_HOLD_MS 40   // hold after reaching each phase

// -----------------------------------------
// Board 0x40 — LEFT SIDE
// -----------------------------------------
#define CH_LF_COXA 15
#define CH_LF_FEMUR 14
#define CH_LF_TIBIA 13

#define CH_LM_COXA 11
#define CH_LM_FEMUR 10
#define CH_LM_TIBIA 9

#define CH_LB_COXA 7
#define CH_LB_FEMUR 6
#define CH_LB_TIBIA 5

// -----------------------------------------
// Board 0x41 — RIGHT SIDE
// -----------------------------------------
#define CH_RF_COXA 0
#define CH_RF_FEMUR 1
#define CH_RF_TIBIA 2

#define CH_RM_COXA 4
#define CH_RM_FEMUR 5
#define CH_RM_TIBIA 6

#define CH_RB_COXA 15
#define CH_RB_FEMUR 14
#define CH_RB_TIBIA 13

// -----------------------------------------
// TRIM OFFSETS
// -----------------------------------------
#define TRIM_LF_COXA 12
#define TRIM_LF_FEMUR 3
#define TRIM_LF_TIBIA 8

#define TRIM_LM_COXA 16
#define TRIM_LM_FEMUR 4
#define TRIM_LM_TIBIA -5

#define TRIM_LB_COXA 12
#define TRIM_LB_FEMUR 3
#define TRIM_LB_TIBIA 10

#define TRIM_RF_COXA 12
#define TRIM_RF_FEMUR -2
#define TRIM_RF_TIBIA 3

#define TRIM_RM_COXA 13
#define TRIM_RM_FEMUR -1
#define TRIM_RM_TIBIA 7

#define TRIM_RB_COXA 13
#define TRIM_RB_FEMUR 12
#define TRIM_RB_TIBIA 9
