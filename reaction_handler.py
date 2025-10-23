"""
Обработчик реакций для Telegram бота
"""

import logging
from typing import Optional, Dict, Any
from telegram import Update, Message
from telegram.ext import ContextTypes
from reactions_config import get_reaction_config, get_action_message, REACTIONS_CONFIG
from google_sheets import GoogleSheetsReminder

logger = logging.getLogger(__name__)

class ReactionHandler:
    def __init__(self, google_sheets: GoogleSheetsReminder):
        """
        Инициализация обработчика реакций
        
        Args:
            google_sheets: Экземпляр GoogleSheetsReminder для работы с данными
        """
        self.google_sheets = google_sheets
        self.user_states = {}  # Состояния пользователей
        self.last_reminders = {}  # Последние напоминания пользователей
        
    async def handle_reaction(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """
        Обрабатывает реакцию пользователя
        
        Args:
            update: Объект Update от Telegram
            context: Контекст бота
            
        Returns:
            True если реакция обработана, False если нет
        """
        try:
            # Проверяем, есть ли реакция в сообщении
            if not hasattr(update.message, 'reaction') or not update.message.reaction:
                return False
                
            reaction = update.message.reaction
            user_id = update.effective_user.id
            
            if not reaction:
                return False
                
            # Получаем первую реакцию (обычно пользователь ставит одну)
            emoji = reaction[0].emoji if reaction else None
            
            if not emoji:
                return False
                
            logger.info(f"Получена реакция {emoji} от пользователя {user_id}")
            
            # Получаем конфигурацию реакции
            reaction_config = get_reaction_config(emoji)
            if not reaction_config:
                logger.warning(f"Неизвестная реакция: {emoji} - исправляем")
                
                # Принудительно устанавливаем только разрешенные реакции
                from reaction_manager import ReactionManager
                reaction_manager = ReactionManager(context.bot)
                await reaction_manager.enforce_reactions(update.message, "reminder_management")
                
                # Отправляем сообщение пользователю о том, что реакция не поддерживается
                await update.message.reply_text(
                    f"❌ Реакция {emoji} не поддерживается.\n\n"
                    f"🎯 <b>Доступные реакции:</b>\n"
                    f"❌ <b>Отменить</b> - отменить напоминание\n"
                    f"✅ <b>Выполнено</b> - отметить как выполненное",
                    parse_mode='HTML'
                )
                return False
                
            # Выполняем действие
            action = reaction_config["action"]
            result = await self._execute_action(action, update, context, user_id)
            
            if result:
                # Отправляем подтверждение
                message = get_action_message(action)
                await update.message.reply_text(message)
                
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при обработке реакции: {e}")
            return False
    
    async def _execute_action(self, action: str, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
        """
        Выполняет конкретное действие
        
        Args:
            action: Название действия
            update: Объект Update от Telegram
            context: Контекст бота
            user_id: ID пользователя
            
        Returns:
            True если действие выполнено успешно
        """
        try:
            if action == "cancel_reminder":
                return await self._cancel_reminder(update, context, user_id)
            elif action == "mark_done":
                return await self._mark_done(update, context, user_id)
            else:
                logger.warning(f"Неизвестное действие: {action}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка при выполнении действия {action}: {e}")
            return False
    
    async def _cancel_reminder(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
        """Отмена напоминания"""
        try:
            # Получаем последнее напоминание пользователя
            last_reminder = self.last_reminders.get(user_id)
            if not last_reminder:
                await update.message.reply_text("❌ Не найдено напоминание для отмены.")
                return False
            
            # Обновляем статус в Google Sheets
            success = self.google_sheets.update_reminder_status(last_reminder['row'], 'canceled')
            
            if success:
                logger.info(f"Пользователь {user_id} отменил напоминание в строке {last_reminder['row']}")
                return True
            else:
                await update.message.reply_text("❌ Ошибка при отмене напоминания.")
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
                await update.message.reply_text("❌ Не найдено напоминание для отметки.")
                return False
            
            # Обновляем статус в Google Sheets
            success = self.google_sheets.update_reminder_status(last_reminder['row'], 'done')
            
            if success:
                logger.info(f"Пользователь {user_id} отметил напоминание как выполненное в строке {last_reminder['row']}")
                return True
            else:
                await update.message.reply_text("❌ Ошибка при отметке напоминания.")
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
