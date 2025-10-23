# 🧪 Локальное тестирование голосовых сообщений

## 1. Создание тестового бота

### Шаги:
1. Создайте нового бота через [@BotFather](https://t.me/BotFather)
2. Получите токен тестового бота
3. Найдите ваш Chat ID через [@userinfobot](https://t.me/userinfobot)

### Настройка .env для тестирования:
```bash
# Создайте .env.test файл
cp .env .env.test
```

Отредактируйте `.env.test`:
```env
TELEGRAM_TOKEN=your_test_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
OPENAI_API_KEY=your_openai_api_key_here
```

## 2. Локальный запуск

### Активация виртуального окружения:
```bash
source venv/bin/activate
```

### Установка зависимостей:
```bash
pip install requests pydub
```

### Установка ffmpeg (macOS):
```bash
brew install ffmpeg
```

### Запуск с тестовыми переменными:
```bash
# Загружаем тестовые переменные
export $(cat .env.test | xargs)
python main.py
```

## 3. Тестирование компонентов

### Тест VoiceProcessor:
```python
# test_voice.py
import asyncio
from voice_processor import VoiceProcessor
import os
from dotenv import load_dotenv

load_dotenv('.env.test')

async def test_voice_processor():
    processor = VoiceProcessor(os.getenv('OPENAI_API_KEY'))
    
    # Тест с аудиофайлом
    # Создайте тестовый аудиофайл или используйте существующий
    print("VoiceProcessor инициализирован успешно")

if __name__ == "__main__":
    asyncio.run(test_voice_processor())
```

### Тест импортов:
```bash
python -c "
from voice_processor import VoiceProcessor
from telegram_bot import ReminderBot
print('✅ Все модули импортируются успешно')
"
```

## 4. Тестирование без Telegram

### Мок-тест обработки голосовых сообщений:
```python
# test_voice_mock.py
import asyncio
from voice_processor import VoiceProcessor
import os
from dotenv import load_dotenv

load_dotenv('.env.test')

async def test_voice_processing():
    processor = VoiceProcessor(os.getenv('OPENAI_API_KEY'))
    
    # Создаем мок-объект Update
    class MockVoice:
        def __init__(self):
            self.file_id = "test_file_id"
            self.duration = 5
    
    class MockMessage:
        def __init__(self):
            self.voice = MockVoice()
        
        async def reply_text(self, text):
            print(f"Bot reply: {text}")
    
    class MockUpdate:
        def __init__(self):
            self.message = MockMessage()
    
    # Тестируем обработку
    update = MockUpdate()
    result = await processor.process_voice_message(update)
    print(f"Результат обработки: {result}")

if __name__ == "__main__":
    asyncio.run(test_voice_processing())
```

## 5. Тестирование с реальным аудиофайлом

### Создание тестового аудио:
```bash
# Создайте тестовый аудиофайл (если у вас есть ffmpeg)
echo "Напомни мне завтра в 15:00 о встрече" | say -o test_reminder.wav
```

### Тест с файлом:
```python
# test_with_file.py
import asyncio
from voice_processor import VoiceProcessor
import os
from dotenv import load_dotenv

load_dotenv('.env.test')

async def test_with_audio_file():
    processor = VoiceProcessor(os.getenv('OPENAI_API_KEY'))
    
    # Тестируем транскрипцию с файлом
    audio_file = "test_reminder.wav"  # ваш тестовый файл
    
    if os.path.exists(audio_file):
        text = await processor._transcribe_audio(audio_file)
        print(f"Распознанный текст: {text}")
    else:
        print("Тестовый аудиофайл не найден")

if __name__ == "__main__":
    asyncio.run(test_with_audio_file())
```

## 6. Отладка и логирование

### Включение подробных логов:
```python
# В main.py добавьте:
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Мониторинг в реальном времени:
```bash
# Запуск с выводом логов
python main.py 2>&1 | tee bot.log
```

## 7. Проверка зависимостей

### Проверка всех компонентов:
```bash
python -c "
import requests
print('✅ requests')

try:
    from pydub import AudioSegment
    print('✅ pydub')
except ImportError:
    print('❌ pydub не установлен')

import openai
print('✅ openai')

from telegram import Update
print('✅ python-telegram-bot')
"
```

## 8. Тестирование на сервере (без остановки основного бота)

### Создание тестового сервиса:
```bash
# На сервере создайте копию сервиса
sudo cp /etc/systemd/system/reminder-bot.service /etc/systemd/system/reminder-bot-test.service
```

### Редактирование тестового сервиса:
```bash
sudo nano /etc/systemd/system/reminder-bot-test.service
```

Измените:
- `Description=Telegram Reminder Bot Test`
- `WorkingDirectory=/opt/telegram_bots/reminder_bot_test`
- `ExecStart=/opt/telegram_bots/reminder_bot_test/venv/bin/python /opt/telegram_bots/reminder_bot_test/main.py`

### Запуск тестового сервиса:
```bash
sudo systemctl daemon-reload
sudo systemctl start reminder-bot-test.service
sudo systemctl status reminder-bot-test.service
```

## 🎯 Рекомендуемый порядок тестирования:

1. **Создайте тестового бота** через BotFather
2. **Настройте .env.test** с токенами тестового бота
3. **Установите зависимости** локально
4. **Протестируйте импорты** и базовую функциональность
5. **Запустите локально** с тестовым ботом
6. **Отправьте голосовое сообщение** тестовому боту
7. **Проверьте логи** и работу всех компонентов

Это позволит вам безопасно тестировать новую функциональность, не затрагивая работающий продакшн бот!
