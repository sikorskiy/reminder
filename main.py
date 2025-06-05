import os
import json
import logging
from datetime import datetime
import pandas as pd
import pytz
from dotenv import load_dotenv
import httpx
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

# Проверка токена
logger.info(f"Используемый токен: {TELEGRAM_TOKEN}")

# Пути к файлам
REMINDERS_FILE = 'reminders.csv'
SENT_LOG_FILE = 'sent_log.json'
DEFAULT_TIMEZONE = 'Europe/Moscow'

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
    # Заменяем все пустые значения и пробелы на московский часовой пояс
    df['timezone'] = df['timezone'].fillna(DEFAULT_TIMEZONE).replace('', DEFAULT_TIMEZONE).str.strip()
    return df

async def send_reminder(reminder_id, text):
    """Отправка напоминания в Telegram"""
    try:
        # Очищаем токен от возможных лишних символов
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
    """Проверка и отправка напоминаний"""
    sent_log = load_sent_log()
    reminders = load_reminders()
    
    current_time = datetime.now(pytz.UTC)
    
    for index, row in reminders.iterrows():
        reminder_id = f"{row['datetime']}_{row['text']}"
        if reminder_id in sent_log:
            continue
            
        try:
            # Используем московский часовой пояс, если указанный невалидный
            try:
                timezone = pytz.timezone(row['timezone'])
            except pytz.exceptions.UnknownTimeZoneError:
                logger.warning(f"Неизвестный часовой пояс '{row['timezone']}', используем {DEFAULT_TIMEZONE}")
                timezone = pytz.timezone(DEFAULT_TIMEZONE)

            # Исправленная обработка временной зоны
            if row['datetime'].tzinfo is None or row['datetime'].tzinfo.utcoffset(row['datetime']) is None:
                reminder_time = row['datetime'].tz_localize(timezone)
            else:
                reminder_time = row['datetime'].tz_convert(timezone)
            reminder_time_utc = reminder_time.astimezone(pytz.UTC)

            if current_time >= reminder_time_utc:
                success = await send_reminder(reminder_id, row['text'])
                if success:
                    sent_log.append(reminder_id)
                    save_sent_log(sent_log)
        except Exception as e:
            logger.error(f"Ошибка при обработке напоминания {reminder_id}: {e}")

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