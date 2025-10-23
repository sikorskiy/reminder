# 🚀 Быстрый старт: Развертывание голосовых сообщений

## ✅ Что уже сделано

1. **Код отправлен в Git** - все изменения в репозитории
2. **Созданы скрипты развертывания** - автоматическое обновление
3. **Документация готова** - подробные инструкции

## 🎯 Следующие шаги

### Вариант 1: Автоматическое развертывание (Рекомендуется)

```bash
# 1. Отредактируйте IP сервера в deploy.sh
nano deploy.sh
# Измените: SERVER_HOST="your-server-ip"

# 2. Инициализируйте Git на сервере
./deploy.sh --init

# 3. Обновите код на сервере
./deploy.sh --update
```

### Вариант 2: Ручное развертывание

```bash
# На сервере выполните:
cd /opt/telegram_bots/reminder_bot

# Остановите сервис
sudo systemctl stop reminder-bot.service

# Обновите код из Git
git fetch origin
git reset --hard origin/main

# Установите зависимости
source venv/bin/activate
pip install requests pydub
sudo apt install ffmpeg

# Запустите сервис
sudo systemctl start reminder-bot.service
```

## 🧪 Тестирование

### Локальное тестирование
```bash
# Запустите тесты
python test_local.py
```

### Тестирование на сервере
```bash
# Проверьте статус
./deploy.sh --status

# Отправьте боту голосовое сообщение:
# "Напомни мне через 1 минуту о тесте"
```

## 📊 Мониторинг

```bash
# Логи в реальном времени
./deploy.sh --logs

# Или напрямую на сервере:
journalctl -u reminder-bot.service -f
```

## 🆘 Если что-то пошло не так

### Откат к предыдущей версии
```bash
# На сервере
cd /opt/telegram_bots/reminder_bot
sudo systemctl stop reminder-bot.service
git reset --hard HEAD~1
sudo systemctl start reminder-bot.service
```

### Проверка логов
```bash
journalctl -u reminder-bot.service --no-pager -n 50
```

## 🎉 Готово!

После успешного развертывания ваш бот будет поддерживать:
- ✅ Текстовые сообщения (как раньше)
- ✅ Голосовые сообщения (новое!)
- ✅ Автоматическое распознавание речи
- ✅ Создание напоминаний из голоса

**Отправьте боту голосовое сообщение и протестируйте новую функциональность!**
