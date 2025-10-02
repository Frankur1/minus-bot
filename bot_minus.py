import os
import tempfile
import subprocess
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ======================
# 🔑 Твой токен
# ======================
TOKEN = "8083958487:AAFBcJBZHMcFdgxSjVEXF5OIdkNEk1ebJUA"

# ======================
# Логирование
# ======================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ======================
# Старт
# ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Отправь ссылку на YouTube, и я выделю вокал 🎤")


# ======================
# Обработка ссылки
# ======================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    chat_id = update.message.chat_id

    await update.message.reply_text("🔄 Скачиваю аудио...")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = os.path.join(tmpdir, "input.mp4")
            audio_file = os.path.join(tmpdir, "audio.wav")

            # Скачиваем с yt-dlp
            cmd_download = [
                "yt-dlp",
                "-f", "bestaudio",
                "-o", input_file,
                url
            ]
            subprocess.run(cmd_download, check=True)

            # Конвертируем в WAV через ffmpeg
            cmd_ffmpeg = [
                "ffmpeg", "-y",
                "-i", input_file,
                "-vn",
                "-acodec", "pcm_s16le",
                "-ar", "44100",
                "-ac", "2",
                audio_file
            ]
            subprocess.run(cmd_ffmpeg, check=True)

            await update.message.reply_text("🎶 Разделяю вокал и минус... (модель htdemucs, быстрый режим)")

            # Используем htdemucs вместо mdx_extra_q (быстрее, меньше моделей)
            subprocess.run(
                ["demucs", "-n", "htdemucs", "--two-stems=vocals", "-o", tmpdir, audio_file],
                check=True
            )

            # Пути к результатам
            song_name = os.path.splitext(os.path.basename(audio_file))[0]
            output_dir = os.path.join(tmpdir, "htdemucs", song_name)

            vocals = os.path.join(output_dir, "vocals.wav")
            no_vocals = os.path.join(output_dir, "no_vocals.wav")

            await update.message.reply_text("📤 Отправляю результат...")

            # Отправляем файлы в чат
            if os.path.exists(vocals):
                await context.bot.send_audio(chat_id=chat_id, audio=open(vocals, "rb"))
            if os.path.exists(no_vocals):
                await context.bot.send_audio(chat_id=chat_id, audio=open(no_vocals, "rb"))

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await update.message.reply_text(f"❌ Ошибка: {e}")


# ======================
# Основной запуск
# ======================
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("=== Bot запущен ===")
    app.run_polling()


if __name__ == "__main__":
    main()
