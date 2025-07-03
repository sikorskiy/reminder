import os
import logging
from datetime import datetime
import pytz
from dotenv import load_dotenv
import httpx
import pandas as pd
from google_sheets import GoogleSheetsReminder
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram_bot import ReminderBot
import asyncio
from typing import Optional

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Конфигурация Google Sheets
GS_CREDS = 'finagent-461009-8c1e97a2ff0c.json'
GS_SPREADSHEET = 'reminders'
GS_WORKSHEET = 'reminders'
DEFAULT_TIMEZONE = 'Europe/Moscow'

# Инициализация Google Sheets
gs = GoogleSheetsReminder(GS_CREDS, GS_SPREADSHEET, GS_WORKSHEET)

async def send_reminder(reminder_id: str, text: str) -> bool:
    """Отправка напоминания в Telegram"""
    try:
        clean_token = TELEGRAM_TOKEN.strip()
        url = f"https://api.telegram.org/bot{clean_token}/sendMessage"
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": text
                }
            )
            if response.status_code == 200:
                logger.info(f"Отправлено напоминание: {text}")
                return True
            else:
                logger.error(f"Ошибка при отправке: {response.text}")
                return False
    except Exception as e:
        logger.error(f"Ошибка при отправке напоминания: {e}")
        return False

async def check_reminders() -> None:
    """Проверка и отправка напоминаний из Google Sheets"""
    reminders = gs.get_reminders()
    current_time = datetime.now(pytz.UTC)
    
    for reminder in reminders:
        reminder_id = f"{reminder['datetime']}_{reminder['text']}"
        try:
            # Обработка часового пояса
            timezone_str = reminder.get('timezone') or DEFAULT_TIMEZONE
            try:
                timezone = pytz.timezone(timezone_str)
            except pytz.exceptions.UnknownTimeZoneError:
                logger.warning(f"Неизвестный часовой пояс '{timezone_str}', используем {DEFAULT_TIMEZONE}")
                timezone = pytz.timezone(DEFAULT_TIMEZONE)
            
            # Парсинг и конвертация времени
            dt = pd.to_datetime(reminder['datetime'])
            if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
                reminder_time = dt.tz_localize(timezone)
            else:
                reminder_time = dt.tz_convert(timezone)
            
            reminder_time_utc = reminder_time.astimezone(pytz.UTC)
            
            # Проверка времени и отправка
            if current_time >= reminder_time_utc:
                success = await send_reminder(reminder_id, reminder['text'])
                if success:
                    gs.mark_as_sent(reminder['row'])
                    
        except Exception as e:
            logger.error(f"Ошибка при обработке напоминания {reminder_id}: {e}")

async def main() -> None:
    """Основная функция"""
    # Проверка переменных окружения
    if not all([TELEGRAM_TOKEN, OPENAI_API_KEY]):
        missing = []
        if not TELEGRAM_TOKEN:
            missing.append('TELEGRAM_TOKEN')
        if not OPENAI_API_KEY:
            missing.append('OPENAI_API_KEY')
        logger.error(f"Отсутствуют необходимые переменные окружения: {', '.join(missing)}")
        return
        
    # Создание и запуск компонентов
    bot = ReminderBot(TELEGRAM_TOKEN, OPENAI_API_KEY, gs)
    
    # Настройка планировщика
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        check_reminders,
        CronTrigger(minute='*'),
        id='check_reminders',
        replace_existing=True
    )
    scheduler.start()
    logger.info("Планировщик напоминаний запущен")
    
    # Запуск бота
    logger.info("Telegram бот запущен")
    
    try:
        bot_task = asyncio.create_task(bot.run_async())
        await bot_task
    except KeyboardInterrupt:
        logger.info("Получен сигнал завершения...")
    except Exception as e:
        logger.error(f"Ошибка в main: {e}")
    finally:
        scheduler.shutdown()
        logger.info("Работа завершена")

if __name__ == '__main__':
    asyncio.run(main()) 