# Telegram Reminder Bot

Бот для отправки напоминаний в Telegram на основе данных из CSV файла.

## Требования

- Python 3.8+
- Telegram Bot Token
- Telegram Chat ID

## Установка

1. Клонируйте репозиторий:
```bash
git clone <repository-url>
cd reminderbot
```

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Создайте файл `.env` на основе `.env.example`:
```bash
cp .env.example .env
```

4. Отредактируйте `.env` файл, добавив свои значения:
```
TELEGRAM_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

## Использование

1. Подготовьте файл `reminders.csv` с напоминаниями в формате:
```
datetime,text,timezone
2025-08-15 09:00,Текст напоминания,Europe/Moscow
```

2. Запустите бота:
```bash
python main.py
```

## Деплой

### GitHub Actions

1. Создайте секреты в настройках репозитория:
   - `TELEGRAM_TOKEN`
   - `TELEGRAM_CHAT_ID`

2. Настройте GitHub Actions для запуска по расписанию (пример в `.github/workflows/reminder.yml`).

### Render / Railway

1. Создайте новое приложение
2. Добавьте переменные окружения:
   - `TELEGRAM_TOKEN`
   - `TELEGRAM_CHAT_ID`
3. Укажите команду запуска: `python main.py`

## Формат напоминаний

- `datetime`: Дата и время в формате YYYY-MM-DD HH:MM
- `text`: Текст напоминания
- `timezone`: Часовой пояс (по умолчанию Europe/Moscow)

## Примечания

- Бот проверяет напоминания каждую минуту
- Отправленные напоминания сохраняются в `sent_log.json`
- Для остановки бота используйте Ctrl+C 