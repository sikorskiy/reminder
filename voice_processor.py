import os
import logging
import tempfile
import requests
from typing import Optional
import openai
from telegram import Update

try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    logging.warning("pydub не установлен. Голосовые сообщения не будут поддерживаться.")

logger = logging.getLogger(__name__)

class VoiceProcessor:
    def __init__(self, openai_api_key: str):
        """
        Инициализация процессора голосовых сообщений
        
        Args:
            openai_api_key: API ключ OpenAI для Whisper
        """
        self.openai_api_key = openai_api_key
        self.client = openai.OpenAI(api_key=openai_api_key)
        
    async def process_voice_message(self, update: Update, context) -> Optional[str]:
        """
        Обрабатывает голосовое сообщение и возвращает распознанный текст
        
        Args:
            update: Объект Update от Telegram
            context: Контекст бота
            
        Returns:
            Распознанный текст или None в случае ошибки
        """
        try:
            voice = update.message.voice
            
            # Получаем информацию о файле
            file_info = await context.bot.get_file(voice.file_id)
            file_url = file_info.file_path
            
            logger.info(f"Обрабатываем голосовое сообщение: {voice.file_id}")
            
            # Скачиваем файл
            audio_data = await self._download_audio(file_url)
            if not audio_data:
                return None
                
            # Конвертируем в нужный формат
            audio_file = await self._convert_audio(audio_data)
            if not audio_file:
                return None
                
            # Распознаем речь с помощью Whisper
            text = await self._transcribe_audio(audio_file)
            
            # Очищаем временные файлы
            if audio_file and os.path.exists(audio_file):
                os.remove(audio_file)
                
            return text
            
        except Exception as e:
            logger.error(f"Ошибка при обработке голосового сообщения: {e}")
            return None
    
    async def _download_audio(self, file_url: str) -> Optional[bytes]:
        """Скачивает аудиофайл по URL"""
        try:
            response = requests.get(file_url, timeout=30)
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error(f"Ошибка при скачивании аудио: {e}")
            return None
    
    async def _convert_audio(self, audio_data: bytes) -> Optional[str]:
        """
        Конвертирует аудио в формат, поддерживаемый Whisper (MP3)
        """
        if not PYDUB_AVAILABLE:
            logger.error("pydub не доступен для конвертации аудио")
            return None
            
        try:
            # Создаем временный файл для исходного аудио
            with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as temp_input:
                temp_input.write(audio_data)
                temp_input_path = temp_input.name
            
            # Создаем временный файл для конвертированного аудио
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_output:
                temp_output_path = temp_output.name
            
            # Конвертируем OGG в MP3
            audio = AudioSegment.from_ogg(temp_input_path)
            audio.export(temp_output_path, format="mp3")
            
            # Удаляем временный входной файл
            os.remove(temp_input_path)
            
            return temp_output_path
            
        except Exception as e:
            logger.error(f"Ошибка при конвертации аудио: {e}")
            # Очищаем временные файлы в случае ошибки
            try:
                if 'temp_input_path' in locals() and os.path.exists(temp_input_path):
                    os.remove(temp_input_path)
                if 'temp_output_path' in locals() and os.path.exists(temp_output_path):
                    os.remove(temp_output_path)
            except:
                pass
            return None
    
    async def _transcribe_audio(self, audio_file_path: str) -> Optional[str]:
        """
        Распознает речь в аудиофайле с помощью OpenAI Whisper
        """
        try:
            with open(audio_file_path, 'rb') as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="ru"  # Указываем русский язык для лучшего распознавания
                )
            
            text = transcript.text.strip()
            logger.info(f"Распознанный текст: {text}")
            return text
            
        except Exception as e:
            logger.error(f"Ошибка при распознавании речи: {e}")
            return None
