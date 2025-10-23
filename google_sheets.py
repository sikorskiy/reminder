import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

class GoogleSheetsReminder:
    def __init__(self, creds_path, spreadsheet_name, worksheet_name='reminders'):
        creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
        self.gc = gspread.authorize(creds)
        self.sh = self.gc.open(spreadsheet_name)
        self.ws = self.sh.worksheet(worksheet_name)

    def get_reminders(self):
        """Возвращает список напоминаний (словарей) из таблицы, где sent не True."""
        records = self.ws.get_all_records()
        reminders = []
        for i, row in enumerate(records, start=2):  # первая строка — заголовки
            if not str(row.get('sent', '')).strip().lower() == 'true':
                reminders.append({
                    'row': i,  # для отметки об отправке
                    'datetime': row['datetime'],
                    'text': row['text'],
                    'timezone': row.get('timezone', ''),
                    'comment': row.get('comment', ''),  # комментарий (пересланное сообщение)
                })
        return reminders

    def mark_as_sent(self, row):
        """Отмечает напоминание как отправленное по номеру строки."""
        self.ws.update_cell(row, 4, 'TRUE')  # 4 — номер колонки 'sent'
    
    def update_reminder_status(self, row, status):
        """
        Обновляет статус напоминания в пятом столбце
        
        Args:
            row: Номер строки в таблице
            status: Новый статус ('done' или 'canceled')
            
        Returns:
            bool: True если успешно обновлено, False в случае ошибки
        """
        try:
            # Обновляем пятый столбец (колонка 5)
            self.ws.update_cell(row, 5, status)
            return True
        except Exception as e:
            print(f"Ошибка при обновлении статуса напоминания: {e}")
            return False
    
    def get_reminder_by_row(self, row):
        """
        Получает напоминание по номеру строки
        
        Args:
            row: Номер строки в таблице
            
        Returns:
            dict: Данные напоминания или None если не найдено
        """
        try:
            # Получаем все значения строки
            row_values = self.ws.row_values(row)
            if len(row_values) >= 4:
                return {
                    'row': row,
                    'datetime': row_values[0],
                    'text': row_values[1],
                    'timezone': row_values[2],
                    'sent': row_values[3] if len(row_values) > 3 else '',
                    'status': row_values[4] if len(row_values) > 4 else '',
                    'comment': row_values[5] if len(row_values) > 5 else ''
                }
            return None
        except Exception as e:
            print(f"Ошибка при получении напоминания: {e}")
            return None
        
    def add_reminder(self, datetime_str: str = None, text: str = None, timezone: str = 'Europe/Moscow', comment: str = ''):
        """
        Добавляет новое напоминание в таблицу
        
        Args:
            datetime_str: Дата и время в формате YYYY-MM-DD HH:MM:SS (может быть None для напоминаний без времени)
            text: Текст напоминания
            timezone: Часовой пояс (по умолчанию Europe/Moscow)
            comment: Комментарий (пересланное сообщение)
            
        Returns:
            int: Номер строки если успешно добавлено, None в случае ошибки
        """
        try:
            # Добавляем новую строку в конец таблицы
            # Структура: datetime, text, timezone, sent, status, comment
            # Если datetime_str None, сохраняем пустую строку
            datetime_value = datetime_str if datetime_str is not None else ''
            new_row = [datetime_value, text, timezone, 'FALSE', '', comment]
            print(f"Добавляем строку в Google Sheets: {new_row}")
            self.ws.append_row(new_row)
            
            # Получаем номер последней добавленной строки
            all_values = self.ws.get_all_values()
            row_number = len(all_values)
            
            return row_number
        except Exception as e:
            print(f"Ошибка при добавлении напоминания: {e}")
            return None
    
    def update_reminder_comment(self, row, comment):
        """
        Обновляет комментарий напоминания в шестом столбце
        
        Args:
            row: Номер строки в таблице
            comment: Новый комментарий
            
        Returns:
            bool: True если успешно обновлено, False в случае ошибки
        """
        try:
            # Обновляем шестой столбец (колонка 6)
            self.ws.update_cell(row, 6, comment)
            return True
        except Exception as e:
            print(f"Ошибка при обновлении комментария напоминания: {e}")
            return False 