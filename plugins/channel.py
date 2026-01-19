# --| This code created by: Jisshu_bots & SilentXBotz |--#
# --| Quality Order & Poster Fix by: Jarvis |--#

import re
import hashlib
import asyncio
from info import *
from utils import *
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.users_chats_db import db
from database.ia_filterdb import save_file, unpack_new_file_id
import aiohttp
from typing import Optional
from collections import defaultdict


# ================= CONFIG ================= #

CAPTION_LANGUAGES = [
    "Bhojpuri", "Hindi", "Bengali", "Tamil", "English", "Bangla",
    "Telugu", "Malayalam", "Kannada", "Marathi", "Punjabi", "Bengoli",
    "Gujrati", "Korean", "Gujarati", "Spanish", "French", "German",
    "Chinese", "Arabic", "Portuguese", "Russian", "Japanese",
    "Odia", "Assamese", "Urdu",
]

QUALITY_ORDER = ["480p", "720p", "1080p", "2160p"]

POST_DELAY = 10

UPDATE_CAPTION = """<blockquote><b>𝖭𝖤𝖶 {} 𝖠𝖣𝖣𝖤𝖣 ✅</b></blockquote>

🎬 <code>{}</code> || {}
🔰 <b>Quality: {}</b>
🎧 <b>Audio: {}</b>

<blockquote><b>✨ Telegram Files ✨</b></blockquote>

{}

<blockquote><b>〽️Powered by➠ @RkCineHub</b></blockquote>"""

REQUEST_BUTTON = InlineKeyboardMarkup(
    [[InlineKeyboardButton("🎬 MOVIE REQUEST GROUP", url="https://t.me/Rk2x_Request")]]
)

notified_movies = set()
movie_files = defaultdict(list)
processing_movies = set()

media_filter = filters.document | filters.video | filters.audio


# ================= MAIN HANDLER ================= #

@Client.on_message(filters.chat(CHANNELS) & media_filter)
async def media(bot, message):
    bot_id = bot.me.id
    media = getattr(message, message.media.value, None)

    if media.mime_type in ["video/mp4", "video/x-matroska", "document/mp4"]:
        media.file_type = message.media.value
        media.caption = message.caption

        success_sts = await save_file(media)
        if success_sts == "suc" and await db.get_send_movie_update_status(bot_id):
            await queue_movie_file(bot, media)


# ================= QUEUE FILE ================= #

async def queue_movie_file(bot, media):
    try:
        file_name = await movie_name_format(media.file_name)
        caption = await movie_name_format(media.caption or "")

        year_match = re.search(r"\b(19|20)\d{2}\b", caption)
        year = year_match.group(0) if year_match else None

        season_match = re.search(r"(?i)(?:s|season)0*(\d{1,2})", caption) or \
                       re.search(r"(?i)(?:s|season)0*(\d{1,2})", file_name)

        if year:
            file_name = file_name[: file_name.find(year) + 4]
        elif season_match:
            season = season_match.group(1)
            file_name = file_name[: file_name.find(season) + 1]

        quality = await get_qualities(caption) or "HDRip"
        jisshuquality = await Jisshu_qualities(caption, media.file_name) or "720p"

        language = (
            ", ".join([lang for lang in CAPTION_LANGUAGES if lang.lower() in caption.lower()])
            or "Not Idea"
        )

        file_size_str = format_file_size(media.file_size)
        file_id, _ = unpack_new_file_id(media.file_id)

        movie_files[file_name].append(
            {
                "quality": quality,
                "jisshuquality": jisshuquality,
                "file_id": file_id,
                "file_size": file_size_str,
                "caption": caption,
                "language": language,
                "year": year,
            }
        )

        if file_name in processing_movies:
            return

        processing_movies.add(file_name)

        try:
            await asyncio.sleep(POST_DELAY)
            if file_name in movie_files:
                await send_movie_update(bot, file_name, movie_files[file_name])
                del movie_files[file_name]
        finally:
            processing_movies.remove(file_name)

    except Exception as e:
        processing_movies.discard(file_name)
        await bot.send_message(LOG_CHANNEL, f"Error:\n{e}")


# ================= SEND UPDATE ================= #

async def send_movie_update(bot, file_name, files):
    if file_name in notified_movies:
        return
    notified_movies.add(file_name)

    imdb_data = await get_imdb(file_name)
    title = imdb_data.get("title", file_name)
    kind = imdb_data.get("kind", "MOVIE").upper().replace(" ", "_")
    if kind == "TV_SERIES":
        kind = "SERIES"

    # ✅ POSTER FIX (IMDB → API fallback)
    poster = imdb_data.get("poster")
    if not poster:
        poster = await fetch_movie_poster(title, files[0]["year"])

    # ---------- LANGUAGE ----------
    languages = set()
    for f in files:
        if f["language"] != "Not Idea":
            languages.update(f["language"].split(", "))
    language = ", ".join(sorted(languages)) or "Not Idea"

    # ---------- QUALITY LINE FIX ----------
    quality_set = {f["jisshuquality"] for f in files}
    sorted_qualities = [q for q in QUALITY_ORDER if q in quality_set]
    quality_line = ", ".join(sorted_qualities)

    # ---------- FILE LIST FIX ----------
    quality_map = {}
    for f in files:
        quality_map[f["jisshuquality"]] = f

    quality_text = ""
    for q in QUALITY_ORDER:
        if q in quality_map:
            f = quality_map[q]
            quality_text += (
                f"📦 {q} : "
                f"<a href='https://t.me/{temp.U_NAME}?start=file_0_{f['file_id']}'>"
                f"{f['file_size']}</a>\n"
            )

    full_caption = UPDATE_CAPTION.format(
        kind,
        title,
        files[0]["year"],
        quality_line,
        language,
        quality_text
    )

    await bot.send_photo(
        chat_id=await db.movies_update_channel_id() or MOVIE_UPDATE_CHANNEL,
        photo=poster or "https://te.legra.ph/file/88d845b4f8a024a71465d.jpg",
        caption=full_caption,
        parse_mode=enums.ParseMode.HTML,
        has_spoiler=True,
        reply_markup=REQUEST_BUTTON
    )


# ================= HELPERS ================= #

async def get_imdb(file_name):
    try:
        imdb = await get_poster(await movie_name_format(file_name))
        if not imdb:
            return {}
        return imdb
    except:
        return {}


async def fetch_movie_poster(title, year=None):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                f"https://jisshuapis.vercel.app/api.php?query={title.replace(' ', '+')}",
                timeout=5
            ) as res:
                if res.status == 200:
                    data = await res.json()
                    for k in ["jisshu-2", "jisshu-3", "jisshu-4"]:
                        if data.get(k):
                            return data[k][0]
        except:
            pass
    return None


async def get_qualities(text):
    for q in ["2160p", "1080p", "720p", "480p", "HDRip", "WEB-DL", "HDTS", "CAM"]:
        if q.lower() in text.lower():
            return q
    return "HDRip"


async def Jisshu_qualities(text, file_name):
    text = (text + " " + file_name).lower()
    for q in ["2160p", "1080p", "720p", "480p"]:
        if q in text:
            return q
    return "720p"


async def movie_name_format(name):
    return re.sub(r"[^\w\s]", " ", name or "").replace("_", " ").strip()


def format_file_size(size):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
