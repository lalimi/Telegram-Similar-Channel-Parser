# proxy format 'type://host:port' or 'type://user:pass@host:port'
PROXY = None

# code parameters (don't touch if you don't know what you're doing)
LINE_FORMAT = "{username}:{participants_count}:{title}"
SAVING_DIRECTORY = "saved_channels"

from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import os

# API credentials should be provided via environment variables
TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "")
TELEGRAM_DEVICE_MODEL = "MacBook Air M1"
TELEGRAM_SYSTEM_VERSION = "macOS 14.4.1"
TELEGRAM_APP_VERSION = "4.16.8 arm64"

# Telegram Bot token for bot integration
# Can be set via the .env file
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
