# text_to_speech_silero.py
# Модуль для локальной озвучки через Silero TTS
# Используется голос 'kseniya' (женский, более мягкий и приятный)

import os
import logging
import subprocess
from silero_tts.silero_tts import SileroTTS

logger = logging.getLogger(__name__)

# Глобальная переменная для модели (загружается один раз)
_tts = None

def get_tts_model(language: str = "ru", speaker: str = "kseniya"):
    """
    Загружает модель Silero при первом вызове и возвращает объект.
    Можно менять спикера динамически.
    """
    global _tts
    if _tts is None:
        logger.info("Загрузка модели Silero TTS (это может занять некоторое время)...")
        _tts = SileroTTS(
            model_id='v4_ru',      # последняя русская модель
            language=language,
            speaker=speaker,
            sample_rate=48000,
            device='cpu'           # можно 'cuda' для GPU
        )
        logger.info("Модель успешно загружена")
    return _tts

def convert_wav_to_mp3(wav_path: str, mp3_path: str = None) -> str:
    """
    Конвертирует WAV в MP3 с помощью FFmpeg.
    Если mp3_path не указан, заменяет расширение на .mp3.
    Возвращает путь к MP3.
    """
    if mp3_path is None:
        mp3_path = wav_path.replace('.wav', '.mp3')
    
    # Проверяем, есть ли FFmpeg
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.warning("FFmpeg не найден, оставляем WAV файл")
        return wav_path

    # Конвертация с хорошим качеством
    cmd = [
        'ffmpeg', '-i', wav_path,
        '-codec:a', 'libmp3lame',
        '-qscale:a', '2',      # качество от 0 (лучшее) до 9 (худшее)
        mp3_path,
        '-y'                   # перезаписывать без подтверждения
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            # Удаляем исходный WAV
            os.remove(wav_path)
            logger.info(f"Конвертировано в MP3: {mp3_path}")
            return mp3_path
        else:
            logger.error(f"Ошибка FFmpeg: {result.stderr}")
            return wav_path
    except Exception as e:
        logger.error(f"Ошибка при конвертации: {e}")
        return wav_path

def text_to_speech(
    text: str,
    output_path: str = "media/voice.mp3",
    language: str = "ru",
    speaker: str = "kseniya",        # изменён на более приятный голос
    sample_rate: int = 48000
) -> str:
    """
    Преобразует текст в речь локально через Silero TTS.
    Возвращает путь к аудиофайлу (MP3, если удалось сконвертировать, иначе WAV).
    
    Доступные русские спикеры: 'xenia', 'baya', 'kseniya', 'random'.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Для Silero лучше временно сохранить в WAV, потом конвертировать
    wav_path = output_path.replace('.mp3', '.wav') if output_path.endswith('.mp3') else output_path + '.wav'

    try:
        tts = get_tts_model(language, speaker)
        
        # Если спикер изменился, переключаем
        if tts.speaker != speaker:
            tts.change_speaker(speaker)
        
        logger.info(f"Синтез речи через Silero (спикер: {speaker})...")
        
        # Вызов без параметра speed (скорость регулируем количеством фактов)
        tts.tts(text, wav_path)
        
        logger.info(f"Аудио сохранено во временный WAV: {wav_path}")
        
        # Если просили MP3, конвертируем
        if output_path.endswith('.mp3'):
            final_path = convert_wav_to_mp3(wav_path, output_path)
            logger.info(f"✅ Готово: {final_path}")
            return final_path
        else:
            # Оставляем как WAV
            logger.info(f"✅ Готово: {wav_path}")
            return wav_path

    except Exception as e:
        logger.error(f"❌ Ошибка при синтезе Silero: {e}")
        raise e

# ----------------------------------------------------------
# Тестовый блок для прослушивания голосов (можно запустить напрямую)
# ----------------------------------------------------------
if __name__ == "__main__":
    # Настройка логирования для консоли
    logging.basicConfig(level=logging.INFO)
    test_text = "Привет! Это тестовое сообщение. Как вам этот голос?"
    for s in ["xenia", "baya", "kseniya"]:
        print(f"\nГенерирую голос: {s}")
        text_to_speech(test_text, f"test_{s}.mp3", speaker=s)
        print(f"Создан файл test_{s}.mp3")
    print("\nВсе тестовые файлы созданы. Прослушайте и выберите лучший голос.")