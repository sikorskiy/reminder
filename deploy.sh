#!/bin/bash

# Скрипт для быстрого развертывания изменений на сервер
# Запускать с локальной машины

echo "🚀 Быстрое развертывание на сервер..."

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

# Конфигурация (измените под ваш сервер)
SERVER_USER="root"
SERVER_HOST="80.90.183.91"  # Замените на IP вашего сервера
SERVER_PROJECT_DIR="/opt/telegram_bots/reminder_bot"
SERVICE_NAME="reminder-bot.service"

# Проверка параметров
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "Использование: $0 [опции]"
    echo ""
    echo "Опции:"
    echo "  --help, -h     Показать эту справку"
    echo "  --init         Инициализировать Git на сервере"
    echo "  --update       Обновить код на сервере"
    echo "  --status       Проверить статус сервиса"
    echo "  --logs         Показать логи сервиса"
    echo ""
    echo "Примеры:"
    echo "  $0 --init      # Первоначальная настройка"
    echo "  $0 --update    # Обновление кода"
    echo "  $0 --status    # Проверка статуса"
    exit 0
fi

# Функция для выполнения команд на сервере
run_on_server() {
    ssh "$SERVER_USER@$SERVER_HOST" "$1"
}

# Функция для копирования файлов на сервер
copy_to_server() {
    scp "$1" "$SERVER_USER@$SERVER_HOST:$2"
}

# Инициализация Git на сервере
init_server() {
    log "Инициализация Git на сервере..."
    
    # Проверяем, существует ли уже Git репозиторий
    if run_on_server "[ -d '$SERVER_PROJECT_DIR/.git' ]"; then
        log "Git репозиторий уже существует, используем простое обновление..."
        
        # Копируем простой скрипт обновления
        copy_to_server "simple_update.sh" "/tmp/"
        
        # Запускаем простое обновление
        run_on_server "chmod +x /tmp/simple_update.sh && /tmp/simple_update.sh"
    else
        log "Создаем новый Git репозиторий..."
        
        # Копируем скрипт инициализации
        copy_to_server "init_server_git.sh" "/tmp/"
        
        # Запускаем инициализацию
        run_on_server "chmod +x /tmp/init_server_git.sh && /tmp/init_server_git.sh"
    fi
    
    if [ $? -eq 0 ]; then
        log "✅ Инициализация завершена"
    else
        error "❌ Ошибка при инициализации"
        exit 1
    fi
}

# Обновление кода на сервере
update_server() {
    log "Обновление кода на сервере..."
    
    # Сначала пушим изменения в Git
    log "Отправка изменений в Git..."
    git add .
    git commit -m "Update: $(date '+%Y-%m-%d %H:%M:%S')"
    git push origin main
    
    if [ $? -ne 0 ]; then
        error "❌ Ошибка при отправке в Git"
        exit 1
    fi
    
    # Копируем скрипт обновления
    copy_to_server "deploy_update.sh" "/tmp/"
    
    # Запускаем обновление
    run_on_server "chmod +x /tmp/deploy_update.sh && /tmp/deploy_update.sh"
    
    if [ $? -eq 0 ]; then
        log "✅ Обновление завершено"
    else
        error "❌ Ошибка при обновлении"
        exit 1
    fi
}

# Проверка статуса сервиса
check_status() {
    log "Проверка статуса сервиса..."
    
    run_on_server "systemctl status $SERVICE_NAME --no-pager"
    
    echo ""
    info "Последние логи:"
    run_on_server "journalctl -u $SERVICE_NAME --no-pager -n 10"
}

# Показ логов
show_logs() {
    log "Показ логов сервиса..."
    
    run_on_server "journalctl -u $SERVICE_NAME -f"
}

# Основная логика
case "$1" in
    "--init")
        init_server
        ;;
    "--update")
        update_server
        ;;
    "--status")
        check_status
        ;;
    "--logs")
        show_logs
        ;;
    "")
        # Если параметры не указаны, показываем меню
        echo "Выберите действие:"
        echo "1) Инициализировать Git на сервере"
        echo "2) Обновить код на сервере"
        echo "3) Проверить статус сервиса"
        echo "4) Показать логи"
        echo "5) Выход"
        echo ""
        read -p "Введите номер (1-5): " choice
        
        case $choice in
            1) init_server ;;
            2) update_server ;;
            3) check_status ;;
            4) show_logs ;;
            5) exit 0 ;;
            *) error "Неверный выбор" ;;
        esac
        ;;
    *)
        error "Неизвестная опция: $1"
        echo "Используйте --help для справки"
        exit 1
        ;;
esac
