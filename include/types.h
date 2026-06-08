#pragma once

enum TestMode {
  MODE_NONE,
  MODE_SITTING_TEST,
  MODE_ROTATE_TEST,
  MODE_ROTATE_LOOP_TEST,
  MODE_BODY_MOTION_TEST,
  MODE_TRIPOD_GAIT,
  MODE_WAVE
};

enum LoopDirection { LOOP_STOPPED, LOOP_LEFT, LOOP_RIGHT };

enum RobotMode {
  ROBOT_MODE_IDLE,
  ROBOT_MODE_STANDING,
  ROBOT_MODE_SITTING,
  ROBOT_MODE_GAIT,
  ROBOT_MODE_ROTATING,
  ROBOT_MODE_WAVING,
  ROBOT_MODE_GESTURE,
  ROBOT_MODE_BODY,
  ROBOT_MODE_CAMERA_PAN
};

enum RobotCommandType {
  ROBOT_CMD_NONE,
  ROBOT_CMD_PING,
  ROBOT_CMD_STATUS,
  ROBOT_CMD_STAND,
  ROBOT_CMD_SIT,
  ROBOT_CMD_STOP,
  ROBOT_CMD_GAIT,
  ROBOT_CMD_ROTATE,
  ROBOT_CMD_WAVE,
  ROBOT_CMD_BODY,
  ROBOT_CMD_GESTURE,
  ROBOT_CMD_FACE,
  ROBOT_CMD_BLINK,
  ROBOT_CMD_LEAN,
  ROBOT_CMD_LOOK,
  ROBOT_CMD_NOD,
  ROBOT_CMD_SHAKE,
  ROBOT_CMD_IDLE_STYLE,
  ROBOT_CMD_CAMERA_PAN
};

enum CameraPanPos {
  CAM_PAN_LEFT,
  CAM_PAN_FRONT_LEFT,
  CAM_PAN_CENTER,
  CAM_PAN_FRONT_RIGHT,
  CAM_PAN_RIGHT
};

enum GaitDir {
  GAIT_DIR_FORWARD,
  GAIT_DIR_BACKWARD,
  GAIT_DIR_LEFT,
  GAIT_DIR_RIGHT,
  GAIT_DIR_FORWARD_LEFT,
  GAIT_DIR_FORWARD_RIGHT,
  GAIT_DIR_BACKWARD_LEFT,
  GAIT_DIR_BACKWARD_RIGHT,
  GAIT_DIR_CUSTOM
};

enum MotionBoundType {
  MOTION_BOUND_CONTINUOUS,
  MOTION_BOUND_DURATION_MS,
  MOTION_BOUND_STEPS,
  MOTION_BOUND_DISTANCE_CM
};

struct GaitCommand {
  GaitDir dir = GAIT_DIR_FORWARD;
  char dirName[20] = "forward";
  float speed = 0.0f;
  float stepLength = 0.0f;
  float stepHeight = 0.0f;
  float x = 0.0f;
  float y = 0.0f;
  MotionBoundType bound = MOTION_BOUND_CONTINUOUS;
  unsigned long durationMs = 0;
  int steps = 0;
  float distanceCm = 0.0f;
  bool ambiguousBound = false;
  bool invalidDirection = false;
  bool invalidNumeric = false;
};

struct RotateCommand {
  LoopDirection dir = LOOP_LEFT;
  char dirName[12] = "left";
  int cycles = 0;
  int degrees = 0;
  bool continuous = false;
  bool ambiguousBound = false;
  bool invalidDirection = false;
  bool invalidNumeric = false;
};

struct WaveCommand {
  int leg = 3;
  int count = 2;
};

struct BodyCommand {
  float x = 0.0f;
  float y = 0.0f;
  float z = 0.0f;
};

struct GestureCommand {
  char name[16] = "idle";
  float intensity = 0.5f;
};

struct FaceCommand {
  char name[20] = "idle";
  char text[24] = "";
  unsigned long duration_ms = 3500UL;
  bool persistent = false;
  bool invalidFace = false;
  bool hasText = false;
};

struct LeanCommand {
  char dir[12] = "left";
  float amount_mm = 20.0f;
  unsigned long duration_ms = 400;
  bool invalidDirection = false;
  bool invalidNumeric = false;
};

struct LookCommand {
  char dir[12] = "center";
  unsigned long duration_ms = 1200UL;
  bool persistent = false;
  bool invalidDirection = false;
  bool invalidNumeric = false;
};

struct NodShakeCommand {
  int count = 2;
  bool invalidNumeric = false;
};

struct IdleStyleCommand {
  char style[16] = "breathing";
  bool invalidStyle = false;
};

struct CameraPanCommand {
  CameraPanPos pos = CAM_PAN_CENTER;
  char posName[16] = "center";
  int offsetDeg = 0; // TEMP: command-time camera trim for servo calibration.
  bool invalidPos = false;
  bool invalidNumeric = false;
};

struct RobotCommand {
  RobotCommandType type = ROBOT_CMD_NONE;
  char cmdName[20] = "";
  bool rawServoControl = false;
  bool invalidNumeric = false;
  GaitCommand gait;
  RotateCommand rotate;
  WaveCommand wave;
  BodyCommand body;
  GestureCommand gesture;
  FaceCommand face;
  LeanCommand lean;
  LookCommand look;
  NodShakeCommand nodShake;
  IdleStyleCommand idleStyle;
  CameraPanCommand cameraPan;
};

struct RobotStatus {
  RobotMode mode = ROBOT_MODE_IDLE;
  bool gaitRunning = false;
  bool rotateRunning = false;
  bool gestureRunning = false;
  const char* activeCmd = "";
  const char* gesture = "";
  const char* face = "idle";
  bool faceTemporary = false;
  const char* dir = "";
  float speed = 0.0f;
  const char* bound = "none";
  int stepsTarget = 0;
  int stepsDone = 0;
  unsigned long durationTargetMs = 0;
  unsigned long durationElapsedMs = 0;
  float distanceTargetCm = 0.0f;
  int rotateCyclesTarget = 0;
  int rotateCyclesDone = 0;
  bool rotateContinuous = false;
  const char* headPanPosition = "center";
  bool headPanRunning = false;
  bool interruptible = true;
  const char* lastError = "";
};
