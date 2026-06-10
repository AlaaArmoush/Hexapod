#pragma once

// I2C & PWM
#define I2C_SDA 21
#define I2C_SCL 22
#define I2C_CLOCK_HZ 400000
#define PCA_LEFT_I2C_ADDRESS  0x40
#define PCA_RIGHT_I2C_ADDRESS 0x41
#define SERVO_FREQ 50

#define SERVO_BASELINE 100
#define STEP_DEGREE 5

// Smooth loop tuning
#define LOOP_INTERP_STEP 1 // degrees per update
#define LOOP_UPDATE_MS 5  // update interval
#define LOOP_HOLD_MS 27   // hold after reaching each phase
#define ROTATE_LOOP_UPDATE_MS 4 // rotate update interval; higher = slower turn

// Command-driven firmware
#define AUTO_STAND_ON_BOOT    0
#define ENABLE_DEBUG_MENU     1
#define FIRMWARE_VERSION      1
#define SERIAL_STARTUP_DELAY_MS 2000

// OLED display
#define OLED_I2C_ADDRESS  0x3C
#define OLED_RESET        -1
#define SCREEN_WIDTH      128
#define SCREEN_HEIGHT     128
#define OLED_CONTRAST     0xFF
#define OLED_FRAME_INTERVAL_MS      42UL
#define OLED_GAIT_FRAME_INTERVAL_MS 200UL
#define FACE_COMMAND_DURATION_MS 3500UL
#define LOOK_DURATION_DEFAULT_MS 1200UL
#define LOOK_DURATION_MAX_MS     4000UL

// Safe motion defaults and limits
#define GAIT_SPEED_DEFAULT    0.06f
#define GAIT_SPEED_MAX        0.06f
#define GAIT_SPEED_MIN        0.005f
#define GAIT_STEP_LEN_DEFAULT 30.0f
#define GAIT_STEP_LEN_MAX     60.0f
#define GAIT_STEP_HT_DEFAULT  25.0f
#define GAIT_STEP_HT_MAX      70.0f
#define GAIT_STEPS_DEFAULT    1
#define GAIT_DURATION_MS_MAX  10000UL
#define GAIT_STEPS_MAX        50
#define GAIT_DISTANCE_CM_MAX  200.0f
#define GAIT_CM_PER_CYCLE_DEFAULT 5.0f
#define BODY_OFFSET_MAX       60.0f
#define ROTATE_CYCLES_DEFAULT 1
#define ROTATE_CYCLES_MAX     12

// Expressive motion limits
#define LEAN_AMOUNT_MAX_MM    60.0f
#define LEAN_DURATION_MAX_MS  2000UL
#define NOD_COUNT_MAX         6
#define SHAKE_COUNT_MAX       6
#define LOOK_BODY_OFFSET_Y    25.0f
#define LOOK_BODY_OFFSET_X    18.0f

// Camera head / face pan servo — MG996R on PCA9685.
// Default: board 0 (0x40), channel 7. Keep board/channel centralized for wiring changes.
#define CAMERA_SERVO_BOARD              0
#define CAMERA_SERVO_CHANNEL            10
#define CAMERA_SERVO_MIN_DEG            30
#define CAMERA_SERVO_MAX_DEG            150
#define CAMERA_SERVO_TRIM               0
#define CAMERA_PAN_LEFT_DEG             140
#define CAMERA_PAN_FRONT_LEFT_DEG       120
#define CAMERA_PAN_CENTER_DEG           90
#define CAMERA_PAN_FRONT_RIGHT_DEG      60
#define CAMERA_PAN_RIGHT_DEG            40
#define CAMERA_SERVO_SLEW_DEG_PER_UPDATE 5
#define CAMERA_SERVO_UPDATE_MS          10UL

// Sit pose targets copied from the sitting branch global sit() function.
#define SIT_FEMUR_DELTA   75
#define SIT_TIBIA_DELTA   30
#define SIT_INTERP_STEP    1

// -----------------------------------------
// Board 0x40 — LEFT SIDE
// -----------------------------------------
#define CH_LF_COXA 15
#define CH_LF_FEMUR 14
#define CH_LF_TIBIA 13

#define CH_LM_COXA 6
#define CH_LM_FEMUR 5
#define CH_LM_TIBIA 4

#define CH_LB_COXA 2
#define CH_LB_FEMUR 1
#define CH_LB_TIBIA 0

// -----------------------------------------
// Board 0x41 — RIGHT SIDE
// -----------------------------------------
#define CH_RF_COXA 2
#define CH_RF_FEMUR 1
#define CH_RF_TIBIA 0

#define CH_RM_COXA 6
#define CH_RM_FEMUR 5
#define CH_RM_TIBIA 4

#define CH_RB_COXA 15
#define CH_RB_FEMUR 14
#define CH_RB_TIBIA 13

// -----------------------------------------
// TRIM OFFSETS
// -----------------------------------------
#define TRIM_LF_COXA 12
#define TRIM_LF_FEMUR 13
#define TRIM_LF_TIBIA 8

#define TRIM_LM_COXA 16
#define TRIM_LM_FEMUR 14
#define TRIM_LM_TIBIA -5

#define TRIM_LB_COXA 12
#define TRIM_LB_FEMUR 4
#define TRIM_LB_TIBIA 10

#define TRIM_RF_COXA 12
#define TRIM_RF_FEMUR -12
#define TRIM_RF_TIBIA 3

#define TRIM_RM_COXA 13
#define TRIM_RM_FEMUR -11
#define TRIM_RM_TIBIA 7

#define TRIM_RB_COXA 13
#define TRIM_RB_FEMUR 2
#define TRIM_RB_TIBIA 9
