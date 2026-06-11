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

// Place one leg at an IK foot target, then layer on joint-space deltas expressed
// semantically: femurUp raises the femur, tibiaIn tucks the tibia inward. The
// left/right sign convention (left = +delta, right = -delta for both) is handled
// here — see the leg table in ik.cpp.
static void writeLookUpLeg(int leg, float x, float y, float z, int femurUp, int tibiaIn) {
  IKSolution s;
  if (solveLegIK(leg, x, y, z, s) != IK_OK) return;
  const LegDesc& d = LEGS[leg];
  int sign = d.mirrored ? +1 : -1;
  servoWriteRaw(d.board_coxa,  d.ch_coxa,  s.coxa  + d.trim_coxa);
  servoWriteRaw(d.board_femur, d.ch_femur, s.femur + sign * femurUp + d.trim_femur);
  servoWriteRaw(d.board_tibia, d.ch_tibia, s.tibia + sign * tibiaIn + d.trim_tibia);
}

// Pitch the body nose-up so the camera aims higher. Positive foot-Z folds a leg
// (that corner of the body drops); negative extends it (that corner rises).
// +Y is the right side, so the right-middle leg splays out with +Y and the
// left-middle with -Y. Leg indices: LF=0, LM=1, LB=2, RF=3, RM=4, RB=5.
void poseLookUpTuned(int frontFemurUp, int frontTibiaIn, int backFemurUp, int backTibiaIn) {
  // Front: femur/tibia deltas (default: femur down, tibia in) to keep feet planted.
  writeLookUpLeg(0, 0.0f, 0.0f, -LOOK_UP_FRONT_LIFT_Z, frontFemurUp, frontTibiaIn);  // LF
  writeLookUpLeg(3, 0.0f, 0.0f, -LOOK_UP_FRONT_LIFT_Z, frontFemurUp, frontTibiaIn);  // RF
  // Middle: splay outward for a wider base.
  writeLookUpLeg(1, 0.0f, -LOOK_UP_MID_SPLAY_Y, 0.0f, 0, 0);  // LM
  writeLookUpLeg(4, 0.0f, +LOOK_UP_MID_SPLAY_Y, 0.0f, 0, 0);  // RM
  // Back: fold (rear drops) plus femur/tibia deltas.
  writeLookUpLeg(2, 0.0f, 0.0f, +LOOK_UP_BACK_FOLD_Z, backFemurUp, backTibiaIn);  // LB
  writeLookUpLeg(5, 0.0f, 0.0f, +LOOK_UP_BACK_FOLD_Z, backFemurUp, backTibiaIn);  // RB
}

void poseLookUp() {
  poseLookUpTuned(-LOOK_UP_FRONT_FEMUR_DOWN_DEG, LOOK_UP_FRONT_TIBIA_IN_DEG,
                  LOOK_UP_BACK_FEMUR_UP_DEG, LOOK_UP_BACK_TIBIA_IN_DEG);
}
