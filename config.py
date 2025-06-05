# config.py

from dotenv import load_dotenv
from pathlib import Path
import os

# Загружаем переменные из .env (он должен лежать рядом с этим файлом)
load_dotenv(Path(__file__).parent / ".env")

# --- Proxy (необязательно) ---
# Формат: "type://host:port" или "type://user:pass@host:port"
# Пример: PROXY = "socks5://user:password@127.0.0.1:1080"
PROXY = os.getenv("PROXY", None)

# --- Формат сохранения строк для вывода похожих каналов ---
# Например: "{username}:{participants_count}:{title}"
LINE_FORMAT = os.getenv("LINE_FORMAT", "{username}:{participants_count}:{title}")

# Директория, в которую записываются файлы (Level 1 и CSV)
SAVING_DIRECTORY = os.getenv("SAVING_DIRECTORY", "saved_channels")

# --- Telegram API credentials ---
# BOT_TOKEN (для запуска бот-части)
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Для Telethon (парсер уровней)
TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "")

# Информация о клиенте (можно оставить любые строки или получить из `config`)
TELEGRAM_DEVICE_MODEL = os.getenv("TELEGRAM_DEVICE_MODEL", "MacBook Air M1")
TELEGRAM_SYSTEM_VERSION = os.getenv("TELEGRAM_SYSTEM_VERSION", "macOS 14.4.1")
TELEGRAM_APP_VERSION = os.getenv("TELEGRAM_APP_VERSION", "4.16.8 arm64")

# Если нужно добавить задержку между запросами (по умолчанию 1.5 секунды)
DELAY_BETWEEN_REQUESTS = float(os.getenv("DELAY_BETWEEN_REQUESTS", "1.5"))
