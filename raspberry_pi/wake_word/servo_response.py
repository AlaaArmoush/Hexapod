from __future__ import annotations

import sys

DIRECTION_TO_PAN: dict[str, str] = {
    "left":        "left",
    "right":       "right",
    "center":      "center",
    "front_left":  "front_left",
    "front_right": "front_right",
}


def respond_to_direction(direction: str, bridge: object | None = None) -> None:
    """
    Maps a direction string to a camera_pan command and sends it via bridge.
    If bridge is None, prints the command (dry-run for laptop testing).
    """
    from bridge.robot_commands import build_camera_pan
    
    pan_pos = DIRECTION_TO_PAN.get(direction, "center")
    cmd = build_camera_pan(pos=pan_pos)

    if bridge is None:
        print(f"[dry-run] camera_pan → {cmd}", file=sys.stderr)
    else:
        bridge.send_command(cmd)
