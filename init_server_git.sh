#!/bin/bash

# Скрипт для инициализации Git репозитория на сервере
# Запускать на сервере от имени root

echo "🔧 Инициализация Git репозитория на сервере..."

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
REPO_URL="https://github.com/sikorskiy/reminder.git"  # Замените на ваш репозиторий
SERVICE_NAME="reminder-bot.service"

# Проверка существования директории
if [ ! -d "$PROJECT_DIR" ]; then
    error "Директория $PROJECT_DIR не найдена"
    info "Создаем директорию..."
    mkdir -p "$PROJECT_DIR"
fi

cd "$PROJECT_DIR" || {
    error "Не удалось перейти в директорию $PROJECT_DIR"
    exit 1
}

# Проверка, является ли директория Git репозиторием
if [ -d ".git" ]; then
    warn "Директория уже является Git репозиторием"
    info "Текущий remote:"
    git remote -v
    
    # Автоматически обновляем remote URL если он отличается
    CURRENT_URL=$(git remote get-url origin)
    if [ "$CURRENT_URL" != "$REPO_URL" ]; then
        log "Обновляем remote URL с $CURRENT_URL на $REPO_URL"
        git remote set-url origin "$REPO_URL"
        log "Remote URL обновлен"
    else
        log "Remote URL уже корректный"
    fi
else
    log "Инициализация Git репозитория..."
    
    # Инициализация Git
    git init
    
    # Добавление remote
    git remote add origin "$REPO_URL"
    
    # Настройка Git
    git config user.name "Server Bot"
    git config user.email "server@bot.local"
    
    log "Git репозиторий инициализирован"
fi

# Получение изменений
log "Получение изменений из репозитория..."
git fetch origin

if [ $? -ne 0 ]; then
    error "Ошибка при получении изменений из репозитория"
    info "Проверьте URL репозитория и доступ к интернету"
    exit 1
fi

# Проверка ветки main
if git show-ref --verify --quiet refs/remotes/origin/main; then
    log "Переключение на ветку main..."
    # Проверяем, существует ли уже локальная ветка main
    if git show-ref --verify --quiet refs/heads/main; then
        log "Локальная ветка main уже существует, переключаемся на неё"
        git checkout main
        git pull origin main
    else
        git checkout -b main origin/main
    fi
else
    error "Ветка main не найдена в удаленном репозитории"
    exit 1
fi

# Проверка файлов
log "Проверка файлов проекта..."
required_files=(
    "main.py"
    "telegram_bot.py"
    "message_processor.py"
    "google_sheets.py"
    "requirements.txt"
    ".env"
    "finagent-461009-8c1e97a2ff0c.json"
)

missing_files=()
for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        missing_files+=("$file")
    fi
done

if [ ${#missing_files[@]} -gt 0 ]; then
    warn "Отсутствуют следующие файлы:"
    for file in "${missing_files[@]}"; do
        echo "  - $file"
    done
    info "Убедитесь, что все необходимые файлы присутствуют"
fi

# Проверка виртуального окружения
if [ ! -d "venv" ]; then
    warn "Виртуальное окружение не найдено"
    info "Создаем виртуальное окружение..."
    python3 -m venv venv
fi

# Активация виртуального окружения
source venv/bin/activate

# Установка зависимостей
log "Установка зависимостей..."
pip install --upgrade pip
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

# Проверка сервиса
if systemctl is-active --quiet "$SERVICE_NAME"; then
    log "Сервис $SERVICE_NAME уже запущен"
    info "Для применения изменений перезапустите сервис:"
    info "sudo systemctl restart $SERVICE_NAME"
else
    warn "Сервис $SERVICE_NAME не запущен"
    info "Для запуска используйте:"
    info "sudo systemctl start $SERVICE_NAME"
fi

log "✅ Инициализация завершена!"
echo ""
info "📋 Следующие шаги:"
info "1. Убедитесь, что файл .env настроен корректно"
info "2. Проверьте Google Sheets credentials"
info "3. Запустите сервис: sudo systemctl start $SERVICE_NAME"
info "4. Для будущих обновлений используйте: sudo ./deploy_update.sh"
