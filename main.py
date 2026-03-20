# main.py
# Основной бот для генерации видео с поддержкой пользовательских материалов
# Адаптирован для работы на Render (включает Flask-сервер для пинга)

import asyncio
import threading
import time
import logging
import os
import sqlite3
import httpx
import random
from flask import Flask

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InputFile, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler
)

# Импорты наших модулей (убедитесь, что они есть в проекте)
from config import BOT_TOKEN, STORAGE_BOT_TOKEN
from ideas import get_script
from text_to_speech import text_to_speech
from video_fetcher import fetch_videos_for_theme
from video_editor import create_video_with_audio, mix_audio_files
from utils import generate_unique_filename

# ----------------------------------------------------------
# Flask-сервер для поддержания активности на Render
# ----------------------------------------------------------
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot is running", 200

@flask_app.route('/favicon.ico')
def favicon():
    return "", 204

def run_flask():
    """Запуск Flask в отдельном потоке с логированием."""
    try:
        port = int(os.environ.get('PORT', 10000))
        logging.info(f"Starting Flask on port {port}")
        flask_app.run(host='0.0.0.0', port=port)
    except Exception as e:
        logging.error(f"Flask failed to start: {e}")

# ----------------------------------------------------------
# Настройка логирования
# ----------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Создаём необходимые папки
os.makedirs("media", exist_ok=True)
os.makedirs("cache/thumbnails", exist_ok=True)

# ----------------------------------------------------------
# Константы и маппинги
# ----------------------------------------------------------
THEME_MAP = {
    "🤖 Искусственный интеллект": "ai",
    "💪 Мужская мотивация": "motivation",
    "🔥 Тренды России": "trends"
}

# Состояния для ConversationHandler
SELECTING_ACTION, COLLECTING_VIDEOS, WAITING_TEXT, CONFIRM_GENERATION, \
    WAITING_AUDIO, AFTER_AUDIO, WAITING_EXTRA_AUDIO, WAITING_VIDEO_AFTER_TEXT = range(8)

# ----------------------------------------------------------
# Работа с базой данных (общая для обоих ботов)
# ----------------------------------------------------------
def get_video_file_id(video_id: int, user_id: int):
    conn = sqlite3.connect("user_materials.db")
    c = conn.cursor()
    c.execute("SELECT file_id FROM videos WHERE id=? AND user_id=?", (video_id, user_id))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def get_text_by_id(text_id: int, user_id: int):
    conn = sqlite3.connect("user_materials.db")
    c = conn.cursor()
    c.execute("SELECT content FROM texts WHERE id=? AND user_id=?", (text_id, user_id))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

# ----------------------------------------------------------
# Скачивание файлов из storage бота
# ----------------------------------------------------------
async def download_file_from_storage(file_id: str, save_path: str) -> str:
    url = f"https://api.telegram.org/bot{STORAGE_BOT_TOKEN}/getFile?file_id={file_id}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        if resp.status_code != 200:
            raise Exception(f"Ошибка получения file_path: {resp.text}")
        data = resp.json()
        if not data.get("ok"):
            raise Exception(f"Ошибка: {data}")
        file_path = data["result"]["file_path"]
        file_url = f"https://api.telegram.org/file/bot{STORAGE_BOT_TOKEN}/{file_path}"
        file_resp = await client.get(file_url)
        if file_resp.status_code != 200:
            raise Exception(f"Ошибка скачивания файла: {file_resp.status_code}")
        with open(save_path, "wb") as f:
            f.write(file_resp.content)
    return save_path

# ----------------------------------------------------------
# Команда /start – главное меню
# ----------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    buttons = [
        [KeyboardButton("📹 Мои видео")],
        [KeyboardButton("📝 Мой текст")],
        [KeyboardButton("🎵 Мое аудио")],
        [KeyboardButton("🌐 Pexels/Pixabay")],
        [KeyboardButton("🏠 Главное меню")]
    ]
    reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    await update.message.reply_text(
        "Выберите действие:\n\n"
        "📹 Мои видео – перешлите одно или несколько видео из Storage Bot\n"
        "📝 Мой текст – перешлите текст из Storage Bot (только один)\n"
        "🎵 Мое аудио – перешлите музыку или голосовое из Storage Bot\n"
        "🌐 Pexels/Pixabay – автоматический режим с выбором темы",
        reply_markup=reply_markup
    )
    return SELECTING_ACTION

# ----------------------------------------------------------
# Обработчик выбора действия (SELECTING_ACTION)
# ----------------------------------------------------------
async def handle_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if text == "📹 Мои видео":
        context.user_data["videos"] = []
        await update.message.reply_text(
            "Пересылайте видео из Storage Bot одно за другим.\n"
            "Когда закончите, нажмите кнопку '✅ Готово, видео выбраны'.",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("✅ Готово, видео выбраны")]],
                resize_keyboard=True
            )
        )
        return COLLECTING_VIDEOS
    elif text == "📝 Мой текст":
        await update.message.reply_text(
            "Перешлите один текст из Storage Bot.\n"
            "(Только один текстовый фрагмент будет использован.)"
        )
        return WAITING_TEXT
    elif text == "🎵 Мое аудио":
        await update.message.reply_text(
            "Перешлите один аудиофайл или голосовое сообщение из Storage Bot."
        )
        return WAITING_AUDIO
    elif text == "🌐 Pexels/Pixabay":
        buttons = [
            [KeyboardButton("🤖 Искусственный интеллект")],
            [KeyboardButton("💪 Мужская мотивация")],
            [KeyboardButton("🔥 Тренды России")],
            [KeyboardButton("🏠 Главное меню")]
        ]
        reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
        await update.message.reply_text("Выберите тему для автоматической генерации:", reply_markup=reply_markup)
        return SELECTING_ACTION
    elif text == "🏠 Главное меню":
        await start(update, context)
        return SELECTING_ACTION
    elif text in THEME_MAP:
        await automatic_generation(update, context, THEME_MAP[text])
        return SELECTING_ACTION
    else:
        await update.message.reply_text("Пожалуйста, используйте кнопки меню.")
        return SELECTING_ACTION

# ----------------------------------------------------------
# Состояние COLLECTING_VIDEOS – сбор видео
# ----------------------------------------------------------
async def collect_videos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "✅ Готово, видео выбраны":
        if not context.user_data.get("videos"):
            await update.message.reply_text("Вы не добавили ни одного видео.")
            return COLLECTING_VIDEOS
        # После сбора видео проверяем, есть ли уже текст и аудио
        if "script" in context.user_data:
            if "audio_file_id" in context.user_data:
                return await start_video_creation(update, context)
            else:
                await update.message.reply_text(
                    "Видео и текст сохранены. Хотите добавить фоновое аудио?",
                    reply_markup=ReplyKeyboardMarkup([
                        [KeyboardButton("🎵 Переслать аудио")],
                        [KeyboardButton("⏭ Пропустить (без аудио)")]
                    ], resize_keyboard=True)
                )
                return WAITING_EXTRA_AUDIO
        else:
            await update.message.reply_text(
                "Видео сохранены. Теперь выберите текст (перешлите или сгенерируйте).",
                reply_markup=ReplyKeyboardMarkup([
                    [KeyboardButton("📝 Переслать текст")],
                    [KeyboardButton("✨ Сгенерировать текст")],
                ], resize_keyboard=True)
            )
            return WAITING_TEXT
    if not update.message.forward_origin or not update.message.video:
        await update.message.reply_text("Пожалуйста, пересылайте только видео из Storage Bot.")
        return COLLECTING_VIDEOS
    video = update.message.video
    context.user_data.setdefault("videos", []).append(video.file_id)
    await update.message.reply_text(f"✅ Видео добавлено (всего: {len(context.user_data['videos'])}).")
    return COLLECTING_VIDEOS

# ----------------------------------------------------------
# Состояние WAITING_TEXT – ожидание текста или генерация
# ----------------------------------------------------------
async def waiting_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "✨ Сгенерировать текст":
        await update.message.reply_text(
            "Выберите тему для сценария или нажмите 'Случайная тема':",
            reply_markup=ReplyKeyboardMarkup([
                [KeyboardButton("🤖 Искусственный интеллект")],
                [KeyboardButton("💪 Мужская мотивация")],
                [KeyboardButton("🔥 Тренды России")],
                [KeyboardButton("🎲 Случайная тема")],
                [KeyboardButton("🏠 Главное меню")]
            ], resize_keyboard=True)
        )
        return CONFIRM_GENERATION
    elif update.message.text == "📝 Переслать текст":
        await update.message.reply_text("Перешлите текст из Storage Bot.")
        return WAITING_TEXT

    if update.message.forward_origin and update.message.text:
        context.user_data["script"] = update.message.text
        if "videos" not in context.user_data or not context.user_data["videos"]:
            await update.message.reply_text(
                "✅ Текст получен. Теперь выберите видео:",
                reply_markup=ReplyKeyboardMarkup([
                    [KeyboardButton("📹 Выбрать видео")],
                    [KeyboardButton("⏭ Использовать видео из интернете")]
                ], resize_keyboard=True)
            )
            return WAITING_VIDEO_AFTER_TEXT
        else:
            if "audio_file_id" not in context.user_data:
                await update.message.reply_text(
                    "✅ Текст получен. Хотите добавить фоновое аудио?",
                    reply_markup=ReplyKeyboardMarkup([
                        [KeyboardButton("🎵 Переслать аудио")],
                        [KeyboardButton("⏭ Пропустить (без аудио)")]
                    ], resize_keyboard=True)
                )
                return WAITING_EXTRA_AUDIO
            else:
                return await start_video_creation(update, context)
    else:
        await update.message.reply_text("Пожалуйста, выберите действие из меню или перешлите текст.")
        return WAITING_TEXT

# ----------------------------------------------------------
# Состояние CONFIRM_GENERATION – выбор темы для генерации текста
# ----------------------------------------------------------
async def confirm_generation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if text == "🎲 Случайная тема":
        theme = random.choice(["ai", "motivation", "trends"])
    elif text in THEME_MAP:
        theme = THEME_MAP[text]
    elif text == "🏠 Главное меню":
        await start(update, context)
        return SELECTING_ACTION
    else:
        await update.message.reply_text("Пожалуйста, выберите тему из предложенных.")
        return CONFIRM_GENERATION
    context.user_data["script"] = get_script(theme)
    await update.message.reply_text(f"✅ Сценарий сгенерирован.")
    if "videos" not in context.user_data or not context.user_data["videos"]:
        await update.message.reply_text(
            "Теперь выберите видео:",
            reply_markup=ReplyKeyboardMarkup([
                [KeyboardButton("📹 Выбрать видео")],
                [KeyboardButton("⏭ Использовать видео из интернете")]
            ], resize_keyboard=True)
        )
        return WAITING_VIDEO_AFTER_TEXT
    else:
        if "audio_file_id" not in context.user_data:
            await update.message.reply_text(
                "Хотите добавить фоновое аудио?",
                reply_markup=ReplyKeyboardMarkup([
                    [KeyboardButton("🎵 Переслать аудио")],
                    [KeyboardButton("⏭ Пропустить (без аудио)")]
                ], resize_keyboard=True)
            )
            return WAITING_EXTRA_AUDIO
        else:
            return await start_video_creation(update, context)

# ----------------------------------------------------------
# Состояние WAITING_VIDEO_AFTER_TEXT – выбор видео после текста
# ----------------------------------------------------------
async def waiting_video_after_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if text == "📹 Выбрать видео":
        context.user_data["videos"] = []
        await update.message.reply_text(
            "Пересылайте видео из Storage Bot одно за другим.\n"
            "Когда закончите, нажмите кнопку '✅ Готово, видео выбраны'.",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("✅ Готово, видео выбраны")]],
                resize_keyboard=True
            )
        )
        return COLLECTING_VIDEOS
    elif text == "⏭ Использовать видео из интернете":
        if "audio_file_id" not in context.user_data:
            await update.message.reply_text(
                "Хотите добавить фоновое аудио?",
                reply_markup=ReplyKeyboardMarkup([
                    [KeyboardButton("🎵 Переслать аудио")],
                    [KeyboardButton("⏭ Пропустить (без аудио)")]
                ], resize_keyboard=True)
            )
            return WAITING_EXTRA_AUDIO
        else:
            return await start_video_creation(update, context)
    else:
        await update.message.reply_text("Пожалуйста, выберите действие.")
        return WAITING_VIDEO_AFTER_TEXT

# ----------------------------------------------------------
# Состояние WAITING_EXTRA_AUDIO – ожидание дополнительного аудио
# ----------------------------------------------------------
async def waiting_extra_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "⏭ Пропустить (без аудио)":
        if "videos" not in context.user_data or not context.user_data["videos"]:
            await update.message.reply_text(
                "Теперь выберите видео:",
                reply_markup=ReplyKeyboardMarkup([
                    [KeyboardButton("📹 Выбрать видео")],
                    [KeyboardButton("⏭ Использовать видео из интернете")]
                ], resize_keyboard=True)
            )
            return WAITING_VIDEO_AFTER_TEXT
        else:
            return await start_video_creation(update, context)
    elif update.message.text == "🎵 Переслать аудио":
        await update.message.reply_text("Перешлите аудиофайл или голосовое сообщение из Storage Bot.")
        return WAITING_EXTRA_AUDIO
    elif update.message.audio or update.message.voice:
        if update.message.audio:
            context.user_data["audio_file_id"] = update.message.audio.file_id
            context.user_data["audio_type"] = "audio"
        else:
            context.user_data["audio_file_id"] = update.message.voice.file_id
            context.user_data["audio_type"] = "voice"
        await update.message.reply_text("✅ Аудио получено.")
        if "videos" not in context.user_data or not context.user_data["videos"]:
            await update.message.reply_text(
                "Теперь выберите видео:",
                reply_markup=ReplyKeyboardMarkup([
                    [KeyboardButton("📹 Выбрать видео")],
                    [KeyboardButton("⏭ Использовать видео из интернете")]
                ], resize_keyboard=True)
            )
            return WAITING_VIDEO_AFTER_TEXT
        else:
            await update.message.reply_text("Начинаю создание видео...")
            return await start_video_creation(update, context)
    else:
        await update.message.reply_text("Пожалуйста, выберите действие или перешлите аудио.")
        return WAITING_EXTRA_AUDIO

# ----------------------------------------------------------
# Состояние WAITING_AUDIO – ожидание аудио (первичное)
# ----------------------------------------------------------
async def waiting_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.audio or update.message.voice:
        if update.message.audio:
            context.user_data["audio_file_id"] = update.message.audio.file_id
            context.user_data["audio_type"] = "audio"
        else:
            context.user_data["audio_file_id"] = update.message.voice.file_id
            context.user_data["audio_type"] = "voice"
        await update.message.reply_text("✅ Аудио получено. Теперь выберите видео (если нужно) или текст.")
        await update.message.reply_text(
            "Выберите, что добавить:",
            reply_markup=ReplyKeyboardMarkup([
                [KeyboardButton("📹 Выбрать видео")],
                [KeyboardButton("📝 Выбрать текст")],
                [KeyboardButton("✅ Создать видео")]
            ], resize_keyboard=True)
        )
        return AFTER_AUDIO
    else:
        await update.message.reply_text("Пожалуйста, перешлите аудиофайл или голосовое сообщение из Storage Bot.")
        return WAITING_AUDIO

# ----------------------------------------------------------
# Состояние AFTER_AUDIO – после получения аудио (выбор следующего шага)
# ----------------------------------------------------------
async def after_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if text == "📹 Выбрать видео":
        context.user_data["videos"] = []
        await update.message.reply_text(
            "Пересылайте видео из Storage Bot одно за другим.\n"
            "Когда закончите, нажмите кнопку '✅ Готово, видео выбраны'.",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("✅ Готово, видео выбраны")]],
                resize_keyboard=True
            )
        )
        return COLLECTING_VIDEOS
    elif text == "📝 Выбрать текст":
        await update.message.reply_text("Перешлите текст из Storage Bot.")
        return WAITING_TEXT
    elif text == "✅ Создать видео":
        if "videos" not in context.user_data or not context.user_data["videos"]:
            await update.message.reply_text(
                "Теперь выберите видео:",
                reply_markup=ReplyKeyboardMarkup([
                    [KeyboardButton("📹 Выбрать видео")],
                    [KeyboardButton("⏭ Использовать видео из интернете")]
                ], resize_keyboard=True)
            )
            return WAITING_VIDEO_AFTER_TEXT
        else:
            return await start_video_creation(update, context)
    else:
        await update.message.reply_text("Пожалуйста, используйте кнопки меню.")
        return AFTER_AUDIO

# ----------------------------------------------------------
# Функция запуска создания видео (общая)
# ----------------------------------------------------------
async def start_video_creation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    video_file_ids = context.user_data.get("videos", [])
    script = context.user_data.get("script")
    audio_file_id = context.user_data.get("audio_file_id")

    if not video_file_ids and not script and not audio_file_id:
        await update.message.reply_text("Нет материалов для создания видео. Начните заново.")
        return SELECTING_ACTION

    await update.message.reply_text("Начинаю создание видео...", reply_markup=ReplyKeyboardRemove())

    audio_path = None
    video_paths = []
    final_audio_path = None

    try:
        if script:
            await update.message.reply_text("🔊 Озвучиваю текст...")
            audio_path = await asyncio.to_thread(text_to_speech, script, "media/voice.mp3")
        else:
            audio_path = None

        if video_file_ids:
            await update.message.reply_text(f"📥 Скачиваю {len(video_file_ids)} видео...")
            for file_id in video_file_ids:
                save_path = os.path.join("media", generate_unique_filename("user_video", ".mp4"))
                await download_file_from_storage(file_id, save_path)
                video_paths.append(save_path)
        else:
            await update.message.reply_text("🎥 Ищу видео в интернете...")
            video_paths = await asyncio.to_thread(fetch_videos_for_theme, "motivation", 3)

        if not video_paths:
            await update.message.reply_text("❌ Не удалось получить видео.")
            return SELECTING_ACTION

        if audio_file_id:
            await update.message.reply_text("📥 Скачиваю ваше аудио...")
            audio_save_path = os.path.join("media", generate_unique_filename("user_audio", ".mp3"))
            await download_file_from_storage(audio_file_id, audio_save_path)
            if audio_path:
                await update.message.reply_text("🎚 Смешиваю аудио с фоновой музыкой...")
                mixed_audio_path = os.path.join("media", generate_unique_filename("mixed_audio", ".mp3"))
                final_audio_path = await asyncio.to_thread(mix_audio_files, audio_path, audio_save_path, mixed_audio_path, bg_volume=0.3)
                os.remove(audio_path)
                os.remove(audio_save_path)
                audio_path = final_audio_path
            else:
                audio_path = audio_save_path

        if not audio_path:
            await update.message.reply_text("❌ Нет аудиодорожки для видео.")
            return SELECTING_ACTION

        await update.message.reply_text("✂️ Склеиваю видео и аудио...")
        final_filename = generate_unique_filename("final", ".mp4")
        final_video_path = os.path.join("media", final_filename)
        final_video_path = await asyncio.to_thread(
            create_video_with_audio, video_paths, audio_path, final_video_path
        )

        await update.message.reply_text("✅ Видео готово! Отправляю...")
        with open(final_video_path, 'rb') as f:
            await update.message.reply_video(
                video=InputFile(f),
                caption="Готово!",
                read_timeout=60,
                write_timeout=60
            )

        _cleanup_temp_files(audio_path, video_paths)
        os.remove(final_video_path)

    except Exception as e:
        logger.exception("Ошибка при создании видео")
        await update.message.reply_text(f"❌ Ошибка: {e}")
        _cleanup_temp_files(audio_path, video_paths)
        if audio_path and audio_path != final_audio_path:
            try:
                os.remove(audio_path)
            except:
                pass

    context.user_data.clear()
    await start(update, context)
    return SELECTING_ACTION

def _cleanup_temp_files(audio_path, video_paths):
    try:
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)
        for v in video_paths:
            if v and os.path.exists(v):
                os.remove(v)
    except Exception as e:
        logger.warning(f"Не удалось удалить временные файлы: {e}")

# ----------------------------------------------------------
# Автоматическая генерация (Pexels/Pixabay)
# ----------------------------------------------------------
async def automatic_generation(update: Update, context: ContextTypes.DEFAULT_TYPE, theme: str):
    user = update.effective_user.first_name or "Пользователь"
    logger.info(f"Пользователь {user} выбрал тему: {theme}")
    audio_path = None
    video_paths = []
    try:
        await update.message.reply_text("🎬 Генерирую сценарий...")
        script = get_script(theme)
        await update.message.reply_text("🔊 Озвучиваю текст...")
        audio_path = await asyncio.to_thread(text_to_speech, script, "media/voice.mp3")
        await update.message.reply_text("🎥 Ищу подходящие видео...")
        video_paths = await asyncio.to_thread(fetch_videos_for_theme, theme, 3)
        if not video_paths:
            await update.message.reply_text("❌ Не удалось найти видео. Попробуйте другую тему.")
            _cleanup_temp_files(audio_path, [])
            return
        await update.message.reply_text("✂️ Склеиваю видео и аудио...")
        final_filename = generate_unique_filename("final", ".mp4")
        final_video_path = os.path.join("media", final_filename)
        final_video_path = await asyncio.to_thread(create_video_with_audio, video_paths, audio_path, final_video_path)
        await update.message.reply_text("✅ Видео готово! Отправляю...")
        with open(final_video_path, 'rb') as f:
            await update.message.reply_video(
                video=InputFile(f),
                caption="Вот твоё видео!",
                read_timeout=60,
                write_timeout=60
            )
        _cleanup_temp_files(audio_path, video_paths)
        os.remove(final_video_path)
    except Exception as e:
        logger.exception("Ошибка при автоматической генерации")
        await update.message.reply_text(f"❌ Ошибка: {e}")
        _cleanup_temp_files(audio_path, video_paths)

# ----------------------------------------------------------
# Отмена
# ----------------------------------------------------------
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Действие отменено.", reply_markup=ReplyKeyboardRemove())
    context.user_data.clear()
    return await start(update, context)

# ----------------------------------------------------------
# Основная асинхронная функция запуска бота
# ----------------------------------------------------------
async def run_bot():
    """Создаёт и запускает приложение бота."""
    app = Application.builder().token(BOT_TOKEN).read_timeout(60).write_timeout(60).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECTING_ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_action)],
            COLLECTING_VIDEOS: [MessageHandler(filters.ALL, collect_videos)],
            WAITING_TEXT: [MessageHandler(filters.ALL, waiting_text)],
            CONFIRM_GENERATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_generation)],
            WAITING_VIDEO_AFTER_TEXT: [MessageHandler(filters.ALL, waiting_video_after_text)],
            WAITING_AUDIO: [MessageHandler(filters.ALL, waiting_audio)],
            AFTER_AUDIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, after_audio)],
            WAITING_EXTRA_AUDIO: [MessageHandler(filters.ALL, waiting_extra_audio)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )
    app.add_handler(conv_handler)

    logger.info("Бот запущен и готов к работе...")
    await app.run_polling()

# ----------------------------------------------------------
# Точка входа
# ----------------------------------------------------------
def main():
    """Запускает Flask в фоновом потоке, затем бота."""
    # Запуск Flask в отдельном потоке
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("Flask-сервер запущен в фоновом потоке")
    time.sleep(3)  # Даём время Flask запуститься и открыть порт

    # Запуск бота
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.exception(f"Критическая ошибка: {e}")

if __name__ == "__main__":
    main()