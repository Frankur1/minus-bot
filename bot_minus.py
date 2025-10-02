import logging
import os
import tempfile
import yt_dlp
import ffmpeg
import subprocess

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# =============================
TOKEN = "8083958487:AAFBcJBZHMcFdgxSjVEXF5OIdkNEk1ebJUA"
# =============================

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет 👋 Пришли ссылку на YouTube, и я уберу вокал 🎶")


async def process_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    await update.message.reply_text("⏳ Скачиваю...")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = os.path.join(tmpdir, "input.mp4")

            # yt-dlp
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": input_file,
                "noplaylist": True,
                "cookiefile": "cookies.txt",
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            await update.message.reply_text("🎶 Скачано. Извлекаю аудио...")

            # в WAV
            audio_wav = os.path.join(tmpdir, "audio.wav")
            ffmpeg.input(input_file).output(
                audio_wav, format="wav", acodec="pcm_s16le", ac=2, ar="44100"
            ).overwrite_output().run()

            await update.message.reply_text("🎤 Убираю вокал (Demucs)...")

            # Demucs сразу в mp3
            subprocess.run(
                ["demucs", "--two-stems=vocals", "--mp3", "-o", tmpdir, audio_wav],
                check=True
            )

            # папка где результат
            sep_folder = os.path.join(tmpdir, "htdemucs", "audio")
            no_vocals_mp3 = os.path.join(sep_folder, "no_vocals.mp3")

            if not os.path.exists(no_vocals_mp3):
                await update.message.reply_text("⚠️ Ошибка: не найден минус")
                return

            await update.message.reply_audio(audio=open(no_vocals_mp3, "rb"))

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await update.message.reply_text(f"❌ Ошибка: {e}")


def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_video))
    logger.info("=== Bot started ===")
    app.run_polling()


if __name__ == "__main__":
    main()
