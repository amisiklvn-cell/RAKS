"""Configuration for RAKS AI v1.0.1.

Settings are stored outside Git as JSON. Secrets are never stored here; only
the *name* of an environment variable may be stored.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

APP_NAME = "RAKS AI"
APP_NAME_SHORT = "RAKS"
VERSION = "1.0.1"
PROJECT_URL = "https://github.com/amisiklvn-cell/RAKS"

WORKSPACE_ROOT = Path.home() / "RAKS"
CONFIG_DIR = Path.home() / ".config" / "raks"
CONFIG_FILE = CONFIG_DIR / "config.json"
STATE_DIR = Path.home() / ".local" / "state" / "raks"
LOG_DIR = STATE_DIR
LOG_FILE = LOG_DIR / "raks.log"
DATA_DIR = Path.home() / ".local" / "share" / "raks"
DB_FILE = DATA_DIR / "raks.db"
BACKUP_DIR = DATA_DIR / "backups"

MENU_ITEMS = (
    "AI Conversation",
    "Coding Assistant",
    "Project Manager",
    "Terminal Tools",
    "Cybersecurity Lab",
    "Web Research",
    "Automation Center",
    "Memory & History",
    "System Monitor",
    "Settings",
)

DEFAULT_SETTINGS: Dict[str, Any] = {
    "route_mode": "auto",
    "online_provider": "pollinations",
    "online_model": "openai",
    "online_key_env": "",
    "local_cli": "",
    "local_model": "",
    "local_max_tokens": 256,
    "request_timeout": 30,
    "web_host": "127.0.0.1",
    "web_port": 8765,
    "workspaces": [str(WORKSPACE_ROOT)],
    "memory_enabled": True,
}


def settings_path(custom: Optional[str] = None) -> Path:
    return Path(custom).expanduser() if custom else CONFIG_FILE


def load_settings(custom: Optional[str] = None) -> Dict[str, Any]:
    """Load JSON settings, falling back to defaults. Env vars override keys."""
    settings = dict(DEFAULT_SETTINGS)
    path = settings_path(custom)
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            settings.update({k: v for k, v in loaded.items() if k in DEFAULT_SETTINGS})
    except (OSError, json.JSONDecodeError):
        pass

    env_map = {
        "RAKS_ROUTE_MODE": "route_mode",
        "RAKS_ONLINE_PROVIDER": "online_provider",
        "RAKS_ONLINE_MODEL": "online_model",
        "RAKS_ONLINE_KEY_ENV": "online_key_env",
        "RAKS_LOCAL_CLI": "local_cli",
        "RAKS_LOCAL_MODEL": "local_model",
    }
    for env_name, key in env_map.items():
        if os.environ.get(env_name):
            settings[key] = os.environ[env_name]

    if os.environ.get("RAKS_WEB_PORT", "").isdigit():
        settings["web_port"] = int(os.environ["RAKS_WEB_PORT"])
    return settings


def save_settings(settings: Dict[str, Any], custom: Optional[str] = None) -> Path:
    """Persist settings atomically with 0600 permissions. No secret values."""
    path = settings_path(custom)
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = {k: v for k, v in settings.items() if k in DEFAULT_SETTINGS}
    temporary = path.with_name(path.name + ".tmp")
    try:
        # Create with private permissions before any configuration bytes are
        # written, then atomically replace the old file.
        descriptor = os.open(
            str(temporary),
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
            0o600,
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(clean, indent=2, sort_keys=True) + "\n")
        os.replace(str(temporary), str(path))
        path.chmod(0o600)
    except OSError:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return path
