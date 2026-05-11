#include "config.h"
#include "display_controller.h"
#include "menu.h"
#include "robot_controller.h"
#include "serial_protocol.h"
#include "servo_driver.h"
#include <Arduino.h>
#include <Wire.h>

void setup() {
  Serial.begin(115200);
  delay(SERIAL_STARTUP_DELAY_MS);

  Wire.begin(I2C_SDA, I2C_SCL);

  servoDriver_0.begin();
  servoDriver_0.setOscillatorFrequency(27000000);
  servoDriver_0.setPWMFreq(SERVO_FREQ);

  servoDriver_1.begin();
  servoDriver_1.setOscillatorFrequency(27000000);
  servoDriver_1.setPWMFreq(SERVO_FREQ);

  displayInit();
  robotInit();
  serialProtocolInit();

#if AUTO_STAND_ON_BOOT
  robotCommandStand();
#endif
}

void loop() {
  serialProtocolUpdate();
  robotUpdate();
  displayUpdate();
#if ENABLE_DEBUG_MENU
  debugMenuUpdate();
#endif
  delay(5);
}
