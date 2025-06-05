from telethon import TelegramClient
import config

client = TelegramClient('sessions/account', config.TELEGRAM_API_ID, config.TELEGRAM_API_HASH)
client.start()
print("Userbot is ready!")
client.disconnect()

