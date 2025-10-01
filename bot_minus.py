import logging
import os
import tempfile
import subprocess
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# === ЛОГИ ===
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === ТОКЕН ===
TOKEN = "8083958487:AAFBcJBZHMcFdgxSjVEXF5OIdkNEk1ebJUA"

# === КОМАНДА /minus ===
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Используй так: /minus <ссылка на YouTube>")
        return

    url = context.args[0]
    msg = await update.message.reply_text("⏳ Готовлюсь...")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "input.wav")
            output_path = os.path.join(tmpdir, "minus.mp3")

            # === ШАГ 1: Скачиваем с YouTube ===
            logger.info(f"yt-dlp start: {url}")
            ydl_cmd = [
                "yt-dlp",
                "--no-playlist",
                "--cookies", "cookies.txt",  # cookies от расширения
                "-x", "--audio-format", "wav",
                "-o", input_path,
                url
            ]
            subprocess.run(ydl_cmd, check=True)
            logger.info("yt-dlp done")

            # === ШАГ 2: Demucs (удаляем вокал) ===
            logger.info("Demucs start")
            demucs_cmd = [
                "python3", "-m", "demucs.separate",
                "--two-stems", "vocals",
                "-o", tmpdir,
                input_path
            ]
            subprocess.run(demucs_cmd, check=True)
            no_vocals_path = os.path.join(tmpdir, "htdemucs", "input", "no_vocals.wav")
            logger.info("Demucs done")

            # === ШАГ 3: Конвертация в mp3 ===
            logger.info("FFmpeg start")
            ffmpeg_cmd = [
                "ffmpeg", "-y", "-i", no_vocals_path,
                "-b:a", "160k",
                output_path
            ]
            subprocess.run(ffmpeg_cmd, check=True)
            logger.info("FFmpeg done")

            # === ШАГ 4: Отправка файла ===
            await update.message.reply_document(
                document=open(output_path, "rb"),
                filename="minus.mp3"
            )
            await msg.edit_text("✅ Готово!")

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        await msg.edit_text(f"❌ Ошибка: {e}")

# === MAIN ===
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("minus", handle))

    # Render требует запуск через webhook
    PORT = int(os.environ.get("PORT", 8443))
    RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")
    if not RENDER_URL:
        raise RuntimeError("Не найден RENDER_EXTERNAL_URL — Render сам задаёт этот env var")

    webhook_url = f"{RENDER_URL}/{TOKEN}"

    logger.info(f"Starting webhook at {webhook_url}")

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TOKEN,
        webhook_url=webhook_url
    )

if __name__ == "__main__":
    main()
