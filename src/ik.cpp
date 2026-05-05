#include "ik.h"
#include <Arduino.h>

// -----------------------------------------
// Leg table
// Index order: LF=0, LM=1, LB=2, RF=3, RM=4, RB=5
//
// Directional sign:
//   Left  femur : upward = +delta
//   Right femur : upward = -delta
//   Left  tibia : inward = +delta
//   Right tibia : inward = -delta
//   Coxa  both  : clockwise = +delta (handled by mountAngle transform)
// -----------------------------------------
const LegDesc LEGS[6] = {
    // ---- LEFT SIDE (board 0, mirrored=true) ----
    // LF
    { 0, CH_LF_COXA,  TRIM_LF_COXA,
      0, CH_LF_FEMUR, TRIM_LF_FEMUR,
      0, CH_LF_TIBIA, TRIM_LF_TIBIA,
      -30.0f, true },
    // LM
    { 0, CH_LM_COXA,  TRIM_LM_COXA,
      0, CH_LM_FEMUR, TRIM_LM_FEMUR,
      0, CH_LM_TIBIA, TRIM_LM_TIBIA,
      -90.0f, true },
    // LB
    { 0, CH_LB_COXA,  TRIM_LB_COXA,
      0, CH_LB_FEMUR, TRIM_LB_FEMUR,
      0, CH_LB_TIBIA, TRIM_LB_TIBIA,
      -150.0f, true },

    // ---- RIGHT SIDE (board 1, mirrored=false) ----
    // RF
    { 1, CH_RF_COXA,  TRIM_RF_COXA,
      1, CH_RF_FEMUR, TRIM_RF_FEMUR,
      1, CH_RF_TIBIA, TRIM_RF_TIBIA,
      30.0f, false },
    // RM
    { 1, CH_RM_COXA,  TRIM_RM_COXA,
      1, CH_RM_FEMUR, TRIM_RM_FEMUR,
      1, CH_RM_TIBIA, TRIM_RM_TIBIA,
      90.0f, false },
    // RB
    { 1, CH_RB_COXA,  TRIM_RB_COXA,
      1, CH_RB_FEMUR, TRIM_RB_FEMUR,
      1, CH_RB_TIBIA, TRIM_RB_TIBIA,
      150.0f, false },
};

// -----------------------------------------
// Internal helpers
// -----------------------------------------

// Clamp a value between lo and hi
static float clampf(float v, float lo, float hi) {
    if (v < lo) return lo;
    if (v > hi) return hi;
    return v;
}
// Safe acos — clamps input to [-1, 1] to avoid NaN on floating-point drift
static float safeAcos(float v) {
    return acos(clampf(v, -1.0f, 1.0f));
}

// -----------------------------------------
// legIK
// -----------------------------------------
// Steps:
//  1. Rotate body-frame target into leg-local frame using mountAngle
//  2. Apply legZeroOffset so (0,0,0) maps to the neutral standing foot
//  3. Solve coxa angle (XY plane, atan2)
//  4. Collapse XY reach into a scalar, solve femur+tibia via law of cosines
//  5. Apply mirror flip if needed, compute servo deltas, write hardware
// -----------------------------------------
IKResult solveLegIK(int legIndex, float target_x, float target_y, float target_z, IKSolution& out) {
    if (legIndex < 0 || legIndex >= 6) return IK_INVALID_LEG;

    const LegDesc& leg = LEGS[legIndex];

    // --- Step 1: rotate into leg-local frame ---
    float mountRad = leg.mountAngle * DEG_TO_RAD;
    float sinA = sinf(mountRad);
    float cosA = cosf(mountRad);

    // Standard 2D rotation (right-hand, CCW positive)
    float lx =  cosA * target_x + sinA * target_y;
    float ly =  sinA * target_x - cosA * target_y;
    float lz =  target_z;

    // --- Step 2: apply zero offset ---
    lx += LEG_ZERO_X;   // shift so neutral reach is (LEG_ZERO_X, 0, LEG_ZERO_Z)
    // ly offset is 0 (leg points straight out at neutral)
    lz += LEG_ZERO_Z;   // shift so neutral height is LEG_ZERO_Z

    // --- Step 3: coxa angle ---
    // atan2 gives the angle in the local XY plane.
    // At neutral lx=LEG_ZERO_X, ly=0 → atan2(0, LEG_ZERO_X)=0 → servoJ1AngleDeg=90°
    float servoJ1AngleDeg = atan2f(ly, lx) * RAD_TO_DEG + 90.0f;

    // --- Step 4: femur + tibia (law of cosines in the reach-Z plane) ---
    // Horizontal distance from coxa pivot to foot, minus coxa segment length
    float y_j2_plane = sqrtf(lx*lx + ly*ly) - LENGTH_COXA;

    // Straight-line distance from femur pivot to foot
    float L = sqrtf(y_j2_plane*y_j2_plane + lz*lz);

    // Clamp D to reachable range to avoid NaN
    float maxL = LENGTH_FEMUR + LENGTH_TIBIA - 0.1f;
    if (L > maxL) L = maxL;

    // Angle of the line from femur pivot to foot (below horizontal = negative)
    float A_signed_deg = atan2f(lz, y_j2_plane) * RAD_TO_DEG;  // negative when foot is below

    // Law of cosines: angle at femur pivot inside the femur-tibia triangle
    float cosB = (L*L + LENGTH_FEMUR*LENGTH_FEMUR - LENGTH_TIBIA*LENGTH_TIBIA)
                          / (2.0f * L * LENGTH_FEMUR);
    float B_deg = safeAcos(cosB) * RAD_TO_DEG;

    // Law of cosines: angle at tibia pivot
    float cosJ3 = (LENGTH_FEMUR*LENGTH_FEMUR + LENGTH_TIBIA*LENGTH_TIBIA - L*L)
                          / (2.0f * LENGTH_FEMUR * LENGTH_TIBIA);
    float j3_deg = safeAcos(cosJ3) * RAD_TO_DEG;

    // --- Step 5: map to servo angles applying mirror convention ---
    int servoJ2AngleDeg, servoJ3AngleDeg;

    if (leg.mirrored) {
        // Left side: femur upward = +delta from 90
        // A_signed_deg is negative when foot is below pivot (normal standing) →
        // (A_signed_deg + B_deg) brings femur to the correct angle
        // At neutral: A_signed_deg≈-56°, B_deg≈56° → sum≈0 → servo at 90° ✓
        servoJ2AngleDeg = (int)(A_signed_deg + B_deg) + 90;
        servoJ3AngleDeg = (int)j3_deg;          // 0° = straight, grows as leg bends
    } else {
        // Right side: femur upward = -delta from 90
        servoJ2AngleDeg = (int)(A_signed_deg + B_deg) * -1 + 90;
        servoJ3AngleDeg = 180 - (int)j3_deg;
    }

    // Clamp to safe servo range
    servoJ1AngleDeg  = clampf(servoJ1AngleDeg,  0, 180);
    servoJ2AngleDeg = (int)clampf((float)servoJ2AngleDeg, 0, 180);
    servoJ3AngleDeg = (int)clampf((float)servoJ3AngleDeg, 0, 180);

    out.coxa = (int)servoJ1AngleDeg;
    out.femur = servoJ2AngleDeg;
    out.tibia = servoJ3AngleDeg;
    return IK_OK;
}

void legIK(int legIndex, float target_x, float target_y, float target_z) {
    IKSolution solution;
    if (solveLegIK(legIndex, target_x, target_y, target_z, solution) != IK_OK) return;

    const LegDesc& leg = LEGS[legIndex];
    servoWriteRaw(leg.board_coxa,  leg.ch_coxa,  solution.coxa  + leg.trim_coxa);
    servoWriteRaw(leg.board_femur, leg.ch_femur, solution.femur + leg.trim_femur);
    servoWriteRaw(leg.board_tibia, leg.ch_tibia, solution.tibia + leg.trim_tibia);
}

// -----------------------------------------
// ikStand — all feet at neutral standing position
// Body-frame target for each leg is (0, 0, 0).
// The legZeroOffset inside legIK maps this to
// the physical neutral foot point.
// -----------------------------------------
void ikStand() {
    for (int i = 0; i < 6; i++) {
        legIK(i, 0.0f, 0.0f, 0.0f);
    }
}
