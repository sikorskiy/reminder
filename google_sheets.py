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
                })
        return reminders

    def mark_as_sent(self, row):
        """Отмечает напоминание как отправленное по номеру строки."""
        self.ws.update_cell(row, 4, 'TRUE')  # 4 — номер колонки 'sent'
        
    def add_reminder(self, datetime_str: str, text: str, timezone: str = 'Europe/Moscow'):
        """
        Добавляет новое напоминание в таблицу
        
        Args:
            datetime_str: Дата и время в формате YYYY-MM-DD HH:MM:SS
            text: Текст напоминания
            timezone: Часовой пояс (по умолчанию Europe/Moscow)
            
        Returns:
            bool: True если успешно добавлено, False в случае ошибки
        """
        try:
            # Добавляем новую строку в конец таблицы
            new_row = [datetime_str, text, timezone, 'FALSE']  # FALSE означает "не отправлено"
            self.ws.append_row(new_row)
            return True
        except Exception as e:
            print(f"Ошибка при добавлении напоминания: {e}")
            return False 