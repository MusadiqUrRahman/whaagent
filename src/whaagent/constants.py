"""Framework constants."""

from pathlib import Path

import platformdirs

# Project root directory (used by some internal tooling)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Storage directory for persistent data (follows OS conventions)
STORAGE_DIR = Path(platformdirs.user_data_dir("whaagent"))

# Logs directory
LOGS_DIR = Path(platformdirs.user_log_dir("whaagent"))
