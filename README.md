# Telegram AI Bot

Базовый Telegram-бот на Python с подключением к OpenAI-Compatible endpoint.

## Возможности

- Ответы на текстовые сообщения в Telegram
- Поддержка OpenAI-Compatible API через `OPENAI_BASE_URL`
- История диалога для каждого пользователя
- Команда `/reset` для очистки истории
- Готовые файлы для публикации в GitHub и деплоя на хостинг

## Файлы проекта

```text
bot.py              # основной код бота
requirements.txt    # зависимости Python
.env.example        # пример переменных окружения
.gitignore          # исключения для Git
Procfile            # команда запуска для хостингов Heroku-like
runtime.txt         # версия Python
```

## Переменные окружения

На хостинге добавь переменные:

```env
TELEGRAM_TOKEN=токен_из_BotFather
OPENAI_API_KEY=ключ_от_твоего_endpoint
OPENAI_BASE_URL=https://your-endpoint.com/v1
OPENAI_MODEL=название_модели
SYSTEM_PROMPT=Ты полезный Telegram-ассистент. Отвечай на русском языке, понятно и по делу.
MAX_HISTORY_MESSAGES=20
```

Важно: `.env` нельзя публиковать в GitHub. Для примера есть `.env.example`.

## Локальный запуск

```bash
python -m venv venv
```

Windows:

```bash
venv\Scripts\activate
```

macOS/Linux:

```bash
source venv/bin/activate
```

Установка зависимостей:

```bash
pip install -r requirements.txt
```

Создай `.env` на основе `.env.example`:

```bash
cp .env.example .env
```

Запуск:

```bash
python bot.py
```

## Публикация в GitHub

```bash
git init
git add .
git commit -m "Initial Telegram AI bot"
git branch -M main
git remote add origin https://github.com/USERNAME/REPOSITORY.git
git push -u origin main
```

## Команда запуска на хостинге

Если Bothost просит команду запуска, используй:

```bash
python bot.py
```

Если хостинг читает `Procfile`, там уже указано:

```Procfile
worker: python bot.py
```

## Важно

Бот работает через polling. Это проще для старта и обычно не требует webhook/домена.
