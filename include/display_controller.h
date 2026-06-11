#pragma once

enum FaceState {
  FACE_IDLE,
  FACE_NEUTRAL,
  FACE_HAPPY,
  FACE_CURIOUS,
  FACE_SCARED,
  FACE_SLEEPY,
  FACE_LISTENING,
  FACE_WALKING,
  FACE_ROTATING,
  FACE_WAVING,
  FACE_ERROR,
  FACE_BLINKING,
  FACE_THINKING,
  FACE_LOVE,
  FACE_SURPRISED,
  FACE_STARSTRUCK,
  FACE_DIZZY,
  FACE_CONFUSED,
  FACE_SAD,
  FACE_SLEEP,
  FACE_LOADING,
  FACE_ALERT,
  FACE_LOW_BATTERY,
  FACE_BOOP,
  FACE_SCAN,
  FACE_CLOCK,
  FACE_CALENDAR,
  FACE_SEARCH,
  FACE_CAMERA,
  FACE_MEMORY,
  FACE_TIMER,
  FACE_REMINDER,
  FACE_BATTERY,
  FACE_SYSTEM,
  FACE_WIFI,
  FACE_MICROPHONE,
  FACE_AUDIO,
  FACE_SUCCESS,
  FACE_COUNT
};

void displayInit();
void displayUpdate();
void displaySetFace(FaceState face);
void displaySetTemporaryFace(FaceState face, unsigned long durationMs);
void displaySetFaceText(const char* text);
void displayRestoreBaseFace();
FaceState displayGetCurrentFace();
bool displayIsTemporaryFace();
const char* displayFaceName(FaceState face);
bool displayParseFaceName(const char* name, FaceState& out);
void displayNotifyCommand();
void displaySetGaze(const char* dir);
void displayCenterGaze();
void displayTriggerBlink();
