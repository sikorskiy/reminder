#!/bin/bash

# Простой скрипт для обновления существующего Git репозитория на сервере
# Запускать на сервере от имени root

echo "🔄 Обновление существующего Git репозитория..."

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Переменные
PROJECT_DIR="/opt/telegram_bots/reminder_bot"
REPO_URL="https://github.com/sikorskiy/reminder.git"
SERVICE_NAME="reminder-bot.service"

# Переход в рабочую директорию
cd "$PROJECT_DIR" || {
    error "Директория $PROJECT_DIR не найдена"
    exit 1
}

# Проверка Git репозитория
if [ ! -d ".git" ]; then
    error "Директория не является Git репозиторием"
    exit 1
fi

log "Обновляем remote URL..."
git remote set-url origin "$REPO_URL"

log "Получаем изменения из репозитория..."
git fetch origin

if [ $? -ne 0 ]; then
    error "Ошибка при получении изменений из репозитория"
    exit 1
fi

log "Переключаемся на ветку main..."
git checkout main 2>/dev/null || git checkout -b main origin/main

log "Обновляем код до последней версии..."
git reset --hard origin/main

if [ $? -ne 0 ]; then
    error "Ошибка при обновлении кода"
    exit 1
fi

log "✅ Код успешно обновлен!"

# Проверка файлов
log "Проверка файлов проекта..."
if [ -f "voice_processor.py" ]; then
    log "✅ voice_processor.py найден"
else
    warn "⚠️ voice_processor.py не найден"
fi

if [ -f "requirements.txt" ]; then
    log "✅ requirements.txt найден"
else
    error "❌ requirements.txt не найден"
    exit 1
fi

# Установка зависимостей
log "Установка Python зависимостей..."
source venv/bin/activate
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    error "Ошибка при установке зависимостей"
    exit 1
fi

# Установка системных зависимостей
log "Проверка системных зависимостей..."
if ! command -v ffmpeg &> /dev/null; then
    log "Установка ffmpeg..."
    apt update && apt install -y ffmpeg
fi

log "✅ Обновление завершено!"
echo ""
info "Для применения изменений перезапустите сервис:"
info "sudo systemctl restart $SERVICE_NAME"
