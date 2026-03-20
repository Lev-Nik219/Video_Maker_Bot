import logging
import sqlite3
import threading
import time
import os
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

from config import STORAGE_BOT_TOKEN

MAIN_BOT_USERNAME = "LN_Video_Maker_Bot"  # username основного бота (без @)

# ----------------------------------------------------------
# Flask-сервер для порта
# ----------------------------------------------------------
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Storage Bot is running", 200

@flask_app.route('/favicon.ico')
def favicon():
    return "", 204

def run_flask():
    try:
        port = int(os.environ.get('PORT', 10000))
        logging.info(f"Starting Flask on port {port}")
        flask_app.run(host='0.0.0.0', port=port)
    except Exception as e:
        logging.error(f"Flask failed to start: {e}")

# ----------------------------------------------------------
# Основная логика бота
# ----------------------------------------------------------
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    conn = sqlite3.connect("user_materials.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS texts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            file_id TEXT NOT NULL,
            thumbnail_id TEXT,
            duration INTEGER,
            width INTEGER,
            height INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS audios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            file_id TEXT NOT NULL,
            type TEXT NOT NULL,
            duration INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    logger.info("Database initialized")

def get_user_videos(user_id: int):
    conn = sqlite3.connect("user_materials.db")
    c = conn.cursor()
    c.execute("SELECT id, file_id, duration, timestamp FROM videos WHERE user_id=? ORDER BY timestamp DESC", (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_user_texts(user_id: int):
    conn = sqlite3.connect("user_materials.db")
    c = conn.cursor()
    c.execute("SELECT id, content, timestamp FROM texts WHERE user_id=? ORDER BY timestamp DESC", (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_user_audios(user_id: int):
    conn = sqlite3.connect("user_materials.db")
    c = conn.cursor()
    c.execute("SELECT id, file_id, type, duration, timestamp FROM audios WHERE user_id=? ORDER BY timestamp DESC", (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows

# ----- Обработчики команд -----
async def myvideos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    videos = get_user_videos(user_id)
    if not videos:
        await update.message.reply_text("У вас нет сохранённых видео.")
        return
    keyboard = []
    for vid_id, file_id, duration, ts in videos[:10]:
        date_time = ts[8:10] + "." + ts[5:7] + " " + ts[11:16]
        button_text = f"🎬 Видео {date_time} ({duration} сек)"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"selvideo_{vid_id}")])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите видео:", reply_markup=reply_markup)

async def mytexts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    texts = get_user_texts(user_id)
    if not texts:
        await update.message.reply_text("У вас нет сохранённых текстов.")
        return
    keyboard = []
    for txt_id, content, ts in texts[:10]:
        preview = content[:30] + "..." if len(content) > 30 else content
        date_time = ts[8:10] + "." + ts[5:7] + " " + ts[11:16]
        button_text = f"📝 {preview} ({date_time})"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"seltext_{txt_id}")])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите текст:", reply_markup=reply_markup)

async def myaudios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    audios = get_user_audios(user_id)
    if not audios:
        await update.message.reply_text("У вас нет сохранённых аудиофайлов.")
        return
    keyboard = []
    for aud_id, file_id, typ, duration, ts in audios[:10]:
        date_time = ts[8:10] + "." + ts[5:7] + " " + ts[11:16]
        if typ == 'audio':
            icon = "🎵"
            desc = f"Музыка {date_time}"
        else:
            icon = "🎤"
            desc = f"Голосовое {date_time}"
        button_text = f"{icon} {desc} ({duration} сек)"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"selaudio_{aud_id}")])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите аудио:", reply_markup=reply_markup)

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "cancel":
        await query.edit_message_text("Действие отменено.")
        return

    if data.startswith("selvideo_"):
        video_id = data.split("_")[1]
        context.user_data["selected_video"] = video_id
        await query.edit_message_text("✅ Видео выбрано. Теперь выберите текст, аудио или отправьте команду /mytexts или /myaudios.")
        return

    if data.startswith("seltext_"):
        text_id = data.split("_")[1]
        context.user_data["selected_text"] = text_id
        await query.edit_message_text("✅ Текст выбран. Теперь выберите видео или аудио.")
        return

    if data.startswith("selaudio_"):
        audio_id = data.split("_")[1]
        context.user_data["selected_audio"] = audio_id
        if "selected_video" in context.user_data:
            video_id = context.user_data.pop("selected_video")
            text_id = context.user_data.get("selected_text")
            audio_id = context.user_data.pop("selected_audio")
            param = f"v{video_id}_t{text_id if text_id else ''}_a{audio_id}"
            link = f"https://t.me/{MAIN_BOT_USERNAME}?start={param}"
            await query.edit_message_text(
                f"✅ Видео и аудио выбраны!\n\n"
                f"Нажмите на ссылку, чтобы перейти в основного бота и начать создание видео:\n{link}",
                disable_web_page_preview=True
            )
        else:
            await query.edit_message_text("✅ Аудио выбрано. Теперь выберите видео или отправьте команду /myvideos.")
            return

# ----- Обработчики для сохранения материалов -----
async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    video = update.message.video
    if not video:
        await update.message.reply_text("Пожалуйста, отправьте видео как файл.")
        return
    thumb_id = video.thumbnail.file_id if video.thumbnail else None
    try:
        conn = sqlite3.connect("user_materials.db")
        c = conn.cursor()
        c.execute("""
            INSERT INTO videos (user_id, file_id, thumbnail_id, duration, width, height)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, video.file_id, thumb_id, video.duration, video.width, video.height))
        conn.commit()
        conn.close()
        await update.message.reply_text(
            f"✅ Ваше видео сохранено.\n"
            f"Длительность: {video.duration} сек\n"
            f"Размер: {video.width}x{video.height}"
        )
    except Exception as e:
        logger.exception("Ошибка при сохранении видео")
        await update.message.reply_text("❌ Произошла ошибка при сохранении видео.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    if not text or text.startswith('/'):
        return
    try:
        conn = sqlite3.connect("user_materials.db")
        c = conn.cursor()
        c.execute("INSERT INTO texts (user_id, content) VALUES (?, ?)", (user_id, text))
        conn.commit()
        conn.close()
        await update.message.reply_text("✅ Ваш текст сохранён в хранилище.")
    except Exception as e:
        logger.exception("Ошибка при сохранении текста")
        await update.message.reply_text("❌ Произошла ошибка при сохранении текста.")

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    audio = update.message.audio
    voice = update.message.voice
    if audio:
        file_id = audio.file_id
        duration = audio.duration
        typ = 'audio'
    elif voice:
        file_id = voice.file_id
        duration = voice.duration
        typ = 'voice'
    else:
        await update.message.reply_text("Пожалуйста, отправьте аудиофайл или голосовое сообщение.")
        return
    try:
        conn = sqlite3.connect("user_materials.db")
        c = conn.cursor()
        c.execute("INSERT INTO audios (user_id, file_id, type, duration) VALUES (?, ?, ?, ?)",
                  (user_id, file_id, typ, duration))
        conn.commit()
        conn.close()
        await update.message.reply_text(
            f"✅ {'Музыка' if typ=='audio' else 'Голосовое'} сохранена.\n"
            f"Длительность: {duration} сек"
        )
    except Exception as e:
        logger.exception("Ошибка при сохранении аудио")
        await update.message.reply_text("❌ Произошла ошибка при сохранении аудио.")

def main():
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("Flask-сервер запущен в фоновом потоке")
    time.sleep(2)

    init_db()
    app = Application.builder().token(STORAGE_BOT_TOKEN).build()
    app.add_handler(CommandHandler("myvideos", myvideos))
    app.add_handler(CommandHandler("mytexts", mytexts))
    app.add_handler(CommandHandler("myaudios", myaudios))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.VIDEO, handle_video))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.AUDIO | filters.VOICE, handle_audio))
    logger.info("Storage bot started with audio support")
    app.run_polling()

if __name__ == "__main__":
    main()