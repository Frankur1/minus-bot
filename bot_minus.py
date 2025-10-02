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
TOKEN = "8083958487:AAFBcJBZHMcFdgxSjVEXF5OIdkNEk1ebJUA"
COOKIES_FILE = "cookies.txt"
FFMPEG_PATH = "/usr/bin/ffmpeg"   # ✅ используем системный ffmpeg напрямую
# =======================

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)

YOUTUBE_REGEX = re.compile(r'(https?://)?(www\.)?(youtube\.com|youtu\.be)/\S+')

def cleanup_temp():
    temp_dir = "/tmp"
    for root, dirs, files in os.walk(temp_dir):
        for f in files:
            try: os.remove(os.path.join(root, f))
            except: pass
        for d in dirs:
            try: shutil.rmtree(os.path.join(root, d))
            except: pass

def preload_models():
    """Прогреваем Demucs, чтобы скачать модели при старте"""
    try:
        # создаем секундный WAV тишины
        test_wav = "/tmp/silence.wav"
        if not os.path.exists(test_wav):
            import wave, struct
            with wave.open(test_wav, 'w') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(44100)
                wf.writeframes(struct.pack('<h', 0) * 44100)

        subprocess.run(
            ["demucs", "-n", "mdx_extra_q", "--two-stems=vocals", "-o", "/tmp", test_wav],
            check=True
        )
        print("✅ Demucs модели загружены")
    except Exception as e:
        print(f"⚠️ Ошибка прогрева: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    match = YOUTUBE_REGEX.search(text)
    if not match: return

    url = match.group(0)
    await update.message.reply_text("⏳ Обрабатываю видео...")

    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = os.path.join(tmpdir, "input.mp4")
        audio_file = os.path.join(tmpdir, "audio.wav")
        output_file = os.path.join(tmpdir, "minus.wav")

        # === 1. Скачиваем видео
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

        # === 2. Конвертим в WAV через системный ffmpeg
        try:
            subprocess.run(
                [FFMPEG_PATH, "-i", input_file, "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", audio_file],
                check=True
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка при конвертации: {e}")
            return

        # === 3. Прогоняем через Demucs
        try:
            subprocess.run(
                ["demucs", "-n", "mdx_extra_q", "--two-stems=vocals", "-o", tmpdir, audio_file],
                check=True
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка при разделении: {e}")
            return

        # === 4. Ищем минус
        minus_path = None
        for root, dirs, files in os.walk(tmpdir):
            for f in files:
                if "no_vocals" in f and f.endswith(".wav"):
                    minus_path = os.path.join(root, f)
                    break

        if not minus_path:
            await update.message.reply_text("❌ Не удалось найти минус")
            return

        # === 5. Отправляем в Telegram
        try:
            with open(minus_path, "rb") as f:
                await update.message.reply_audio(f, title="Минус 🎶")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка при отправке: {e}")
            return

    cleanup_temp()

def main():
    preload_models()  # ✅ прогрев при старте
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logging.info("=== Bot started ===")
    app.run_polling()

if __name__ == "__main__":
    main()
