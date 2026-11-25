"""Static configuration for RAKS AI v0.1.0."""

from pathlib import Path

APP_NAME = "RAKS AI"
APP_NAME_SHORT = "RAKS"
VERSION = "0.1.0"
PROJECT_URL = "https://github.com/amisiklvn-cell/RAKS"

# Future file tools will be restricted to this workspace. No file tools are
# active in v0.1.0; this is only the approved boundary for later stages.
WORKSPACE_ROOT = Path.home() / "RAKS"

LOG_DIR = Path.home() / ".local" / "state" / "raks"
LOG_FILE = LOG_DIR / "raks.log"

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
