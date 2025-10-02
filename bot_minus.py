import logging
import os
import re
import tempfile
import shutil
import subprocess
import shutil
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
import yt_dlp

# ====== НАСТРОЙКИ ======
TOKEN = "8083958487:AAFBcJBZHMcFdgxSjVEXF5OIdkNEk1ebJUA"   # 🔴 твой токен
COOKIES_FILE = "cookies.txt"   # если есть cookies.txt — будет использован
# =======================

# Фикс ffmpeg под Railway (часто кладётся не в /usr/bin, а в /usr/local/bin)
if not shutil.which("ffmpeg"):
    os.environ["PATH"] += os.pathsep + "/usr/local/bin"

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
    await update.message.reply_text("⏳ Скачиваю видео...")

    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = os.path.join(tmpdir, "input.mp4")
        audio_file = os.path.join(tmpdir, "audio.wav")

        # yt-dlp: качаем только аудио
        ydl_opts = {
            "outtmpl": input_file,
            "format": "bestaudio/best",
            "noplaylist": True,
        }
        if os.path.exists(COOKIES_FILE):
            ydl_opts["cookiefile"] = COOKIES_FILE

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка при скачивании: {e}")
            return

        # конвертим в WAV через ffmpeg
        await update.message.reply_text("🎵 Конвертирую в WAV...")
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", input_file, "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", audio_file],
                check=True
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка при конвертации: {e}")
            return

        # Demucs: разделяем
        await update.message.reply_text("🎤 Убираю вокал...")
        try:
            subprocess.run(
                ["demucs", "-n", "mdx_extra_q", "--two-stems=vocals", "-o", tmpdir, audio_file],
                check=True,
                env={**os.environ, "PATH": os.environ["PATH"] + ":/usr/local/bin"}
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
        await update.message.reply_text("📤 Отправляю результат...")
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
