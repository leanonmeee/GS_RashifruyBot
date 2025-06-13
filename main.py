import os
from faster_whisper import WhisperModel
import uuid
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters
import ffmpeg
import subprocess
import asyncio

# Загружаем модель whisper
model = WhisperModel("base", device="cpu")  # можешь использовать "tiny", "base", "small", "medium", "large"

# Папка для хранения файлов
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Обработка старт-команды
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Пришли мне голосовое сообщение или кружок, и я пришлю тебе расшифровку текстом.")

# Преобразование OGG в WAV через ffmpeg-python
def convert_ogg_to_wav(ogg_path, wav_path):
    subprocess.run([
        "ffmpeg", "-i", ogg_path,
        "-ar", "16000", "-ac", "1",
        "-c:a", "pcm_s16le", wav_path,
        "-y"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

async def transcribe_audio(path):
    return await asyncio.to_thread(model.transcribe, path)

# Обработка голосовых и кружков
async def handle_voice_or_video_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = update.message.voice or update.message.video_note
    if not file:
        await update.message.reply_text("⚠️ Это не голосовое сообщение или кружок.")
        return

    file_id = str(uuid.uuid4())
    ogg_path = os.path.join(DOWNLOAD_DIR, f"{file_id}.ogg")
    wav_path = os.path.join(DOWNLOAD_DIR, f"{file_id}.wav")

    wait_message = await update.message.reply_text("⏳ Подождите, расшифровываю...")

    try:
        telegram_file = await context.bot.get_file(file.file_id)
        await telegram_file.download_to_drive(ogg_path)
        convert_ogg_to_wav(ogg_path, wav_path)

        segments, _ = await transcribe_audio(wav_path)
        text = " ".join([seg.text for seg in segments]).replace("?", ".").strip()

        await wait_message.delete()

        if text:
            await update.message.reply_text(
                f"📝 Расшифровка:\n{text}",
                reply_to_message_id=update.message.message_id
            )
        else:
            await update.message.reply_text(
                "❌ Не удалось распознать речь.",
                reply_to_message_id=update.message.message_id
            )

    except Exception as e:
        await wait_message.delete()
        await update.message.reply_text(
            f"⚠️ Ошибка: {e}",
            reply_to_message_id=update.message.message_id
        )
    finally:
        for path in (ogg_path, wav_path):
            if os.path.exists(path):
                os.remove(path)

# Запуск бота
if __name__ == "__main__":
    TOKEN = "" # ВСТАВИТЬ СЮДА СВОЙ ТОКЕН БОТА
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VOICE | filters.VIDEO_NOTE, handle_voice_or_video_note))

    print("Бот запущен...")
    app.run_polling()