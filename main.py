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

# ВАЖНО: GS_SPREADSHEET — это название вашей Google Таблицы, как оно отображается в Google Drive (например, 'ReminderBotData').
GS_CREDS = 'finagent-461009-8c1e97a2ff0c.json'
GS_SPREADSHEET = 'reminders'  # пример: название таблицы в Google Drive
GS_WORKSHEET = 'reminders'  # имя листа

gs = GoogleSheetsReminder(GS_CREDS, GS_SPREADSHEET, GS_WORKSHEET)

DEFAULT_TIMEZONE = 'Europe/Moscow'

async def send_reminder(reminder_id, text):
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

async def check_reminders():
    """Проверка и отправка напоминаний из Google Sheets"""
    reminders = gs.get_reminders()
    current_time = datetime.now(pytz.UTC)
    for reminder in reminders:
        reminder_id = f"{reminder['datetime']}_{reminder['text']}"
        try:
            try:
                timezone = pytz.timezone(reminder['timezone']) if reminder['timezone'] else pytz.timezone(DEFAULT_TIMEZONE)
            except pytz.exceptions.UnknownTimeZoneError:
                logger.warning(f"Неизвестный часовой пояс '{reminder['timezone']}', используем {DEFAULT_TIMEZONE}")
                timezone = pytz.timezone(DEFAULT_TIMEZONE)
            dt = pd.to_datetime(reminder['datetime'])
            if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
                reminder_time = dt.tz_localize(timezone)
            else:
                reminder_time = dt.tz_convert(timezone)
            reminder_time_utc = reminder_time.astimezone(pytz.UTC)
            if current_time >= reminder_time_utc:
                success = await send_reminder(reminder_id, reminder['text'])
                if success:
                    gs.mark_as_sent(reminder['row'])
        except Exception as e:
            logger.error(f"Ошибка при обработке напоминания {reminder_id}: {e}")

async def main():
    """Основная функция"""
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        check_reminders,
        CronTrigger(minute='*'),
        id='check_reminders',
        replace_existing=True
    )
    scheduler.start()
    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main()) 