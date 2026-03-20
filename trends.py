# trends.py
# Модуль для получения актуальных новостных трендов через NewsAPI
# Использует бесплатный API newsapi.org (100 запросов в день)

import logging
import requests
import random
from config import NEWS_API_KEY

logger = logging.getLogger(__name__)

# Запасной список трендов на случай недоступности API
FALLBACK_TRENDS = [
    "В России вырос спрос на электромобили",
    "Новый закон о такси вступил в силу",
    "Цены на аренду жилья изменились в крупных городах",
    "Популярный блогер запустил новый челлендж",
    "Учёные сделали открытие в области медицины",
    "Москва вошла в топ-3 городов по качеству жизни",
    "В Госдуме обсуждают новые меры поддержки семей",
    "Курс рубля укрепился на этой неделе",
    "Открылся новый парк развлечений в Сочи",
    "Зимний фестиваль стартует в эти выходные"
]

def get_trends(limit: int = 5) -> list:
    """
    Получает свежие новости по России через NewsAPI.
    Возвращает список заголовков (не более limit штук).
    При ошибке или отсутствии ключа возвращает случайную выборку из FALLBACK_TRENDS.
    """
    if not NEWS_API_KEY:
        logger.warning("NewsAPI ключ отсутствует, используются запасные тренды")
        return random.sample(FALLBACK_TRENDS, min(limit, len(FALLBACK_TRENDS)))

    url = "https://newsapi.org/v2/top-headlines"
    params = {
        "country": "ru",           # новости России
        "apiKey": NEWS_API_KEY,
        "pageSize": limit,         # количество заголовков
        "language": "ru",
        "sortBy": "popularity"     # сортировка по популярности
    }

    try:
        logger.info("Запрос к NewsAPI за трендами...")
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()  # выбросит исключение при коде ошибки
        data = response.json()

        if data.get("status") != "ok":
            logger.error(f"NewsAPI вернул ошибку: {data.get('message')}")
            return random.sample(FALLBACK_TRENDS, min(limit, len(FALLBACK_TRENDS)))

        articles = data.get("articles", [])
        if not articles:
            logger.warning("NewsAPI не вернул статей, используются запасные тренды")
            return random.sample(FALLBACK_TRENDS, min(limit, len(FALLBACK_TRENDS)))

        # Извлекаем заголовки
        trends = [article["title"] for article in articles if article.get("title")]
        logger.info(f"Получено {len(trends)} трендов из NewsAPI")
        return trends[:limit]

    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка подключения к NewsAPI: {e}")
        return random.sample(FALLBACK_TRENDS, min(limit, len(FALLBACK_TRENDS)))
    except Exception as e:
        logger.exception(f"Неожиданная ошибка: {e}")
        return random.sample(FALLBACK_TRENDS, min(limit, len(FALLBACK_TRENDS)))

def get_random_trend() -> str:
    """
    Возвращает один случайный тренд.
    Удобно для вставки в сценарий.
    """
    trends = get_trends(limit=10)
    return random.choice(trends) if trends else "новости дня"

# Для тестирования
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Случайный тренд:", get_random_trend())