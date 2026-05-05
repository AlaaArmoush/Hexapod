#pragma once

void serialProtocolInit();
void serialProtocolUpdate();
void serialSendOk(const char* cmd);
void serialSendError(const char* error);
void serialSendEvent(const char* event);
