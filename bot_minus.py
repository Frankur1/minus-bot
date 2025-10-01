import logging
import os
import re
import tempfile
import shutil
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
import yt_dlp
import subprocess

# ====== НАСТРОЙКИ ======
TOKEN = "8083958487:AAFBcJBZHMcFdgxSjVEXF5OIdkNEk1ebJUA"   # 🔴 ТВОЙ ТОКЕН
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIES_FILE = os.path.join(BASE_DIR, "cookies.txt")   # 🔴 Абсолютный путь к кукам
# =======================

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)

YOUTUBE_REGEX = re.compile(r'(https?://)?(www\.)?(youtube\.com|youtu\.be)/\S+')

def cleanup_temp():
    """Удаляет временные файлы из /tmp"""
    temp_dir = "/tmp"
    for root, dirs, files in os.walk(temp_dir):
        for f in files:
            try:
                os.remove(os.path.join(root, f))
            except:
                pass
        for d in dirs:
            try:
                shutil.rmtree(os.path.join(root, d))
            except:
                pass

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    match = YOUTUBE_REGEX.search(text)
    if not match:
        return

    url = match.group(0)
    await update.message.reply_text("⏳ Обрабатываю видео, подожди немного...")

    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = os.path.join(tmpdir, "input.mp4")

        # yt-dlp: качаем видео
        ydl_opts = {
            "outtmpl": input_file,
            "format": "bestaudio/best",
            "noplaylist": True,
        }
        if os.path.exists(COOKIES_FILE):
            ydl_opts["cookiefile"] = COOKIES_FILE
            logging.info(f"Использую cookies: {COOKIES_FILE}")
        else:
            logging.warning("⚠️ Файл cookies.txt не найден!")

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка при скачивании: {e}")
            return

        # Demucs: разделяем
        try:
            subprocess.run(
                ["demucs", "--two-stems=vocals", "-o", tmpdir, input_file],
                check=True
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка при разделении: {e}")
            return

        # ищем минус
        minus_path = None
        for root, dirs, files in os.walk(tmpdir):
            for f in files:
                if "no_vocals" in f and f.endswith(".wav"):
                    minus_path = os.path.join(root, f)
                    break

        if not minus_path:
            await update.message.reply_text("❌ Не удалось найти минусовку")
            return

        # отправляем в телегу
        try:
            with open(minus_path, "rb") as f:
                await update.message.reply_audio(f, title="Минус готов 🎶")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка при отправке: {e}")
            return

    cleanup_temp()

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logging.info("=== Bot started with polling ===")
    app.run_polling()

if __name__ == "__main__":
    main()
