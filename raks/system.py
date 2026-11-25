"""Lightweight system status helpers using only the standard library."""

from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path
from typing import Dict, Optional


def parse_meminfo(path: str = "/proc/meminfo") -> Dict[str, int]:
    """Return selected /proc/meminfo values in kB. Empty dict if unavailable."""
    values: Dict[str, int] = {}
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return values

    for line in lines:
        if ":" not in line:
            continue
        key, remainder = line.split(":", 1)
        parts = remainder.strip().split()
        if parts and parts[0].isdigit():
            values[key] = int(parts[0])
    return values


def format_bytes(amount: Optional[int]) -> str:
    if amount is None:
        return "unknown"
    value = float(amount)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return "unknown"


def disk_info(path: Optional[str] = None) -> Dict[str, int]:
    target = Path(path) if path else Path.home()
    try:
        stat = os.statvfs(target)
    except (OSError, AttributeError):
        return {}
    return {
        "free_bytes": stat.f_bavail * stat.f_frsize,
        "total_bytes": stat.f_blocks * stat.f_frsize,
    }


def process_usage() -> Dict[str, int]:
    """Return current-process memory usage in kB (Linux /proc, else zeros)."""
    values = {"rss_kb": 0, "vms_kb": 0}
    try:
        lines = Path("/proc/self/status").read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return values
    for line in lines:
        if line.startswith("VmRSS:"):
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                values["rss_kb"] = int(parts[1])
        elif line.startswith("VmSize:"):
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                values["vms_kb"] = int(parts[1])
    return values


def collect_system_status() -> Dict[str, str]:
    memory = parse_meminfo()
    disk = disk_info()
    total_kb = memory.get("MemTotal")
    available_kb = memory.get("MemAvailable")

    return {
        "platform": platform.system() or "unknown",
        "architecture": platform.machine() or "unknown",
        "python": platform.python_version(),
        "ram_total": format_bytes(total_kb * 1024 if total_kb is not None else None),
        "ram_available": format_bytes(available_kb * 1024 if available_kb is not None else None),
        "storage_free": format_bytes(disk.get("free_bytes")),
        "git": "available" if shutil.which("git") else "missing",
        "gh": "available" if shutil.which("gh") else "missing",
        "ai_engine": "hybrid router",
        "mode": "offline-first",
    }
