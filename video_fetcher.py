# video_fetcher.py
# Модуль для поиска и скачивания фоновых видео с Pexels и Pixabay
# Поддерживает кэширование и случайное смешивание видео из обоих источников

import os
import logging
import random
import hashlib
import shutil
import requests
import yt_dlp
from config import PEXELS_API_KEY, PIXABAY_API_KEY
from utils import generate_unique_filename

logger = logging.getLogger(__name__)

# ----------------------------------------------------------
# Настройки кэша
# ----------------------------------------------------------
CACHE_DIR = "cache"

def _get_cache_path(url: str) -> str:
    """Возвращает путь к файлу в кэше для заданного URL (по хэшу MD5)."""
    url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
    return os.path.join(CACHE_DIR, f"{url_hash}.mp4")

def _get_from_cache(url: str) -> str | None:
    """Проверяет наличие файла в кэше, возвращает путь или None."""
    cache_path = _get_cache_path(url)
    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
        logger.debug(f"Видео найдено в кэше: {cache_path}")
        return cache_path
    return None

def _save_to_cache(url: str, file_path: str) -> str:
    """Копирует файл в кэш, возвращает путь кэша."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_path = _get_cache_path(url)
    shutil.copy2(file_path, cache_path)
    logger.info(f"Видео сохранено в кэш: {cache_path}")
    return cache_path

# ----------------------------------------------------------
# Функции для работы с Pexels API
# ----------------------------------------------------------
def search_pexels_videos(query: str, per_page: int = 5) -> list:
    """Ищет видео на Pexels, возвращает список прямых ссылок на файлы."""
    url = "https://api.pexels.com/videos/search"
    headers = {"Authorization": PEXELS_API_KEY}
    params = {
        "query": query,
        "per_page": per_page,
        "orientation": "portrait"
    }
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code != 200:
            logger.error(f"Pexels API ошибка {response.status_code}: {response.text}")
            return []
        data = response.json()
        videos_data = data.get("videos", [])
        urls = []
        for video in videos_data:
            files = video.get("video_files", [])
            best = None
            for f in files:
                if f.get("quality") == "hd":
                    best = f
                    break
            if not best and files:
                best = files[0]
            if best:
                link = best.get("link")
                if link:
                    urls.append(link)
        return urls
    except Exception as e:
        logger.exception(f"Ошибка при поиске на Pexels: {e}")
        return []

# ----------------------------------------------------------
# Функции для работы с Pixabay API
# ----------------------------------------------------------
def search_pixabay_videos(query: str, per_page: int = 5) -> list:
    """
    Ищет видео на Pixabay, возвращает список прямых ссылок на файлы.
    Выбирает видео с качеством 'large' или 'medium'.
    """
    url = "https://pixabay.com/api/videos/"
    params = {
        "key": PIXABAY_API_KEY,
        "q": query,
        "per_page": per_page,
        "safesearch": "true",
        "orientation": "vertical"  # вертикальные видео
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            logger.error(f"Pixabay API ошибка {response.status_code}: {response.text}")
            return []
        data = response.json()
        hits = data.get("hits", [])
        urls = []
        for hit in hits:
            videos = hit.get("videos", {})
            # Выбираем лучшее доступное качество: large > medium > small
            if "large" in videos:
                file_url = videos["large"]["url"]
            elif "medium" in videos:
                file_url = videos["medium"]["url"]
            elif "small" in videos:
                file_url = videos["small"]["url"]
            else:
                continue
            if file_url:
                urls.append(file_url)
        return urls
    except Exception as e:
        logger.exception(f"Ошибка при поиске на Pixabay: {e}")
        return []

# ----------------------------------------------------------
# Общая функция поиска видео из обоих источников
# ----------------------------------------------------------
def search_videos_from_all(query: str, per_source: int = 5) -> list:
    """
    Собирает видео из Pexels и Pixabay по одному запросу,
    возвращает общий перемешанный список ссылок.
    """
    pexels_urls = search_pexels_videos(query, per_source)
    pixabay_urls = search_pixabay_videos(query, per_source)
    all_urls = pexels_urls + pixabay_urls
    random.shuffle(all_urls)
    logger.info(f"Всего собрано {len(all_urls)} ссылок (Pexels: {len(pexels_urls)}, Pixabay: {len(pixabay_urls)})")
    return all_urls

# ----------------------------------------------------------
# Скачивание видео с использованием кэша
# ----------------------------------------------------------
def download_video(url: str, save_path: str) -> str:
    """Скачивает видео через yt-dlp или берёт из кэша."""
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)

    cached = _get_from_cache(url)
    if cached:
        shutil.copy2(cached, save_path)
        return save_path

    logger.info(f"Скачивание видео (новое): {url}")
    ydl_opts = {
        'outtmpl': save_path,
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'http_headers': {'Referer': 'https://www.pexels.com/'}  # для Pexels; Pixabay обычно не требует
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        if os.path.exists(save_path):
            file_size = os.path.getsize(save_path) / (1024 * 1024)
            logger.info(f"Скачано: {save_path} ({file_size:.2f} МБ)")
            _save_to_cache(url, save_path)
            return save_path
        else:
            raise Exception("Файл не создан после скачивания")
    except Exception as e:
        logger.error(f"Ошибка скачивания {url}: {e}")
        raise

# ----------------------------------------------------------
# Основная функция для получения видео по теме
# ----------------------------------------------------------
def fetch_videos_for_theme(theme: str, count: int = 3) -> list:
    """
    Возвращает список путей к скачанным видео для заданной темы.
    Видео собираются из Pexels и Pixabay по расширенным ключевым словам.
    """
    # Ключевые слова для разных тем (можно расширять)
    keywords = {
        "ai": ["artificial intelligence", "robot", "technology", "future", "computer",
               "tech", "ai", "machine learning", "neural network", "cyberpunk"],
        "motivation": ["sport", "gym", "workout", "success", "motivation", "fitness",
                       "running", "training", "exercise", "discipline"],
        "trends": ["russia", "news", "people", "city", "crowd", "street", "moscow",
                   "urban", "festival", "event", "celebration"],
    }
    fallback_keywords = ["nature", "background", "video", "landscape"]

    kw_list = keywords.get(theme, fallback_keywords)
    random.shuffle(kw_list)

    downloaded = []
    for keyword in kw_list:
        if len(downloaded) >= count:
            break
        logger.info(f"Поиск видео по ключевому слову: '{keyword}'")
        urls = search_videos_from_all(keyword, per_source=count * 2)
        random.shuffle(urls)
        for url in urls:
            if len(downloaded) >= count:
                break
            save_path = os.path.join("media", generate_unique_filename(f"video_{theme}", ".mp4"))
            try:
                download_video(url, save_path)
                downloaded.append(save_path)
            except Exception as e:
                logger.warning(f"Не удалось скачать {url}: {e}")
                continue

    if not downloaded:
        logger.warning("Не удалось найти видео, пробуем fallback ключевые слова...")
        for keyword in fallback_keywords:
            urls = search_videos_from_all(keyword, per_source=count)
            random.shuffle(urls)
            for url in urls:
                save_path = os.path.join("media", generate_unique_filename(f"fallback_{theme}", ".mp4"))
                try:
                    download_video(url, save_path)
                    downloaded.append(save_path)
                    if len(downloaded) >= count:
                        break
                except:
                    continue
            if downloaded:
                break

    logger.info(f"Итого скачано {len(downloaded)} видео для темы '{theme}'")
    return downloaded

# ----------------------------------------------------------
# Проверка доступности API (опционально)
# ----------------------------------------------------------
def check_pexels_api() -> bool:
    try:
        return len(search_pexels_videos("test", 1)) > 0
    except:
        return False

def check_pixabay_api() -> bool:
    try:
        return len(search_pixabay_videos("test", 1)) > 0
    except:
        return False