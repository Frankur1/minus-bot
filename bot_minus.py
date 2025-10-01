import logging
import tempfile
import subprocess
from pathlib import Path
import asyncio

from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# 🔑 Твой токен
TOKEN = "8083958487:AAFBcJBZHMcFdgxSjVEXF5OIdkNEk1ebJUA"

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger("minusbot")

# ==== Вспомогательные функции ====


async def run_cmd(cmd: list[str], cwd: Path = None):
    """Запуск команды в subprocess + логирование"""
    logger.info("Running command: %s", " ".join(cmd))
    process = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    stdout, _ = await process.communicate()
    logger.info(stdout.decode())
    return process.returncode


async def make_minus(url: str, msg):
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # === 1. Скачать YouTube ===
            await msg.edit_text("🔽 Скачиваю трек с YouTube…")
            wav_path = tmpdir / "input.wav"
            cmd_dl = [
                "yt-dlp",
                "--no-playlist",  # ⚡️ важно! не тянем весь плейлист
                "-x",
                "--audio-format", "wav",
                "-o", str(wav_path),
                url,
            ]
            code = await run_cmd(cmd_dl, cwd=tmpdir)
            if code != 0 or not wav_path.exists():
                await msg.edit_text("❌ Ошибка при скачивании")
                return

            # === 2. Demucs разделение ===
            await msg.edit_text("🎙 Разделяю вокал и минус…")
            sep_dir = tmpdir / "sep"
            cmd_demucs = [
                "python3.11", "-m", "demucs.separate",
                "--two-stems", "vocals",
                "-o", str(sep_dir),
                str(wav_path),
            ]
            code = await run_cmd(cmd_demucs, cwd=tmpdir)
            if code != 0:
                await msg.edit_text("❌ Ошибка Demucs")
                return

            no_vocals = next(sep_dir.rglob("no_vocals.wav"))

            # === 3. Конвертация в MP3 ===
            await msg.edit_text("🎶 Конвертирую в MP3…")
            mp3_path = tmpdir / "minus.mp3"
            cmd_ffmpeg = [
                "ffmpeg", "-y",
                "-i", str(no_vocals),
                "-b:a", "160k",
                str(mp3_path),
            ]
            code = await run_cmd(cmd_ffmpeg, cwd=tmpdir)
            if code != 0 or not mp3_path.exists():
                await msg.edit_text("❌ Ошибка при конвертации в MP3")
                return

            # === 4. Отправка файла ===
            await msg.edit_text("📤 Отправляю минус…")
            await msg.reply_document(document=open(mp3_path, "rb"))

            await msg.edit_text("✅ Готово! Отправлен минус.")

    except Exception as e:
        logger.exception("Ошибка в make_minus")
        await msg.edit_text(f"❌ Ошибка: {e}")


# ==== Хэндлеры ====


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    text = update.message.text.strip()
    if text.startswith("http"):
        msg = await update.message.reply_text("Начинаю обработку…")
        await make_minus(text, msg)


def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    logger.info("=== Bot starting === minusbot v3.9 (with token)")
    app.run_polling()


if __name__ == "__main__":
    main()
