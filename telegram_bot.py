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
        self.MESSAGE_LINK_TIMEOUT = 10  # 10 секунд
        
        # Добавляем обработчики
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("buttons", self.buttons_command))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.FORWARDED, self.handle_message))
        self.application.add_handler(MessageHandler(filters.VOICE, self.handle_voice_message))
        # Обработчик для пересылаемых сообщений - только для связывания с предыдущими
        self.application.add_handler(MessageHandler(filters.FORWARDED, self.handle_forwarded_only))
        # Обработчик для inline-кнопок
        self.application.add_handler(CallbackQueryHandler(self.handle_callback_query))
    
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
        
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений"""
        user_message = update.message.text
        user_id = update.effective_user.id
        
        logger.info(f"Получено сообщение от пользователя {user_id}: {user_message}")
        
        # Очищаем устаревшие сообщения
        self.cleanup_expired_messages()
        
        # Сохраняем текущее сообщение для возможного связывания со следующим
        import time
        self.last_user_messages[user_id] = {
            'message': user_message,
            'timestamp': time.time(),
            'update': update,
            'context': context
        }
        
        # Делаем паузу, чтобы проверить, придет ли еще сообщение
        await asyncio.sleep(1)
        
        # Проверяем, пришло ли новое сообщение от этого пользователя за время ожидания
        new_message = await self.check_for_new_message(user_id, user_message)
        
        if new_message is None:
            # Нового сообщения не пришло - обрабатываем текущее как одиночное
            await self.process_single_message(user_message, update, context)
            # Удаляем сообщение из хранилища после обработки
            if user_id in self.last_user_messages:
                del self.last_user_messages[user_id]
        else:
            # Пришло новое сообщение - НЕ обрабатываем текущее здесь
            # Оно будет обработано в handle_forwarded_only или останется в last_user_messages
            logger.info(f"Обнаружено новое сообщение от пользователя {user_id}, оставляем текущее в last_user_messages")
    
    async def check_for_new_message(self, user_id, current_message):
        """Проверяет, пришло ли новое сообщение от пользователя после текущего"""
        try:
            # Получаем последние обновления
            updates = await self.application.bot.get_updates(limit=10)
            
            # Ищем сообщения от того же пользователя, которые пришли после текущего
            for update in updates:
                if (update.message and 
                    update.message.from_user and 
                    update.message.from_user.id == user_id and
                    update.message.text != current_message):  # Новое сообщение
                    logger.info(f"Найдено новое сообщение в check_for_new_message: text='{update.message.text}', forward_from={update.message.forward_from}")
                    return update.message
            logger.info(f"Новое сообщение не найдено в check_for_new_message для пользователя {user_id}")
            return None
        except Exception as e:
            logger.error(f"Ошибка при проверке нового сообщения: {e}")
            return None
    
    async def handle_forwarded_only(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик пересылаемых сообщений - только для связывания с предыдущими"""
        user_id = update.effective_user.id
        forwarded_message = update.message
        
        logger.info(f"Получено пересылаемое сообщение от пользователя {user_id}")
        
        # Получаем текст пересылаемого сообщения
        forwarded_text = forwarded_message.text or forwarded_message.caption or "Пересланное сообщение без текста"
        logger.info(f"Пересылаемое сообщение: text='{forwarded_message.text}', caption='{forwarded_message.caption}', итоговый текст='{forwarded_text}'")
        
        # Проверяем, есть ли недавнее сообщение В ПРИНЦИПЕ (без привязки к user_id)
        if self.last_user_messages:
            import time
            # Берем самое свежее сообщение из буфера
            last_user_id, last_msg_data = max(self.last_user_messages.items(), key=lambda kv: kv[1]['timestamp'])
            time_diff = time.time() - last_msg_data['timestamp']
            logger.info(f"Найдено последнее сообщение в last_user_messages (user {last_user_id}): '{last_msg_data['message']}', время разницы: {time_diff:.2f}с, таймаут: {self.MESSAGE_LINK_TIMEOUT}с")
            
            # Если прошло меньше таймаута - связываем сообщения
            if time_diff < self.MESSAGE_LINK_TIMEOUT:
                logger.info(f"Связываем сообщения: первое='{last_msg_data['message']}', второе='{forwarded_text}'")
                await self.handle_message_pair(
                    last_msg_data['message'],
                    forwarded_text,
                    last_msg_data['update'],
                    last_msg_data['context']
                )
                # Удаляем связанное сообщение из буфера
                if last_user_id in self.last_user_messages:
                    del self.last_user_messages[last_user_id]
                return
            else:
                logger.info(f"Последнее сообщение слишком старое: {time_diff:.2f}с > {self.MESSAGE_LINK_TIMEOUT}с")
        else:
            logger.info("Буфер last_user_messages пуст")
        
        # Буфер пуст или сообщение устарело — обрабатываем пересылаемое как самостоятельное напоминание
        processing_message = await update.message.reply_text("📎 Обрабатываю пересылаемое сообщение...")
        
        try:
            # Извлекаем информацию о напоминании из ТЕКСТА ПЕРЕСЛАННОГО
            reminder_info = self.message_processor.extract_reminder_info(forwarded_text)
            
            if reminder_info is None:
                await processing_message.edit_text(
                    f"❌ Не удалось распознать напоминание в пересылаемом сообщении:\n<i>{forwarded_text}</i>",
                    parse_mode='HTML'
                )
                return
            
            # Валидируем
            is_valid, error_message = self.message_processor.validate_reminder_info(reminder_info)
            if not is_valid:
                logger.warning(f"Ошибка валидации для пользователя {user_id}: {error_message}")
                await processing_message.edit_text(
                    f"🤔 <b>Не удалось создать напоминание</b>\n\n<i>Причина:</i> {error_message}",
                    parse_mode='HTML'
                )
                return
            
            # Сохраняем: текст из reminder_info, а ПОЛНЫЙ пересланный — в comment (6 столбец)
            row_number = self.google_sheets.add_reminder(
                datetime_str=reminder_info.get('datetime'),
                text=reminder_info['text'],
                timezone=reminder_info.get('timezone', 'Europe/Moscow'),
                comment=forwarded_text
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
            # Извлекаем информацию о напоминании из первого сообщения
            reminder_info = self.message_processor.extract_reminder_info(first_message)
            
            if reminder_info is None:
                await processing_message.edit_text(
                    "❌ Не удалось распознать напоминание в первом сообщении.\n\n"
                    "Попробуйте указать время более четко."
                )
                return
                
            # Валидируем информацию
            is_valid, error_message = self.message_processor.validate_reminder_info(reminder_info)
            
            if not is_valid:
                await processing_message.edit_text(
                    f"🤔 <b>Не удалось создать напоминание</b>\n\n"
                    f"<i>Причина:</i> {error_message}"
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
            # Извлекаем информацию о напоминании с помощью ChatGPT
            reminder_info = self.message_processor.extract_reminder_info(user_message)
            
            if reminder_info is None:
                await processing_message.edit_text(
                    "❌ Не удалось распознать напоминание в вашем сообщении.\n\n"
                    "Попробуйте указать время более четко, например:\n"
                    "• \"Напомни мне завтра в 15:00 о встрече\"\n"
                    "• \"Купить хлеб через 2 часа\""
                )
                return
                
            # Валидируем информацию
            is_valid, error_message = self.message_processor.validate_reminder_info(reminder_info)
            
            if not is_valid:
                logger.warning(f"Ошибка валидации для пользователя {user_id}: {error_message}")
                logger.warning(f"Данные напоминания: {reminder_info}")
                await processing_message.edit_text(
                    f"🤔 <b>Не удалось создать напоминание</b>\n\n"
                    f"<i>Причина:</i> {error_message}\n\n"
                    f"💡 <b>Как правильно создать напоминание:</b>\n"
                    f"• \"Напомни мне завтра в 15:00 о встрече\"\n"
                    f"• \"Купить хлеб через 2 часа\"\n"
                    f"• \"Позвонить маме в субботу в 10 утра\"\n"
                    f"• \"Сдать отчет в пятницу до 18:00\"\n"
                    f"• \"Напомни про встречу\" (через 1 час)\n\n"
                    f"🎤 <i>Также можно отправить голосовое сообщение!</i>",
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
            
            # Извлекаем информацию о напоминании с помощью ChatGPT
            reminder_info = self.message_processor.extract_reminder_info(recognized_text)
            
            if reminder_info is None:
                await processing_message.edit_text(
                    f"❌ Не удалось распознать напоминание в тексте:\n<i>{recognized_text}</i>\n\n"
                    "Попробуйте указать время более четко, например:\n"
                    "• \"Напомни мне завтра в 15:00 о встрече\"\n"
                    "• \"Купить хлеб через 2 часа\"",
                    parse_mode='HTML'
                )
                return
                
            # Валидируем информацию
            is_valid, error_message = self.message_processor.validate_reminder_info(reminder_info)
            
            if not is_valid:
                logger.warning(f"Ошибка валидации для пользователя {user_id}: {error_message}")
                logger.warning(f"Данные напоминания: {reminder_info}")
                await processing_message.edit_text(
                    f"🤔 <b>Не удалось создать напоминание</b>\n\n"
                    f"<i>Причина:</i> {error_message}\n\n"
                    f"💡 <b>Как правильно создать напоминание:</b>\n"
                    f"• \"Напомни мне завтра в 15:00 о встрече\"\n"
                    f"• \"Купить хлеб через 2 часа\"\n"
                    f"• \"Позвонить маме в субботу в 10 утра\"\n"
                    f"• \"Сдать отчет в пятницу до 18:00\"\n"
                    f"• \"Напомни про встречу\" (через 1 час)\n\n"
                    f"🎤 <i>Также можно отправить голосовое сообщение!</i>",
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