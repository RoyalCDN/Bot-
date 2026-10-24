import asyncio
import os
import re
import shutil
import tempfile

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from yt_dlp import YoutubeDL


BOT_TOKEN = os.environ["8744638182:AAHKoWZgZ3SR1c0Rl-oiou84DXxrZ-5ng9M"]
MAX_SIZE = 50 * 1024 * 1024
URL_RE = re.compile(
    r"https?://(?:[\w-]+\.)?(?:youtube\.com|youtu\.be|tiktok\.com)/\S+"
)


def download(url: str, mode: str, outdir: str) -> dict:
    opts = {
        "outtmpl": os.path.join(outdir, "%(id)s.%(ext)s"),
        "quiet": True,
        "noplaylist": True,
        "max_filesize": MAX_SIZE,
    }
    if mode == "mp4":
        opts.update(
            {
                "format": "bv*[ext=mp4][height<=720]+ba[ext=m4a]/b[ext=mp4]/b",
                "merge_output_format": "mp4",
            }
        )
    else:
        opts.update(
            {
                "format": "bestaudio/best",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }
        )

    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        path = ydl.prepare_filename(info)
    if mode == "mp3":
        path = os.path.splitext(path)[0] + ".mp3"
    return {"path": path, "title": info.get("title", "media")[:1000]}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send me a YouTube or TikTok link.")


async def on_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    match = URL_RE.search(update.message.text or "")
    if not match:
        await update.message.reply_text("Please send a valid YouTube or TikTok link.")
        return
    context.user_data["url"] = match.group(0)
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🎬 MP4", callback_data="mp4"),
                InlineKeyboardButton("🎵 MP3", callback_data="mp3"),
            ]
        ]
    )
    await update.message.reply_text("Choose a format:", reply_markup=keyboard)


async def on_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    mode = query.data
    url = context.user_data.get("url")
    if not url:
        await query.edit_message_text("Session expired. Please send the link again.")
        return

    await query.edit_message_text(f"Downloading {mode.upper()}… ⏳")
    tmpdir = tempfile.mkdtemp()
    try:
        result = await asyncio.to_thread(download, url, mode, tmpdir)
        path, title = result["path"], result["title"]

        if os.path.getsize(path) > MAX_SIZE:
            await query.message.reply_text("File is larger than Telegram's 50 MB limit.")
            return

        with open(path, "rb") as file:
            if mode == "mp4":
                await query.message.reply_video(
                    file, caption=title[:1024], supports_streaming=True
                )
            else:
                await query.message.reply_audio(
                    file, title=title[:64], caption=title[:1024]
                )
        await query.edit_message_text("✅ Done.")
    except Exception as exc:
        await query.message.reply_text(f"Download failed: {exc}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_link))
    app.add_handler(CallbackQueryHandler(on_choice))
    app.run_polling()


if __name__ == "__main__":
    main()
