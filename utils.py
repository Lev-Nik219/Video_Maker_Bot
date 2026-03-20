# utils.py
# Вспомогательные функции для проекта Telegram-бота
# Содержит функции для работы с файлами, генерации уникальных имён и очистки

import os
import shutil
import logging
import time
from datetime import datetime, timedelta

# Настраиваем логгер для этого модуля
logger = logging.getLogger(__name__)

# ----------------------------------------------------------
# Функция для создания папки, если она не существует
# ----------------------------------------------------------
def ensure_dir(directory: str) -> None:
    """
    Создаёт директорию, если она ещё не существует.
    Используется для гарантии наличия папки media, cache и других.
    """
    if not os.path.exists(directory):
        os.makedirs(directory)
        logger.info(f"Создана директория: {directory}")

# ----------------------------------------------------------
# Функция для безопасного удаления одного файла
# ----------------------------------------------------------
def safe_delete(file_path: str) -> bool:
    """
    Безопасно удаляет файл, если он существует.
    Возвращает True, если файл был удалён, иначе False.
    Логирует ошибки при удалении.
    """
    try:
        if os.path.isfile(file_path):
            os.remove(file_path)
            logger.debug(f"Файл удалён: {file_path}")
            return True
        else:
            logger.debug(f"Файл не найден для удаления: {file_path}")
            return False
    except Exception as e:
        logger.error(f"Ошибка при удалении файла {file_path}: {e}")
        return False

# ----------------------------------------------------------
# Функция для очистки старых временных файлов в папке media или cache
# ----------------------------------------------------------
def cleanup_old_files(directory: str = "media", hours: int = 24) -> int:
    """
    Удаляет все файлы в указанной директории, которые старше заданного количества часов.
    Возвращает количество удалённых файлов.
    """
    if not os.path.exists(directory):
        logger.warning(f"Директория {directory} не существует, очистка не требуется.")
        return 0

    now = time.time()
    cutoff = now - (hours * 3600)  # порог в секундах
    deleted_count = 0

    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        # Пропускаем подпапки (если есть)
        if os.path.isfile(file_path):
            # Получаем время последнего изменения файла
            file_mtime = os.path.getmtime(file_path)
            if file_mtime < cutoff:
                if safe_delete(file_path):
                    deleted_count += 1

    logger.info(f"Очистка {directory}: удалено {deleted_count} старых файлов (старше {hours} ч.)")
    return deleted_count

# ----------------------------------------------------------
# Функция для форматирования длительности в секундах в вид ММ:СС
# ----------------------------------------------------------
def format_duration(seconds: float) -> str:
    """
    Преобразует секунды в строку формата ММ:СС.
    Например: 65 -> 01:05
    """
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"

# ----------------------------------------------------------
# Функция для генерации уникального имени файла на основе времени
# ----------------------------------------------------------
def generate_unique_filename(prefix: str = "video", extension: str = ".mp4") -> str:
    """
    Создаёт уникальное имя файла на основе текущей метки времени.
    Например: video_20250301_153045.mp4
    Используется в video_fetcher.py и video_editor.py для создания уникальных имён.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}{extension}"

# ----------------------------------------------------------
# Пример использования (можно раскомментировать для теста)
# ----------------------------------------------------------
if __name__ == "__main__":
    # Настройка логирования для консоли при тестировании
    logging.basicConfig(level=logging.INFO)

    # Тест создания папки
    ensure_dir("test_folder")

    # Тест удаления файла
    test_file = "test_folder/test.txt"
    with open(test_file, "w") as f:
        f.write("test")
    safe_delete(test_file)

    # Тест очистки (создадим старый файл)
    old_file = "test_folder/old.txt"
    with open(old_file, "w") as f:
        f.write("old")
    # Установим время модификации в прошлое (10 дней назад)
    old_time = time.time() - 10 * 24 * 3600
    os.utime(old_file, (old_time, old_time))

    count = cleanup_old_files("test_folder", hours=24)
    print(f"Удалено старых файлов: {count}")

    # Тест форматирования
    print(format_duration(125))  # 02:05

    # Тест уникального имени
    print(generate_unique_filename("final", ".mp4"))

    # Удалим тестовую папку
    shutil.rmtree("test_folder")