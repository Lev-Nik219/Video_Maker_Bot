# config.py
# Загрузка переменных окружения для работы бота
# Все секретные ключи должны быть заданы через переменные окружения (например, на Render)

import os

# Основной токен Telegram-бота (обязательный)
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не задан! Укажите его в переменных окружения.")

# Токен второго бота-хранилища (опциональный, если используется)
STORAGE_BOT_TOKEN = os.getenv('STORAGE_BOT_TOKEN')  # может быть None

# API-ключи для внешних сервисов (опционально, если не заданы – будут использоваться запасные варианты)
PEXELS_API_KEY = os.getenv('PEXELS_API_KEY')
PIXABAY_API_KEY = os.getenv('PIXABAY_API_KEY')
NEWS_API_KEY = os.getenv('NEWS_API_KEY')

print("✅ Конфигурация загружена. BOT_TOKEN присутствует.")