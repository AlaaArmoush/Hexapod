#include "serial_protocol.h"
#include "command_parser.h"
#include "command_router.h"
#include "config.h"
#include "display_controller.h"
#include "robot_controller.h"
#include <Arduino.h>

static char lineBuffer[192];
static size_t lineLength = 0;

void serialProtocolInit() {
  Serial.print("{\"event\":\"ready\",\"firmware\":\"hexapod\",\"protocol\":");
  Serial.print(FIRMWARE_VERSION);
  Serial.println("}");
}

void serialSendOk(const char* cmd) {
  Serial.print("{\"ok\":true,\"cmd\":\"");
  Serial.print(cmd ? cmd : "");
  Serial.println("\"}");
}

void serialSendError(const char* error) {
  Serial.print("{\"ok\":false,\"error\":\"");
  Serial.print(error ? error : "error");
  Serial.println("\"}");
}

void serialSendEvent(const char* event) {
  Serial.print("{\"event\":\"");
  Serial.print(event ? event : "");
  Serial.println("\"}");
}

void serialProtocolUpdate() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\r') continue;

    if (c == '\n') {
      lineBuffer[lineLength] = '\0';
      displayNotifyCommand();  // count every line so the boot sleep face survives the handshake
      RobotCommand command;
      ParseResult result = parseCommand(lineBuffer, command);
      lineLength = 0;

      if (result == PARSE_EMPTY) return;
      if (result == PARSE_MALFORMED) {
        robotSetLastError(lineBuffer[0] == '{' ? "malformed_json" : "malformed_command");
        serialSendError(lineBuffer[0] == '{' ? "malformed_json" : "malformed_command");
        return;
      }
      routeCommand(command);
      return;
    }

    if (lineLength < sizeof(lineBuffer) - 1) {
      lineBuffer[lineLength++] = c;
    } else {
      lineLength = 0;
      robotSetLastError("line_too_long");
      serialSendError("line_too_long");
    }
  }
}
