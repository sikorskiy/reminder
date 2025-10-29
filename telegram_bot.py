import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from message_processor import MessageProcessor
from google_sheets import GoogleSheetsReminder
from voice_processor import VoiceProcessor
from inline_button_handler import InlineButtonHandler
from inline_buttons import InlineButtonManager
import os
import asyncio

logger = logging.getLogger(__name__)

class ReminderBot:
    def __init__(self, telegram_token: str, openai_api_key: str, google_sheets: GoogleSheetsReminder):
        """
        Инициализация бота
        
        Args:
            telegram_token: Токен Telegram бота
            openai_api_key: API ключ OpenAI
            google_sheets: Экземпляр GoogleSheetsReminder
        """
        self.telegram_token = telegram_token
        self.google_sheets = google_sheets
        self.message_processor = MessageProcessor(openai_api_key)
        self.voice_processor = VoiceProcessor(openai_api_key)
        self.inline_button_handler = InlineButtonHandler(google_sheets)
        
        # Создаем приложение
        self.application = Application.builder().token(telegram_token).build()
        
        # Инициализируем менеджер inline-кнопок
        self.inline_button_manager = InlineButtonManager(self.application.bot)
        
        # Временное хранение последнего сообщения от каждого пользователя
        self.last_user_messages = {}  # {user_id: {'message': text, 'timestamp': time, 'update': update_obj}}
        
        # Таймаут для связывания сообщений (в секундах)
        self.MESSAGE_LINK_TIMEOUT = 2  # 2 секунды
        
        # Добавляем обработчики
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("buttons", self.buttons_command))
        # Единый обработчик для всех текстовых сообщений (обычных и пересланных)
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_unified_message))
        self.application.add_handler(MessageHandler(filters.VOICE, self.handle_voice_message))
        # Обработчик для inline-кнопок
        self.application.add_handler(CallbackQueryHandler(self.handle_callback_query))
    
    def _build_forwarded_gpt_input(self, forwarded_text: str) -> str:
        """Готовит обогащённый ввод для GPT по пересланному сообщению."""
        return (
            "Преобразуй пересланный текст ниже в короткую и конкретную формулировку задачи "
            "для напоминания (без слов 'напомни', только суть действия). Если в тексте есть время/дату — "
            "используй их. Если времени нет — верни datetime: null. Текст пересланного: "
            f"{forwarded_text}"
        )

    def _extract_and_validate(self, text: str):
        """
        Унифицированный вызов GPT-извлечения и последующей валидации.
        Возвращает кортеж (reminder_info | None, error_message | "").
        """
        reminder_info = self.message_processor.extract_reminder_info(text)
        if reminder_info is None:
            return None, "Не удалось распознать напоминание"
        is_valid, error_message = self.message_processor.validate_reminder_info(reminder_info)
        if is_valid:
            return reminder_info, ""
        # Если время в прошлом – пробуем один раз пересчитать, принудительно смещая в будущее
        if error_message == "Время напоминания не может быть в прошлом":
            adjusted_text = (
                f"{text}\n\n"
                "ВНИМАНИЕ: Предыдущее вычисление дало прошедшее время. Пересчитай дату/время так, "
                "чтобы оно было в ближайшем будущем относительно текущего момента, сохранив исходный смысл."
            )
            second = self.message_processor.extract_reminder_info(adjusted_text)
            if second is None:
                return None, error_message
            is_valid2, err2 = self.message_processor.validate_reminder_info(second)
            if is_valid2:
                return second, ""
            return None, err2
        return None, error_message
    
    def cleanup_expired_messages(self):
        """Очищает устаревшие последние сообщения"""
        import time
        current_time = time.time()
        expired_users = []
        
        for user_id, data in self.last_user_messages.items():
            if current_time - data['timestamp'] > self.MESSAGE_LINK_TIMEOUT:
                expired_users.append(user_id)
        
        for user_id in expired_users:
            del self.last_user_messages[user_id]
        
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        welcome_message = """
🤖 Привет! Я бот-напоминальщик.

Ты можешь:
📝 Написать мне текстовое сообщение с напоминанием
🎤 Отправить голосовое сообщение с напоминанием

Примеры:
• "Напомни мне завтра в 15:00 о встрече"
• "Купить хлеб через 2 часа"
• "Позвонить маме в субботу в 10 утра"

Используй /help для получения справки.
        """
        await update.message.reply_text(welcome_message)
        
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_message = """
📋 Как использовать бота:

📝 Текстовые сообщения:
1. Напиши сообщение с напоминанием в любом формате
2. Бот автоматически распознает время и текст
3. Напоминание будет добавлено в таблицу

🎤 Голосовые сообщения:
1. Отправь голосовое сообщение с напоминанием
2. Бот распознает речь и извлечет информацию
3. Напоминание будет добавлено в таблицу

Примеры сообщений:
• "Напомни мне завтра в 15:00 о встрече"
• "Купить хлеб через 2 часа"
• "Позвонить маме в субботу в 10 утра"
• "Встреча с клиентом 20 января в 14:30"

Команды:
/start - Начать работу с ботом
/help - Показать эту справку
/buttons - Показать доступные кнопки управления
        """
        await update.message.reply_text(help_message)
        
    async def buttons_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /buttons"""
        help_text = self.inline_button_manager.format_buttons_help()
        
        await update.message.reply_text(help_text, parse_mode='HTML')
        
    async def handle_unified_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Единый обработчик всех текстовых сообщений (обычных и пересланных).
        
        Логика:
        1. Сохраняет сообщение в буфер
        2. Ждёт 2 секунды
        3. Если пришло пересланное - обрабатывает пару
        4. Если не пришло - обрабатывает как одиночное
        """
        user_id = update.effective_user.id
        message = update.message
        is_forwarded = bool(message.forward_origin)
        
        # Получаем текст сообщения
        message_text = message.text or message.caption or "Сообщение без текста"
        if is_forwarded:
            logger.info(f"Получено пересланное сообщение от пользователя {user_id}: {message_text}")
        else:
            logger.info(f"Получено обычное сообщение от пользователя {user_id}: {message_text}")
        
        # Очищаем устаревшие сообщения
        self.cleanup_expired_messages()
        
        # Проверяем, есть ли уже сообщение в буфере от этого пользователя
        # (это означает, что пришло второе сообщение в паре)
        existing_message = self.last_user_messages.get(user_id)
        
        import time
        current_time = time.time()
        
        # Если есть предыдущее сообщение от этого пользователя и оно не старше 2 секунд
        if existing_message and (current_time - existing_message['timestamp']) < 2:
            # Это вторая часть пары!
            first_is_forwarded = existing_message.get('is_forwarded', False)
            # Пара: обычное + пересланное (в любом порядке)
            if (not first_is_forwarded and is_forwarded) or (first_is_forwarded and not is_forwarded):
                first_message = existing_message['message']
                second_message = message_text
                # Если первое было пересланным - меняем порядок
                if first_is_forwarded:
                    first_message, second_message = second_message, first_message
                logger.info(f"Обрабатываем пару: первое='{first_message}', второе='{second_message}'")
                await self.handle_message_pair(first_message, second_message, existing_message['update'], existing_message['context'])
                # Очищаем буфер
                self.last_user_messages.pop(user_id, None)
                return
        
        # Сохраняем сообщение в буфер
        self.last_user_messages[user_id] = {
            'message': message_text,
            'is_forwarded': is_forwarded,
            'timestamp': current_time,
            'update': update,
            'context': context
        }
        
        # Пауза 2 секунды для возможности получения следующего сообщения
        await asyncio.sleep(2)
        
        # Проверяем, не было ли удалено наше сообщение из буфера (значит, обработалось как пара)
        if user_id not in self.last_user_messages:
            logger.info(f"Сообщение {user_id} уже обработано как пара")
            return
        
        # Проверяем, не появилось ли более свежее сообщение от этого пользователя
        current_data = self.last_user_messages.get(user_id)
        if current_data and current_data['timestamp'] > current_time:
            # Появилось более свежее сообщение - значит, наше уже обрабатывается парой
            logger.info(f"Обнаружено более свежее сообщение - наше уже в паре")
            return
        
        # Не пришло второго сообщения - обрабатываем как одиночное
        if is_forwarded:
            await self.process_single_forwarded(update, context, message_text)
        else:
            await self.process_single_message(message_text, update, context)
        
        # Очищаем буфер
        self.last_user_messages.pop(user_id, None)
    
    async def process_single_forwarded(self, update: Update, context: ContextTypes.DEFAULT_TYPE, forwarded_text: str):
        """Обрабатывает одиночное пересланное сообщение"""
        user_id = update.effective_user.id
        forwarded_message = update.message
        
        processing_message = await update.message.reply_text("📎 Обрабатываю пересылаемое сообщение...")
        
        try:
            # Готовим ввод и извлекаем через общий метод
            gpt_input = self._build_forwarded_gpt_input(forwarded_text)
            reminder_info, err = self._extract_and_validate(gpt_input)
            if not reminder_info:
                await processing_message.edit_text(
                    (f"❌ Не удалось распознать напоминание в пересылаемом сообщении:\n<i>{forwarded_text}</i>"
                     if err == "Не удалось распознать напоминание" else
                     f"🤔 <b>Не удалось создать напоминание</b>\n\n<i>Причина:</i> {err}"),
                    parse_mode='HTML'
                )
                return
            
            # Определяем источник пересылки для комментария
            def _format_forward_origin(msg):
                origin = getattr(msg, 'forward_origin', None)
                try:
                    # MessageOriginUser
                    sender_user = getattr(origin, 'sender_user', None)
                    if sender_user:
                        name = " ".join(filter(None, [sender_user.first_name, sender_user.last_name]))
                        username = f"@{sender_user.username}" if getattr(sender_user, 'username', None) else ""
                        return f"Пользователь: {name or username or sender_user.id}"
                    # MessageOriginChat
                    sender_chat = getattr(origin, 'sender_chat', None)
                    if sender_chat and getattr(sender_chat, 'title', None):
                        return f"Чат: {sender_chat.title}"
                    # MessageOriginChannel
                    channel_chat = getattr(origin, 'chat', None)
                    if channel_chat and getattr(channel_chat, 'title', None):
                        return f"Канал: {channel_chat.title}"
                    # Hidden user name
                    hidden_name = getattr(origin, 'sender_user_name', None)
                    if hidden_name:
                        return f"Пользователь: {hidden_name}"
                except Exception:
                    pass
                return "Источник неизвестен"

            forward_from_str = _format_forward_origin(forwarded_message)

            # Сохраняем: текст из reminder_info, а ПОЛНЫЙ пересланный + источник — в comment (6 столбец)
            row_number = self.google_sheets.add_reminder(
                datetime_str=reminder_info.get('datetime'),
                text=reminder_info['text'],
                timezone=reminder_info.get('timezone', 'Europe/Moscow'),
                comment=f"От: {forward_from_str}\n\n{forwarded_text}"
            )
            
            if row_number:
                # Сохраняем для inline-кнопок
                reminder_data = {
                    'row': row_number,
                    'datetime': reminder_info.get('datetime'),
                    'text': reminder_info['text'],
                    'timezone': reminder_info.get('timezone', 'Europe/Moscow')
                }
                self.inline_button_handler.set_last_reminder(user_id, reminder_data)
                
                # Формируем ответ
                from datetime import datetime
                timezone = reminder_info.get('timezone', 'Europe/Moscow')
                text = reminder_info['text']
                
                if reminder_info.get('datetime'):
                    dt = datetime.strptime(reminder_info['datetime'], '%Y-%m-%d %H:%M:%S')
                    formatted_time = dt.strftime('%d.%m.%Y в %H:%M')
                    time_info = f"⏰ <b>Время:</b> {formatted_time}\n🌍 <b>Часовой пояс:</b> {timezone}\n\n🔔 Вы получите уведомление в указанное время."
                    table_info = f"<code>{reminder_info['datetime']} | {text} | {timezone} | FALSE | | От: {forward_from_str} | {forwarded_text[:50]}...</code>"
                else:
                    time_info = "⚠️ <b>Время не указано</b> - напоминание создано без даты и времени"
                    table_info = f"<code> | {text} | {timezone} | FALSE | | От: {forward_from_str} | {forwarded_text[:50]}...</code>"
                
                success_message = (
                    f"✅ <b>Напоминание добавлено из пересылаемого сообщения!</b>\n\n"
                    f"👤 <b>Источник:</b> {forward_from_str}\n"
                    f"📎 <b>Пересланное сообщение:</b> {forwarded_text[:100]}{'...' if len(forwarded_text) > 100 else ''}\n\n"
                    f"📝 <b>Текст напоминания:</b> {text}\n"
                    f"{time_info}\n\n"
                    f"📊 <i>Строка в таблице:</i>\n"
                    f"{table_info}"
                )
                await processing_message.edit_text(success_message, parse_mode='HTML')
            else:
                await processing_message.edit_text("❌ Ошибка при сохранении напоминания. Попробуйте позже.")
        
        except Exception as e:
            logger.error(f"Ошибка при самостоятельной обработке пересылаемого сообщения: {e}")
            await processing_message.edit_text(
                "❌ Произошла ошибка при обработке пересылаемого сообщения. Попробуйте позже."
            )
    
    async def handle_message_pair(self, first_message, second_message, update, context):
        """Обрабатывает пару сообщений: поясняющее + пересылаемое"""
        user_id = update.effective_user.id
        
        # Отправляем сообщение о том, что обрабатываем
        processing_message = await update.message.reply_text("🤔 Обрабатываю пару сообщений...")
        
        try:
            # Извлекаем информацию о напоминании из первого сообщения (общий метод)
            reminder_info, err = self._extract_and_validate(first_message)
            if not reminder_info:
                await processing_message.edit_text(
                    ("❌ Не удалось распознать напоминание в первом сообщении.\n\nПопробуйте указать время более четко."
                     if err == "Не удалось распознать напоминание" else
                     f"🤔 <b>Не удалось создать напоминание</b>\n\n<i>Причина:</i> {err}"),
                    parse_mode='HTML'
                )
                return
                
            # Добавляем напоминание в Google Sheets с комментарием
            logger.info(f"Добавляем напоминание с комментарием: '{second_message}'")
            row_number = self.google_sheets.add_reminder(
                datetime_str=reminder_info.get('datetime'),  # Может быть None
                text=reminder_info['text'],
                timezone=reminder_info.get('timezone', 'Europe/Moscow'),
                comment=second_message  # Второе сообщение как комментарий
            )
            
            if row_number:
                # Сохраняем информацию о последнем напоминании для кнопок
                reminder_data = {
                    'row': row_number,
                    'datetime': reminder_info.get('datetime'),  # Может быть None
                    'text': reminder_info['text'],
                    'timezone': reminder_info.get('timezone', 'Europe/Moscow')
                }
                self.inline_button_handler.set_last_reminder(user_id, reminder_data)
                
                # Формируем сообщение об успехе
                from datetime import datetime
                timezone = reminder_info.get('timezone', 'Europe/Moscow')
                text = reminder_info['text']
                
                # Проверяем, есть ли время
                if reminder_info.get('datetime'):
                    dt = datetime.strptime(reminder_info['datetime'], '%Y-%m-%d %H:%M:%S')
                    formatted_time = dt.strftime('%d.%m.%Y в %H:%M')
                    time_info = f"⏰ <b>Время:</b> {formatted_time}\n🌍 <b>Часовой пояс:</b> {timezone}\n\n🔔 Вы получите уведомление в указанное время."
                    table_info = f"<code>{reminder_info['datetime']} | {text} | {timezone} | FALSE | | {second_message[:50]}...</code>"
                else:
                    time_info = "⚠️ <b>Время не указано</b> - напоминание создано без даты и времени"
                    table_info = f"<code> | {text} | {timezone} | FALSE | | {second_message[:50]}...</code>"
                
                success_message = (
                    f"✅ <b>Напоминание добавлено из пары сообщений!</b>\n\n"
                    f"📝 <b>Текст напоминания:</b> {text}\n"
                    f"📎 <b>Комментарий:</b> {second_message[:100]}{'...' if len(second_message) > 100 else ''}\n"
                    f"{time_info}\n\n"
                    f"📊 <i>Строка в таблице:</i>\n"
                    f"{table_info}"
                )
                
                await processing_message.edit_text(success_message, parse_mode='HTML')
            else:
                await processing_message.edit_text("❌ Ошибка при сохранении напоминания. Попробуйте позже.")
                
        except Exception as e:
            logger.error(f"Ошибка при обработке пары сообщений: {e}")
            await processing_message.edit_text(
                "❌ Произошла ошибка при обработке пары сообщений. Попробуйте позже."
            )
    
    async def process_single_message(self, user_message, update, context):
        """Обрабатывает одиночное сообщение"""
        user_id = update.effective_user.id
        
        # Отправляем сообщение о том, что обрабатываем
        processing_message = await update.message.reply_text("🤔 Обрабатываю ваше сообщение...")
        
        try:
            # Унифицированное извлечение + валидация
            reminder_info, err = self._extract_and_validate(user_message)
            if not reminder_info:
                await processing_message.edit_text(
                    ("❌ Не удалось распознать напоминание в вашем сообщении.\n\n"
                    "Попробуйте указать время более четко, например:\n"
                    "• \"Напомни мне завтра в 15:00 о встрече\"\n"
                    "• \"Купить хлеб через 2 часа\""
                     if err == "Не удалось распознать напоминание" else
                     f"🤔 <b>Не удалось создать напоминание</b>\n\n<i>Причина:</i> {err}"),
                    parse_mode='HTML'
                )
                return
                
            # Добавляем напоминание в Google Sheets
            row_number = self.google_sheets.add_reminder(
                datetime_str=reminder_info.get('datetime'),  # Может быть None
                text=reminder_info['text'],
                timezone=reminder_info.get('timezone', 'Europe/Moscow'),
                comment=''  # Пустой комментарий для обычных сообщений
            )
            
            if row_number:
                # Сохраняем информацию о последнем напоминании для кнопок
                reminder_data = {
                    'row': row_number,
                    'datetime': reminder_info.get('datetime'),  # Может быть None
                    'text': reminder_info['text'],
                    'timezone': reminder_info.get('timezone', 'Europe/Moscow')
                }
                self.inline_button_handler.set_last_reminder(user_id, reminder_data)
                
                # Форматируем время для отображения
                from datetime import datetime
                timezone = reminder_info.get('timezone', 'Europe/Moscow')
                text = reminder_info['text']
                
                # Проверяем, есть ли время
                if reminder_info.get('datetime'):
                    dt = datetime.strptime(reminder_info['datetime'], '%Y-%m-%d %H:%M:%S')
                    formatted_time = dt.strftime('%d.%m.%Y в %H:%M')
                    time_info = f"⏰ <b>Время:</b> {formatted_time}\n🌍 <b>Часовой пояс:</b> {timezone}\n\n🔔 Вы получите уведомление в указанное время."
                    table_info = f"<code>{reminder_info['datetime']} | {text} | {timezone} | FALSE</code>"
                else:
                    time_info = "⚠️ <b>Время не указано</b> - напоминание создано без даты и времени"
                    table_info = f"<code> | {text} | {timezone} | FALSE</code>"
                
                success_message = (
                    f"✅ <b>Напоминание добавлено!</b>\n\n"
                    f"📝 <b>Текст:</b> {text}\n"
                    f"{time_info}\n\n"
                    f"📊 <i>Строка в таблице:</i>\n"
                    f"{table_info}"
                )
                
                await processing_message.edit_text(success_message, parse_mode='HTML')
            else:
                await processing_message.edit_text("❌ Ошибка при сохранении напоминания. Попробуйте позже.")
                
        except Exception as e:
            logger.error(f"Ошибка при обработке сообщения: {e}")
            await processing_message.edit_text(
                "❌ Произошла ошибка при обработке сообщения. Попробуйте позже."
            )
    
    async def handle_voice_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик голосовых сообщений"""
        user_id = update.effective_user.id
        voice = update.message.voice
        
        logger.info(f"Получено голосовое сообщение от пользователя {user_id}, длительность: {voice.duration}с")
        
        # Отправляем сообщение о том, что обрабатываем
        processing_message = await update.message.reply_text("🎤 Обрабатываю голосовое сообщение...")
        
        try:
            # Распознаем речь
            recognized_text = await self.voice_processor.process_voice_message(update, context)
            
            if not recognized_text:
                await processing_message.edit_text(
                    "❌ Не удалось распознать голосовое сообщение.\n\n"
                    "Попробуйте:\n"
                    "• Говорить четче и медленнее\n"
                    "• Убедиться, что микрофон работает\n"
                    "• Отправить текстовое сообщение вместо голосового"
                )
                return
            
            # Обновляем сообщение о распознанном тексте
            await processing_message.edit_text(f"🎤 <b>Распознанный текст:</b>\n<i>{recognized_text}</i>\n\n🤔 Обрабатываю напоминание...", parse_mode='HTML')
            
            # Унифицированное извлечение + валидация
            reminder_info, err = self._extract_and_validate(recognized_text)
            if not reminder_info:
                await processing_message.edit_text(
                    (f"❌ Не удалось распознать напоминание в тексте:\n<i>{recognized_text}</i>\n\n"
                    "Попробуйте указать время более четко, например:\n"
                    "• \"Напомни мне завтра в 15:00 о встрече\"\n"
                     "• \"Купить хлеб через 2 часа\""
                     if err == "Не удалось распознать напоминание" else
                     f"🤔 <b>Не удалось создать напоминание</b>\n\n<i>Причина:</i> {err}"),
                    parse_mode='HTML'
                )
                return
                
            # Добавляем напоминание в Google Sheets
            success = self.google_sheets.add_reminder(
                datetime_str=reminder_info.get('datetime'),  # Может быть None
                text=reminder_info['text'],
                timezone=reminder_info.get('timezone', 'Europe/Moscow')
            )
            
            if success:
                # Форматируем время для отображения
                from datetime import datetime
                timezone = reminder_info.get('timezone', 'Europe/Moscow')
                text = reminder_info['text']
                
                # Проверяем, есть ли время
                if reminder_info.get('datetime'):
                    dt = datetime.strptime(reminder_info['datetime'], '%Y-%m-%d %H:%M:%S')
                    formatted_time = dt.strftime('%d.%m.%Y в %H:%M')
                    time_info = f"⏰ <b>Время:</b> {formatted_time}\n🌍 <b>Часовой пояс:</b> {timezone}\n\n🔔 Вы получите уведомление в указанное время."
                    table_info = f"<code>{reminder_info['datetime']} | {text} | {timezone} | FALSE</code>"
                else:
                    time_info = "⚠️ <b>Время не указано</b> - напоминание создано без даты и времени"
                    table_info = f"<code> | {text} | {timezone} | FALSE</code>"
                
                success_message = (
                    f"✅ <b>Напоминание добавлено из голосового сообщения!</b>\n\n"
                    f"🎤 <b>Распознанный текст:</b> {recognized_text}\n\n"
                    f"📝 <b>Текст напоминания:</b> {text}\n"
                    f"{time_info}\n\n"
                    f"📊 <i>Строка в таблице:</i>\n"
                    f"{table_info}"
                )
                
                await processing_message.edit_text(success_message, parse_mode='HTML')
            else:
                await processing_message.edit_text("❌ Ошибка при сохранении напоминания. Попробуйте позже.")
                
        except Exception as e:
            logger.error(f"Ошибка при обработке голосового сообщения: {e}")
            await processing_message.edit_text(
                "❌ Произошла ошибка при обработке голосового сообщения. Попробуйте позже."
            )
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик inline-кнопок"""
        user_id = update.effective_user.id
        
        logger.info(f"Получен callback от пользователя {user_id}")
        
        try:
            # Обрабатываем callback
            handled = await self.inline_button_handler.handle_callback_query(update, context)
            
            if not handled:
                await update.callback_query.answer("❌ Неизвестное действие.")
                
        except Exception as e:
            logger.error(f"Ошибка при обработке callback: {e}")
            await update.callback_query.answer("❌ Произошла ошибка при обработке действия.")
    
    # async def handle_forwarded_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    #     """Обработчик пересылаемых сообщений"""
        user_id = update.effective_user.id
        forwarded_message = update.message
        
        logger.info(f"Получено пересылаемое сообщение от пользователя {user_id}")
        
        # Получаем текст пересылаемого сообщения
        forwarded_text = forwarded_message.text or forwarded_message.caption or "Пересланное сообщение без текста"
        
        # Проверяем, было ли недавно обычное сообщение от этого пользователя
        if user_id in self.last_user_messages:
            import time
            last_msg_data = self.last_user_messages[user_id]
            time_diff = time.time() - last_msg_data['timestamp']
            
            # Если прошло меньше таймаута - связываем сообщения
            if time_diff < self.MESSAGE_LINK_TIMEOUT:
                # НЕ удаляем здесь - это сделает handle_message_pair
                
                # Обрабатываем пару сообщений
                await self.handle_message_pair(
                    last_msg_data['message'], 
                    forwarded_text, 
                    last_msg_data['update'], 
                    last_msg_data['context']
                )
                return
        
        # Нет недавнего сообщения - обрабатываем пересылаемое как обычное напоминание
        processing_message = await update.message.reply_text("📎 Обрабатываю пересылаемое сообщение...")
        
        try:
            # Проверяем, есть ли ожидающее поясняющее сообщение для этого пользователя (старая логика)
            if False:  # Отключаем старую логику
                # Есть ожидающее поясняющее сообщение - объединяем их
                explanatory_data = self.pending_explanatory_messages[user_id]
                explanatory_message = explanatory_data['message']
                reminder_data = explanatory_data['reminder_data']
                
                # Обновляем напоминание с комментарием
                success = self.google_sheets.update_reminder_comment(reminder_data['row'], forwarded_text)
                
                if success:
                    # Очищаем ожидающее сообщение
                    del self.pending_explanatory_messages[user_id]
                    
                    # Формируем сообщение об успехе
                    success_message = (
                        f"✅ <b>Напоминание обновлено с пересылаемым сообщением!</b>\n\n"
                        f"📝 <b>Текст напоминания:</b> {reminder_data['text']}\n"
                        f"📎 <b>Пересланное сообщение:</b> {forwarded_text[:100]}{'...' if len(forwarded_text) > 100 else ''}\n\n"
                        f"🔔 Напоминание будет отправлено в указанное время с пересылаемым сообщением."
                    )
                    
                    await processing_message.edit_text(success_message, parse_mode='HTML')
                    return
                else:
                    await processing_message.edit_text("❌ Ошибка при обновлении напоминания. Попробуйте позже.")
                    return
            
            # Нет ожидающего поясняющего сообщения - обрабатываем как обычное напоминание
            # Извлекаем информацию о напоминании с помощью ChatGPT
            reminder_info = self.message_processor.extract_reminder_info(forwarded_text)
            
            if reminder_info is None:
                await processing_message.edit_text(
                    f"❌ Не удалось распознать напоминание в пересылаемом сообщении:\n<i>{forwarded_text}</i>\n\n"
                    "Попробуйте добавить поясняющее сообщение с указанием времени.",
                    parse_mode='HTML'
                )
                return
                
            # Валидируем информацию
            is_valid, error_message = self.message_processor.validate_reminder_info(reminder_info)
            
            if not is_valid:
                logger.warning(f"Ошибка валидации для пользователя {user_id}: {error_message}")
                await processing_message.edit_text(
                    f"🤔 <b>Не удалось создать напоминание</b>\n\n"
                    f"<i>Причина:</i> {error_message}\n\n"
                    f"💡 <b>Попробуйте добавить поясняющее сообщение с указанием времени.</b>",
                    parse_mode='HTML'
                )
                return
                
            # Добавляем напоминание в Google Sheets с комментарием
            row_number = self.google_sheets.add_reminder(
                datetime_str=reminder_info['datetime'],
                text=reminder_info['text'],
                timezone=reminder_info.get('timezone', 'Europe/Moscow'),
                comment=forwarded_text  # Пересылаемое сообщение как комментарий
            )
            
            if row_number:
                # Сохраняем информацию о последнем напоминании для кнопок
                reminder_data = {
                    'row': row_number,
                    'datetime': reminder_info.get('datetime'),  # Может быть None
                    'text': reminder_info['text'],
                    'timezone': reminder_info.get('timezone', 'Europe/Moscow')
                }
                self.inline_button_handler.set_last_reminder(user_id, reminder_data)
                
                # Форматируем время для отображения
                from datetime import datetime
                timezone = reminder_info.get('timezone', 'Europe/Moscow')
                text = reminder_info['text']
                
                # Проверяем, есть ли время
                if reminder_info.get('datetime'):
                    dt = datetime.strptime(reminder_info['datetime'], '%Y-%m-%d %H:%M:%S')
                    formatted_time = dt.strftime('%d.%m.%Y в %H:%M')
                    time_info = f"⏰ <b>Время:</b> {formatted_time}\n🌍 <b>Часовой пояс:</b> {timezone}\n\n🔔 Вы получите уведомление в указанное время."
                    table_info = f"<code>{reminder_info['datetime']} | {text} | {timezone} | FALSE | | {forwarded_text[:50]}...</code>"
                else:
                    time_info = "⚠️ <b>Время не указано</b> - напоминание создано без даты и времени"
                    table_info = f"<code> | {text} | {timezone} | FALSE | | {forwarded_text[:50]}...</code>"
                
                success_message = (
                    f"✅ <b>Напоминание добавлено из пересылаемого сообщения!</b>\n\n"
                    f"📎 <b>Пересланное сообщение:</b> {forwarded_text[:100]}{'...' if len(forwarded_text) > 100 else ''}\n\n"
                    f"📝 <b>Текст напоминания:</b> {text}\n"
                    f"{time_info}\n\n"
                    f"📊 <i>Строка в таблице:</i>\n"
                    f"{table_info}"
                )
                
                await processing_message.edit_text(success_message, parse_mode='HTML')
            else:
                await processing_message.edit_text("❌ Ошибка при сохранении напоминания. Попробуйте позже.")
                
        except Exception as e:
            logger.error(f"Ошибка при обработке пересылаемого сообщения: {e}")
            await processing_message.edit_text(
                "❌ Произошла ошибка при обработке пересылаемого сообщения. Попробуйте позже."
            )
            
    def run(self):
        """Запуск бота"""
        logger.info("Запуск Telegram бота...")
        self.application.run_polling()

    async def run_async(self):
        """Запуск Telegram бота в существующем event loop"""
        logger.info("Запуск Telegram бота (async)...")
        try:
            # Инициализируем и запускаем бота
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()
            
            # Ждем бесконечно (бот будет работать в фоне)
            while True:
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Ошибка запуска Telegram бота: {e}")
            raise 