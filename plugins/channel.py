# --| This code created by: Jisshu_bots & SilentXBotz |--#

import re
import hashlib
import asyncio
import aiohttp
from typing import Optional
from collections import defaultdict

from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from info import *
from utils import *
from database.users_chats_db import db
from database.ia_filterdb import save_file, unpack_new_file_id


# ---------------- CONFIG ---------------- #

CAPTION_LANGUAGES = [
    "Bhojpuri","Hindi","Bengali","Tamil","English","Bangla","Telugu",
    "Malayalam","Kannada","Marathi","Punjabi","Gujarati","Korean",
    "Spanish","French","German","Chinese","Arabic","Portuguese",
    "Russian","Japanese","Odia","Assamese","Urdu",
]

POST_DELAY = 10

# 🔥 SINGLE SOURCE OF TRUTH (CAPTION)
UPDATE_CAPTION = """<b>💯 NEW FILES ADDED ✅</b>

🖥 <b>File name:</b> {title}

♻️ <b>Category:</b> {category}
🎞 <b>Quality:</b> {quality}
💿 <b>Format:</b> {format}
🌍 <b>Audio:</b> {audio}

📁 <b>Recently Added Files:</b> {recent}
🗄 <b>Total Files:</b> {total}
"""


# ---------------- RUNTIME STORES ---------------- #

movie_files = defaultdict(list)
processing_movies = set()
notified_movies = set()

media_filter = filters.document | filters.video | filters.audio


# ---------------- MEDIA HANDLER ---------------- #

@Client.on_message(filters.chat(CHANNELS) & media_filter)
async def media(bot, message):
    bot_id = bot.me.id
    media = getattr(message, message.media.value, None)

    if not media:
        return

    if media.mime_type not in ["video/mp4", "video/x-matroska", "document/mp4"]:
        return

    media.caption = message.caption or ""

    success = await save_file(media)
    if success == "suc" and await db.get_send_movie_update_status(bot_id):
        await queue_movie_file(bot, media)


# ---------------- QUEUE ---------------- #

async def queue_movie_file(bot, media):
    try:
        file_name = await movie_name_format(media.file_name)
        caption = media.caption

        quality = extract_quality(caption, media.file_name)
        audio = extract_audio(caption)
        category = detect_category(caption, media.file_name)
        video_format = detect_format(caption, media.file_name)

        file_id, _ = unpack_new_file_id(media.file_id)

        movie_files[file_name].append({
            "file_id": file_id,
            "quality": quality,
            "audio": audio,
            "category": category,
            "format": video_format
        })

        if file_name in processing_movies:
            return

        processing_movies.add(file_name)
        await asyncio.sleep(POST_DELAY)

        files = movie_files.pop(file_name, [])
        processing_movies.discard(file_name)

        if files:
            await send_movie_update(bot, file_name, files)

    except Exception as e:
        processing_movies.discard(file_name)
        await bot.send_message(LOG_CHANNEL, f"Movie update error:\n{e}")


# ---------------- SEND UPDATE ---------------- #

async def send_movie_update(bot, file_name, files):
    if file_name in notified_movies:
        return
    notified_movies.add(file_name)

    title = file_name

    quality_text = ", ".join(sorted({f["quality"] for f in files}))
    audio_text = ", ".join(sorted({f["audio"] for f in files if f["audio"]})) or "Unknown"

    category = files[0]["category"]
    video_format = files[0]["format"]

    recent_files = len(files)
    try:
        total_files = await db.get_movie_files_count(title)
    except:
        total_files = recent_files

    poster = await fetch_movie_poster(title)
    image_url = poster or "https://te.legra.ph/file/88d845b4f8a024a71465d.jpg"

    caption = UPDATE_CAPTION.format(
        title=title,
        category=category,
        quality=quality_text,
        format=video_format,
        audio=audio_text,
        recent=recent_files,
        total=total_files
    )

    buttons = InlineKeyboardMarkup(
        [[InlineKeyboardButton(
            "📥 Get Files",
            url=f"https://t.me/{temp.U_NAME}?start=all_{generate_unique_id(title)}"
        )]]
    )

    movie_update_channel = await db.movies_update_channel_id()

    await bot.send_photo(
        chat_id=movie_update_channel if movie_update_channel else MOVIE_UPDATE_CHANNEL,
        photo=image_url,
        caption=caption,
        reply_markup=buttons,
        has_spoiler=True,
        parse_mode=enums.ParseMode.HTML
    )


# ---------------- HELPERS ---------------- #

def detect_category(text, file_name):
    combined = (text + " " + file_name).lower()
    if re.search(r"s\d{1,2}|season|episode|e\d{1,2}", combined):
        return "#Series"
    return "#Movies"


def detect_format(text, file_name):
    combined = (text + " " + file_name).lower()
    if "web-dl" in combined or "webdl" in combined:
        return "WEB-DL"
    if "bluray" in combined or "blu-ray" in combined:
        return "BluRay"
    if "hdtv" in combined:
        return "HDTV"
    if "hdrip" in combined:
        return "HDRip"
    return "HDRip"


def extract_quality(text, file_name):
    combined = (text + " " + file_name).lower()
    for q in ["2160p","1080p","720p","480p"]:
        if q in combined:
            return q
    return "720p"


def extract_audio(text):
    found = [l for l in CAPTION_LANGUAGES if l.lower() in text.lower()]
    return ", ".join(sorted(set(found)))


async def fetch_movie_poster(title: str) -> Optional[str]:
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                f"https://jisshuapis.vercel.app/api.php?query={title.replace(' ','+')}",
                timeout=5
            ) as r:
                data = await r.json()
                for k in ["jisshu-2","jisshu-3","jisshu-4"]:
                    if data.get(k):
                        return data[k][0]
        except:
            return None


def generate_unique_id(name: str) -> str:
    return hashlib.md5(name.encode("utf-8")).hexdigest()[:5]


async def movie_name_format(name):
    return re.sub(
        r"[._@\-\[\]\(\)]", " ",
        re.sub(r"@\w+|#\w+", "", name)
    ).strip()
