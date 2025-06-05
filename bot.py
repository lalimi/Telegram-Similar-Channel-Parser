"""Simple Telegram bot integration for the Similar Channel Parser.

This bot accepts the ``/parse`` command with a channel username and
responds with a list of similar channels.  It reuses the
``SimilarChannelParser`` class from ``main.py``.

Make sure to provide ``BOT_TOKEN`` in your ``.env`` file.
"""

import asyncio
from io import BytesIO
from typing import List

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
    """Sends a simple greeting and usage hint."""
    await update.message.reply_text(
        "Send /parse <channel_username> to get a list of similar channels."
    )


async def parse_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /parse command."""
    if not context.args:
        await update.message.reply_text("Usage: /parse <channel_username>")
        return

    username = context.args[0]

    try:
        channels = await parser.get_similar_channels(username)
    except Exception as exc:  # pragma: no cover - network call
        await update.message.reply_text(f"Error: {exc}")
        return

    if not channels:
        await update.message.reply_text("No similar channels found.")
        return

    text = "\n".join(channels)
    if len(text) < 4000:
        await update.message.reply_text(text)
    else:
        # If there are many channels, send them as a text file
        buffer = BytesIO(text.encode("utf-8"))
        buffer.name = "channels.txt"
        await update.message.reply_document(buffer)


async def main() -> None:
    """Runs the Telegram bot."""
    await parser.connect()

    application = ApplicationBuilder().token(config.BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("parse", parse_command))

    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    await application.updater.idle()


if __name__ == "__main__":  # pragma: no cover - entry point
    asyncio.run(main())

