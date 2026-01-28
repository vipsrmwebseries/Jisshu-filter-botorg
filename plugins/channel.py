# --| This code created by: Jisshu_bots & SilentXBotz |--#
import re
import hashlib
import asyncio
from info import *
from utils import *
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton  # ← ONLY REQUIRED IMPORT
from database.users_chats_db import db
from database.ia_filterdb import save_file, unpack_new_file_id
import aiohttp
from typing import Optional
from collections import defaultdict

CAPTION_LANGUAGES = [
    "Bhojpuri","Hindi","Bengali","Tamil","English","Bangla","Telugu",
    "Malayalam","Kannada","Marathi","Punjabi","Bengoli","Gujrati",
    "Korean","Gujarati","Spanish","French","German","Chinese",
    "Arabic","Portuguese","Russian","Japanese","Odia","Assamese","Urdu",
]

UPDATE_CAPTION = """<blockquote><b>NEW {} ADDED ✅</b></blockquote>

<b>Tɪᴛʟᴇ :<b><code>{}</code>
<b>Yᴇᴀʀ :{}</b>

🔰 <b>Qᴜᴀʟɪᴛʏ:</b> {}
🎧 <b>Aᴜᴅɪᴏ:</b> {}

<blockquote><b>✨ Telegram Files ✨</b></blockquote>

<b>{}</b>

<blockquote><b>⚡Powered by @RkCineHub</b></blockquote>"""

QUALITY_CAPTION = """📦 {} : {}\n"""

notified_movies = set()
movie_files = defaultdict(list)
POST_DELAY = 10
processing_movies = set()

media_filter = filters.document | filters.video | filters.audio


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


async def queue_movie_file(bot, media):
    try:
        file_name = await movie_name_format(media.file_name)
        caption = await movie_name_format(media.caption)

        year_match = re.search(r"\b(19|20)\d{2}\b", caption)
        year = year_match.group(0) if year_match else None

        quality = await get_qualities(caption) or "HDRip"
        jisshuquality = await Jisshu_qualities(caption, media.file_name) or "720p"

        language = (
            ", ".join([l for l in CAPTION_LANGUAGES if l.lower() in caption.lower()])
            or "Not Idea"
        )

        file_size_str = format_file_size(media.file_size)
        file_id, _ = unpack_new_file_id(media.file_id)

        movie_files[file_name].append({
            "quality": quality,
            "jisshuquality": jisshuquality,
            "file_id": file_id,
            "file_size": file_size_str,
            "caption": caption,
            "language": language,
            "year": year,
        })

        if file_name in processing_movies:
            return

        processing_movies.add(file_name)
        await asyncio.sleep(POST_DELAY)

        if file_name in movie_files:
            await send_movie_update(bot, file_name, movie_files[file_name])
            del movie_files[file_name]

        processing_movies.remove(file_name)

    except Exception as e:
        processing_movies.discard(file_name)
        await bot.send_message(LOG_CHANNEL, f"Movie update error: {e}")


async def send_movie_update(bot, file_name, files):
    if file_name in notified_movies:
        return
    notified_movies.add(file_name)

    imdb_data = await get_imdb(file_name)
    title = imdb_data.get("title", file_name)
    year = imdb_data.get("year") or files[0]["year"] or ""

    poster = await fetch_movie_poster(title, year)
    poster = poster or "https://te.legra.ph/file/88d845b4f8a024a71465d.jpg"

    kind = imdb_data.get("kind", "MOVIE").upper()
    language = ", ".join({f["language"] for f in files})
    quality = ", ".join({f["jisshuquality"] for f in files})

    quality_text = ""
    for f in files:
        link = f"<a href='https://t.me/{temp.U_NAME}?start=file_0_{f['file_id']}'>{f['file_size']}</a>"
        quality_text += f"📦 {f['jisshuquality']} : {link}\n"

    full_caption = UPDATE_CAPTION.format(
        kind, title, year, quality, language, quality_text
    )

    # ✅ ONLY ADDITION — SEARCH BUTTON
    buttons = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔎 Tap to Search", url="https://t.me/Rk2x_Request")]]
    )

    movie_update_channel = await db.movies_update_channel_id()

    await bot.send_photo(
        chat_id=movie_update_channel if movie_update_channel else MOVIE_UPDATE_CHANNEL,
        photo=poster,
        caption=full_caption,
        parse_mode=enums.ParseMode.HTML,
        has_spoiler=True,
        reply_markup=buttons   # ← ONLY CHANGE
    )


# ================= IMDb ================= #

async def get_imdb(file_name):
    try:
        imdb = await get_poster(file_name)
        if not imdb:
            return {}
        return {
            "title": imdb.get("title", file_name),
            "kind": imdb.get("kind", "Movie"),
            "year": imdb.get("year"),
        }
    except:
        return {}


# ================= POSTER ================= #

async def fetch_movie_poster(title: str, year: Optional[str] = None):
    async with aiohttp.ClientSession() as session:
        url = f"https://jisshuapis.vercel.app/api.php?query={title.replace(' ', '+')}"
        async with session.get(url) as r:
            if r.status != 200:
                return None
            data = await r.json()
            for k in ["jisshu-2", "jisshu-3", "jisshu-4"]:
                if data.get(k):
                    return data[k][0]
    return None


# ================= HELPERS ================= #

async def get_qualities(text):
    for q in ["480p","720p","1080p","HDRip","WEB-DL","HEVC"]:
        if q.lower() in text.lower():
            return q
    return "HDRip"


async def Jisshu_qualities(text, file_name):
    for q in ["2160p","1080p","720p","480p"]:
        if q.lower() in (text + file_name).lower():
            return q
    return "720p"


async def movie_name_format(text):
    return re.sub(r"[^\w\s]", " ", text).strip()


def format_file_size(size):
    for unit in ["B","KB","MB","GB","TB"]:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"
