# config.py
import os

BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не задан!")

STORAGE_BOT_TOKEN = os.getenv('STORAGE_BOT_TOKEN')
if not STORAGE_BOT_TOKEN:
    raise ValueError("❌ STORAGE_BOT_TOKEN не задан!")

# остальные ключи опциональны
PEXELS_API_KEY = os.getenv('PEXELS_API_KEY')
PIXABAY_API_KEY = os.getenv('PIXABAY_API_KEY')
NEWS_API_KEY = os.getenv('NEWS_API_KEY')

print("✅ Конфигурация загружена.")