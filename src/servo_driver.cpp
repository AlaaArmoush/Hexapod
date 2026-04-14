#include "servo_driver.h"

Adafruit_PWMServoDriver servoDriver_0 = Adafruit_PWMServoDriver(0x40);
Adafruit_PWMServoDriver servoDriver_1 = Adafruit_PWMServoDriver(0x41);

// Reference angles before trim
int coxaRef = 90;
int femurRef = 90;
int tibiaRef = 90;

// --------------------------------------------------
// Low-level write
// --------------------------------------------------
void servoWriteRaw(uint8_t board, uint8_t ch, int angle) {
  angle = constrain(angle, 0, 180);
  int pwm = SERVO_BASELINE + angle * 2;

 if (board == 0)
    servoDriver_0.setPWM(ch, 0, pwm);
 else
    servoDriver_1.setPWM(ch, 0, pwm);
}

void servoNeutral(uint8_t board, uint8_t ch, int trim) {
  servoWriteRaw(board, ch, 90 + trim);
}

// --------------------------------------------------
// Standing pose = all joints at 90 + trim
// --------------------------------------------------
void stand() {
  Serial.println("Applying standing pose...");

  // Left Front
  servoNeutral(0, CH_LF_COXA, TRIM_LF_COXA);
  servoNeutral(0, CH_LF_FEMUR, TRIM_LF_FEMUR);
  servoNeutral(0, CH_LF_TIBIA, TRIM_LF_TIBIA);

  // Left Middle
  servoNeutral(0, CH_LM_COXA, TRIM_LM_COXA);
  servoNeutral(0, CH_LM_FEMUR, TRIM_LM_FEMUR);
  servoNeutral(0, CH_LM_TIBIA, TRIM_LM_TIBIA);

  // Left Back
  servoNeutral(0, CH_LB_COXA, TRIM_LB_COXA);
  servoNeutral(0, CH_LB_FEMUR, TRIM_LB_FEMUR);
  servoNeutral(0, CH_LB_TIBIA, TRIM_LB_TIBIA);

  // Right Front
  servoNeutral(1, CH_RF_COXA, TRIM_RF_COXA);
  servoNeutral(1, CH_RF_FEMUR, TRIM_RF_FEMUR);
  servoNeutral(1, CH_RF_TIBIA, TRIM_RF_TIBIA);

  // Right Middle
  servoNeutral(1, CH_RM_COXA, TRIM_RM_COXA);
  servoNeutral(1, CH_RM_FEMUR, TRIM_RM_FEMUR);
  servoNeutral(1, CH_RM_TIBIA, TRIM_RM_TIBIA);

  // Right Back
  servoNeutral(1, CH_RB_COXA, TRIM_RB_COXA);
  servoNeutral(1, CH_RB_FEMUR, TRIM_RB_FEMUR);
  servoNeutral(1, CH_RB_TIBIA, TRIM_RB_TIBIA);
}
