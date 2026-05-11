import os
import platform as platform_module
import shutil
import socket
import time
from pathlib import Path
from typing import Optional

from .base import ToolResult


def _read_cpu_temp() -> Optional[float]:
    thermal_path = Path("/sys/class/thermal/thermal_zone0/temp")
    try:
        raw = thermal_path.read_text(encoding="utf-8").strip()
        return round(float(raw) / 1000.0, 1)
    except (OSError, ValueError):
        return None


def _read_uptime() -> Optional[float]:
    try:
        raw = Path("/proc/uptime").read_text(encoding="utf-8").split()[0]
        return float(raw)
    except (OSError, IndexError, ValueError):
        return None


def _read_mem_used_pct() -> Optional[float]:
    try:
        import psutil

        return round(float(psutil.virtual_memory().percent), 1)
    except ImportError:
        pass

    try:
        values = {}
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            key, raw_value = line.split(":", 1)
            values[key] = float(raw_value.strip().split()[0])

        total = values.get("MemTotal")
        available = values.get("MemAvailable")
        if not total or available is None:
            return None
        return round(((total - available) / total) * 100.0, 1)
    except (OSError, ValueError, IndexError):
        return None


def system_status() -> ToolResult:
    disk = shutil.disk_usage(os.getcwd())
    disk_used_pct = round((disk.used / disk.total) * 100.0, 1) if disk.total else None
    uptime_s = _read_uptime()
    mem_used_pct = _read_mem_used_pct()
    cpu_temp = _read_cpu_temp()

    data = {
        "cpu_temp": cpu_temp,
        "mem_used_pct": mem_used_pct,
        "disk_used_pct": disk_used_pct,
        "uptime_s": uptime_s,
        "platform": platform_module.platform(),
    }

    return ToolResult(
        ok=True,
        action="system_status",
        spoken_text="System status is available.",
        data=data,
        display_face="system",
    )


def network_status() -> ToolResult:
    started = time.monotonic()
    connected = False
    latency_ms = None

    try:
        with socket.create_connection(("8.8.8.8", 53), timeout=1.5):
            connected = True
            latency_ms = round((time.monotonic() - started) * 1000.0, 1)
    except OSError:
        connected = False

    spoken = "Network is connected." if connected else "Network does not appear to be connected."
    return ToolResult(
        ok=True,
        action="network_status",
        spoken_text=spoken,
        data={"connected": connected, "latency_ms": latency_ms},
        display_face="wifi",
    )


def battery_status() -> ToolResult:
    return ToolResult(
        ok=True,
        action="battery_status",
        spoken_text="No battery source is configured yet.",
        data={
            "implemented": False,
            "message": "No battery source detected.",
        },
        display_face="battery",
    )
