#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

#define I2C_SDA     21
#define I2C_SCL     22
#define SERVO_FREQ  50

#define SERVO_BASELINE 100
#define STEP_DEGREE 5

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

// -----------------------------
// OFFSETS
// -----------------------------
#define TRIM_LF_COXA    12
#define TRIM_LF_FEMUR    3
#define TRIM_LF_TIBIA    8

#define TRIM_LM_COXA    16
#define TRIM_LM_FEMUR    4
#define TRIM_LM_TIBIA   -5

#define TRIM_LB_COXA    12
#define TRIM_LB_FEMUR    3
#define TRIM_LB_TIBIA   10

#define TRIM_RF_COXA    12
#define TRIM_RF_FEMUR   -2
#define TRIM_RF_TIBIA    3

#define TRIM_RM_COXA    13
#define TRIM_RM_FEMUR   -1
#define TRIM_RM_TIBIA    7

#define TRIM_RB_COXA    15
#define TRIM_RB_FEMUR   12
#define TRIM_RB_TIBIA    9

Adafruit_PWMServoDriver servoDriver_0 = Adafruit_PWMServoDriver(0x40);
Adafruit_PWMServoDriver servoDriver_1 = Adafruit_PWMServoDriver(0x41);

// Reference angles before trim
int coxaRef  = 90;
int femurRef = 90;
int tibiaRef = 90;

// Tuning deltas relative to standing reference
int femurDelta = 0;
int tibiaDelta = 0;

// --------------------------------------------------
// Low-level write
// --------------------------------------------------
void servoWriteRaw(uint8_t board, uint8_t ch, int angle) {
  angle = constrain(angle, 0, 180);
  int pwm = SERVO_BASELINE + angle * 2;

  if (board == 0) servoDriver_0.setPWM(ch, 0, pwm);
  else            servoDriver_1.setPWM(ch, 0, pwm);
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

// --------------------------------------------------
// Apply current sitting-tuning pose
//
// Directional logic used:
// Right Femur: downward + / upward -
// Left  Femur: downward - / upward +
// Right Tibia: inward - / outward +
// Left  Tibia: inward + / outward -
//
// Up arrow    => femur upward
// Down arrow  => femur downward
// Left arrow  => tibia inward
// Right arrow => tibia outward
// --------------------------------------------------
void applyTuningPose() {
  // Coxa stays at standing neutral
  servoWriteRaw(0, CH_LF_COXA, coxaRef + TRIM_LF_COXA);
  servoWriteRaw(0, CH_LM_COXA, coxaRef + TRIM_LM_COXA);
  servoWriteRaw(0, CH_LB_COXA, coxaRef + TRIM_LB_COXA);

  servoWriteRaw(1, CH_RF_COXA, coxaRef + TRIM_RF_COXA);
  servoWriteRaw(1, CH_RM_COXA, coxaRef + TRIM_RM_COXA);
  servoWriteRaw(1, CH_RB_COXA, coxaRef + TRIM_RB_COXA);

  // Femur
  // Left upward = positive, downward = negative
  servoWriteRaw(0, CH_LF_FEMUR, femurRef + femurDelta + TRIM_LF_FEMUR);
  servoWriteRaw(0, CH_LM_FEMUR, femurRef + femurDelta + TRIM_LM_FEMUR);
  servoWriteRaw(0, CH_LB_FEMUR, femurRef + femurDelta + TRIM_LB_FEMUR);

  // Right upward = negative, downward = positive
  servoWriteRaw(1, CH_RF_FEMUR, femurRef - femurDelta + TRIM_RF_FEMUR);
  servoWriteRaw(1, CH_RM_FEMUR, femurRef - femurDelta + TRIM_RM_FEMUR);
  servoWriteRaw(1, CH_RB_FEMUR, femurRef - femurDelta + TRIM_RB_FEMUR);

  // Tibia
  // Left inward = positive, outward = negative
  servoWriteRaw(0, CH_LF_TIBIA, tibiaRef + tibiaDelta + TRIM_LF_TIBIA);
  servoWriteRaw(0, CH_LM_TIBIA, tibiaRef + tibiaDelta + TRIM_LM_TIBIA);
  servoWriteRaw(0, CH_LB_TIBIA, tibiaRef + tibiaDelta + TRIM_LB_TIBIA);

  // Right inward = negative, outward = positive
  servoWriteRaw(1, CH_RF_TIBIA, tibiaRef - tibiaDelta + TRIM_RF_TIBIA);
  servoWriteRaw(1, CH_RM_TIBIA, tibiaRef - tibiaDelta + TRIM_RM_TIBIA);
  servoWriteRaw(1, CH_RB_TIBIA, tibiaRef - tibiaDelta + TRIM_RB_TIBIA);
}

void printCurrentPose() {
  Serial.println();
  Serial.println("===== CURRENT TUNING VALUES =====");
  Serial.print("Femur delta from stand: ");
  Serial.println(femurDelta);
  Serial.print("Tibia delta from stand: ");
  Serial.println(tibiaDelta);

  Serial.println("Actual commanded femur angles:");
  Serial.print("  Left  femurs  = ");
  Serial.println(femurRef + femurDelta);
  Serial.print("  Right femurs  = ");
  Serial.println(femurRef - femurDelta);

  Serial.println("Actual commanded tibia angles:");
  Serial.print("  Left  tibias  = ");
  Serial.println(tibiaRef + tibiaDelta);
  Serial.print("  Right tibias  = ");
  Serial.println(tibiaRef - tibiaDelta);

  Serial.println();
  Serial.println("Controls:");
  Serial.println("  Up Arrow    -> Femur upward");
  Serial.println("  Down Arrow  -> Femur downward");
  Serial.println("  Left Arrow  -> Tibia inward");
  Serial.println("  Right Arrow -> Tibia outward");
  Serial.println("  r           -> Reset femur/tibia to standing reference");
  Serial.println("  p           -> Print current values");
  Serial.println("=================================");
  Serial.println();
}

// --------------------------------------------------
// Wait until user types s or S
// --------------------------------------------------
void waitForStandCommand() {
  Serial.println();
  Serial.println("Type 's' or 'S' in Serial Monitor to stand.");
  Serial.println();

  while (true) {
    if (Serial.available()) {
      char c = Serial.read();
      if (c == 's' || c == 'S') {
        stand();
        femurDelta = 0;
        tibiaDelta = 0;
        applyTuningPose();
        printCurrentPose();
        return;
      }
    }
    delay(10);
  }
}

// --------------------------------------------------
// Parse arrow keys
// Most terminals send:
// Up    = ESC [ A
// Down  = ESC [ B
// Right = ESC [ C
// Left  = ESC [ D
// --------------------------------------------------
void handleSerialControl() {
  if (!Serial.available()) return;

  char c = Serial.read();

  // simple keys
  if (c == 'r' || c == 'R') {
    femurDelta = 0;
    tibiaDelta = 0;
    applyTuningPose();
    printCurrentPose();
    return;
  }

  if (c == 'p' || c == 'P') {
    printCurrentPose();
    return;
  }

  // arrow keys
  if (c == 27) { // ESC
    while (Serial.available() < 2) {
      delay(1);
    }

    char c1 = Serial.read(); // should be '['
    char c2 = Serial.read(); // A/B/C/D

    if (c1 != '[') return;

    switch (c2) {
      case 'A': // Up -> femur downwards
        femurDelta -= STEP_DEGREE;
        applyTuningPose();
        Serial.println("Down Arrow -> Femur downward");
        printCurrentPose();
        break;

      case 'B': // Down -> femur upward
        femurDelta += STEP_DEGREE;
        applyTuningPose();
        Serial.println("Up Arrow -> Femur downward");
        printCurrentPose();
        break;

      case 'C': // Right -> tibia outward
        tibiaDelta -= STEP_DEGREE;
        applyTuningPose();
        Serial.println("Right Arrow: Tibia outward");
        printCurrentPose();
        break;

      case 'D': // Left -> tibia inward
        tibiaDelta += STEP_DEGREE;
        applyTuningPose();
        Serial.println("Left Arrow: Tibia inward");
        printCurrentPose();
        break;
    }
  }
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

  waitForStandCommand();
}

void loop() {
  handleSerialControl();
  delay(5);
}