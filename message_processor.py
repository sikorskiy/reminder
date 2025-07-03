import os
import logging
import openai
from datetime import datetime
import pytz
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

class MessageProcessor:
    def __init__(self, api_key: str):
        """Инициализация процессора сообщений с OpenAI API"""
        openai.api_key = api_key
        self.client = openai.OpenAI(api_key=api_key)
        
    def extract_reminder_info(self, message: str) -> Optional[Dict]:
        """
        Извлекает информацию о напоминании из текстового сообщения с помощью ChatGPT
        
        Args:
            message: Текстовое сообщение пользователя
            
        Returns:
            Словарь с информацией о напоминании или None, если не удалось распознать
        """
        try:
            # Получаем текущую дату и время в московском часовом поясе
            moscow_tz = pytz.timezone('Europe/Moscow')
            current_time = datetime.now(moscow_tz)
            current_time_str = current_time.strftime('%Y-%m-%d %H:%M:%S')
            
            system_prompt = f"""
            Ты помощник для извлечения информации о напоминаниях из текстовых сообщений.
            
            ТЕКУЩАЯ ДАТА И ВРЕМЯ: {current_time_str} (Europe/Moscow)
            
            Проанализируй сообщение и извлеки следующую информацию:
            1. Текст напоминания (что нужно напомнить). Важно, чтобы ты писал напоминание с большой буквы, а также описывал именно суть действия, а не просто слова "напомнить что-тот там в конкретное время". Например, "Напомни мне зарегистрироваться на марафон завтра": суть напоминания это "Зарегистрироваться на марафон"
            2. Дата и время (в формате YYYY-MM-DD HH:MM:SS) - РАССЧИТЫВАЙ ОТНОСИТЕЛЬНО ТЕКУЩЕЙ ДАТЫ
            3. Часовой пояс (если указан, иначе используй Europe/Moscow)
            
            ВАЖНО: Всегда рассчитывай время относительно текущей даты {current_time_str}.
            
            Если в сообщении нет четкой информации о времени, верни null.
            
            Примеры расчетов:
            - "через 1 час" = текущее время + 1 час
            - "завтра в 15:00" = завтра в 15:00
            - "в пятницу в 14:30" = ближайшая пятница в 14:30
            - "через 30 минут" = текущее время + 30 минут
            
            ВОЗВРАЩАЙ JSON С КЛЮЧАМИ НА АНГЛИЙСКОМ:
            {{"text": "текст напоминания", "datetime": "YYYY-MM-DD HH:MM:SS", "timezone": "Europe/Moscow"}}
            
            Возвращай только JSON объект или null, если не удалось распознать напоминание.
            """
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                temperature=0.1,
                max_tokens=200
            )
            
            result = response.choices[0].message.content.strip()
            
            # Пытаемся распарсить JSON ответ
            import json
            try:
                reminder_info = json.loads(result)
                if reminder_info is None:
                    return None
                    
                # Проверяем обязательные поля
                if 'text' not in reminder_info or 'datetime' not in reminder_info:
                    logger.warning(f"Неполная информация о напоминании: {reminder_info}")
                    return None
                    
                # Добавляем часовой пояс по умолчанию, если не указан
                if 'timezone' not in reminder_info:
                    reminder_info['timezone'] = 'Europe/Moscow'
                    
                logger.info(f"Успешно извлечена информация о напоминании: {reminder_info}")
                return reminder_info
                
            except json.JSONDecodeError:
                logger.error(f"Ошибка парсинга JSON ответа: {result}")
                return None
                
        except Exception as e:
            logger.error(f"Ошибка при обработке сообщения с ChatGPT: {e}")
            return None
    
    def validate_reminder_info(self, reminder_info: Dict) -> Tuple[bool, str]:
        """
        Валидирует извлеченную информацию о напоминании
        
        Args:
            reminder_info: Словарь с информацией о напоминании
            
        Returns:
            Кортеж (is_valid, error_message)
        """
        try:
            # Проверяем наличие обязательных полей
            if 'text' not in reminder_info:
                return False, "Отсутствует текст напоминания"
            if 'datetime' not in reminder_info:
                return False, "Отсутствует дата и время"
                
            # Проверяем формат даты
            datetime_str = reminder_info['datetime']
            try:
                dt = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
                # Проверяем, что время не в прошлом
                if dt < datetime.now():
                    return False, "Время напоминания не может быть в прошлом"
            except ValueError:
                return False, "Неверный формат даты и времени"
                
            # Проверяем часовой пояс
            if 'timezone' in reminder_info:
                try:
                    pytz.timezone(reminder_info['timezone'])
                except pytz.exceptions.UnknownTimeZoneError:
                    return False, f"Неизвестный часовой пояс: {reminder_info['timezone']}"
                    
            return True, ""
            
        except Exception as e:
            return False, f"Ошибка валидации: {str(e)}" 