import os
import logging
import tempfile
import yt_dlp
import subprocess
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# Логирование
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)

# Токен бота (Railway -> Variables -> BOT_TOKEN)
TOKEN = os.getenv("BOT_TOKEN")

# Куки для YouTube
COOKIES_FILE = "cookies.txt"  # загрузи в проект

# Обработчик сообщений (ловим ссылки на YouTube)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if "youtube.com" not in text and "youtu.be" not in text:
        return  # не ютуб ссылка — пропускаем

    logging.info(f"Получена ссылка: {text}")

    # Создаем временную директорию
    with tempfile.TemporaryDirectory() as tmpdir:
        video_path = os.path.join(tmpdir, "input.mp4")
        audio_path = os.path.join(tmpdir, "vocals.wav")

        # yt-dlp: качаем видео (без плейлистов, с куками)
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": video_path,
            "cookiefile": COOKIES_FILE,
            "noplaylist": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([text])
        except Exception as e:
            await update.message.reply_text(f"Ошибка при скачивании: {e}")
            return

        # Demucs (минусуем)
        try:
            cmd = [
                "demucs",
                "-n", "htdemucs",
                "-o", tmpdir,
                video_path
            ]
            subprocess.run(cmd, check=True)

            # Demucs создает подпапку tmpdir/htdemucs/... берем vocals.wav
            demucs_out = os.path.join(tmpdir, "htdemucs", "input", "vocals.wav")

            if os.path.exists(demucs_out):
                os.rename(demucs_out, audio_path)
            else:
                await update.message.reply_text("Не удалось найти результат Demucs")
                return

        except Exception as e:
            await update.message.reply_text(f"Ошибка Demucs: {e}")
            return

        # Отправляем в Telegram
        try:
            await update.message.reply_audio(audio=open(audio_path, "rb"))
        except Exception as e:
            await update.message.reply_text(f"Ошибка при отправке: {e}")
            return

        logging.info("Файлы очищены — tmpdir удалён автоматически.")

# Запуск бота
def main():
    if not TOKEN:
        raise RuntimeError("Нет BOT_TOKEN — добавь его в Railway Variables")

    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("=== Bot started with polling ===")
    app.run_polling()

if __name__ == "__main__":
    main()
