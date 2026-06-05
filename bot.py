import os
import logging
from typing import List, Dict

from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "20"))

SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    "Ты полезный Telegram-ассистент. Отвечай на русском языке, понятно и по делу.",
)

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN не найден. Добавь переменную окружения.")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY не найден. Добавь переменную окружения.")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

client = OpenAI(
    api_key=OPENAI_API_KEY,
    base_url=OPENAI_BASE_URL,
)


def get_history(context: ContextTypes.DEFAULT_TYPE) -> List[Dict[str, str]]:
    return context.user_data.get("history", [])


def save_history(context: ContextTypes.DEFAULT_TYPE, history: List[Dict[str, str]]) -> None:
    context.user_data["history"] = history[-MAX_HISTORY_MESSAGES:]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Привет! Напиши мне сообщение, и я отвечу через AI-модель.\n\n"
        "Команды:\n"
        "/start — показать приветствие\n"
        "/reset — очистить историю диалога"
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["history"] = []
    await update.message.reply_text("История диалога очищена.")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    user_text = update.message.text.strip()
    if not user_text:
        return

    await update.message.chat.send_action(action=ChatAction.TYPING)

    history = get_history(context)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *history,
        {"role": "user", "content": user_text},
    ]

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.7,
        )
        answer = response.choices[0].message.content or "Не удалось получить ответ."

        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": answer})
        save_history(context, history)

        # Telegram ограничивает длину сообщения. Делим длинные ответы на части.
        for i in range(0, len(answer), 4000):
            await update.message.reply_text(answer[i : i + 4000])

    except Exception as exc:
        logger.exception("Ошибка при обращении к AI endpoint")
        await update.message.reply_text(
            "Произошла ошибка при обращении к AI endpoint. "
            "Проверь OPENAI_BASE_URL, OPENAI_API_KEY и OPENAI_MODEL.\n\n"
            f"Техническая ошибка: {exc}"
        )


async def handle_non_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Пока я умею отвечать только на текстовые сообщения. "
        "Загрузку файлов можно добавить следующим этапом."
    )


def main() -> None:
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(~filters.TEXT & ~filters.COMMAND, handle_non_text))

    logger.info("Бот запущен через polling")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
