#include <Arduino.h>
#include <Wire.h>

#ifdef I2C_SCANNER

#define SDA_PIN 21
#define SCL_PIN 22

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("I2C SCANNER START");
  Serial.println("SDA: GPIO21, SCL: GPIO22");

  pinMode(SDA_PIN, INPUT_PULLUP);
  pinMode(SCL_PIN, INPUT_PULLUP);
  Serial.print("Idle SDA=");
  Serial.print(digitalRead(SDA_PIN));
  Serial.print(" SCL=");
  Serial.println(digitalRead(SCL_PIN));

  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(10000);
  Wire.setTimeOut(50);
}

void loop() {
  byte count = 0;

  Serial.println("Scanning...");

  for (byte address = 1; address < 127; address++) {
    Wire.beginTransmission(address);
    byte error = Wire.endTransmission();

    if (error == 0) {
      Serial.print("Found I2C device at 0x");
      if (address < 16) Serial.print("0");
      Serial.println(address, HEX);
      count++;
    }
  }

  if (count == 0) {
    Serial.println("No I2C devices found.");
  } else {
    Serial.print("Found ");
    Serial.print(count);
    Serial.println(" device(s).");
  }

  Serial.println();
  delay(2000);
}

#else

#include "config.h"
#include "display_controller.h"
#include "gait_controller.h"
#include "menu.h"
#include "robot_controller.h"
#include "serial_protocol.h"
#include "servo_driver.h"

static void printPcaStatus(const char *name, uint8_t board) {
  uint8_t address = pcaAddressForBoard(board);
  Serial.print("PCA9685 ");
  Serial.print(name);
  Serial.print(" 0x");
  if (address < 16) Serial.print("0");
  Serial.print(address, HEX);
  Serial.print(": ");
  Serial.println(pcaBoardPresent(board) ? "FOUND" : "MISSING");
}

void setup() {
  Serial.begin(115200);
  delay(SERIAL_STARTUP_DELAY_MS);

  Wire.begin(I2C_SDA, I2C_SCL);
  Wire.setClock(I2C_CLOCK_HZ);
  Wire.setTimeOut(50);
  Serial.println("Checking PCA9685 I2C devices...");
  printPcaStatus("left", 0);
  printPcaStatus("right", 1);

  // ESP32 I2C peripheral can lock after a NACK during probe.
  // Flush and reinitialise the bus before handing it to the drivers.
  Wire.end();
  delay(10);
  Wire.begin(I2C_SDA, I2C_SCL);
  Wire.setClock(I2C_CLOCK_HZ);
  Wire.setTimeOut(50);

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

  static unsigned long lastDisplayUpdateMs = 0;
  unsigned long now = millis();
  unsigned long displayInterval = gaitIsRunning() ? OLED_GAIT_FRAME_INTERVAL_MS : OLED_FRAME_INTERVAL_MS;
  if (now - lastDisplayUpdateMs >= displayInterval) {
    lastDisplayUpdateMs = now;
    displayUpdate();
  }

#if ENABLE_DEBUG_MENU
  debugMenuUpdate();
#endif
  delay(5);
}

#endif
