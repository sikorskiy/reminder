"""
Конфигурация реакций для Telegram бота
"""

# Доступные реакции и их логика
REACTIONS_CONFIG = {
    "❌": {
        "name": "Отменить", 
        "description": "Отменить напоминание",
        "action": "cancel_reminder",
        "emoji": "❌"
    },
    "✅": {
        "name": "Выполнено",
        "description": "Отметить как выполненное",
        "action": "mark_done",
        "emoji": "✅"
    }
}

# Реакции для разных состояний
REACTION_SETS = {
    "reminder_confirmation": ["❌", "✅"],  # Подтверждение напоминания
    "reminder_management": ["❌", "✅"],  # Управление напоминанием
    "main_menu": ["❌", "✅"],  # Главное меню
    "list_view": ["❌", "✅"]  # Просмотр списка
}

# Сообщения для разных действий
ACTION_MESSAGES = {
    "cancel_reminder": "❌ Напоминание отменено.",
    "mark_done": "✅ Напоминание отмечено как выполненное."
}

def get_reactions_for_state(state: str) -> list:
    """Получить список реакций для определенного состояния"""
    return REACTION_SETS.get(state, [])

def get_reaction_config(emoji: str) -> dict:
    """Получить конфигурацию реакции по эмодзи"""
    return REACTIONS_CONFIG.get(emoji, {})

def get_action_message(action: str) -> str:
    """Получить сообщение для действия"""
    return ACTION_MESSAGES.get(action, "Действие выполнено.")
