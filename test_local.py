#!/usr/bin/env python3
"""
Тестовый скрипт для локального тестирования голосовых сообщений
"""

import asyncio
import os
import logging
from dotenv import load_dotenv
from voice_processor import VoiceProcessor
from message_processor import MessageProcessor

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_voice_processor():
    """Тестирование VoiceProcessor"""
    logger.info("🧪 Тестирование VoiceProcessor...")
    
    # Загружаем переменные окружения
    load_dotenv()
    openai_key = os.getenv('OPENAI_API_KEY')
    
    if not openai_key:
        logger.error("❌ OPENAI_API_KEY не найден в переменных окружения")
        return False
    
    try:
        processor = VoiceProcessor(openai_key)
        logger.info("✅ VoiceProcessor инициализирован успешно")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации VoiceProcessor: {e}")
        return False

async def test_message_processor():
    """Тестирование MessageProcessor"""
    logger.info("🧪 Тестирование MessageProcessor...")
    
    load_dotenv()
    openai_key = os.getenv('OPENAI_API_KEY')
    
    if not openai_key:
        logger.error("❌ OPENAI_API_KEY не найден в переменных окружения")
        return False
    
    try:
        processor = MessageProcessor(openai_key)
        
        # Тестируем извлечение информации из текста
        test_message = "Напомни мне завтра в 15:00 о встрече с клиентом"
        reminder_info = processor.extract_reminder_info(test_message)
        
        if reminder_info:
            logger.info(f"✅ MessageProcessor работает. Результат: {reminder_info}")
            return True
        else:
            logger.error("❌ MessageProcessor не смог извлечь информацию")
            return False
            
    except Exception as e:
        logger.error(f"❌ Ошибка тестирования MessageProcessor: {e}")
        return False

def test_dependencies():
    """Проверка зависимостей"""
    logger.info("🧪 Проверка зависимостей...")
    
    dependencies = [
        ('requests', 'requests'),
        ('openai', 'openai'),
        ('telegram', 'python-telegram-bot'),
        ('pydub', 'pydub'),
        ('dotenv', 'python-dotenv'),
        ('gspread', 'gspread'),
        ('pandas', 'pandas'),
        ('pytz', 'pytz'),
        ('apscheduler', 'apscheduler')
    ]
    
    all_ok = True
    for name, package in dependencies:
        try:
            __import__(package)
            logger.info(f"✅ {name}")
        except ImportError:
            logger.error(f"❌ {name} не установлен")
            all_ok = False
    
    return all_ok

def test_environment():
    """Проверка переменных окружения"""
    logger.info("🧪 Проверка переменных окружения...")
    
    load_dotenv()
    
    required_vars = [
        'TELEGRAM_TOKEN',
        'TELEGRAM_CHAT_ID', 
        'OPENAI_API_KEY'
    ]
    
    all_ok = True
    for var in required_vars:
        value = os.getenv(var)
        if value:
            logger.info(f"✅ {var}: {'SET' if value else 'NOT SET'}")
        else:
            logger.error(f"❌ {var}: NOT SET")
            all_ok = False
    
    return all_ok

async def test_audio_conversion():
    """Тестирование конвертации аудио (если доступен тестовый файл)"""
    logger.info("🧪 Тестирование конвертации аудио...")
    
    # Проверяем наличие ffmpeg
    import subprocess
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            logger.info("✅ ffmpeg доступен")
        else:
            logger.error("❌ ffmpeg не работает")
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError):
        logger.error("❌ ffmpeg не установлен")
        return False
    
    return True

async def main():
    """Основная функция тестирования"""
    logger.info("🚀 Начинаем локальное тестирование...")
    
    tests = [
        ("Зависимости", test_dependencies),
        ("Переменные окружения", test_environment),
        ("VoiceProcessor", test_voice_processor),
        ("MessageProcessor", test_message_processor),
        ("Конвертация аудио", test_audio_conversion)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        logger.info(f"\n{'='*50}")
        logger.info(f"Тест: {test_name}")
        logger.info(f"{'='*50}")
        
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"❌ Ошибка в тесте {test_name}: {e}")
            results.append((test_name, False))
    
    # Итоговый отчет
    logger.info(f"\n{'='*50}")
    logger.info("📊 ИТОГОВЫЙ ОТЧЕТ")
    logger.info(f"{'='*50}")
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1
    
    logger.info(f"\nРезультат: {passed}/{total} тестов пройдено")
    
    if passed == total:
        logger.info("🎉 Все тесты пройдены! Можно запускать бота локально.")
        logger.info("\nДля запуска используйте:")
        logger.info("python main.py")
    else:
        logger.error("⚠️  Некоторые тесты провалены. Исправьте ошибки перед запуском.")
    
    return passed == total

if __name__ == "__main__":
    asyncio.run(main())
