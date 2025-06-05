"""Simple Telegram bot integration for the Similar Channel Parser.

This bot accepts commands to interact with the parser.
``/parse`` – получить список похожих каналов.
``/start`` и ``/help`` – вывести подсказку.
It reuses the ``SimilarChannelParser`` class from ``main.py``.

Make sure to provide ``BOT_TOKEN`` in your ``.env`` file.
"""

import asyncio
from io import BytesIO

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

import config
from main import SimilarChannelParser


parser = SimilarChannelParser()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a greeting and brief instructions."""
    await update.message.reply_text(
        "Привет! Этот бот ищет похожие телеграм‑каналы. "
        "Используйте /parse <канал> чтобы начать."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Explains available commands."""
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

    progress = await update.message.reply_text("Собираю похожие каналы...")

    try:
        channels = await parser.get_similar_channels(username)
    except Exception as exc:  # pragma: no cover - network call
        await update.message.reply_text(f"Error: {exc}")
        await progress.delete()
        return

    if not channels:
        await update.message.reply_text("No similar channels found.")
        await progress.delete()
        return

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


async def main() -> None:
    """Runs the Telegram bot."""
    await parser.connect()

    application = ApplicationBuilder().token(config.BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("parse", parse_command))

    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    await application.updater.idle()


if __name__ == "__main__":  # pragma: no cover - entry point
    asyncio.run(main())

