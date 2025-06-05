import os
import json
import logging
from datetime import datetime
import pandas as pd
import pytz
from dotenv import load_dotenv
from telegram.ext import Application
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

# Пути к файлам
REMINDERS_FILE = 'reminders.csv'
SENT_LOG_FILE = 'sent_log.json'

def load_sent_log():
    """Загрузка журнала отправленных напоминаний"""
    if os.path.exists(SENT_LOG_FILE):
        with open(SENT_LOG_FILE, 'r') as f:
            return json.load(f)
    return []

def save_sent_log(sent_log):
    """Сохранение журнала отправленных напоминаний"""
    with open(SENT_LOG_FILE, 'w') as f:
        json.dump(sent_log, f)

def load_reminders():
    """Загрузка напоминаний из CSV файла"""
    df = pd.read_csv(REMINDERS_FILE)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df['timezone'] = df['timezone'].fillna('Europe/Moscow')
    return df

async def send_reminder(reminder_id, text):
    """Отправка напоминания в Telegram"""
    try:
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        await application.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)
        logger.info(f"Отправлено напоминание: {text}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при отправке напоминания: {e}")
        return False

async def check_reminders():
    """Проверка и отправка напоминаний"""
    sent_log = load_sent_log()
    reminders = load_reminders()
    
    current_time = datetime.now(pytz.UTC)
    
    for index, row in reminders.iterrows():
        reminder_id = f"{row['datetime']}_{row['text']}"
        if reminder_id in sent_log:
            continue
            
        reminder_time = row['datetime'].tz_localize(row['timezone'])
        reminder_time_utc = reminder_time.astimezone(pytz.UTC)
        
        if current_time >= reminder_time_utc:
            success = await send_reminder(reminder_id, row['text'])
            if success:
                sent_log.append(reminder_id)
                save_sent_log(sent_log)

async def main():
    """Основная функция"""
    scheduler = AsyncIOScheduler()
    
    # Проверка каждую минуту
    scheduler.add_job(
        check_reminders,
        CronTrigger(minute='*'),
        id='check_reminders',
        replace_existing=True
    )
    
    scheduler.start()
    
    try:
        # Бесконечный цикл для поддержания работы бота
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main()) 