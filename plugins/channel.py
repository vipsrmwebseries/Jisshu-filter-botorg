# --| This code created by: Jisshu_bots & SilentXBotz |--#

import re
import hashlib
import asyncio
import aiohttp
from typing import Optional
from collections import defaultdict

from info import *
from utils import *
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.users_chats_db import db
from database.ia_filterdb import save_file, unpack_new_file_id


CAPTION_LANGUAGES = [
    "Bhojpuri","Hindi","Bengali","Tamil","English","Bangla","Telugu",
    "Malayalam","Kannada","Marathi","Punjabi","Bengoli","Gujrati",
    "Korean","Gujarati","Spanish","French","German","Chinese",
    "Arabic","Portuguese","Russian","Japanese","Odia","Assamese","Urdu"
]

DEFAULT_POSTER = "https://graph.org/file/ac3e879a72b7e0c90eb52-0b04163efc1dcbd378.jpg"

UPDATE_CAPTION = """<blockquote><b>𝖭𝖤𝖶 {kind} 𝖠𝖣𝖣𝖤𝖣 ✅</b></blockquote>

🎬 <code>{title}</code> | <b>({year})</b>

🎥 <b>Genres:</b> {genres}

⭐ <b>IMDb:</b> <a href="{imdb_url}">{imdb_rating}</a>

🔰 <b>Quality:</b> {quality}

🎧 <b>Audio:</b> {language}

<blockquote><b>⚡ Powered by @RkCineHub</b></blockquote>
"""

POST_DELAY = 10
notified_movies = set()
movie_files = defaultdict(list)
processing_movies = set()

media_filter = filters.document | filters.video | filters.audio


@Client.on_message(filters.chat(CHANNELS) & media_filter)
async def media(bot, message):
    media = getattr(message, message.media.value, None)
    if not media:
        return

    if media.mime_type not in ["video/mp4", "video/x-matroska", "document/mp4"]:
        return

    media.caption = message.caption or ""
    if await save_file(media) != "suc":
        return

    if not await db.get_send_movie_update_status(bot.me.id):
        return

    await queue_movie_file(bot, media)


async def queue_movie_file(bot, media):
    file_name = await movie_name_format(media.file_name)
    caption = await movie_name_format(media.caption)

    year_match = re.search(r"\b(19|20)\d{2}\b", caption)
    year = year_match.group(0) if year_match else None

    quality = await get_qualities(caption)
    language = ", ".join(
        [l for l in CAPTION_LANGUAGES if l.lower() in caption.lower()]
    ) or "Not Available"

    file_id, _ = unpack_new_file_id(media.file_id)

    movie_files[file_name].append({
        "file_id": file_id,
        "quality": quality,
        "language": language,
        "year": year
    })

    if file_name in processing_movies:
        return

    processing_movies.add(file_name)
    await asyncio.sleep(POST_DELAY)

    await send_movie_update(bot, file_name, movie_files[file_name])

    movie_files.pop(file_name, None)
    processing_movies.remove(file_name)


async def send_movie_update(bot, file_name, files):
    if file_name in notified_movies:
        return
    notified_movies.add(file_name)

    imdb = await get_imdb(file_name)

    title = imdb.get("title") or file_name
    year = imdb.get("year") or files[0]["year"] or "N/A"

    imdb_url = imdb.get("url", "https://www.imdb.com")
    imdb_rating = imdb.get("rating", "N/A")
    genres = imdb.get("genres", "N/A")
    kind = imdb.get("kind", "Movie").upper()

    poster = await fetch_movie_poster(title)
    if not poster:
        poster = DEFAULT_POSTER

    language = ", ".join({f["language"] for f in files})
    quality = ", ".join({f["quality"] for f in files})

    caption = UPDATE_CAPTION.format(
        kind=kind,
        title=title,
        year=year,
        genres=genres,
        imdb_url=imdb_url,
        imdb_rating=imdb_rating,
        quality=quality,
        language=language
    )

    buttons = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔎 Tap to Search", url="https://t.me/Rk2x_Request")]]
    )

    channel = await db.movies_update_channel_id() or MOVIE_UPDATE_CHANNEL

    await bot.send_photo(
        chat_id=channel,
        photo=poster,
        caption=caption,
        parse_mode=enums.ParseMode.HTML,
        has_spoiler=True,
        reply_markup=buttons
    )


# ================= IMDb ================= #

async def get_imdb(name):
    try:
        imdb = await get_poster(name)
        if not imdb:
            return {}
        genres = imdb.get("genres")
        if isinstance(genres, list):
            genres = ", ".join(genres)
        return {
            "title": imdb.get("title"),
            "year": imdb.get("year"),
            "url": imdb.get("url"),
            "rating": imdb.get("rating", "N/A"),
            "kind": imdb.get("kind", "Movie"),
            "genres": genres
        }
    except:
        return {}


# ================= POSTER ================= #

async def fetch_movie_poster(title: str) -> Optional[str]:
    async with aiohttp.ClientSession() as session:
        try:
            url = f"https://jisshuapis.vercel.app/api.php?query={title.replace(' ', '+')}"
            async with session.get(url, timeout=5) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                for k in ["jisshu-2", "jisshu-3", "jisshu-4"]:
                    if data.get(k):
                        return data[k][0]
        except:
            return None
    return None


# ================= HELPERS ================= #

async def get_qualities(text):
    for q in ["480p","720p","1080p","HDRip","WEB-DL","HEVC"]:
        if q.lower() in text.lower():
            return q
    return "HDRip"


async def movie_name_format(text):
    return re.sub(r"[^\w\s]", " ", text).strip()
