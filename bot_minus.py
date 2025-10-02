import logging
import os
import re
import tempfile
import shutil
import subprocess
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
import yt_dlp

# ====== НАСТРОЙКИ ======
TOKEN = "ТВОЙ_ТОКЕН"   # <<< сюда вставляешь токен
COOKIES_FILE = "cookies.txt"
# =======================

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)

YOUTUBE_REGEX = re.compile(r'(https?://)?(www\.)?(youtube\.com|youtu\.be)/\S+')

def get_ffmpeg_path():
    """Ищем ffmpeg в системе"""
    path = shutil.which("ffmpeg")
    if path:
        return path
    return "/usr/local/bin/ffmpeg"  # fallback


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
        output_file = os.path.join(tmpdir, "minus.wav")

        # yt-dlp
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
            await update.message.reply_text("✅ Видео скачано, конвертирую в WAV...")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка при скачивании: {e}")
            return

        # ffmpeg → wav
        try:
            subprocess.run(
                [get_ffmpeg_path(), "-i", input_file, "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", audio_file],
                check=True
            )
            await update.message.reply_text("🎵 Аудио подготовлено, разделяю вокал...")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка при конвертации: {e}")
            return

        # demucs
        try:
            env = os.environ.copy()
            ffmpeg_dir = os.path.dirname(get_ffmpeg_path())
            env["PATH"] = ffmpeg_dir + ":" + env["PATH"]

            subprocess.run(
                ["demucs", "--two-stems=vocals", "-n", "mdx_extra_q", "-o", tmpdir, audio_file],
                check=True,
                env=env
            )
            await update.message.reply_text("🔄 Вокал отделён, ищу минус...")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка при разделении: {e}")
            return

        # ищем no_vocals.wav
        minus_path = None
        for root, dirs, files in os.walk(tmpdir):
            for f in files:
                if "no_vocals" in f and f.endswith(".wav"):
                    minus_path = os.path.join(root, f)
                    break

        if not minus_path:
            await update.message.reply_text("❌ Не удалось найти минусовку")
            return

        # Отправляем
        try:
            with open(minus_path, "rb") as f:
                await update.message.reply_audio(f, title="Минус готов 🎶")
            await update.message.reply_text("✅ Всё готово!")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка при отправке: {e}")


def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logging.info("=== Bot started with polling ===")
    app.run_polling()


if __name__ == "__main__":
    main()
