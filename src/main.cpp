#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

#define I2C_SDA     21
#define I2C_SCL     22
#define SERVO_FREQ  50

#define SERVO_BASELINE 100

// Board 0x40 — LEFT SIDE
#define CH_LF_COXA    15
#define CH_LF_FEMUR   14
#define CH_LF_TIBIA   13

#define CH_LM_COXA    11
#define CH_LM_FEMUR   10
#define CH_LM_TIBIA    9

#define CH_LB_COXA     7
#define CH_LB_FEMUR    6
#define CH_LB_TIBIA    5

// Board 0x41 — RIGHT SIDE
#define CH_RF_COXA     0
#define CH_RF_FEMUR    1
#define CH_RF_TIBIA    2

#define CH_RM_COXA     4
#define CH_RM_FEMUR    5
#define CH_RM_TIBIA    6

#define CH_RB_COXA    15
#define CH_RB_FEMUR   14
#define CH_RB_TIBIA   13

// ─────────────────────────────────────────────
//  *OFFSETS*
// ─────────────────────────────────────────────

// --- Left Front ---
#define TRIM_LF_COXA    12
#define TRIM_LF_FEMUR   3
#define TRIM_LF_TIBIA   8

// --- Left Middle ---
#define TRIM_LM_COXA    16
#define TRIM_LM_FEMUR   4
#define TRIM_LM_TIBIA   -5

// --- Left Back ---
#define TRIM_LB_COXA    12
#define TRIM_LB_FEMUR   3
#define TRIM_LB_TIBIA   10

/*******************************/
// --- Right Front ---
#define TRIM_RF_COXA    12
#define TRIM_RF_FEMUR   -2
#define TRIM_RF_TIBIA   3

// --- Right Middle ---
#define TRIM_RM_COXA    13
#define TRIM_RM_FEMUR   -1
#define TRIM_RM_TIBIA   7

// --- Right Back ---
#define TRIM_RB_COXA    15
#define TRIM_RB_FEMUR   12
#define TRIM_RB_TIBIA   9

Adafruit_PWMServoDriver servoDriver_0 = Adafruit_PWMServoDriver(0x40);
Adafruit_PWMServoDriver servoDriver_1 = Adafruit_PWMServoDriver(0x41);

void servoWriteRaw(uint8_t board, uint8_t ch, int angle) {
  int pwm = SERVO_BASELINE + angle * 2;
  if (board == 0) servoDriver_0.setPWM(ch, 0, pwm);
  else            servoDriver_1.setPWM(ch, 0, pwm);
}
void servoNeutral(uint8_t board, uint8_t ch, int trim) {
  servoWriteRaw(board, ch, 90 + trim);
}

void setup() {
  Serial.begin(115200);
  Wire.begin(I2C_SDA, I2C_SCL);
  delay(500);

  servoDriver_0.begin();
  servoDriver_0.setOscillatorFrequency(27000000);
  servoDriver_0.setPWMFreq(SERVO_FREQ);

  servoDriver_1.begin();
  servoDriver_1.setOscillatorFrequency(27000000);
  servoDriver_1.setPWMFreq(SERVO_FREQ);

  Serial.println("Centering all joints to 90° + trim offsets.");

  // Left Front
  servoNeutral(0, CH_LF_COXA,  TRIM_LF_COXA);
  servoNeutral(0, CH_LF_FEMUR, TRIM_LF_FEMUR);
  servoNeutral(0, CH_LF_TIBIA, TRIM_LF_TIBIA);

  // Left Middle
  servoNeutral(0, CH_LM_COXA,  TRIM_LM_COXA);
  servoNeutral(0, CH_LM_FEMUR, TRIM_LM_FEMUR);
  servoNeutral(0, CH_LM_TIBIA, TRIM_LM_TIBIA);

  // Left Back
  servoNeutral(0, CH_LB_COXA,  TRIM_LB_COXA);
  servoNeutral(0, CH_LB_FEMUR, TRIM_LB_FEMUR);
  servoNeutral(0, CH_LB_TIBIA, TRIM_LB_TIBIA);

  // Right Front
  servoNeutral(1, CH_RF_COXA,  TRIM_RF_COXA);
  servoNeutral(1, CH_RF_FEMUR, TRIM_RF_FEMUR);
  servoNeutral(1, CH_RF_TIBIA, TRIM_RF_TIBIA);

  // Right Middle
  servoNeutral(1, CH_RM_COXA,  TRIM_RM_COXA);
  servoNeutral(1, CH_RM_FEMUR, TRIM_RM_FEMUR);
  servoNeutral(1, CH_RM_TIBIA, TRIM_RM_TIBIA);

  // Right Back
  servoNeutral(1, CH_RB_COXA,  TRIM_RB_COXA);
  servoNeutral(1, CH_RB_FEMUR, TRIM_RB_FEMUR);
  servoNeutral(1, CH_RB_TIBIA, TRIM_RB_TIBIA);
}

void loop() {
  delay(1000);
}