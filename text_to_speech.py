# text_to_speech.py
# Модуль для преобразования текста в речь с помощью Google TTS (gTTS)
# Возвращает путь к сохранённому аудиофайлу

import os
import logging
from gtts import gTTS

# Настраиваем логгер для этого модуля
logger = logging.getLogger(__name__)

def text_to_speech(text: str, output_path: str = "media/voice.mp3", lang: str = 'ru') -> str:
    """
    Преобразует текст в речь с помощью Google TTS и сохраняет в MP3 файл.

    Параметры:
        text (str): Текст для озвучивания.
        output_path (str): Путь для сохранения аудиофайла (по умолчанию 'media/voice.mp3').
        lang (str): Язык озвучки (по умолчанию 'ru' — русский).

    Возвращает:
        str: Путь к созданному аудиофайлу.

    Исключения:
        Exception: Если произошла ошибка при генерации или сохранении.
    """
    try:
        # Создаём папку для файла, если она не существует (например, media)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Генерируем речь с указанным языком
        tts = gTTS(text=text, lang=lang)

        # Сохраняем в файл
        tts.save(output_path)

        logger.info(f"✅ Аудиофайл успешно создан: {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"❌ Ошибка при создании аудио: {e}")
        # Пробрасываем исключение дальше, чтобы вызывающий код мог обработать
        raise e

# ----------------------------------------------------------
# Пример использования (можно раскомментировать для теста):
# if __name__ == "__main__":
#     test_text = "Привет, это тестовая озвучка."
#     text_to_speech(test_text, "test_voice.mp3")
# ----------------------------------------------------------