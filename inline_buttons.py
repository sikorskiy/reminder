"""
Модуль для работы с inline-кнопками в Telegram боте
"""

import logging
from typing import List, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Bot
from telegram.ext import CallbackQueryHandler

logger = logging.getLogger(__name__)

class InlineButtonManager:
    def __init__(self, bot: Bot):
        """
        Инициализация менеджера inline-кнопок
        
        Args:
            bot: Экземпляр Telegram бота
        """
        self.bot = bot
    
    def create_reminder_buttons(self) -> InlineKeyboardMarkup:
        """
        Создает клавиатуру с кнопками для управления напоминанием
        
        Returns:
            InlineKeyboardMarkup с кнопками
        """
        keyboard = [
            [
                InlineKeyboardButton("❌ Отменить", callback_data="cancel_reminder"),
                InlineKeyboardButton("✅ Выполнено", callback_data="mark_done")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def create_help_buttons(self) -> InlineKeyboardMarkup:
        """
        Создает клавиатуру с кнопками справки
        
        Returns:
            InlineKeyboardMarkup с кнопками
        """
        keyboard = [
            [
                InlineKeyboardButton("❌ Отменить", callback_data="cancel_reminder"),
                InlineKeyboardButton("✅ Выполнено", callback_data="mark_done")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    async def add_buttons_to_message(self, message: Message) -> bool:
        """
        Добавляет inline-кнопки к существующему сообщению
        
        Args:
            message: Сообщение для добавления кнопок
            
        Returns:
            True если кнопки добавлены успешно
        """
        try:
            keyboard = self.create_reminder_buttons()
            
            # Редактируем сообщение, добавляя кнопки
            await self.bot.edit_message_reply_markup(
                chat_id=message.chat_id,
                message_id=message.message_id,
                reply_markup=keyboard
            )
            
            logger.info(f"Добавлены inline-кнопки к сообщению {message.message_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при добавлении inline-кнопок: {e}")
            return False
    
    def get_button_description(self, callback_data: str) -> str:
        """
        Получает описание кнопки по callback_data
        
        Args:
            callback_data: Данные callback
            
        Returns:
            Описание кнопки
        """
        descriptions = {
            "cancel_reminder": "❌ Отменить напоминание",
            "mark_done": "✅ Отметить как выполненное"
        }
        return descriptions.get(callback_data, "Неизвестная кнопка")
    
    def format_buttons_help(self) -> str:
        """
        Форматирует справку по кнопкам
        
        Returns:
            Отформатированная справка
        """
        help_text = "🎯 <b>Доступные действия:</b>\n\n"
        help_text += "❌ <b>Отменить</b> - отменить напоминание\n"
        help_text += "✅ <b>Выполнено</b> - отметить как выполненное\n\n"
        help_text += "💡 <b>Как использовать:</b>\n"
        help_text += "1. Создайте напоминание\n"
        help_text += "2. Нажмите на одну из кнопок под сообщением\n"
        help_text += "3. Бот выполнит соответствующее действие"
        
        return help_text
