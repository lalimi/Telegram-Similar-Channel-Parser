# test_userbot.py
from telethon import TelegramClient
import config

client = TelegramClient('sessions/account', config.TELEGRAM_API_ID, config.TELEGRAM_API_HASH)
client.start()  # <-- запросит номер телефона и код (один раз!)
print("Userbot is ready!")
