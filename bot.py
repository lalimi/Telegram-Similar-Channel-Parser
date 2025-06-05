"""Simple Telegram bot integration for the Similar Channel Parser.

This bot accepts commands to interact with the parser.
``/parse`` – получить список похожих каналов.
``/start`` и ``/help`` – вывести подсказку.
It reuses the ``SimilarChannelParser`` class from ``main.py``.

Make sure to provide ``BOT_TOKEN`` in your ``.env`` file.
"""

import asyncio
import sys
from io import BytesIO

from loguru import logger

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

logger.remove()
logger.add(
    sink=sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> - <level>{message}</level>",
)

import config
from main import SimilarChannelParser


parser = SimilarChannelParser()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a greeting and brief instructions."""
    logger.info("/start from %s", update.effective_user.id)
    await update.message.reply_text(
        "Привет! Этот бот ищет похожие телеграм‑каналы. "
        "Используйте /parse <канал> чтобы начать."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Explains available commands."""
    logger.info("/help from %s", update.effective_user.id)
    await update.message.reply_text(
        "/parse <канал> – найти похожие каналы\n"
        "/help – показать это сообщение"
    )


async def parse_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /parse command."""
    if not context.args:
        await update.message.reply_text("Usage: /parse <channel_username>")
        return

    username = context.args[0]
    logger.info("/parse %s from %s", username, update.effective_user.id)

    progress = await update.message.reply_text("Собираю похожие каналы...")

    try:
        channels = await parser.get_similar_channels(username)
    except Exception as exc:  # pragma: no cover - network call
        logger.error("Failed to fetch channels for %s: %s", username, exc)
        await update.message.reply_text(f"Error: {exc}")
        await progress.delete()
        return

    if not channels:
        await update.message.reply_text("No similar channels found.")
        await progress.delete()
        return
    logger.info("Found %d channels for %s", len(channels), username)

    text = "\n".join(channels)
    if len(text) < 4000:
        await progress.delete()
        await update.message.reply_text(text)
    else:
        # If there are many channels, send them as a text file
        buffer = BytesIO(text.encode("utf-8"))
        buffer.name = "channels.txt"
        await progress.delete()
        await update.message.reply_document(buffer)
    logger.info("Results sent for %s", username)


async def main() -> None:
    """Runs the Telegram bot."""
    logger.info("Connecting to Telegram API")
    await parser.connect()

    application = ApplicationBuilder().token(config.BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("parse", parse_command))

    await application.initialize()
    await application.start()
    logger.info("Bot started")
    await application.updater.start_polling()
    await application.updater.idle()


if __name__ == "__main__":  # pragma: no cover - entry point
    asyncio.run(main())

