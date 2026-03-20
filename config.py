import os

# Основной токен Telegram-бота (обязательный)
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не задан! Укажите его в переменных окружения.")

# Токен второго бота-хранилища (обязательный, если используется storage_bot.py)
STORAGE_BOT_TOKEN = os.getenv('STORAGE_BOT_TOKEN')
if not STORAGE_BOT_TOKEN:
    raise ValueError("❌ STORAGE_BOT_TOKEN не задан! Укажите его в переменных окружения.")

# API-ключи для внешних сервисов (опционально)
PEXELS_API_KEY = os.getenv('PEXELS_API_KEY')
PIXABAY_API_KEY = os.getenv('PIXABAY_API_KEY')
NEWS_API_KEY = os.getenv('NEWS_API_KEY')

print("✅ Конфигурация загружена. BOT_TOKEN и STORAGE_BOT_TOKEN присутствуют.")