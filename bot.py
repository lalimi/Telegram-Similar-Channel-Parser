import asyncio
import csv
from io import StringIO, BytesIO

from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, MessageHandler, filters
)
import config
from main import SimilarChannelParser, parse_username_from_line, parse_line_to_dict

# Список авторизованных пользователей
AUTHORIZED_USERS = [501410189, 480322199]  # lalimi, illiaholovko

# Состояния ConversationHandler
ASK_CHANNEL_LEVEL1, ASK_CHANNEL_LEVEL2 = range(2)

# Получить главное меню (inline)
def get_main_keyboard(user_id):
    buttons = [
        [InlineKeyboardButton("🔍 Парсинг Level 1 (бесплатно)", callback_data="level1")]
    ]
    if user_id in AUTHORIZED_USERS:
        buttons.append([InlineKeyboardButton("🏆 Парсинг Level 2 (PRO)", callback_data="level2")])
    else:
        buttons.append([InlineKeyboardButton("🏆 Парсинг Level 2 (PRO)", callback_data="level2")])
    buttons.append([InlineKeyboardButton("📋 Инструкция", callback_data="help")])
    return InlineKeyboardMarkup(buttons)

# Клавиатура "Назад"
def get_back_keyboard():
    return ReplyKeyboardMarkup([["⬅️Назад"]], resize_keyboard=True)

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"Привет, {user.first_name}!\n\n"
        "Я анализирую похожие Telegram-каналы на одном или двух уровнях и выдаю отчёт.\n"
        "Выбери действие:",
        reply_markup=get_main_keyboard(user.id)
    )

# Обработка callback главного меню
async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    if query.data == "level1":
        await context.bot.send_message(
            chat_id=user_id,
            text="Введите username канала для парсинга Level 1 (например, @target_channel):",
            reply_markup=get_back_keyboard()
        )
        return ASK_CHANNEL_LEVEL1
    elif query.data == "level2":
        if user_id not in AUTHORIZED_USERS:
            await context.bot.send_message(
                chat_id=user_id,
                text="Level 2 (PRO) доступен только авторизованным пользователям. Для доступа — напиши @lalimi.",
                reply_markup=get_main_keyboard(user_id)
            )
            return ConversationHandler.END
        await context.bot.send_message(
            chat_id=user_id,
            text="Введите username канала для парсинга Level 2 (например, @target_channel):",
            reply_markup=get_back_keyboard()
        )
        return ASK_CHANNEL_LEVEL2
    elif query.data == "help":
        await help_msg(update, context)
        return ConversationHandler.END

# Инструкция
async def help_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = (
        "📊 <b>Telegram Similar Channel Parser</b> — ищет похожие каналы и помогает анализировать ниши.\n"
        "🔹 <b>Level 1</b> — базовый парсинг (бесплатно для всех)\n"
        "🔸 <b>Level 2 (PRO)</b> — глубокий парсинг (по подписке)\n\n"
        "Как пользоваться:\n"
        "1️⃣ Нажми кнопку или используй команду\n"
        "2️⃣ Введи username интересующего канала (например, <code>@target_channel</code>)\n"
        "3️⃣ Получи результаты прямо сюда — списком или файлом CSV\n\n"
        "💡 Хочешь доступ к Level 2? Просто напиши мне в <a href='https://t.me/lalimi'>@lalimi</a> в Telegram!\n"
        "💸 Оплата любым удобным способом, активация за 5 минут\n\n"
        "❓ Остались вопросы? Пиши — всегда отвечу и помогу!\n"
        "Ваш бот 🔥"
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(txt, parse_mode="HTML", reply_markup=get_main_keyboard(update.effective_user.id))
    else:
        await update.message.reply_text(txt, parse_mode="HTML", reply_markup=get_main_keyboard(update.effective_user.id))

# Level 1: запрос username
async def ask_channel_level1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️Назад":
        await update.message.reply_text(
            "Главное меню:",
            reply_markup=get_main_keyboard(update.effective_user.id)
        )
        return ConversationHandler.END

    username = update.message.text.strip().lstrip("@")
    user_id = update.effective_user.id

    await update.message.reply_text("⏳ Запускаю парсинг Level 1, подождите…")

    try:
        channels = await parser.get_similar_channels(username)
        if not channels:
            await update.message.reply_text("Похожие каналы не найдены.", reply_markup=get_main_keyboard(user_id))
        else:
            # Генерируем CSV-таблицу
            output = StringIO()
            writer = csv.DictWriter(
                output,
                fieldnames=["Ссылка", "Кол-во подписчиков", "Название канала"],
                delimiter=","
            )
            writer.writeheader()
            for line in channels:
                parsed = parse_line_to_dict(line, config.LINE_FORMAT)
                if parsed:
                    writer.writerow({
                        "Ссылка": f"https://t.me/{parsed.get('username')}",
                        "Кол-во подписчиков": parsed.get("participants_count"),
                        "Название канала": parsed.get("title"),
                    })
            csv_bytes = BytesIO(output.getvalue().encode("utf-8"))
            csv_bytes.name = f"{username}_level1_report.csv"
            csv_bytes.seek(0)
            await update.message.reply_document(document=csv_bytes, filename=csv_bytes.name)
            await update.message.reply_text("Готово! Вот ваш Level 1 отчёт.", reply_markup=get_main_keyboard(user_id))
    except Exception as exc:
        await update.message.reply_text(f"Ошибка: {exc}", reply_markup=get_main_keyboard(user_id))

    return ConversationHandler.END
async def ask_channel_level2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️Назад":
        await update.message.reply_text(
            "Главное меню:",
            reply_markup=get_main_keyboard(update.effective_user.id)
        )
        return ConversationHandler.END

    username = update.message.text.strip().lstrip("@")
    user_id = update.effective_user.id

    if user_id not in AUTHORIZED_USERS:
        await update.message.reply_text(
            "Level 2 (PRO) доступен только авторизованным пользователям. Для доступа — напиши @lalimi.",
            reply_markup=get_main_keyboard(user_id)
        )
        return ConversationHandler.END

    # Отправляем сообщение ожидания и сохраняем message_id
    waiting_msg = await update.message.reply_text(
        "⏳ Запускаю глубокий парсинг… Результат придёт отдельным сообщением, когда всё будет готово!"
    )

    async def do_parsing_and_send(user_id, username, wait_msg_id, context):
        try:
            channels_l1 = await parser.get_similar_channels(username)
            if not channels_l1:
                await context.bot.delete_message(chat_id=user_id, message_id=wait_msg_id)
                await context.bot.send_message(user_id, "На первом уровне похожих каналов не найдено.")
                return

            level2_data = []
            for line in channels_l1:
                uname = parse_username_from_line(line, config.LINE_FORMAT)
                if uname:
                    channels_l2 = await parser.get_similar_channels(uname)
                    for l2 in channels_l2:
                        parsed = parse_line_to_dict(l2, config.LINE_FORMAT)
                        if parsed:
                            subs = parsed.get("participants_count")
                            try:
                                subs_num = int(str(subs).replace(" ", ""))
                            except Exception:
                                subs_num = 0
                            over_50k_value = subs_num if subs_num > 50000 else ""
                            level2_data.append({
                                "Исходный канал": uname,
                                "Ссылка": f"https://t.me/{parsed.get('username')}",
                                "Кол-во подписчиков": parsed.get("participants_count"),
                                "Название канала": parsed.get("title"),
                                "Подписчиков свыше 50k": over_50k_value,
                            })
                await asyncio.sleep(getattr(config, "DELAY_BETWEEN_REQUESTS", 1.5))

            output = StringIO()
            writer = csv.DictWriter(
                output,
                fieldnames=[
                    "Исходный канал",
                    "Ссылка",
                    "Кол-во подписчиков",
                    "Название канала",
                    "Подписчиков свыше 50k"
                ],
                delimiter=","
            )
            writer.writeheader()
            for row in level2_data:
                writer.writerow(row)
            csv_bytes = BytesIO(output.getvalue().encode("utf-8"))
            csv_bytes.name = f"{username}_level2_report.csv"
            csv_bytes.seek(0)

            await context.bot.delete_message(chat_id=user_id, message_id=wait_msg_id)
            await context.bot.send_document(
                chat_id=user_id,
                document=csv_bytes,
                filename=csv_bytes.name,
                caption="Готово! Вот ваш Level 2 отчёт.",
            )
        except Exception as exc:
            await context.bot.delete_message(chat_id=user_id, message_id=wait_msg_id)
            await context.bot.send_message(user_id, f"Ошибка при глубоком парсинге: {exc}")

    asyncio.create_task(
        do_parsing_and_send(user_id, username, waiting_msg.message_id, context)
    )

    return ConversationHandler.END

# --- Запуск приложения ---

def main():
    global parser
    parser = SimilarChannelParser()  # Создаём парсер только один раз
    app = ApplicationBuilder().token(config.BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start), CallbackQueryHandler(menu_handler)],
        states={
            ASK_CHANNEL_LEVEL1: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_channel_level1)],
            ASK_CHANNEL_LEVEL2: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_channel_level2)],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True,
    )
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("help", help_msg))

    print("Запускаю Telegram-бота с поддержкой PRO Level 2…")
    app.run_polling()

if __name__ == "__main__":
    main()
