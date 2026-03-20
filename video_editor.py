# video_editor.py
# Модуль для склейки видео и аудио с возможностью добавления фоновой музыки

import os
import logging
import time
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy import concatenate_videoclips
from moviepy.audio.AudioClip import CompositeAudioClip, concatenate_audioclips
from utils import generate_unique_filename

logger = logging.getLogger(__name__)

def mix_audio_files(primary_audio_path: str, background_audio_path: str, output_path: str, bg_volume: float = 0.3) -> str:
    """
    Смешивает два аудиофайла: основное (голос) и фоновое (музыка).
    Автоматически подбирает подходящий метод изменения громкости для вашей версии moviepy.
    """
    primary = AudioFileClip(primary_audio_path)
    background = AudioFileClip(background_audio_path)
    
    # Подгоняем длительность фона под основную дорожку
    if background.duration > primary.duration:
        background = background.subclipped(0, primary.duration)
    else:
        n_repeats = int(primary.duration // background.duration) + 1
        background = concatenate_audioclips([background] * n_repeats)
        background = background.subclipped(0, primary.duration)

    # Устанавливаем громкость фона (пробуем разные методы для совместимости)
    try:
        background = background.volumex(bg_volume)
    except AttributeError:
        try:
            background = background.with_volume_scaled(bg_volume)
        except AttributeError:
            background = background.multiply_volume(bg_volume)

    final_audio = CompositeAudioClip([primary, background])
    final_audio.write_audiofile(output_path, codec='libmp3lame')
    
    # Закрываем клипы и даём время на освобождение файлов
    primary.close()
    background.close()
    final_audio.close()
    time.sleep(0.1)
    
    return output_path

def create_video_with_audio(
    video_paths: list,
    audio_path: str,
    output_path: str = None,
    target_size: tuple = (1080, 1920)
) -> str:
    """
    Склеивает несколько видео в одно, накладывает аудио и возвращает путь к итоговому файлу.
    Видео обрезаются/повторяются так, чтобы суммарная длительность равнялась длительности аудио.
    Итоговое видео приводится к вертикальному формату (1080x1920 по умолчанию).
    """
    if output_path is None:
        output_path = os.path.join("media", generate_unique_filename("final", ".mp4"))
    else:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

    audio_clip = None
    video_clips = []
    final_video = None

    try:
        logger.info(f"Загрузка аудио: {audio_path}")
        audio_clip = AudioFileClip(audio_path)
        audio_duration = audio_clip.duration
        logger.info(f"Длительность аудио: {audio_duration:.2f} сек")

        logger.info(f"Загрузка {len(video_paths)} видео...")
        for path in video_paths:
            if not os.path.exists(path):
                logger.warning(f"Файл не найден: {path}, пропускаем")
                continue
            clip = VideoFileClip(path)
            video_clips.append(clip)
            logger.debug(f"Загружено видео: {path}, длительность {clip.duration:.2f} сек")

        if not video_clips:
            raise ValueError("Нет доступных видео для обработки")

        total_video_duration = sum(clip.duration for clip in video_clips)
        logger.info(f"Суммарная длительность видео: {total_video_duration:.2f} сек")

        if total_video_duration < audio_duration:
            logger.info("Видео короче аудио, выполняем зацикливание...")
            repeated = []
            current = 0
            while current < audio_duration:
                for clip in video_clips:
                    repeated.append(clip)
                    current += clip.duration
                    if current >= audio_duration:
                        break
            final_video = concatenate_videoclips(repeated)
        else:
            logger.info("Видео длиннее аудио, выполняем обрезку...")
            final_parts = []
            remaining = audio_duration
            for clip in video_clips:
                if remaining <= 0:
                    break
                if clip.duration <= remaining:
                    final_parts.append(clip)
                    remaining -= clip.duration
                else:
                    final_parts.append(clip.subclipped(0, remaining))
                    remaining = 0
            final_video = concatenate_videoclips(final_parts)

        final_video = final_video.with_audio(audio_clip)
        logger.info(f"Изменение размера видео до {target_size[0]}x{target_size[1]}...")
        final_video = final_video.resized(target_size)

        logger.info(f"Сохранение видео в {output_path}...")
        final_video.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            fps=24,
            threads=2,
            preset='medium',
            logger=None
        )
        logger.info(f"Видео успешно сохранено: {output_path}")
        return output_path

    except Exception as e:
        logger.exception(f"Ошибка при создании видео: {e}")
        raise e

    finally:
        # Освобождаем ресурсы
        if audio_clip:
            audio_clip.close()
        for clip in video_clips:
            clip.close()
        if final_video:
            final_video.close()
        logger.debug("Ресурсы moviepy освобождены")
        time.sleep(0.1)  # даём ОС время на освобождение файлов