# --| This code created by: Jisshu_bots & SilentXBotz |--#

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

CAPTION_LANGUAGES = [
    "Bhojpuri","Hindi","Bengali","Tamil","English","Bangla","Telugu",
    "Malayalam","Kannada","Marathi","Punjabi","Bengoli","Gujrati",
    "Korean","Gujarati","Spanish","French","German","Chinese","Arabic",
    "Portuguese","Russian","Japanese","Odia","Assamese","Urdu",
]

# ✅ PHOTO STYLE CAPTION (BLASTER HUB LIKE)
UPDATE_CAPTION = """<blockquote><b> RK CINEHUB #PREMIUM</b></blockquote>

<b>✅ {title} {season_tag} #{kind}</b>

<blockquote>🎙 <b>{language}</b></blockquote>

⭐ <a href="{imdb_url}"><b>IMDb</b></a> | 🎭 <a href="{tmdb_url}"><b>TMDB</b></a>
🎥 <b>Genre:</b> {genre}
"""

notified_movies = set()
movie_files = defaultdict(list)
POST_DELAY = 10
processing_movies = set()

media_filter = filters.document | filters.video | filters.audio


@Client.on_message(filters.chat(CHANNELS) & media_filter)
async def media(bot, message):
    bot_id = bot.me.id
    media = getattr(message, message.media.value, None)
    if not media:
        return

    if media.mime_type in ["video/mp4", "video/x-matroska", "document/mp4"]:
        media.caption = message.caption or ""
        success_sts = await save_file(media)
        if success_sts == "suc" and await db.get_send_movie_update_status(bot_id):
            await queue_movie_file(bot, media)


async def queue_movie_file(bot, media):
    try:
        file_name = await movie_name_format(media.file_name or "")
        caption = await movie_name_format(media.caption or "")

        season_match = re.search(r"(?i)(?:s|season)0*(\d{1,2})", caption)
        season = season_match.group(1) if season_match else None

        language = (
            ", ".join(lang for lang in CAPTION_LANGUAGES if lang.lower() in caption.lower())
            or "Not Available"
        )

        file_id, _ = unpack_new_file_id(media.file_id)
        movie_files[file_name].append({
            "file_id": file_id,
            "language": language,
            "season": season
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
        await bot.send_message(LOG_CHANNEL, f"<code>{e}</code>")


async def send_movie_update(bot, file_name, files):
    if file_name in notified_movies:
        return
    notified_movies.add(file_name)

    imdb_data = await get_imdb(file_name)

    title = imdb_data.get("title", file_name)
    kind = imdb_data.get("kind", "MOVIE").upper().replace(" ", "_")
    if kind == "TV_SERIES":
        kind = "SERIES"

    imdb_url = imdb_data.get("url") or f"https://www.imdb.com/find?q={title.replace(' ', '+')}"
    tmdb_url = f"https://www.themoviedb.org/search?query={title.replace(' ', '+')}"

    genre = imdb_data.get("genres", "N/A")

    season_tag = ""
    if kind == "SERIES":
        sm = re.search(r"S(\d{1,2})", file_name, re.I)
        if sm:
            season_tag = f"S{int(sm.group(1)):02d}"

    languages = set(f["language"] for f in files if f["language"] != "Not Available")
    language = ", ".join(sorted(languages)) or "Not Available"

    poster = await fetch_movie_poster(title)
    if not poster:
        poster = "https://te.legra.ph/file/88d845b4f8a024a71465d.jpg"

    caption = UPDATE_CAPTION.format(
        title=title,
        season_tag=season_tag,
        kind=kind,
        language=language,
        genre=genre,
        imdb_url=imdb_url,
        tmdb_url=tmdb_url
    )

    buttons = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔍 Tap to Search", url="https://t.me/Rk2x_Request")]]
    )

    channel = await db.movies_update_channel_id() or MOVIE_UPDATE_CHANNEL

    await bot.send_photo(
        chat_id=channel,
        photo=poster,
        caption=caption,
        reply_markup=buttons,
        parse_mode=enums.ParseMode.HTML,
        has_spoiler=True
    )


# ================= HELPERS ================= #

async def get_imdb(file_name):
    try:
        formatted_name = await movie_name_format(file_name)
        imdb = await get_poster(formatted_name)
        if not imdb:
            return {}
        return {
            "title": imdb.get("title", formatted_name),
            "kind": imdb.get("kind", "Movie"),
            "genres": ", ".join(imdb.get("genres", [])) if isinstance(imdb.get("genres"), list) else imdb.get("genres"),
            "url": imdb.get("url"),
        }
    except:
        return {}


async def fetch_movie_poster(title: str) -> Optional[str]:
    async with aiohttp.ClientSession() as session:
        url = f"https://jisshuapis.vercel.app/api.php?query={title.replace(' ', '+')}"
        try:
            async with session.get(url, timeout=5) as res:
                if res.status == 200:
                    data = await res.json()
                    for key in ["jisshu-2", "jisshu-3", "jisshu-4"]:
                        if data.get(key):
                            return data[key][0]
        except:
            pass
    return None


async def movie_name_format(file_name):
    return re.sub(
        r"\s+",
        " ",
        re.sub(r"[._\-]", " ", file_name or "")
    ).strip()

