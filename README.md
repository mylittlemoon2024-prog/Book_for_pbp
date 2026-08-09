# Book Club Bot

Telegram-бот для записи участников книжного клуба на встречи. Список встреч
и записи хранятся в Google-таблице — не нужна отдельная база данных, всё
видно и редактируется вручную.

## Возможности

- 📅 Показывает список ближайших встреч (по дате, из листа `Meetings`).
- ✅ Запись на встречу с указанием имени и телефона.
- ❌ Отмена своей записи.
- 📝 Просмотр своих активных записей (`Мои записи`).
- Учитывает вместимость встречи (`capacity`), если она задана.

## 1. Создать бота в Telegram

1. Напишите [@BotFather](https://t.me/BotFather), отправьте `/newbot`.
2. Придумайте имя и username бота.
3. Получите токен вида `123456789:AA...` — он понадобится в `.env`.

## 2. Подготовить Google-таблицу

1. Создайте новую Google-таблицу.
2. Скопируйте её ID из URL:
   `https://docs.google.com/spreadsheets/d/<ЭТОТ_ID>/edit`.
3. Бот сам создаст листы `Meetings` и `Registrations` с нужными заголовками
   при первом запуске, если их ещё нет. Можно создать их заранее вручную —
   структура такая:

   **Meetings**

   | id | title | date | time | location | capacity | description |
   |----|-------|------|------|----------|----------|--------------|
   | 1 | Обсуждаем «Мастер и Маргарита» | 2026-08-20 | 19:00 | Кафе «Буквы», ул. Ленина 5 | 15 | Приходите с вопросами! |

   `date` — строго в формате `ГГГГ-ММ-ДД`. `capacity` можно оставить пустым —
   тогда лимита мест не будет.

   **Registrations** — заполняется ботом автоматически, трогать не нужно.

## 3. Дать боту доступ к таблице (сервисный аккаунт Google)

1. Зайдите в [Google Cloud Console](https://console.cloud.google.com/),
   создайте проект (или используйте существующий).
2. Включите **Google Sheets API** для проекта (APIs & Services → Enable APIs
   → найти "Google Sheets API" → Enable).
3. Создайте сервисный аккаунт: APIs & Services → Credentials → Create
   Credentials → Service account.
4. Откройте созданный аккаунт → Keys → Add Key → Create new key → JSON.
   Скачается файл — сохраните его в проекте как `credentials.json`.
5. Скопируйте email сервисного аккаунта (вида
   `xxx@xxx.iam.gserviceaccount.com`) и откройте им доступ **Редактор** к
   вашей Google-таблице (кнопка «Настройки доступа» в таблице).

## 4. Настроить окружение

```bash
cp .env.example .env
```

Заполните `.env`:

```
BOT_TOKEN=<токен от BotFather>
SPREADSHEET_ID=<ID таблицы>
GOOGLE_CREDENTIALS_PATH=credentials.json
```

Положите скачанный `credentials.json` в корень проекта (файл уже в
`.gitignore`, в репозиторий он не попадёт).

## 5. Запуск

### Локально

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m bot.main
```

### Через Docker

```bash
docker compose up --build -d
```

Бот работает в режиме long polling — специальный хостинг с публичным URL не
нужен, подойдёт любой сервер/VPS/PaaS (Railway, Render, Fly.io и т.п.), где
можно оставить процесс работающим постоянно.

## Структура проекта

```
bot/
  main.py              — точка входа, запуск polling
  config.py             — чтение .env
  states.py             — FSM-состояния формы записи
  keyboards.py          — инлайн-клавиатуры
  handlers/
    start.py            — /start, главное меню
    registration.py     — список встреч, запись/отмена, "мои записи"
  services/
    sheets.py            — работа с Google Sheets (gspread)
```

## Дальнейшие идеи

- Админ-команды для добавления встреч прямо из Telegram (сейчас встречи
  добавляются вручную в таблицу).
- Напоминания за день до встречи (через `apscheduler` + рассылку).
- Экспорт списка участников встречи одной командой.
