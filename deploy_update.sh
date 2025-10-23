#!/bin/bash

# Скрипт для автоматического обновления Telegram Reminder Bot с сервера
# Запускать на сервере от имени root

echo "🚀 Автоматическое обновление Telegram Reminder Bot..."

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

# Проверка прав root
if [ "$EUID" -ne 0 ]; then
    error "Запустите скрипт от имени root: sudo $0"
    exit 1
fi

# Переменные
PROJECT_DIR="/opt/telegram_bots/reminder_bot"
SERVICE_NAME="reminder-bot.service"
BACKUP_DIR="/opt/telegram_bots/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Создание директории для бэкапов
mkdir -p "$BACKUP_DIR"

log "Начинаем обновление..."

# 1. Остановка сервиса
log "Остановка сервиса $SERVICE_NAME..."
systemctl stop "$SERVICE_NAME"

if [ $? -ne 0 ]; then
    error "Не удалось остановить сервис $SERVICE_NAME"
    exit 1
fi

# 2. Переход в рабочую директорию
cd "$PROJECT_DIR" || {
    error "Директория $PROJECT_DIR не найдена"
    exit 1
}

# 3. Создание бэкапа текущего состояния
log "Создание бэкапа текущего состояния..."
tar -czf "$BACKUP_DIR/reminder_bot_backup_$TIMESTAMP.tar.gz" ./

if [ $? -eq 0 ]; then
    log "Бэкап создан: $BACKUP_DIR/reminder_bot_backup_$TIMESTAMP.tar.gz"
else
    warn "Не удалось создать бэкап, продолжаем обновление..."
fi

# 4. Сохранение текущих изменений (если есть)
log "Сохранение локальных изменений..."
if [ -d ".git" ]; then
    # Если это git репозиторий, сохраняем изменения
    git stash push -m "backup_before_update_$TIMESTAMP"
    log "Локальные изменения сохранены в git stash"
else
    warn "Директория не является git репозиторием"
fi

# 5. Получение обновлений из Git
log "Получение обновлений из Git..."
git fetch origin

if [ $? -ne 0 ]; then
    error "Ошибка при получении обновлений из Git"
    systemctl start "$SERVICE_NAME"
    exit 1
fi

# Проверка наличия новых коммитов
LOCAL_COMMIT=$(git rev-parse HEAD)
REMOTE_COMMIT=$(git rev-parse origin/main)

if [ "$LOCAL_COMMIT" = "$REMOTE_COMMIT" ]; then
    info "Нет новых обновлений. Текущая версия актуальна."
    systemctl start "$SERVICE_NAME"
    exit 0
fi

log "Найдены новые обновления. Применяем изменения..."

# 6. Применение обновлений
git reset --hard origin/main

if [ $? -ne 0 ]; then
    error "Ошибка при применении обновлений"
    systemctl start "$SERVICE_NAME"
    exit 1
fi

# 7. Установка системных зависимостей
log "Проверка системных зависимостей..."
if ! command -v ffmpeg &> /dev/null; then
    log "Установка ffmpeg..."
    apt update && apt install -y ffmpeg
    if [ $? -ne 0 ]; then
        error "Не удалось установить ffmpeg"
        exit 1
    fi
else
    log "ffmpeg уже установлен"
fi

# 8. Активация виртуального окружения и установка Python зависимостей
log "Установка Python зависимостей..."
source venv/bin/activate

if [ $? -ne 0 ]; then
    error "Не удалось активировать виртуальное окружение"
    exit 1
fi

# Обновление pip
pip install --upgrade pip

# Установка зависимостей
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    error "Ошибка при установке Python зависимостей"
    exit 1
fi

# 9. Проверка конфигурации
log "Проверка конфигурации..."

# Проверка .env файла
if [ ! -f ".env" ]; then
    error "Файл .env не найден"
    exit 1
fi

# Проверка Google Sheets credentials
if [ ! -f "finagent-461009-8c1e97a2ff0c.json" ]; then
    error "Файл Google Sheets credentials не найден"
    exit 1
fi

# 10. Тестирование импорта модулей
log "Тестирование импорта модулей..."
python -c "
try:
    from voice_processor import VoiceProcessor
    print('✅ VoiceProcessor импортирован успешно')
except ImportError as e:
    print(f'❌ Ошибка импорта VoiceProcessor: {e}')
    exit(1)

try:
    from telegram_bot import ReminderBot
    print('✅ ReminderBot импортирован успешно')
except ImportError as e:
    print(f'❌ Ошибка импорта ReminderBot: {e}')
    exit(1)

try:
    from message_processor import MessageProcessor
    print('✅ MessageProcessor импортирован успешно')
except ImportError as e:
    print(f'❌ Ошибка импорта MessageProcessor: {e}')
    exit(1)

try:
    from google_sheets import GoogleSheetsReminder
    print('✅ GoogleSheetsReminder импортирован успешно')
except ImportError as e:
    print(f'❌ Ошибка импорта GoogleSheetsReminder: {e}')
    exit(1)
"

if [ $? -ne 0 ]; then
    error "Ошибка при тестировании импорта модулей"
    exit 1
fi

# 11. Перезагрузка systemd
log "Перезагрузка systemd..."
systemctl daemon-reload

# 12. Запуск сервиса
log "Запуск сервиса $SERVICE_NAME..."
systemctl start "$SERVICE_NAME"

# 13. Проверка статуса
sleep 3
if systemctl is-active --quiet "$SERVICE_NAME"; then
    log "✅ Сервис успешно запущен!"
    
    # Показываем статус
    systemctl status "$SERVICE_NAME" --no-pager -l
    
    # Показываем последние логи
    log "Последние логи сервиса:"
    journalctl -u "$SERVICE_NAME" --no-pager -n 10
    
    # Показываем информацию о версии
    CURRENT_COMMIT=$(git rev-parse HEAD)
    COMMIT_MESSAGE=$(git log -1 --pretty=format:"%s")
    COMMIT_DATE=$(git log -1 --pretty=format:"%ad" --date=short)
    
    echo ""
    log "🎉 Обновление завершено успешно!"
    echo ""
    info "📊 Информация о версии:"
    info "Коммит: $CURRENT_COMMIT"
    info "Сообщение: $COMMIT_MESSAGE"
    info "Дата: $COMMIT_DATE"
    echo ""
    info "📋 Что нового:"
    info "• Поддержка голосовых сообщений"
    info "• Распознавание речи с помощью OpenAI Whisper"
    info "• Автоматическая конвертация аудио"
    info "• Улучшенная обработка ошибок"
    echo ""
    info "🧪 Для тестирования отправьте боту голосовое сообщение"
    info "📊 Для мониторинга используйте: journalctl -u $SERVICE_NAME -f"
    
else
    error "❌ Сервис не запустился"
    systemctl status "$SERVICE_NAME" --no-pager -l
    
    # Попытка восстановления из бэкапа
    warn "Попытка восстановления из бэкапа..."
    if [ -f "$BACKUP_DIR/reminder_bot_backup_$TIMESTAMP.tar.gz" ]; then
        log "Восстанавливаем из бэкапа..."
        tar -xzf "$BACKUP_DIR/reminder_bot_backup_$TIMESTAMP.tar.gz"
        systemctl start "$SERVICE_NAME"
        
        if systemctl is-active --quiet "$SERVICE_NAME"; then
            log "✅ Сервис восстановлен из бэкапа"
        else
            error "❌ Не удалось восстановить сервис"
        fi
    fi
    
    exit 1
fi

# 14. Очистка старых бэкапов (оставляем последние 5)
log "Очистка старых бэкапов..."
cd "$BACKUP_DIR"
ls -t reminder_bot_backup_*.tar.gz | tail -n +6 | xargs -r rm
log "Старые бэкапы удалены"

log "✅ Обновление завершено!"
