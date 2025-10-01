import os
import re
import tempfile
import asyncio
import subprocess
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# Токен лучше хранить в переменной окружения, но можно и напрямую
TOKEN = os.getenv("BOT_TOKEN", "ТВОЙ_ТОКЕН_СЮДА")

# Путь к cookies.txt (должен лежать рядом с кодом)
COOKIES_FILE = "www.youtube.com_cookies.txt"

# Регулярка для поиска YouTube-ссылок
YOUTUBE_REGEX = r"(https?://(?:www\.)?(?:youtube\.com|youtu\.be)/\S+)"

async def process_youtube(url: str) -> str:
    """Скачивает видео с YouTube, делает минус и возвращает путь к mp3"""
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "input.wav")
        output_path = os.path.join(tmpdir, "minus.mp3")

        # Шаг 1. Скачиваем через yt-dlp
        ytdlp_cmd = [
            "yt-dlp",
            "--no-playlist",
            "--cookies", COOKIES_FILE,
            "-x",
            "--audio-format", "wav",
            "-o", input_path,
            url,
        ]
        subprocess.run(ytdlp_cmd, check=True)

        # Шаг 2. Отправляем в Demucs (минус)
        demucs_cmd = [
            "demucs",
            "-n", "htdemucs",
            "-o", tmpdir,
            input_path,
        ]
        subprocess.run(demucs_cmd, check=True)

        # Demucs кладёт результат в подкаталог tmpdir/htdemucs/INPUT
        # Берём "no_vocals.wav"
        song_name = os.path.splitext(os.path.basename(input_path))[0]
        demucs_dir = os.path.join(tmpdir, "htdemucs", song_name)
        no_vocals = os.path.join(demucs_dir, "no_vocals.wav")

        # Шаг 3. Конвертируем в mp3
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-i", no_vocals,
            "-codec:a", "libmp3lame",
            "-qscale:a", "2",
            output_path,
        ]
        subprocess.run(ffmpeg_cmd, check=True)

        return output_path


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    match = re.search(YOUTUBE_REGEX, text)
    if not match:
        return  # если это не YouTube-ссылка — игнорируем

    url = match.group(1)
    await update.message.reply_text("⏳ Обрабатываю ссылку, подожди...")

    try:
        mp3_path = await asyncio.to_thread(process_youtube, url)
        await update.message.reply_audio(audio=open(mp3_path, "rb"))
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")


def main():
    app = Application.builder().token(TOKEN).build()

    # Ловим все текстовые сообщения (кроме команд)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("=== Bot started with polling ===")
    app.run_polling()


if __name__ == "__main__":
    main()
