import logging
import os
import tempfile
import yt_dlp
import ffmpeg
import subprocess

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# =============================
# Твой токен
TOKEN = "8083958487:AAFBcJBZHMcFdgxSjVEXF5OIdkNEk1ebJUA"
# =============================

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ===== Команда /start =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет 👋 Пришли мне ссылку на YouTube, и я уберу вокал из песни 🎶")

# ===== Скачивание и обработка =====
async def process_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    await update.message.reply_text("⏳ Скачиваю видео...")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = os.path.join(tmpdir, "input.mp4")
            output_file = os.path.join(tmpdir, "output.mp3")

            # ==== Настройки yt-dlp ====
            ytdl_opts = {
                "format": "bestaudio/best",
                "outtmpl": input_file,
                "noplaylist": True,      # 👈 только одно видео
                "cookiefile": "cookies.txt",
            }

            # Скачивание
            with yt_dlp.YoutubeDL(ytdl_opts) as ydl:
                ydl.download([url])

            await update.message.reply_text("🎶 Видео скачано, начинаю обработку...")

            # ==== Извлечение аудио через ffmpeg ====
            audio_wav = os.path.join(tmpdir, "audio.wav")
            ffmpeg.input(input_file).output(audio_wav, format="wav", acodec="pcm_s16le", ac=2, ar="44100").overwrite_output().run()

            # ==== Убираем вокал через demucs ====
            await update.message.reply_text("🎤 Убираю вокал (Demucs)... Это может занять время...")

            subprocess.run(
                ["demucs", "--two-stems=vocals", "-o", tmpdir, audio_wav],
                check=True
            )

            # demucs сохраняет результат в отдельной папке
            sep_folder = os.path.join(tmpdir, "htdemucs", "audio")
            no_vocals = os.path.join(sep_folder, "no_vocals.wav")

            if not os.path.exists(no_vocals):
                await update.message.reply_text("⚠️ Ошибка: не найден файл без вокала")
                return

            # ==== Конвертируем в mp3 ====
            ffmpeg.input(no_vocals).output(output_file, format="mp3", audio_bitrate="192k").overwrite_output().run()

            # ==== Отправляем обратно ====
            await update.message.reply_audio(audio=open(output_file, "rb"))

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await update.message.reply_text(f"❌ Ошибка: {e}")

# ===== MAIN =====
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_video))

    logger.info("=== Bot started ===")
    app.run_polling()

if __name__ == "__main__":
    main()
