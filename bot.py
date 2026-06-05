import base64
import csv
import json
import logging
import mimetypes
import os
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from docx import Document
from openpyxl import load_workbook
from pypdf import PdfReader

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "20"))
MAX_FILE_CHARS = int(os.getenv("MAX_FILE_CHARS", "60000"))
DOWNLOADS_DIR = Path(os.getenv("DOWNLOADS_DIR", "downloads"))

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

client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
DOWNLOADS_DIR.mkdir(exist_ok=True)

TEXT_EXTENSIONS = {
    ".txt", ".md", ".csv", ".json", ".xml", ".html", ".css", ".js",
    ".ts", ".py", ".java", ".php", ".rb", ".go", ".rs", ".c",
    ".cpp", ".h", ".sql", ".log", ".yaml", ".yml",
}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def get_history(context: ContextTypes.DEFAULT_TYPE) -> List[Dict[str, str]]:
    return context.user_data.get("history", [])


def save_history(context: ContextTypes.DEFAULT_TYPE, history: List[Dict[str, str]]) -> None:
    context.user_data["history"] = history[-MAX_HISTORY_MESSAGES:]


def split_text(text: str, limit: int = 4000) -> List[str]:
    return [text[i : i + limit] for i in range(0, len(text), limit)] or [""]


async def reply_long(update: Update, text: str) -> None:
    for part in split_text(text):
        await update.message.reply_text(part)


def truncate_text(text: str, max_chars: int = MAX_FILE_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    return (
        text[:max_chars]
        + f"\n\n[Файл был обрезан: показаны первые {max_chars} символов из {len(text)}. "
        + "Для больших документов лучше подключить RAG/векторную базу.]"
    )


def extract_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""
        pages.append(f"\n--- Страница {i} ---\n{page_text}")
    return "\n".join(pages).strip()


def extract_docx(path: Path) -> str:
    doc = Document(str(path))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]

    table_text = []
    for table_index, table in enumerate(doc.tables, start=1):
        table_text.append(f"\n--- Таблица {table_index} ---")
        for row in table.rows:
            cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
            table_text.append(" | ".join(cells))

    return "\n".join(paragraphs + table_text).strip()


def extract_xlsx(path: Path) -> str:
    workbook = load_workbook(str(path), data_only=True, read_only=True)
    output = []

    for sheet in workbook.worksheets:
        output.append(f"\n--- Лист: {sheet.title} ---")
        for row in sheet.iter_rows(values_only=True):
            values = ["" if cell is None else str(cell) for cell in row]
            if any(value.strip() for value in values):
                output.append(" | ".join(values))

    return "\n".join(output).strip()


def extract_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="cp1251", errors="ignore")


def extract_file_text(path: Path) -> str:
    ext = path.suffix.lower()

    if ext == ".pdf":
        return extract_pdf(path)
    if ext == ".docx":
        return extract_docx(path)
    if ext in {".xlsx", ".xlsm"}:
        return extract_xlsx(path)
    if ext in TEXT_EXTENSIONS:
        return extract_text_file(path)

    raise ValueError(
        "Неподдерживаемый формат. Сейчас поддерживаются: PDF, DOCX, XLSX, TXT, MD, CSV, JSON и обычные текстовые/кодовые файлы."
    )


def image_to_data_url(path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(path.name)
    mime_type = mime_type or "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def ask_model_with_text(user_prompt: str, history: List[Dict[str, str]]) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *history,
        {"role": "user", "content": user_prompt},
    ]
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        temperature=0.7,
    )
    return response.choices[0].message.content or "Не удалось получить ответ."


def ask_model_with_image(prompt: str, image_path: Path) -> str:
    data_url = image_to_data_url(image_path)
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
        temperature=0.3,
    )
    return response.choices[0].message.content or "Не удалось получить ответ по изображению."


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Привет! Напиши сообщение или загрузи файл, и я обработаю его через AI-модель.\n\n"
        "Команды:\n"
        "/start — показать приветствие\n"
        "/reset — очистить историю диалога\n\n"
        "Файлы: PDF, DOCX, XLSX, TXT, CSV, JSON, MD, изображения JPG/PNG/WebP."
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

    try:
        answer = ask_model_with_text(user_text, history)

        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": answer})
        save_history(context, history)

        await reply_long(update, answer)

    except Exception as exc:
        logger.exception("Ошибка при обращении к AI endpoint")
        await update.message.reply_text(
            "Произошла ошибка при обращении к AI endpoint. "
            "Проверь OPENAI_BASE_URL, OPENAI_API_KEY и OPENAI_MODEL.\n\n"
            f"Техническая ошибка: {exc}"
        )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.document:
        return

    document = update.message.document
    file_name = document.file_name or f"file_{document.file_unique_id}"
    safe_name = Path(file_name).name
    file_path = DOWNLOADS_DIR / safe_name
    caption = update.message.caption or "Проанализируй этот файл: сделай краткое содержание и выдели важные моменты."

    await update.message.chat.send_action(action=ChatAction.UPLOAD_DOCUMENT)
    await update.message.reply_text("Файл получен. Скачиваю и читаю содержимое...")

    try:
        tg_file = await context.bot.get_file(document.file_id)
        await tg_file.download_to_drive(file_path)

        ext = file_path.suffix.lower()

        if ext in IMAGE_EXTENSIONS:
            await update.message.chat.send_action(action=ChatAction.TYPING)
            answer = ask_model_with_image(caption, file_path)
            await reply_long(update, answer)
            return

        extracted_text = extract_file_text(file_path)
        extracted_text = truncate_text(extracted_text)

        if not extracted_text.strip():
            await update.message.reply_text(
                "Я скачал файл, но не смог извлечь из него текст. "
                "Если это скан/PDF-картинка, нужен OCR или модель с vision."
            )
            return

        prompt = (
            f"Пользователь загрузил файл: {safe_name}\n"
            f"Инструкция пользователя: {caption}\n\n"
            "Содержимое файла:\n"
            "```\n"
            f"{extracted_text}\n"
            "```"
        )

        await update.message.chat.send_action(action=ChatAction.TYPING)
        answer = ask_model_with_text(prompt, get_history(context))

        context.user_data["last_file"] = {
            "name": safe_name,
            "text": extracted_text,
        }

        await reply_long(update, answer)

    except Exception as exc:
        logger.exception("Ошибка обработки файла")
        await update.message.reply_text(
            "Не удалось обработать файл.\n\n"
            f"Техническая ошибка: {exc}"
        )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.photo:
        return

    caption = update.message.caption or "Опиши изображение и выдели важные детали."
    photo = update.message.photo[-1]
    file_path = DOWNLOADS_DIR / f"photo_{photo.file_unique_id}.jpg"

    await update.message.reply_text("Фото получено. Анализирую...")

    try:
        tg_file = await context.bot.get_file(photo.file_id)
        await tg_file.download_to_drive(file_path)
        answer = ask_model_with_image(caption, file_path)
        await reply_long(update, answer)

    except Exception as exc:
        logger.exception("Ошибка анализа изображения")
        await update.message.reply_text(
            "Не удалось проанализировать изображение. Возможно, твой endpoint не поддерживает vision.\n\n"
            f"Техническая ошибка: {exc}"
        )


async def handle_non_supported(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Я пока принимаю текст, документы и изображения. "
        "Для аудио/видео нужно отдельно подключить распознавание."
    )


def main() -> None:
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(~filters.COMMAND, handle_non_supported))

    logger.info("Бот запущен через polling")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
