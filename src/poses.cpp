#include "poses.h"
#include "config.h"
#include "ik.h"
#include "interpolation.h"
#include "servo_driver.h"
#include <Arduino.h>

static int sitFemurDelta = 0;
static int sitTibiaDelta = 0;
static unsigned long lastSitUpdate = 0;

static void writeSitPose(int femurDelta, int tibiaDelta) {
  servoWriteRaw(0, CH_LF_COXA, coxaRef + TRIM_LF_COXA);
  servoWriteRaw(0, CH_LM_COXA, coxaRef + TRIM_LM_COXA);
  servoWriteRaw(0, CH_LB_COXA, coxaRef + TRIM_LB_COXA);

  servoWriteRaw(1, CH_RF_COXA, coxaRef + TRIM_RF_COXA);
  servoWriteRaw(1, CH_RM_COXA, coxaRef + TRIM_RM_COXA);
  servoWriteRaw(1, CH_RB_COXA, coxaRef + TRIM_RB_COXA);

  servoWriteRaw(0, CH_LF_FEMUR, femurRef + femurDelta + TRIM_LF_FEMUR);
  servoWriteRaw(0, CH_LM_FEMUR, femurRef + femurDelta + TRIM_LM_FEMUR);
  servoWriteRaw(0, CH_LB_FEMUR, femurRef + femurDelta + TRIM_LB_FEMUR);
  servoWriteRaw(1, CH_RF_FEMUR, femurRef - femurDelta + TRIM_RF_FEMUR);
  servoWriteRaw(1, CH_RM_FEMUR, femurRef - femurDelta + TRIM_RM_FEMUR);
  servoWriteRaw(1, CH_RB_FEMUR, femurRef - femurDelta + TRIM_RB_FEMUR);

  servoWriteRaw(0, CH_LF_TIBIA, tibiaRef + tibiaDelta + TRIM_LF_TIBIA);
  servoWriteRaw(0, CH_LM_TIBIA, tibiaRef + tibiaDelta + TRIM_LM_TIBIA);
  servoWriteRaw(0, CH_LB_TIBIA, tibiaRef + tibiaDelta + TRIM_LB_TIBIA);
  servoWriteRaw(1, CH_RF_TIBIA, tibiaRef - tibiaDelta + TRIM_RF_TIBIA);
  servoWriteRaw(1, CH_RM_TIBIA, tibiaRef - tibiaDelta + TRIM_RM_TIBIA);
  servoWriteRaw(1, CH_RB_TIBIA, tibiaRef - tibiaDelta + TRIM_RB_TIBIA);
}

void poseStand() {
  sitFemurDelta = 0;
  sitTibiaDelta = 0;
  ikStand();
}

void poseSitStart() {
  sitFemurDelta = 0;
  sitTibiaDelta = 0;
  lastSitUpdate = 0;
  writeSitPose(sitFemurDelta, sitTibiaDelta);
}

void poseSitInstant() {
  sitFemurDelta = SIT_FEMUR_DELTA;
  sitTibiaDelta = SIT_TIBIA_DELTA;
  writeSitPose(sitFemurDelta, sitTibiaDelta);
}

bool poseSitUpdate() {
  unsigned long now = millis();
  if (now - lastSitUpdate < LOOP_UPDATE_MS) {
    return sitFemurDelta == SIT_FEMUR_DELTA && sitTibiaDelta == SIT_TIBIA_DELTA;
  }
  lastSitUpdate = now;

  sitFemurDelta = moveTowardI(sitFemurDelta, SIT_FEMUR_DELTA, SIT_INTERP_STEP);
  sitTibiaDelta = moveTowardI(sitTibiaDelta, SIT_TIBIA_DELTA, SIT_INTERP_STEP);
  writeSitPose(sitFemurDelta, sitTibiaDelta);

  return sitFemurDelta == SIT_FEMUR_DELTA && sitTibiaDelta == SIT_TIBIA_DELTA;
}

void poseBodyOffset(float x, float y, float z) {
  for (int i = 0; i < 6; i++) {
    legIK(i, x, y, z);
  }
}
