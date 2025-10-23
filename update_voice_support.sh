#!/bin/bash

# Скрипт для обновления Telegram Reminder Bot с поддержкой голосовых сообщений
# Запускать на сервере от имени root

echo "🚀 Обновление Telegram Reminder Bot с поддержкой голосовых сообщений..."

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Функция для вывода сообщений
log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверка прав root
if [ "$EUID" -ne 0 ]; then
    error "Запустите скрипт от имени root: sudo $0"
    exit 1
fi

# Остановка сервиса
log "Остановка сервиса reminder-bot..."
systemctl stop reminder-bot.service

# Переход в рабочую директорию
cd /opt/telegram_bots/reminder_bot || {
    error "Директория /opt/telegram_bots/reminder_bot не найдена"
    exit 1
}

# Создание бэкапа
log "Создание бэкапа текущих файлов..."
cp telegram_bot.py telegram_bot.py.backup.$(date +%Y%m%d_%H%M%S)
cp requirements.txt requirements.txt.backup.$(date +%Y%m%d_%H%M%S)

# Установка системных зависимостей
log "Установка системных зависимостей..."
apt update
apt install -y ffmpeg

# Активация виртуального окружения и установка Python зависимостей
log "Установка Python зависимостей..."
source venv/bin/activate
pip install requests pydub

# Проверка установки зависимостей
log "Проверка установленных пакетов..."
python -c "
import requests
print('✓ requests установлен')

try:
    from pydub import AudioSegment
    print('✓ pydub установлен')
except ImportError:
    print('✗ pydub не установлен')
    exit(1)

try:
    import openai
    print('✓ openai установлен')
except ImportError:
    print('✗ openai не установлен')
    exit(1)
"

if [ $? -ne 0 ]; then
    error "Ошибка при проверке зависимостей"
    exit 1
fi

# Проверка файлов
log "Проверка файлов..."
if [ ! -f "voice_processor.py" ]; then
    error "Файл voice_processor.py не найден. Убедитесь, что он скопирован в директорию."
    exit 1
fi

if [ ! -f "telegram_bot.py" ]; then
    error "Файл telegram_bot.py не найден."
    exit 1
fi

# Тест импорта новых модулей
log "Тестирование импорта модулей..."
python -c "
try:
    from voice_processor import VoiceProcessor
    print('✓ VoiceProcessor импортирован успешно')
except ImportError as e:
    print(f'✗ Ошибка импорта VoiceProcessor: {e}')
    exit(1)

try:
    from telegram_bot import ReminderBot
    print('✓ ReminderBot импортирован успешно')
except ImportError as e:
    print(f'✗ Ошибка импорта ReminderBot: {e}')
    exit(1)
"

if [ $? -ne 0 ]; then
    error "Ошибка при импорте модулей"
    exit 1
fi

# Запуск сервиса
log "Запуск сервиса reminder-bot..."
systemctl start reminder-bot.service

# Проверка статуса
sleep 3
if systemctl is-active --quiet reminder-bot.service; then
    log "✅ Сервис успешно запущен!"
    systemctl status reminder-bot.service --no-pager -l
else
    error "❌ Сервис не запустился"
    systemctl status reminder-bot.service --no-pager -l
    exit 1
fi

# Показ логов
log "Последние логи сервиса:"
journalctl -u reminder-bot.service --no-pager -n 10

echo ""
log "🎉 Обновление завершено успешно!"
echo ""
echo "📋 Что нового:"
echo "• Поддержка голосовых сообщений"
echo "• Распознавание речи с помощью OpenAI Whisper"
echo "• Автоматическая конвертация аудио"
echo "• Улучшенная обработка ошибок"
echo ""
echo "🧪 Для тестирования отправьте боту голосовое сообщение"
echo "📊 Для мониторинга используйте: journalctl -u reminder-bot.service -f"
