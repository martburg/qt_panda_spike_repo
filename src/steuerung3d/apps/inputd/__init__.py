"""RawControls producer (Human Input Device gateway).

This app reads a local joystick/gamepad (pygame backend) and publishes normalized
RawControls samples over UDP.

Design intent:
  - keep device-specific IO here
  - emit stable RawControls; higher layers do mapping/policy/kinematics
"""
