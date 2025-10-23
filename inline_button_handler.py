"""
Обработчик inline-кнопок для Telegram бота
"""

import logging
from typing import Optional, Dict, Any
from telegram import Update, CallbackQuery
from telegram.ext import ContextTypes
from google_sheets import GoogleSheetsReminder

logger = logging.getLogger(__name__)

class InlineButtonHandler:
    def __init__(self, google_sheets: GoogleSheetsReminder):
        """
        Инициализация обработчика inline-кнопок
        
        Args:
            google_sheets: Экземпляр GoogleSheetsReminder для работы с данными
        """
        self.google_sheets = google_sheets
        self.user_states = {}  # Состояния пользователей
        self.last_reminders = {}  # Последние напоминания пользователей
        
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """
        Обрабатывает нажатие на inline-кнопку
        
        Args:
            update: Объект Update от Telegram
            context: Контекст бота
            
        Returns:
            True если callback обработан, False если нет
        """
        try:
            query = update.callback_query
            user_id = update.effective_user.id
            callback_data = query.data
            
            logger.info(f"Получен callback от пользователя {user_id}: {callback_data}")
            
            # Подтверждаем получение callback
            await query.answer()
            
            # Выполняем действие в зависимости от callback_data
            if callback_data == "cancel_reminder":
                result = await self._cancel_reminder(update, context, user_id)
            elif callback_data == "mark_done":
                result = await self._mark_done(update, context, user_id)
            else:
                logger.warning(f"Неизвестный callback_data: {callback_data}")
                await query.edit_message_text("❌ Неизвестное действие.")
                return False
            
            if result:
                # Обновляем текст сообщения с результатом
                if callback_data == "cancel_reminder":
                    await query.edit_message_text(
                        query.message.text + "\n\n❌ <b>Напоминание отменено.</b>",
                        parse_mode='HTML'
                    )
                elif callback_data == "mark_done":
                    await query.edit_message_text(
                        query.message.text + "\n\n✅ <b>Напоминание отмечено как выполненное.</b>",
                        parse_mode='HTML'
                    )
                
                # Убираем кнопки после выполнения действия
                await query.edit_message_reply_markup(reply_markup=None)
                
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при обработке callback: {e}")
            await query.answer("❌ Произошла ошибка при обработке действия.")
            return False
    
    async def _cancel_reminder(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
        """Отмена напоминания"""
        try:
            # Получаем последнее напоминание пользователя
            last_reminder = self.last_reminders.get(user_id)
            if not last_reminder:
                await update.callback_query.edit_message_text(
                    update.callback_query.message.text + "\n\n❌ <b>Не найдено напоминание для отмены.</b>",
                    parse_mode='HTML'
                )
                return False
            
            # Обновляем статус в Google Sheets
            success = self.google_sheets.update_reminder_status(last_reminder['row'], 'canceled')
            
            if success:
                logger.info(f"Пользователь {user_id} отменил напоминание в строке {last_reminder['row']}")
                return True
            else:
                await update.callback_query.edit_message_text(
                    update.callback_query.message.text + "\n\n❌ <b>Ошибка при отмене напоминания.</b>",
                    parse_mode='HTML'
                )
                return False
                
        except Exception as e:
            logger.error(f"Ошибка при отмене напоминания: {e}")
            return False
    
    async def _mark_done(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
        """Отметить как выполненное"""
        try:
            # Получаем последнее напоминание пользователя
            last_reminder = self.last_reminders.get(user_id)
            if not last_reminder:
                await update.callback_query.edit_message_text(
                    update.callback_query.message.text + "\n\n❌ <b>Не найдено напоминание для отметки.</b>",
                    parse_mode='HTML'
                )
                return False
            
            # Обновляем статус в Google Sheets
            success = self.google_sheets.update_reminder_status(last_reminder['row'], 'done')
            
            if success:
                logger.info(f"Пользователь {user_id} отметил напоминание как выполненное в строке {last_reminder['row']}")
                return True
            else:
                await update.callback_query.edit_message_text(
                    update.callback_query.message.text + "\n\n❌ <b>Ошибка при отметке напоминания.</b>",
                    parse_mode='HTML'
                )
                return False
                
        except Exception as e:
            logger.error(f"Ошибка при отметке напоминания: {e}")
            return False
    
    def get_user_state(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получить состояние пользователя"""
        return self.user_states.get(user_id)
    
    def set_user_state(self, user_id: int, state: Dict[str, Any]) -> None:
        """Установить состояние пользователя"""
        self.user_states[user_id] = state
    
    def clear_user_state(self, user_id: int) -> None:
        """Очистить состояние пользователя"""
        if user_id in self.user_states:
            del self.user_states[user_id]
    
    def set_last_reminder(self, user_id: int, reminder_data: dict) -> None:
        """
        Сохраняет последнее напоминание пользователя
        
        Args:
            user_id: ID пользователя
            reminder_data: Данные напоминания с номером строки
        """
        self.last_reminders[user_id] = reminder_data
        logger.info(f"Сохранено последнее напоминание для пользователя {user_id}: строка {reminder_data.get('row')}")
    
    def get_last_reminder(self, user_id: int) -> Optional[dict]:
        """
        Получает последнее напоминание пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Данные последнего напоминания или None
        """
        return self.last_reminders.get(user_id)
