"""
Утилиты для работы с реакциями в Telegram боте
"""

import logging
from typing import List, Optional
from telegram import Message, Bot
from reactions_config import get_reactions_for_state, REACTIONS_CONFIG

logger = logging.getLogger(__name__)

class ReactionManager:
    def __init__(self, bot: Bot):
        """
        Инициализация менеджера реакций
        
        Args:
            bot: Экземпляр Telegram бота
        """
        self.bot = bot
    
    async def add_reactions_to_message(self, message: Message, state: str) -> bool:
        """
        Добавляет реакции к сообщению
        
        Args:
            message: Сообщение для добавления реакций
            state: Состояние для определения набора реакций
            
        Returns:
            True если реакции добавлены успешно
        """
        try:
            reactions = get_reactions_for_state(state)
            if not reactions:
                logger.warning(f"Нет реакций для состояния: {state}")
                return False
            
            # Добавляем реакции к сообщению с ограничениями
            await self.bot.set_message_reaction(
                chat_id=message.chat_id,
                message_id=message.message_id,
                reaction=[{"type": "emoji", "emoji": emoji} for emoji in reactions],
                is_big=False,  # Обычный размер реакций
                allow_multiple_reactions=False  # Запретить множественные реакции
            )
            
            logger.info(f"Добавлены реакции {reactions} к сообщению {message.message_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при добавлении реакций: {e}")
            return False
    
    async def add_custom_reactions(self, message: Message, reactions: List[str]) -> bool:
        """
        Добавляет пользовательские реакции к сообщению
        
        Args:
            message: Сообщение для добавления реакций
            reactions: Список эмодзи для реакций
            
        Returns:
            True если реакции добавлены успешно
        """
        try:
            # Проверяем, что все реакции существуют в конфигурации
            valid_reactions = [r for r in reactions if r in REACTIONS_CONFIG]
            
            if not valid_reactions:
                logger.warning(f"Нет валидных реакций в списке: {reactions}")
                return False
            
            # Добавляем реакции к сообщению с ограничениями
            await self.bot.set_message_reaction(
                chat_id=message.chat_id,
                message_id=message.message_id,
                reaction=[{"type": "emoji", "emoji": emoji} for emoji in valid_reactions],
                is_big=False,  # Обычный размер реакций
                allow_multiple_reactions=False  # Запретить множественные реакции
            )
            
            logger.info(f"Добавлены пользовательские реакции {valid_reactions} к сообщению {message.message_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при добавлении пользовательских реакций: {e}")
            return False
    
    async def remove_reactions_from_message(self, message: Message) -> bool:
        """
        Удаляет все реакции с сообщения
        
        Args:
            message: Сообщение для удаления реакций
            
        Returns:
            True если реакции удалены успешно
        """
        try:
            await self.bot.set_message_reaction(
                chat_id=message.chat_id,
                message_id=message.message_id,
                reaction=[]
            )
            
            logger.info(f"Удалены реакции с сообщения {message.message_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при удалении реакций: {e}")
            return False
    
    async def enforce_reactions(self, message: Message, state: str) -> bool:
        """
        Принудительно устанавливает только разрешенные реакции на сообщении
        
        Args:
            message: Сообщение для установки реакций
            state: Состояние для определения набора реакций
            
        Returns:
            True если реакции установлены успешно
        """
        try:
            reactions = get_reactions_for_state(state)
            if not reactions:
                logger.warning(f"Нет реакций для состояния: {state}")
                return False
            
            # Принудительно устанавливаем только разрешенные реакции
            await self.bot.set_message_reaction(
                chat_id=message.chat_id,
                message_id=message.message_id,
                reaction=[{"type": "emoji", "emoji": emoji} for emoji in reactions],
                is_big=False,
                allow_multiple_reactions=False
            )
            
            logger.info(f"Принудительно установлены реакции {reactions} на сообщение {message.message_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при принудительной установке реакций: {e}")
            return False
    
    def get_reaction_description(self, emoji: str) -> str:
        """
        Получает описание реакции
        
        Args:
            emoji: Эмодзи реакции
            
        Returns:
            Описание реакции или пустую строку
        """
        reaction_config = REACTIONS_CONFIG.get(emoji, {})
        return reaction_config.get("description", "")
    
    def format_reactions_help(self, state: str) -> str:
        """
        Форматирует справку по реакциям для состояния
        
        Args:
            state: Состояние
            
        Returns:
            Отформатированная справка
        """
        reactions = get_reactions_for_state(state)
        if not reactions:
            return ""
        
        help_text = "🎯 <b>Доступные реакции:</b>\n\n"
        for emoji in reactions:
            config = REACTIONS_CONFIG.get(emoji, {})
            name = config.get("name", "")
            description = config.get("description", "")
            help_text += f"{emoji} <b>{name}</b> - {description}\n"
        
        return help_text
