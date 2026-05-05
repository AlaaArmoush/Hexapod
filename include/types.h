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
  ROBOT_MODE_BODY
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
  ROBOT_CMD_GESTURE
};

enum StopMode {
  STOP_MODE_SMOOTH,
  STOP_MODE_EMERGENCY
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

struct GaitCommand {
  GaitDir dir = GAIT_DIR_FORWARD;
  float speed = 0.0f;
  float stepLength = 0.0f;
  float stepHeight = 0.0f;
  float x = 0.0f;
  float y = 0.0f;
};

struct RotateCommand {
  LoopDirection dir = LOOP_LEFT;
  int cycles = 0;
  int degrees = 0;
  bool continuous = false;
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

struct RobotCommand {
  RobotCommandType type = ROBOT_CMD_NONE;
  StopMode stopMode = STOP_MODE_SMOOTH;
  GaitCommand gait;
  RotateCommand rotate;
  WaveCommand wave;
  BodyCommand body;
  GestureCommand gesture;
};

struct RobotStatus {
  RobotMode mode = ROBOT_MODE_IDLE;
  bool gaitRunning = false;
  bool rotateRunning = false;
  bool gestureRunning = false;
};
