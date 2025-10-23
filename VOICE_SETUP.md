# 🎤 Настройка голосовых сообщений для Telegram Reminder Bot

## 📋 Что добавлено

- **Поддержка голосовых сообщений**: Бот теперь может принимать и обрабатывать голосовые сообщения
- **Распознавание речи**: Использует OpenAI Whisper для преобразования речи в текст
- **Конвертация аудио**: Автоматическая конвертация OGG в MP3 для совместимости с Whisper
- **Обработка ошибок**: Подробные сообщения об ошибках для пользователей

## 🔧 Установка зависимостей

### На локальной машине:
```bash
pip install -r requirements.txt
```

### На сервере:
```bash
cd /opt/telegram_bots/reminder_bot
source venv/bin/activate
pip install requests pydub
```

## 🎵 Дополнительные зависимости для pydub

`pydub` требует установки системных библиотек для работы с аудио:

### Ubuntu/Debian:
```bash
sudo apt update
sudo apt install ffmpeg
```

### CentOS/RHEL:
```bash
sudo yum install ffmpeg
# или для новых версий
sudo dnf install ffmpeg
```

### macOS:
```bash
brew install ffmpeg
```

## 🚀 Развертывание на сервере

### 1. Остановка сервиса
```bash
sudo systemctl stop reminder-bot.service
```

### 2. Обновление кода
```bash
cd /opt/telegram_bots/reminder_bot
# Скопируйте новые файлы:
# - voice_processor.py
# - обновленный telegram_bot.py
# - обновленный requirements.txt
```

### 3. Установка зависимостей
```bash
source venv/bin/activate
pip install requests pydub
```

### 4. Установка системных зависимостей
```bash
sudo apt update
sudo apt install ffmpeg
```

### 5. Запуск сервиса
```bash
sudo systemctl start reminder-bot.service
sudo systemctl status reminder-bot.service
```

## 🧪 Тестирование

### 1. Проверка логов
```bash
journalctl -u reminder-bot.service -f
```

### 2. Тест голосового сообщения
Отправьте боту голосовое сообщение с напоминанием, например:
- "Напомни мне через 5 минут о тесте"
- "Купить молоко завтра в 10 утра"

### 3. Проверка компонентов
```bash
cd /opt/telegram_bots/reminder_bot
source venv/bin/activate
python -c "
from voice_processor import VoiceProcessor
print('VoiceProcessor импортирован успешно')
"
```

## 🔍 Устранение неполадок

### Ошибка "pydub не установлен"
```bash
pip install pydub
```

### Ошибка "ffmpeg не найден"
```bash
sudo apt install ffmpeg
```

### Ошибка распознавания речи
- Проверьте баланс OpenAI API
- Убедитесь, что голосовое сообщение четкое
- Проверьте логи сервиса

### Ошибка конвертации аудио
- Проверьте права доступа к временным файлам
- Убедитесь, что ffmpeg установлен корректно

## 📊 Мониторинг

### Логи сервиса
```bash
journalctl -u reminder-bot.service --no-pager -n 50
```

### Проверка процесса
```bash
ps aux | grep python | grep reminder
```

### Проверка использования диска
```bash
df -h
# Временные файлы должны автоматически удаляться
```

## 🎯 Возможности

- **Текстовые сообщения**: Работают как раньше
- **Голосовые сообщения**: Новый функционал
- **Смешанное использование**: Можно отправлять и текст, и голос
- **Обратная связь**: Бот показывает распознанный текст
- **Обработка ошибок**: Подробные сообщения об ошибках

## 📝 Примеры использования

### Голосовые сообщения:
- "Напомни мне завтра в 15:00 о встрече с клиентом"
- "Купить хлеб через 2 часа"
- "Позвонить маме в субботу в 10 утра"
- "Сдать отчет в пятницу до 18:00"

### Текстовые сообщения:
- Работают как раньше
- Все существующие функции сохранены
