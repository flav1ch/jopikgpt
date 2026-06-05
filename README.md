# Telegram AI Bot с обработкой файлов

Бот работает через Telegram Bot API и OpenAI-Compatible endpoint.
Поддерживает текстовые сообщения, документы и изображения.

## Поддерживаемые файлы

- PDF
- DOCX
- XLSX / XLSM
- TXT
- MD
- CSV
- JSON
- YAML / XML / HTML
- файлы кода
- JPG / PNG / WebP, если твой endpoint поддерживает vision

## Установка локально

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python bot.py
```

## Переменные окружения

Создай `.env` локально или добавь переменные в панели хостинга:

```env
TELEGRAM_TOKEN=...
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://your-custom-endpoint.com/v1
OPENAI_MODEL=your-model-name
MAX_FILE_CHARS=60000
```

## Запуск на хостинге

Команда запуска:

```bash
python bot.py
```

Бот использует polling, поэтому публичный webhook-домен не нужен.

## Как пользоваться

1. Напиши боту обычное сообщение.
2. Загрузи файл.
3. В подписи к файлу можно написать задачу, например:
   - `Сделай краткое содержание`
   - `Найди риски в договоре`
   - `Вытащи все даты и суммы`
   - `Проанализируй таблицу`

Если подписи нет, бот сам сделает краткий анализ файла.

## Ограничения

- Большие файлы обрезаются по `MAX_FILE_CHARS`.
- PDF-сканы без текстового слоя не читаются без OCR.
- Изображения работают только если твой OpenAI-Compatible endpoint поддерживает vision-вход.
- Для больших баз документов лучше подключать RAG/векторную базу.
