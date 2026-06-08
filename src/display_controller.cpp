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
#include <math.h>
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
static char currentFaceText[24] = "";

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
  roboEyes.setWidth(28, 28);
  roboEyes.setHeight(28, 28);
  roboEyes.setBorderradius(6, 6);
  roboEyes.setSpacebetween(14);
}

static void setOledDrive() {
  display.setContrast(OLED_CONTRAST);
}

static void applyGaze() {
  if (available) roboEyes.setPosition(currentGaze);
}

static bool isCustomFace(FaceState face) {
  return face == FACE_LISTENING ||
         face == FACE_ERROR || face == FACE_THINKING || face == FACE_LOVE ||
         face == FACE_SURPRISED || face == FACE_STARSTRUCK || face == FACE_DIZZY ||
         face == FACE_CONFUSED || face == FACE_SLEEP ||
         face == FACE_LOADING || face == FACE_ALERT || face == FACE_LOW_BATTERY ||
         face == FACE_BOOP || face == FACE_SCAN || face == FACE_CLOCK ||
         face == FACE_CALENDAR || face == FACE_SEARCH || face == FACE_CAMERA ||
         face == FACE_MEMORY || face == FACE_TIMER || face == FACE_REMINDER ||
         face == FACE_BATTERY || face == FACE_SYSTEM || face == FACE_WIFI ||
         face == FACE_MICROPHONE || face == FACE_AUDIO || face == FACE_SUCCESS;
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
  display.fillTriangle(cx - w / 2, cy - h / 2, cx + w / 2, cy - h / 2, cx, cy - h / 6, SH110X_BLACK);
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

static void drawArcSegments(int cx, int cy, int radius, int startDeg, int endDeg) {
  int prevX = cx + (int)(cosf((float)startDeg * 0.017453292f) * radius);
  int prevY = cy + (int)(sinf((float)startDeg * 0.017453292f) * radius);
  for (int deg = startDeg + 6; deg <= endDeg; deg += 6) {
    float rad = (float)deg * 0.017453292f;
    int x = cx + (int)(cosf(rad) * radius);
    int y = cy + (int)(sinf(rad) * radius);
    display.drawLine(prevX, prevY, x, y, SH110X_WHITE);
    prevX = x;
    prevY = y;
  }
}

static void drawClockToolFace(unsigned long age) {
  const float twoPi = 6.2831853f;
  int cx = 60;
  int cy = 62;
  display.drawCircle(cx, cy, 36, SH110X_WHITE);
  display.drawCircle(cx, cy, 35, SH110X_WHITE);
  for (int i = 0; i < 12; i++) {
    float angle = -1.5707963f + ((float)i * twoPi / 12.0f);
    int x0 = cx + (int)(cosf(angle) * 29.0f);
    int y0 = cy + (int)(sinf(angle) * 29.0f);
    int x1 = cx + (int)(cosf(angle) * 33.0f);
    int y1 = cy + (int)(sinf(angle) * 33.0f);
    display.drawLine(x0, y0, x1, y1, SH110X_WHITE);
  }

  float sweep = (float)((age / 1000) % 60) / 60.0f;
  float minuteAngle = -1.5707963f + sweep * twoPi;
  float hourAngle = -1.5707963f + (float)((age / 5000) % 12) * twoPi / 12.0f;
  drawThickLine(cx, cy, cx + (int)(cosf(hourAngle) * 17.0f), cy + (int)(sinf(hourAngle) * 17.0f), 3);
  drawThickLine(cx, cy, cx + (int)(cosf(minuteAngle) * 25.0f), cy + (int)(sinf(minuteAngle) * 25.0f), 3);
  display.fillCircle(cx, cy, 3, SH110X_WHITE);
}

static void drawCalendarToolFace() {
  display.drawRoundRect(28, 28, 64, 72, 4, SH110X_WHITE);
  display.fillRect(28, 28, 64, 14, SH110X_WHITE);
  display.fillRect(38, 22, 6, 14, SH110X_WHITE);
  display.fillRect(76, 22, 6, 14, SH110X_WHITE);
  display.drawFastHLine(34, 56, 52, SH110X_WHITE);
  display.drawFastHLine(34, 72, 52, SH110X_WHITE);
  display.drawFastVLine(50, 48, 42, SH110X_WHITE);
  display.drawFastVLine(68, 48, 42, SH110X_WHITE);
  display.fillRect(70, 74, 14, 14, SH110X_WHITE);
  display.fillRect(73, 77, 8, 8, SH110X_BLACK);
}

static void drawSearchToolFace(unsigned long age) {
  int pan = (int)(sinf((float)age / 420.0f) * 5.0f);
  int cx = 54 + pan;
  int cy = 54;
  display.drawCircle(cx, cy, 25, SH110X_WHITE);
  display.drawCircle(cx, cy, 24, SH110X_WHITE);
  drawThickLine(cx + 17, cy + 17, cx + 40, cy + 40, 5);
  display.drawCircle(cx, cy, 8, SH110X_WHITE);
  display.fillRect(cx - 3, cy + 5, 7, 10, SH110X_WHITE);
  display.fillCircle(cx, cy + 20, 3, SH110X_WHITE);
}

static void drawCameraToolFace(unsigned long age) {
  display.drawRoundRect(22, 42, 76, 46, 6, SH110X_WHITE);
  display.fillRect(34, 34, 22, 9, SH110X_WHITE);
  display.drawRoundRect(28, 48, 18, 10, 3, SH110X_WHITE);
  display.drawCircle(64, 65, 19, SH110X_WHITE);
  display.drawCircle(64, 65, 12, SH110X_WHITE);
  display.fillCircle(64, 65, 5, SH110X_WHITE);
  display.fillRect(83, 36, 7, 5, SH110X_WHITE);
  if (age < 180) {
    display.drawLine(92, 36, 108, 24, SH110X_WHITE);
    display.drawLine(97, 46, 116, 44, SH110X_WHITE);
    display.drawLine(88, 31, 92, 14, SH110X_WHITE);
  }
}

static void drawMemoryToolFace(unsigned long age) {
  display.drawRoundRect(34, 32, 52, 58, 4, SH110X_WHITE);
  for (int i = 0; i < 6; i++) {
    display.drawFastHLine(24, 38 + i * 9, 10, SH110X_WHITE);
    display.drawFastHLine(86, 38 + i * 9, 10, SH110X_WHITE);
  }
  for (int i = 0; i < 5; i++) {
    display.drawFastVLine(42 + i * 9, 22, 10, SH110X_WHITE);
    display.drawFastVLine(42 + i * 9, 90, 10, SH110X_WHITE);
  }
  for (int row = 0; row < 3; row++) {
    for (int col = 0; col < 3; col++) {
      int lit = ((age / 260) + row + col * 2) % 4;
      if (lit != 0) {
        display.fillRect(46 + col * 13, 44 + row * 12, 7, 7, SH110X_WHITE);
      } else {
        display.drawRect(46 + col * 13, 44 + row * 12, 7, 7, SH110X_WHITE);
      }
    }
  }
}

static void drawBatteryToolFace() {
  display.drawRoundRect(26, 48, 62, 28, 4, SH110X_WHITE);
  display.fillRect(88, 56, 7, 12, SH110X_WHITE);
  display.fillRect(32, 54, 40, 16, SH110X_WHITE);
  display.drawFastVLine(76, 52, 20, SH110X_WHITE);
  display.fillCircle(44, 90, 2, SH110X_WHITE);
  display.fillCircle(60, 90, 2, SH110X_WHITE);
  display.fillCircle(76, 90, 2, SH110X_WHITE);
}

static void drawMicrophoneToolFace(unsigned long age) {
  display.drawRoundRect(46, 26, 28, 48, 14, SH110X_WHITE);
  display.drawFastHLine(52, 40, 16, SH110X_WHITE);
  display.drawFastHLine(52, 52, 16, SH110X_WHITE);
  display.drawRoundRect(38, 44, 44, 42, 12, SH110X_WHITE);
  display.fillRect(39, 44, 42, 18, SH110X_BLACK);
  display.drawFastVLine(60, 86, 14, SH110X_WHITE);
  display.drawFastHLine(44, 100, 33, SH110X_WHITE);
  if (age < 420) {
    display.drawCircle(60, 52, 34 + (int)(age / 140), SH110X_WHITE);
  }
}

static void drawSuccessToolFace(unsigned long age) {
  display.drawCircle(60, 64, 38, SH110X_WHITE);
  display.drawCircle(60, 64, 37, SH110X_WHITE);
  int phase = age > 360 ? 2 : (age > 180 ? 1 : 0);
  if (phase >= 0) {
    drawThickLine(38, 63, 52, 77, 7);
  }
  if (phase >= 1) {
    drawThickLine(52, 77, 84, 43, 7);
  }
}

static void drawTimerToolFace(unsigned long age) {
  float phase = (float)(age % 1600) / 1600.0f;
  display.drawLine(40, 30, 80, 30, SH110X_WHITE);
  display.drawLine(40, 30, 58, 61, SH110X_WHITE);
  display.drawLine(80, 30, 62, 61, SH110X_WHITE);
  display.drawLine(58, 61, 40, 94, SH110X_WHITE);
  display.drawLine(62, 61, 80, 94, SH110X_WHITE);
  display.drawLine(40, 94, 80, 94, SH110X_WHITE);
  display.drawFastHLine(46, 26, 29, SH110X_WHITE);
  display.drawFastHLine(46, 98, 29, SH110X_WHITE);

  int topHeight = max(2, 16 - (int)(phase * 14.0f));
  display.fillTriangle(48, 36, 72, 36, 60, 36 + topHeight, SH110X_WHITE);
  int bottomHeight = 4 + (int)(phase * 18.0f);
  display.fillTriangle(48, 88, 72, 88, 60, 88 - bottomHeight, SH110X_WHITE);

  int dotY = 61 + (int)(phase * 22.0f);
  display.fillCircle(60, dotY, 2, SH110X_WHITE);
  display.fillCircle(56, 72 + ((age / 120) % 13), 1, SH110X_WHITE);
  display.fillCircle(64, 66 + ((age / 160) % 15), 1, SH110X_WHITE);
}

static void drawReminderToolFace(unsigned long age) {
  int swing = (int)(sinf((float)age / 260.0f) * 5.0f);
  int cx = 60 + swing;
  display.fillCircle(cx, 34, 4, SH110X_WHITE);
  display.drawCircle(cx, 55, 24, SH110X_WHITE);
  display.drawCircle(cx, 55, 23, SH110X_WHITE);
  display.fillRect(cx - 28, 55, 57, 22, SH110X_BLACK);
  display.drawLine(cx - 22, 55, cx - 28, 78, SH110X_WHITE);
  display.drawLine(cx + 22, 55, cx + 28, 78, SH110X_WHITE);
  display.drawFastHLine(cx - 28, 78, 57, SH110X_WHITE);
  display.drawFastHLine(cx - 22, 82, 45, SH110X_WHITE);
  display.fillCircle(60 - swing / 2, 88, 4, SH110X_WHITE);
}

static void drawSystemToolFace(unsigned long age) {
  int cx = 60;
  int cy = 62;
  float spin = (float)(age % 2400) / 2400.0f * 6.2831853f;
  for (int i = 0; i < 8; i++) {
    float angle = spin + (float)i * 0.78539816f;
    int x0 = cx + (int)(cosf(angle) * 23.0f);
    int y0 = cy + (int)(sinf(angle) * 23.0f);
    int x1 = cx + (int)(cosf(angle) * 34.0f);
    int y1 = cy + (int)(sinf(angle) * 34.0f);
    drawThickLine(x0, y0, x1, y1, 5);
  }
  display.drawCircle(cx, cy, 25, SH110X_WHITE);
  display.drawCircle(cx, cy, 24, SH110X_WHITE);
  display.fillCircle(cx, cy, 10, SH110X_BLACK);
  display.drawCircle(cx, cy, 10, SH110X_WHITE);
  display.fillCircle(cx, cy, 3, SH110X_WHITE);
}

static void drawWifiToolFace(unsigned long age) {
  int visible = (age / 260) % 4;
  display.fillCircle(60, 86, 4, SH110X_WHITE);
  if (visible >= 1) {
    drawArcSegments(60, 88, 18, 215, 325);
    drawArcSegments(60, 88, 19, 215, 325);
  }
  if (visible >= 2) {
    drawArcSegments(60, 88, 31, 215, 325);
    drawArcSegments(60, 88, 32, 215, 325);
  }
  if (visible >= 3 || visible == 0) {
    drawArcSegments(60, 88, 44, 215, 325);
    drawArcSegments(60, 88, 45, 215, 325);
  }
}

static void drawSpeakingToolFace(unsigned long age) {
  int heights[3];
  heights[0] = 18 + (int)((sinf((float)age / 170.0f) * 0.5f + 0.5f) * 26.0f);
  heights[1] = 24 + (int)((sinf((float)age / 210.0f + 1.5f) * 0.5f + 0.5f) * 34.0f);
  heights[2] = 18 + (int)((sinf((float)age / 190.0f + 3.0f) * 0.5f + 0.5f) * 26.0f);
  for (int i = 0; i < 3; i++) {
    int x = 38 + i * 20;
    int h = heights[i];
    display.fillRoundRect(x, 84 - h, 12, h, 4, SH110X_WHITE);
    display.fillRect(x + 3, 84 - h + 3, 6, max(2, h - 6), SH110X_BLACK);
  }
  display.drawFastHLine(32, 90, 57, SH110X_WHITE);
}

static void drawFaceTextLabel() {
  if (currentFaceText[0] == '\0') return;

  display.fillRect(0, 112, SCREEN_WIDTH, 16, SH110X_BLACK);
  display.setTextSize(1);
  display.setTextColor(SH110X_WHITE);
  int textWidth = (int)strlen(currentFaceText) * 6;
  int x = (SCREEN_WIDTH - textWidth) / 2;
  if (x < 0) x = 0;
  display.setCursor(x, 116);
  display.print(currentFaceText);
}

static void drawToolFacePlaceholder(FaceState face, unsigned long age) {
  int pulse = 2 + (int)((age / 180) % 4);
  display.drawRoundRect(20, 24, 80, 68, 8, SH110X_WHITE);
  display.drawRoundRect(24, 28, 72, 60, 6, SH110X_WHITE);

  if (face == FACE_CLOCK) {
    display.drawCircle(60, 58, 22, SH110X_WHITE);
    display.drawLine(60, 58, 60, 42, SH110X_WHITE);
    display.drawLine(60, 58, 74, 58, SH110X_WHITE);
  } else if (face == FACE_CALENDAR) {
    display.drawRect(38, 38, 44, 36, SH110X_WHITE);
    display.fillRect(38, 38, 44, 8, SH110X_WHITE);
    display.drawFastHLine(44, 56, 32, SH110X_WHITE);
    display.drawFastVLine(52, 48, 22, SH110X_WHITE);
    display.drawFastVLine(68, 48, 22, SH110X_WHITE);
  } else if (face == FACE_SEARCH) {
    display.drawCircle(54, 54, 17, SH110X_WHITE);
    drawThickLine(66, 66, 80, 80, 3);
  } else if (face == FACE_CAMERA) {
    display.drawRoundRect(34, 42, 52, 34, 5, SH110X_WHITE);
    display.drawCircle(60, 59, 12, SH110X_WHITE);
    display.fillCircle(60, 59, 4, SH110X_WHITE);
  } else if (face == FACE_MEMORY || face == FACE_SYSTEM) {
    display.drawRect(40, 38, 40, 40, SH110X_WHITE);
    for (int i = 0; i < 4; i++) {
      display.drawFastHLine(32, 44 + i * 9, 8, SH110X_WHITE);
      display.drawFastHLine(80, 44 + i * 9, 8, SH110X_WHITE);
      display.drawFastVLine(46 + i * 9, 30, 8, SH110X_WHITE);
      display.drawFastVLine(46 + i * 9, 78, 8, SH110X_WHITE);
    }
    display.fillRect(50, 48, 20, 20, SH110X_WHITE);
  } else if (face == FACE_TIMER) {
    display.drawTriangle(44, 36, 76, 36, 60, 58, SH110X_WHITE);
    display.drawTriangle(44, 80, 76, 80, 60, 58, SH110X_WHITE);
    display.fillCircle(60, 58 + pulse, 2, SH110X_WHITE);
  } else if (face == FACE_REMINDER) {
    display.drawCircle(60, 56, 18, SH110X_WHITE);
    display.fillRect(42, 56, 37, 20, SH110X_BLACK);
    display.drawFastHLine(42, 74, 37, SH110X_WHITE);
    display.fillCircle(60, 78, 3, SH110X_WHITE);
  } else if (face == FACE_BATTERY) {
    display.drawRect(38, 50, 42, 18, SH110X_WHITE);
    display.fillRect(80, 56, 4, 6, SH110X_WHITE);
    display.fillRect(42, 54, 27, 10, SH110X_WHITE);
  } else if (face == FACE_WIFI) {
    display.drawCircle(60, 76, 3, SH110X_WHITE);
    display.drawCircle(60, 76, 15, SH110X_WHITE);
    display.drawCircle(60, 76, 27, SH110X_WHITE);
    display.fillRect(28, 76, 64, 32, SH110X_BLACK);
  } else if (face == FACE_MICROPHONE) {
    display.drawRoundRect(50, 34, 20, 36, 10, SH110X_WHITE);
    display.drawFastVLine(60, 70, 14, SH110X_WHITE);
    display.drawFastHLine(48, 84, 25, SH110X_WHITE);
  } else if (face == FACE_AUDIO) {
    int h0 = 16 + pulse;
    int h1 = 24 - pulse;
    int h2 = 12 + pulse * 2;
    display.fillRect(42, 66 - h0, 9, h0, SH110X_WHITE);
    display.fillRect(56, 66 - h1, 9, h1, SH110X_WHITE);
    display.fillRect(70, 66 - h2, 9, h2, SH110X_WHITE);
  } else if (face == FACE_SUCCESS) {
    drawThickLine(38, 62, 54, 78, 5);
    drawThickLine(54, 78, 84, 44, 5);
  }

  display.setTextSize(1);
  display.setTextColor(SH110X_WHITE);
  display.setCursor(24, 102);
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

  if (face == FACE_LISTENING) {
    drawMicrophoneToolFace(age);
  } else if (face == FACE_ERROR) {
    int r = 8 + (int)(10.0f * intro);
    drawEyeX(38 + shake, 58, r);
    drawEyeX(82 + shake, 58, r);
  } else if (face == FACE_THINKING) {
    display.fillRoundRect(20, 60 + bob, 34, 28, 9, SH110X_WHITE);
    display.fillRoundRect(66, 60 - bob, 34, 28, 9, SH110X_WHITE);
    int dot = (age / 180) % 3;
    for (int i = 0; i < 3; i++) {
      int r = i == dot ? 4 : 2;
      display.fillCircle(40 + i * 14, 38, r, SH110X_WHITE);
    }
  } else if (face == FACE_LOADING) {
    int spinAngle = (int)((float)(age % 1200) / 1200.0f * 360.0f);
    drawArcSegments(60, 58, 28, spinAngle, spinAngle + 270);
    int dx = 60 + (int)(cosf((float)spinAngle * 0.017453292f) * 28.0f);
    int dy = 58 + (int)(sinf((float)spinAngle * 0.017453292f) * 28.0f);
    display.fillCircle(dx, dy, 4, SH110X_WHITE);
    display.setTextSize(1);
    display.setTextColor(SH110X_WHITE);
    display.setCursor(30, 96);
    display.print("loading...");
  } else if (face == FACE_LOVE) {
    int scale = 2 + (intro > 0.65f ? 1 : 0) + (pulse > 0.85f ? 1 : 0);
    drawHeart(36, 56 + bob, scale);
    drawHeart(84, 56 - bob, scale);
  } else if (face == FACE_SURPRISED) {
    int bigR = 8 + (int)(14.0f * intro) + (int)(pulse * 1.0f);
    int smallR = 6 + (int)(9.0f * intro);
    display.fillCircle(34, 60 + bob, bigR, SH110X_WHITE);
    display.fillCircle(88, 61 - bob, smallR, SH110X_WHITE);
  } else if (face == FACE_STARSTRUCK) {
    int r = 8 + (int)(8.0f * intro) + (pulse > 0.75f ? 2 : 0);
    drawStar(36, 58 + bob, r);
    drawStar(84, 58 - bob, r);
  } else if (face == FACE_DIZZY) {
    int phase = (age / 80) % 6;
    drawSpiralEye(36 + bob, 58, phase);
    drawSpiralEye(84 - bob, 58, phase + 2);
  } else if (face == FACE_CONFUSED) {
    display.fillRoundRect(18, 52 + bob, 36, 26, 8, SH110X_WHITE);
    display.fillRoundRect(66, 56 - bob, 36, 26, 8, SH110X_WHITE);
    // Pixel-art "?" (5x7 bitmap, scale=2) tilted above right eye
    static const uint8_t qmark[7] = {
      0b01110, 0b10001, 0b00001, 0b00010, 0b00100, 0b00000, 0b00100
    };
    const int qscale = 2, qox = 81, qoy = 23;
    for (int r = 0; r < 7; r++) {
      for (int c = 0; c < 5; c++) {
        if (qmark[r] & (1 << (4 - c))) {
          display.fillRect(qox + c * qscale + r / 2, qoy + r * qscale, qscale, qscale, SH110X_WHITE);
        }
      }
    }
  } else if (face == FACE_SLEEP) {
    display.fillRoundRect(20, 64 + bob, 36, 8, 4, SH110X_WHITE);
    display.fillRoundRect(66, 64 - bob, 36, 8, 4, SH110X_WHITE);
    drawZed(78, 24 - ((age / 80) % 10), 14);
    drawZed(94, 12 - ((age / 110) % 8), 10);
  } else if (face == FACE_ALERT) {
    bool flash = (age / 140) % 2 == 0;
    int w = flash ? 46 : 38;
    display.fillRoundRect(16, 50, w, 42, 4, SH110X_WHITE);
    display.fillRoundRect(104 - w, 50, w, 42, 4, SH110X_WHITE);
  } else if (face == FACE_LOW_BATTERY) {
    drawDroopyEye(30, 58 + bob, 30, 18);
    drawDroopyEye(72, 58 - bob, 30, 18);
    drawBatteryIcon(84, 88, 26, 14);
  } else if (face == FACE_BOOP) {
    int squash = age < 260 ? (int)(12.0f * (1.0f - intro)) : 0;
    display.fillRoundRect(18, 58 + bob, 42, max(10, 18 - squash), 9, SH110X_WHITE);
    display.fillRoundRect(66, 58 - bob, 42, max(10, 18 - squash), 9, SH110X_WHITE);
    display.fillCircle(60, 78, 4 + (int)(pulse * 2.0f), SH110X_WHITE);
  } else if (face == FACE_SCAN) {
    display.fillRoundRect(20, 52, 36, 36, 8, SH110X_WHITE);
    display.fillRoundRect(66, 52, 36, 36, 8, SH110X_WHITE);
    int scanX = 16 + (age / 18) % 88;
    display.drawFastVLine(scanX, 44, 54, SH110X_BLACK);
    display.drawFastVLine(scanX + 1, 44, 54, SH110X_BLACK);
  } else if (face == FACE_CLOCK) {
    display.setTextColor(SH110X_WHITE);
    display.setTextSize(4);
    const char* timeStr = (currentFaceText[0] != '\0') ? currentFaceText : "--:--";
    int textW = (int)strlen(timeStr) * 24;
    display.setCursor((SCREEN_WIDTH - textW) / 2, 44);
    display.print(timeStr);
    display.setTextSize(1);
    display.setCursor(50, 96);
    display.print("clock");
  } else if (face == FACE_CALENDAR) {
    display.setTextColor(SH110X_WHITE);
    if (currentFaceText[0] != '\0') {
      display.setTextSize(2);
      int textW = (int)strlen(currentFaceText) * 12;
      display.setCursor((SCREEN_WIDTH - textW) / 2, 52);
      display.print(currentFaceText);
    } else {
      display.setTextSize(2);
      display.setCursor(26, 52);
      display.print("no date");
    }
    display.setTextSize(1);
    display.setCursor(46, 84);
    display.print("calendar");
  } else if (face == FACE_SEARCH) {
    drawSearchToolFace(age);
  } else if (face == FACE_CAMERA) {
    drawCameraToolFace(age);
  } else if (face == FACE_MEMORY) {
    drawMemoryToolFace(age);
  } else if (face == FACE_TIMER) {
    drawTimerToolFace(age);
  } else if (face == FACE_REMINDER) {
    drawReminderToolFace(age);
  } else if (face == FACE_BATTERY) {
    drawBatteryToolFace();
  } else if (face == FACE_SYSTEM) {
    drawSystemToolFace(age);
  } else if (face == FACE_WIFI) {
    drawWifiToolFace(age);
  } else if (face == FACE_MICROPHONE) {
    drawMicrophoneToolFace(age);
  } else if (face == FACE_AUDIO) {
    drawSpeakingToolFace(age);
  } else if (face == FACE_SUCCESS) {
    drawSuccessToolFace(age);
  } else {
    drawToolFacePlaceholder(face, age);
  }

  if (face != FACE_CLOCK && face != FACE_CALENDAR) {
    drawFaceTextLabel();
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
      roboEyes.setWidth(36, 36);
      roboEyes.setHeight(32, 32);
      roboEyes.setBorderradius(8, 8);
      roboEyes.setSpacebetween(14);
      roboEyes.setMood(DEFAULT);
      roboEyes.setAutoblinker(ON, 3, 2);
      roboEyes.setIdleMode(ON, 2, 2);
      break;
    case FACE_NEUTRAL:
      roboEyes.setWidth(36, 36);
      roboEyes.setHeight(26, 26);
      roboEyes.setBorderradius(10, 10);
      roboEyes.setSpacebetween(16);
      roboEyes.setMood(DEFAULT);
      roboEyes.setAutoblinker(ON, 6, 2);
      roboEyes.setIdleMode(OFF);
      break;
    case FACE_HAPPY:
      roboEyes.setWidth(38, 38);
      roboEyes.setHeight(22, 22);
      roboEyes.setBorderradius(12, 12);
      roboEyes.setSpacebetween(14);
      roboEyes.setMood(HAPPY);
      roboEyes.anim_laugh();
      break;
    case FACE_CURIOUS:
      roboEyes.setWidth(30, 40);
      roboEyes.setHeight(36, 30);
      roboEyes.setBorderradius(9, 6);
      roboEyes.setSpacebetween(10);
      roboEyes.setMood(DEFAULT);
      roboEyes.setCuriosity(ON);
      currentGaze = E;
      roboEyes.setIdleMode(ON, 1, 1);
      break;
    case FACE_SCARED:
      roboEyes.setWidth(28, 28);
      roboEyes.setHeight(42, 42);
      roboEyes.setBorderradius(4, 4);
      roboEyes.setSpacebetween(16);
      roboEyes.setMood(DEFAULT);
      roboEyes.setHFlicker(ON, 3);
      roboEyes.setSweat(ON);
      break;
    case FACE_SLEEPY:
      roboEyes.setWidth(40, 40);
      roboEyes.setHeight(16, 16);
      roboEyes.setBorderradius(12, 12);
      roboEyes.setSpacebetween(12);
      roboEyes.setMood(TIRED);
      roboEyes.setAutoblinker(ON, 6, 3);
      roboEyes.setIdleMode(OFF);
      break;
    case FACE_LISTENING:
      roboEyes.setWidth(32, 42);
      roboEyes.setHeight(36, 38);
      roboEyes.setBorderradius(6, 10);
      roboEyes.setSpacebetween(8);
      roboEyes.setMood(DEFAULT);
      roboEyes.setCuriosity(ON);
      roboEyes.setIdleMode(OFF);
      break;
    case FACE_WALKING:
      roboEyes.setWidth(36, 36);
      roboEyes.setHeight(30, 30);
      roboEyes.setBorderradius(6, 6);
      roboEyes.setSpacebetween(12);
      roboEyes.setMood(DEFAULT);
      roboEyes.setVFlicker(ON, 2);
      roboEyes.setIdleMode(OFF);
      break;
    case FACE_ROTATING:
      roboEyes.setWidth(34, 34);
      roboEyes.setHeight(26, 26);
      roboEyes.setBorderradius(4, 4);
      roboEyes.setSpacebetween(16);
      roboEyes.setMood(DEFAULT);
      roboEyes.setHFlicker(ON, 2);
      roboEyes.setIdleMode(OFF);
      break;
    case FACE_WAVING:
      roboEyes.setWidth(38, 30);
      roboEyes.setHeight(26, 34);
      roboEyes.setBorderradius(12, 6);
      roboEyes.setSpacebetween(12);
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
      roboEyes.setWidth(30, 38);
      roboEyes.setHeight(22, 32);
      roboEyes.setBorderradius(8, 9);
      roboEyes.setSpacebetween(14);
      roboEyes.setMood(TIRED);
      roboEyes.setCuriosity(ON);
      currentGaze = NE;
      roboEyes.setIdleMode(ON, 2, 1);
      break;
    case FACE_SAD:
      roboEyes.setWidth(36, 36);
      roboEyes.setHeight(22, 22);
      roboEyes.setBorderradius(10, 10);
      roboEyes.setSpacebetween(14);
      roboEyes.setMood(TIRED);
      roboEyes.setAutoblinker(ON, 8, 3);
      roboEyes.setIdleMode(OFF);
      break;
    case FACE_LOVE:
    case FACE_SURPRISED:
    case FACE_STARSTRUCK:
    case FACE_DIZZY:
    case FACE_CONFUSED:
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
    case FACE_AUDIO:
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
  roboEyes.begin(SCREEN_WIDTH, SCREEN_HEIGHT, 24);
  // begin() inherits eyeLyDefault=(64-36)/2=14 from the class default screenHeight=64.
  // Force correct vertical center for the actual 128px display.
  {
    const int centerY = (SCREEN_HEIGHT - 36) / 2;
    roboEyes.eyeLyDefault = centerY;
    roboEyes.eyeRyDefault = centerY;
    roboEyes.eyeLy = centerY;
    roboEyes.eyeRy = centerY;
    roboEyes.eyeLyNext = centerY;
    roboEyes.eyeRyNext = centerY;
  }
  setOledDrive();
  displaySetFace(FACE_IDLE);
}

static void drawSadTears() {
  unsigned long t = millis();
  int lx = roboEyes.eyeLx;
  int ly = roboEyes.eyeLy + roboEyes.eyeLheightCurrent;
  int rx = roboEyes.eyeRx + roboEyes.eyeRwidthCurrent;
  int ry = roboEyes.eyeRy + roboEyes.eyeRheightCurrent;
  display.fillCircle(lx, ly + (int)((t /  70) % 22), 2, SH110X_WHITE);
  display.fillCircle(rx, ry + (int)((t / 90) % 22), 2, SH110X_WHITE);
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
    if (currentFace == FACE_SAD) {
      drawSadTears();
      display.display();
    }
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

void displaySetFaceText(const char* text) {
  if (!text) text = "";
  strncpy(currentFaceText, text, sizeof(currentFaceText) - 1);
  currentFaceText[sizeof(currentFaceText) - 1] = '\0';

  if (isCustomFace(currentFace)) {
    drawCustomFace(currentFace);
    lastCustomDrawMs = millis();
  }
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
    case FACE_AUDIO: return "audio";
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
  else if (equalsIgnoreCase(name, "audio") || equalsIgnoreCase(name, "speaking")) out = FACE_AUDIO;
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
