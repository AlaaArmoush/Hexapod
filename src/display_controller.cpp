#include "display_controller.h"
#include "config.h"
#include <Adafruit_GFX.h>
#include <Adafruit_SH110X.h>
#include <Arduino.h>
#ifdef DEFAULT
#undef DEFAULT
#endif
#include <FluxGarage_RoboEyes.h>
#include <Wire.h>
#include <ctype.h>
#include <string.h>

static Adafruit_SH1107 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);
static RoboEyes<Adafruit_SH1107> roboEyes(display);

static bool available = false;
static FaceState baseFace = FACE_IDLE;
static FaceState currentFace = FACE_IDLE;
static bool tempActive = false;
static unsigned long tempStartedAt = 0;
static unsigned long tempDurationMs = 0;
static unsigned char currentGaze = DEFAULT;
static unsigned long lastCustomDrawMs = 0;
static unsigned long customFaceStartedAt = 0;

static bool equalsIgnoreCase(const char* a, const char* b) {
  if (!a || !b) return false;
  while (*a && *b) {
    if (tolower(*a) != tolower(*b)) return false;
    a++;
    b++;
  }
  return *a == '\0' && *b == '\0';
}

static void resetRoboEyesState() {
  roboEyes.setMood(DEFAULT);
  roboEyes.setPosition(DEFAULT);
  roboEyes.setAutoblinker(OFF);
  roboEyes.setIdleMode(OFF);
  roboEyes.setCuriosity(OFF);
  roboEyes.setCyclops(OFF);
  roboEyes.setHFlicker(OFF, 0);
  roboEyes.setVFlicker(OFF, 0);
  roboEyes.setSweat(OFF);
  roboEyes.setWidth(36, 36);
  roboEyes.setHeight(36, 36);
  roboEyes.setBorderradius(8, 8);
  roboEyes.setSpacebetween(10);
}

static void setOledDrive() {
  display.setContrast(OLED_CONTRAST);
}

static void applyGaze() {
  if (available) roboEyes.setPosition(currentGaze);
}

static bool isCustomFace(FaceState face) {
  return face == FACE_ERROR || face == FACE_THINKING || face == FACE_LOVE ||
         face == FACE_SURPRISED || face == FACE_STARSTRUCK || face == FACE_DIZZY ||
         face == FACE_CONFUSED || face == FACE_SAD || face == FACE_SLEEP ||
         face == FACE_LOADING || face == FACE_ALERT || face == FACE_LOW_BATTERY ||
         face == FACE_BOOP || face == FACE_SCAN || face == FACE_CLOCK ||
         face == FACE_CALENDAR || face == FACE_SEARCH || face == FACE_CAMERA ||
         face == FACE_MEMORY || face == FACE_TIMER || face == FACE_REMINDER ||
         face == FACE_BATTERY || face == FACE_SYSTEM || face == FACE_WIFI ||
         face == FACE_MICROPHONE || face == FACE_SPEAKING || face == FACE_SUCCESS;
}

static void drawThickLine(int x0, int y0, int x1, int y1, int thickness) {
  for (int offset = -(thickness / 2); offset <= thickness / 2; offset++) {
    display.drawLine(x0 + offset, y0, x1 + offset, y1, SH110X_WHITE);
    display.drawLine(x0, y0 + offset, x1, y1 + offset, SH110X_WHITE);
  }
}

static void drawEyeX(int cx, int cy, int radius) {
  drawThickLine(cx - radius, cy - radius, cx + radius, cy + radius, 5);
  drawThickLine(cx + radius, cy - radius, cx - radius, cy + radius, 5);
}

static void drawHeart(int cx, int cy, int scale) {
  const uint16_t rows[] = {
    0b00110001100,
    0b01111011110,
    0b11111111111,
    0b11111111111,
    0b01111111110,
    0b00111111100,
    0b00011111000,
    0b00001110000,
    0b00000100000
  };
  const int cell = scale;
  const int originX = cx - (11 * cell) / 2;
  const int originY = cy - (9 * cell) / 2;
  for (int y = 0; y < 9; y++) {
    for (int x = 0; x < 11; x++) {
      if (rows[y] & (1 << (10 - x))) {
        display.fillRect(originX + x * cell, originY + y * cell, cell, cell, SH110X_WHITE);
      }
    }
  }
}

static void drawStar(int cx, int cy, int r) {
  display.fillTriangle(cx, cy - r, cx - 4, cy - 2, cx + 4, cy - 2, SH110X_WHITE);
  display.fillTriangle(cx, cy + r, cx - 4, cy + 2, cx + 4, cy + 2, SH110X_WHITE);
  display.fillTriangle(cx - r, cy, cx - 2, cy - 4, cx - 2, cy + 4, SH110X_WHITE);
  display.fillTriangle(cx + r, cy, cx + 2, cy - 4, cx + 2, cy + 4, SH110X_WHITE);
  display.fillRect(cx - 4, cy - 4, 9, 9, SH110X_WHITE);
}

static void drawSpiralEye(int cx, int cy, int phase) {
  int radius = 16;
  display.drawCircle(cx, cy, radius, SH110X_WHITE);
  for (int r = radius; r > 3; r -= 4) {
    int x0 = cx - r + ((phase / 2) % 3);
    int y0 = cy - r / 2;
    int w = r * 2;
    int h = r;
    display.drawRoundRect(x0, y0, w, h, 4, SH110X_WHITE);
  }
  display.fillCircle(cx + ((phase % 3) - 1), cy, 2, SH110X_WHITE);
}

static void drawQuestionEye(int cx, int cy) {
  display.fillCircle(cx, cy - 10, 12, SH110X_WHITE);
  display.fillCircle(cx - 4, cy - 10, 6, SH110X_BLACK);
  display.fillRect(cx + 2, cy - 2, 8, 14, SH110X_WHITE);
  display.fillCircle(cx + 6, cy + 18, 3, SH110X_WHITE);
}

static void drawDroopyEye(int cx, int cy, int w, int h) {
  display.fillRoundRect(cx - w / 2, cy - h / 2, w, h, 8, SH110X_WHITE);
  display.fillTriangle(cx - w / 2, cy - h / 2, cx + w / 2, cy - h / 2, cx + w / 2, cy + 2, SH110X_BLACK);
}

static void drawZed(int x, int y, int size) {
  display.drawFastHLine(x, y, size, SH110X_WHITE);
  display.drawLine(x + size - 1, y, x, y + size - 1, SH110X_WHITE);
  display.drawFastHLine(x, y + size - 1, size, SH110X_WHITE);
}

static void drawBatteryIcon(int x, int y, int w, int h) {
  display.drawRect(x, y, w, h, SH110X_WHITE);
  display.fillRect(x + w, y + h / 3, 3, h / 3, SH110X_WHITE);
  display.fillRect(x + 3, y + 3, max(2, w / 4), h - 6, SH110X_WHITE);
}

static void drawToolFacePlaceholder(FaceState face, unsigned long age) {
  int pulse = 2 + (int)((age / 180) % 4);
  display.drawRoundRect(24, 24, 80, 68, 8, SH110X_WHITE);
  display.drawRoundRect(28, 28, 72, 60, 6, SH110X_WHITE);

  if (face == FACE_CLOCK) {
    display.drawCircle(64, 58, 22, SH110X_WHITE);
    display.drawLine(64, 58, 64, 42, SH110X_WHITE);
    display.drawLine(64, 58, 78, 58, SH110X_WHITE);
  } else if (face == FACE_CALENDAR) {
    display.drawRect(42, 38, 44, 36, SH110X_WHITE);
    display.fillRect(42, 38, 44, 8, SH110X_WHITE);
    display.drawFastHLine(48, 56, 32, SH110X_WHITE);
    display.drawFastVLine(56, 48, 22, SH110X_WHITE);
    display.drawFastVLine(72, 48, 22, SH110X_WHITE);
  } else if (face == FACE_SEARCH) {
    display.drawCircle(58, 54, 17, SH110X_WHITE);
    drawThickLine(70, 66, 84, 80, 3);
  } else if (face == FACE_CAMERA) {
    display.drawRoundRect(38, 42, 52, 34, 5, SH110X_WHITE);
    display.drawCircle(64, 59, 12, SH110X_WHITE);
    display.fillCircle(64, 59, 4, SH110X_WHITE);
  } else if (face == FACE_MEMORY || face == FACE_SYSTEM) {
    display.drawRect(44, 38, 40, 40, SH110X_WHITE);
    for (int i = 0; i < 4; i++) {
      display.drawFastHLine(36, 44 + i * 9, 8, SH110X_WHITE);
      display.drawFastHLine(84, 44 + i * 9, 8, SH110X_WHITE);
      display.drawFastVLine(50 + i * 9, 30, 8, SH110X_WHITE);
      display.drawFastVLine(50 + i * 9, 78, 8, SH110X_WHITE);
    }
    display.fillRect(54, 48, 20, 20, SH110X_WHITE);
  } else if (face == FACE_TIMER) {
    display.drawTriangle(48, 36, 80, 36, 64, 58, SH110X_WHITE);
    display.drawTriangle(48, 80, 80, 80, 64, 58, SH110X_WHITE);
    display.fillCircle(64, 58 + pulse, 2, SH110X_WHITE);
  } else if (face == FACE_REMINDER) {
    display.drawCircle(64, 56, 18, SH110X_WHITE);
    display.fillRect(46, 56, 37, 20, SH110X_BLACK);
    display.drawFastHLine(46, 74, 37, SH110X_WHITE);
    display.fillCircle(64, 78, 3, SH110X_WHITE);
  } else if (face == FACE_BATTERY) {
    display.drawRect(42, 50, 42, 18, SH110X_WHITE);
    display.fillRect(84, 56, 4, 6, SH110X_WHITE);
    display.fillRect(46, 54, 27, 10, SH110X_WHITE);
  } else if (face == FACE_WIFI) {
    display.drawCircle(64, 76, 3, SH110X_WHITE);
    display.drawCircle(64, 76, 15, SH110X_WHITE);
    display.drawCircle(64, 76, 27, SH110X_WHITE);
    display.fillRect(32, 76, 64, 32, SH110X_BLACK);
  } else if (face == FACE_MICROPHONE) {
    display.drawRoundRect(54, 34, 20, 36, 10, SH110X_WHITE);
    display.drawFastVLine(64, 70, 14, SH110X_WHITE);
    display.drawFastHLine(52, 84, 25, SH110X_WHITE);
  } else if (face == FACE_SPEAKING) {
    int h0 = 16 + pulse;
    int h1 = 24 - pulse;
    int h2 = 12 + pulse * 2;
    display.fillRect(46, 66 - h0, 9, h0, SH110X_WHITE);
    display.fillRect(60, 66 - h1, 9, h1, SH110X_WHITE);
    display.fillRect(74, 66 - h2, 9, h2, SH110X_WHITE);
  } else if (face == FACE_SUCCESS) {
    drawThickLine(42, 62, 58, 78, 5);
    drawThickLine(58, 78, 88, 44, 5);
  }

  display.setTextSize(1);
  display.setTextColor(SH110X_WHITE);
  display.setCursor(28, 102);
  display.print(displayFaceName(face));
}

static void drawCustomFace(FaceState face) {
  if (!available) return;

  unsigned long age = millis() - customFaceStartedAt;
  float intro = age >= 220 ? 1.0f : (float)age / 220.0f;
  float pulse = sinf((float)age / 180.0f) * 0.5f + 0.5f;
  int bob = (int)(sinf((float)age / 260.0f) * 2.0f);
  int shake = 0;
  if (face == FACE_ERROR && age < 700) {
    shake = ((age / 45) % 2) ? 3 : -3;
  }

  display.clearDisplay();

  if (face == FACE_ERROR) {
    int r = 8 + (int)(10.0f * intro);
    drawEyeX(42 + shake, 58, r);
    drawEyeX(86 + shake, 58, r);
  } else if (face == FACE_THINKING || face == FACE_LOADING) {
    display.fillRoundRect(24, 54 + bob, 34, 34, 9, SH110X_WHITE);
    display.fillRoundRect(70, 54 - bob, 34, 34, 9, SH110X_WHITE);
    int dot = (age / 180) % 3;
    for (int i = 0; i < 3; i++) {
      int r = i == dot ? 4 : 2;
      display.fillCircle(52 + i * 12, 102, r, SH110X_WHITE);
    }
  } else if (face == FACE_LOVE) {
    int scale = 2 + (intro > 0.65f ? 1 : 0) + (pulse > 0.85f ? 1 : 0);
    drawHeart(40, 56 + bob, scale);
    drawHeart(88, 56 - bob, scale);
  } else if (face == FACE_SURPRISED) {
    int bigR = 8 + (int)(14.0f * intro) + (int)(pulse * 1.0f);
    int smallR = 6 + (int)(9.0f * intro);
    display.fillCircle(38, 60 + bob, bigR, SH110X_WHITE);
    display.fillCircle(92, 61 - bob, smallR, SH110X_WHITE);
  } else if (face == FACE_STARSTRUCK) {
    int r = 8 + (int)(8.0f * intro) + (pulse > 0.75f ? 2 : 0);
    drawStar(40, 58 + bob, r);
    drawStar(88, 58 - bob, r);
  } else if (face == FACE_DIZZY) {
    int phase = (age / 80) % 6;
    drawSpiralEye(40 + bob, 58, phase);
    drawSpiralEye(88 - bob, 58, phase + 2);
  } else if (face == FACE_CONFUSED) {
    display.fillRoundRect(22, 48 + bob, 38, 34, 8, SH110X_WHITE);
    drawQuestionEye(88, 60 - bob);
  } else if (face == FACE_SAD) {
    drawDroopyEye(40, 58 + bob, 38, 24);
    drawDroopyEye(88, 58 - bob, 38, 24);
    int tearY = 76 + (age / 90) % 16;
    display.fillCircle(104, tearY, 3, SH110X_WHITE);
  } else if (face == FACE_SLEEP) {
    display.fillRoundRect(24, 64 + bob, 36, 8, 4, SH110X_WHITE);
    display.fillRoundRect(70, 64 - bob, 36, 8, 4, SH110X_WHITE);
    drawZed(82, 24 - ((age / 80) % 10), 14);
    drawZed(98, 12 - ((age / 110) % 8), 10);
  } else if (face == FACE_ALERT) {
    bool flash = (age / 140) % 2 == 0;
    int w = flash ? 46 : 38;
    display.fillRoundRect(20, 50, w, 42, 4, SH110X_WHITE);
    display.fillRoundRect(108 - w, 50, w, 42, 4, SH110X_WHITE);
  } else if (face == FACE_LOW_BATTERY) {
    drawDroopyEye(34, 58 + bob, 30, 18);
    drawDroopyEye(76, 58 - bob, 30, 18);
    drawBatteryIcon(88, 88, 26, 14);
  } else if (face == FACE_BOOP) {
    int squash = age < 260 ? (int)(12.0f * (1.0f - intro)) : 0;
    display.fillRoundRect(22, 58 + bob, 42, max(10, 18 - squash), 9, SH110X_WHITE);
    display.fillRoundRect(70, 58 - bob, 42, max(10, 18 - squash), 9, SH110X_WHITE);
    display.fillCircle(64, 78, 4 + (int)(pulse * 2.0f), SH110X_WHITE);
  } else if (face == FACE_SCAN) {
    display.fillRoundRect(24, 52, 36, 36, 8, SH110X_WHITE);
    display.fillRoundRect(70, 52, 36, 36, 8, SH110X_WHITE);
    int scanX = 20 + (age / 18) % 88;
    display.drawFastVLine(scanX, 44, 54, SH110X_BLACK);
    display.drawFastVLine(scanX + 1, 44, 54, SH110X_BLACK);
  } else {
    drawToolFacePlaceholder(face, age);
  }

  display.display();
}

static void applyFace(FaceState face) {
  if (!available) {
    currentFace = face;
    return;
  }

  if (isCustomFace(face)) {
    currentFace = face;
    currentGaze = DEFAULT;
    customFaceStartedAt = millis();
    drawCustomFace(face);
    lastCustomDrawMs = millis();
    return;
  }

  resetRoboEyesState();
  currentGaze = DEFAULT;

  switch (face) {
    case FACE_IDLE:
      roboEyes.setWidth(46, 46);
      roboEyes.setHeight(42, 42);
      roboEyes.setBorderradius(10, 10);
      roboEyes.setSpacebetween(10);
      roboEyes.setMood(DEFAULT);
      roboEyes.setAutoblinker(ON, 3, 2);
      roboEyes.setIdleMode(ON, 2, 2);
      break;
    case FACE_NEUTRAL:
      roboEyes.setWidth(46, 46);
      roboEyes.setHeight(42, 42);
      roboEyes.setBorderradius(9, 9);
      roboEyes.setMood(DEFAULT);
      roboEyes.setAutoblinker(ON, 4, 2);
      roboEyes.setIdleMode(OFF);
      break;
    case FACE_HAPPY:
      roboEyes.setWidth(50, 50);
      roboEyes.setHeight(30, 30);
      roboEyes.setBorderradius(16, 16);
      roboEyes.setSpacebetween(10);
      roboEyes.setMood(HAPPY);
      roboEyes.anim_laugh();
      break;
    case FACE_CURIOUS:
      roboEyes.setWidth(40, 52);
      roboEyes.setHeight(48, 40);
      roboEyes.setBorderradius(12, 8);
      roboEyes.setSpacebetween(6);
      roboEyes.setMood(DEFAULT);
      roboEyes.setCuriosity(ON);
      currentGaze = E;
      roboEyes.setIdleMode(ON, 1, 1);
      break;
    case FACE_SCARED:
      roboEyes.setWidth(38, 38);
      roboEyes.setHeight(54, 54);
      roboEyes.setBorderradius(4, 4);
      roboEyes.setSpacebetween(12);
      roboEyes.setMood(DEFAULT);
      roboEyes.setHFlicker(ON, 3);
      roboEyes.setSweat(ON);
      break;
    case FACE_SLEEPY:
      roboEyes.setWidth(52, 52);
      roboEyes.setHeight(22, 22);
      roboEyes.setBorderradius(16, 16);
      roboEyes.setSpacebetween(8);
      roboEyes.setMood(TIRED);
      roboEyes.setAutoblinker(ON, 6, 3);
      roboEyes.setIdleMode(OFF);
      break;
    case FACE_LISTENING:
      roboEyes.setWidth(42, 54);
      roboEyes.setHeight(46, 50);
      roboEyes.setBorderradius(8, 14);
      roboEyes.setSpacebetween(4);
      roboEyes.setMood(DEFAULT);
      roboEyes.setCuriosity(ON);
      roboEyes.setIdleMode(OFF);
      break;
    case FACE_WALKING:
      roboEyes.setWidth(48, 48);
      roboEyes.setHeight(40, 40);
      roboEyes.setBorderradius(8, 8);
      roboEyes.setSpacebetween(8);
      roboEyes.setMood(DEFAULT);
      roboEyes.setVFlicker(ON, 2);
      roboEyes.setIdleMode(OFF);
      break;
    case FACE_ROTATING:
      roboEyes.setWidth(44, 44);
      roboEyes.setHeight(34, 34);
      roboEyes.setBorderradius(4, 4);
      roboEyes.setSpacebetween(12);
      roboEyes.setMood(ANGRY);
      roboEyes.setHFlicker(ON, 2);
      roboEyes.setIdleMode(OFF);
      break;
    case FACE_WAVING:
      roboEyes.setWidth(50, 40);
      roboEyes.setHeight(34, 44);
      roboEyes.setBorderradius(16, 8);
      roboEyes.setSpacebetween(8);
      roboEyes.setMood(HAPPY);
      roboEyes.setAutoblinker(ON, 2, 1);
      roboEyes.setIdleMode(OFF);
      break;
    case FACE_ERROR:
      break;
    case FACE_BLINKING:
      roboEyes.blink();
      break;
    case FACE_THINKING:
      roboEyes.setWidth(40, 50);
      roboEyes.setHeight(30, 42);
      roboEyes.setBorderradius(10, 12);
      roboEyes.setSpacebetween(10);
      roboEyes.setMood(TIRED);
      roboEyes.setCuriosity(ON);
      currentGaze = NE;
      roboEyes.setIdleMode(ON, 2, 1);
      break;
    case FACE_LOVE:
    case FACE_SURPRISED:
    case FACE_STARSTRUCK:
    case FACE_DIZZY:
    case FACE_CONFUSED:
    case FACE_SAD:
    case FACE_SLEEP:
    case FACE_LOADING:
    case FACE_ALERT:
    case FACE_LOW_BATTERY:
    case FACE_BOOP:
    case FACE_SCAN:
    case FACE_CLOCK:
    case FACE_CALENDAR:
    case FACE_SEARCH:
    case FACE_CAMERA:
    case FACE_MEMORY:
    case FACE_TIMER:
    case FACE_REMINDER:
    case FACE_BATTERY:
    case FACE_SYSTEM:
    case FACE_WIFI:
    case FACE_MICROPHONE:
    case FACE_SPEAKING:
    case FACE_SUCCESS:
      break;
    case FACE_COUNT:
      break;
  }

  applyGaze();
  currentFace = face;
}

void displayInit() {
  available = display.begin(OLED_I2C_ADDRESS, true);
  if (!available) {
    const uint8_t fallbackAddress = OLED_I2C_ADDRESS == 0x3C ? 0x3D : 0x3C;
    available = display.begin(fallbackAddress, true);
  }

  if (!available) {
    return;
  }

  setOledDrive();
  display.setRotation(1);
  roboEyes.begin(SCREEN_WIDTH, SCREEN_HEIGHT, 100);
  setOledDrive();
  displaySetFace(FACE_IDLE);
}

void displayUpdate() {
  if (tempActive && tempDurationMs > 0 && millis() - tempStartedAt >= tempDurationMs) {
    displayRestoreBaseFace();
  }

  if (isCustomFace(currentFace)) {
    if (millis() - lastCustomDrawMs >= 45) {
      drawCustomFace(currentFace);
      lastCustomDrawMs = millis();
    }
    return;
  }

  if (available) {
    roboEyes.update();
  }
}

void displaySetFace(FaceState face) {
  if (face < FACE_IDLE || face >= FACE_COUNT) face = FACE_IDLE;
  baseFace = face;
  tempActive = false;
  tempDurationMs = 0;
  applyFace(face);
}

void displaySetTemporaryFace(FaceState face, unsigned long durationMs) {
  if (face < FACE_IDLE || face >= FACE_COUNT) face = FACE_IDLE;
  tempActive = true;
  tempStartedAt = millis();
  tempDurationMs = durationMs;
  applyFace(face);
}

void displayRestoreBaseFace() {
  tempActive = false;
  tempDurationMs = 0;
  applyFace(baseFace);
}

FaceState displayGetCurrentFace() {
  return currentFace;
}

bool displayIsTemporaryFace() {
  return tempActive;
}

const char* displayFaceName(FaceState face) {
  switch (face) {
    case FACE_IDLE: return "idle";
    case FACE_NEUTRAL: return "neutral";
    case FACE_HAPPY: return "happy";
    case FACE_CURIOUS: return "curious";
    case FACE_SCARED: return "scared";
    case FACE_SLEEPY: return "sleepy";
    case FACE_LISTENING: return "listening";
    case FACE_WALKING: return "walking";
    case FACE_ROTATING: return "rotating";
    case FACE_WAVING: return "waving";
    case FACE_ERROR: return "error";
    case FACE_BLINKING: return "blinking";
    case FACE_THINKING: return "thinking";
    case FACE_LOVE: return "love";
    case FACE_SURPRISED: return "surprised";
    case FACE_STARSTRUCK: return "starstruck";
    case FACE_DIZZY: return "dizzy";
    case FACE_CONFUSED: return "confused";
    case FACE_SAD: return "sad";
    case FACE_SLEEP: return "sleep";
    case FACE_LOADING: return "loading";
    case FACE_ALERT: return "alert";
    case FACE_LOW_BATTERY: return "low_battery";
    case FACE_BOOP: return "boop";
    case FACE_SCAN: return "scan";
    case FACE_CLOCK: return "clock";
    case FACE_CALENDAR: return "calendar";
    case FACE_SEARCH: return "search";
    case FACE_CAMERA: return "camera";
    case FACE_MEMORY: return "memory";
    case FACE_TIMER: return "timer";
    case FACE_REMINDER: return "reminder";
    case FACE_BATTERY: return "battery";
    case FACE_SYSTEM: return "system";
    case FACE_WIFI: return "wifi";
    case FACE_MICROPHONE: return "microphone";
    case FACE_SPEAKING: return "speaking";
    case FACE_SUCCESS: return "success";
    case FACE_COUNT: break;
  }
  return "idle";
}

bool displayParseFaceName(const char* name, FaceState& out) {
  if (equalsIgnoreCase(name, "idle")) out = FACE_IDLE;
  else if (equalsIgnoreCase(name, "neutral")) out = FACE_NEUTRAL;
  else if (equalsIgnoreCase(name, "happy")) out = FACE_HAPPY;
  else if (equalsIgnoreCase(name, "curious")) out = FACE_CURIOUS;
  else if (equalsIgnoreCase(name, "scared")) out = FACE_SCARED;
  else if (equalsIgnoreCase(name, "sleepy")) out = FACE_SLEEPY;
  else if (equalsIgnoreCase(name, "listening")) out = FACE_LISTENING;
  else if (equalsIgnoreCase(name, "walking")) out = FACE_WALKING;
  else if (equalsIgnoreCase(name, "rotating")) out = FACE_ROTATING;
  else if (equalsIgnoreCase(name, "waving")) out = FACE_WAVING;
  else if (equalsIgnoreCase(name, "error")) out = FACE_ERROR;
  else if (equalsIgnoreCase(name, "blinking")) out = FACE_BLINKING;
  else if (equalsIgnoreCase(name, "thinking")) out = FACE_THINKING;
  else if (equalsIgnoreCase(name, "love")) out = FACE_LOVE;
  else if (equalsIgnoreCase(name, "heart") || equalsIgnoreCase(name, "hearts")) out = FACE_LOVE;
  else if (equalsIgnoreCase(name, "surprised")) out = FACE_SURPRISED;
  else if (equalsIgnoreCase(name, "starstruck") || equalsIgnoreCase(name, "stars")) out = FACE_STARSTRUCK;
  else if (equalsIgnoreCase(name, "dizzy")) out = FACE_DIZZY;
  else if (equalsIgnoreCase(name, "confused")) out = FACE_CONFUSED;
  else if (equalsIgnoreCase(name, "sad")) out = FACE_SAD;
  else if (equalsIgnoreCase(name, "sleep")) out = FACE_SLEEP;
  else if (equalsIgnoreCase(name, "loading")) out = FACE_LOADING;
  else if (equalsIgnoreCase(name, "alert")) out = FACE_ALERT;
  else if (equalsIgnoreCase(name, "low_battery")) out = FACE_LOW_BATTERY;
  else if (equalsIgnoreCase(name, "boop")) out = FACE_BOOP;
  else if (equalsIgnoreCase(name, "scan") || equalsIgnoreCase(name, "scanning")) out = FACE_SCAN;
  else if (equalsIgnoreCase(name, "clock")) out = FACE_CLOCK;
  else if (equalsIgnoreCase(name, "calendar")) out = FACE_CALENDAR;
  else if (equalsIgnoreCase(name, "search")) out = FACE_SEARCH;
  else if (equalsIgnoreCase(name, "camera")) out = FACE_CAMERA;
  else if (equalsIgnoreCase(name, "memory")) out = FACE_MEMORY;
  else if (equalsIgnoreCase(name, "timer")) out = FACE_TIMER;
  else if (equalsIgnoreCase(name, "reminder")) out = FACE_REMINDER;
  else if (equalsIgnoreCase(name, "battery")) out = FACE_BATTERY;
  else if (equalsIgnoreCase(name, "system")) out = FACE_SYSTEM;
  else if (equalsIgnoreCase(name, "wifi") || equalsIgnoreCase(name, "wi-fi")) out = FACE_WIFI;
  else if (equalsIgnoreCase(name, "microphone") || equalsIgnoreCase(name, "mic")) out = FACE_MICROPHONE;
  else if (equalsIgnoreCase(name, "speaking")) out = FACE_SPEAKING;
  else if (equalsIgnoreCase(name, "success")) out = FACE_SUCCESS;
  else return false;
  return true;
}

void displaySetGaze(const char* dir) {
  if (equalsIgnoreCase(dir, "left")) currentGaze = E;
  else if (equalsIgnoreCase(dir, "right")) currentGaze = W;
  else if (equalsIgnoreCase(dir, "up")) currentGaze = N;
  else if (equalsIgnoreCase(dir, "down")) currentGaze = S;
  else currentGaze = DEFAULT;
  applyGaze();
}

void displayCenterGaze() {
  displaySetGaze("center");
}

void displayTriggerBlink() {
  displaySetTemporaryFace(FACE_BLINKING, 300);
}
