# --| This code created by: Jisshu_bots & SilentXBotz |--#
import re
import asyncio
import aiohttp
from collections import defaultdict

from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from info import *
from utils import *
from database.users_chats_db import db
from database.ia_filterdb import save_file, unpack_new_file_id


CAPTION_LANGUAGES = [
    "Bhojpuri","Hindi","Bengali","Tamil","English","Bangla","Telugu",
    "Malayalam","Kannada","Marathi","Punjabi","Gujarati","Korean",
    "Spanish","French","German","Chinese","Arabic","Portuguese",
    "Russian","Japanese","Odia","Assamese","Urdu",
]

# ✅ FINAL CAPTION (IMDb BASED, NO QUALITY TEXT)
UPDATE_CAPTION = """<blockquote><b>RK CINEHUB #PREMIUM</b></blockquote>

<b>✅ {title} {season_tag} | #{kind}</b>

<blockquote>🎙 <b>{language}</b></blockquote>

⭐ <a href="{imdb_url}"><b>IMDb</b></a> | 🎭 <a href="{tmdb_url}"><b>TMDB</b></a>
🎥 <b>Genre:</b> {genre}
"""

POST_DELAY = 15

notified_movies = set()
processing_movies = set()
movie_files = defaultdict(list)

media_filter = filters.document | filters.video | filters.audio


@Client.on_message(filters.chat(CHANNELS) & media_filter)
async def media(bot, message):
    media = getattr(message, message.media.value, None)
    if not media:
        return

    if media.mime_type in ["video/mp4", "video/x-matroska", "document/mp4"]:
        media.caption = message.caption or ""
        sts = await save_file(media)
        if sts == "suc" and await db.get_send_movie_update_status(bot.me.id):
            await queue_movie_file(bot, media)


async def queue_movie_file(bot, media):
    try:
        raw_name = media.file_name or ""
        key_name = await movie_name_format(raw_name)
        caption = await movie_name_format(media.caption or "")

        language = (
            ", ".join(l for l in CAPTION_LANGUAGES if l.lower() in caption.lower())
            or "Not Available"
        )

        file_id, _ = unpack_new_file_id(media.file_id)

        movie_files[key_name].append({
            "file_id": file_id,
            "language": language
        })

        if key_name in processing_movies:
            return

        processing_movies.add(key_name)
        await asyncio.sleep(POST_DELAY)

        await send_movie_update(bot, key_name, movie_files[key_name])

        movie_files.pop(key_name, None)
        processing_movies.remove(key_name)

    except Exception as e:
        processing_movies.discard(key_name)
        await bot.send_message(LOG_CHANNEL, f"Update Error:\n<code>{e}</code>")


async def send_movie_update(bot, key_name, files):
    if key_name in notified_movies:
        return
    notified_movies.add(key_name)

    imdb = await get_imdb(key_name)

    # ✅ TITLE FROM IMDb (SOURCE OF TRUTH)
    title = imdb.get("title") or key_name

    # ✅ KIND FROM IMDb (SOURCE OF TRUTH)
    imdb_kind = (imdb.get("kind") or "").lower()
    if imdb_kind == "movie":
        kind = "MOVIE"
    elif imdb_kind in ["tv series", "tv mini series"]:
        kind = "SERIES"
    else:
        kind = "MOVIE"  # safe fallback

    genre = imdb.get("genres") or "N/A"

    imdb_url = imdb.get("imdb_url") or f"https://www.imdb.com/find?q={title.replace(' ', '+')}"
    tmdb_url = imdb.get("tmdb_url") or f"https://www.themoviedb.org/search?query={title.replace(' ', '+')}"

    season_tag = ""
    if kind == "SERIES":
        sm = re.search(r"S(\d{1,2})", key_name, re.I)
        if sm:
            season_tag = f" | S{int(sm.group(1)):02d}"

    languages = set()
    for f in files:
        languages.update(f["language"].split(", "))
    language = ", ".join(sorted(languages))

    poster = await fetch_movie_poster(title)
    poster = poster or "https://te.legra.ph/file/88d845b4f8a024a71465d.jpg"

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

async def get_imdb(name):
    try:
        data = await get_poster(await movie_name_format(name))
        if not data:
            return {}

        genres = data.get("genres")
        if isinstance(genres, list):
            genres = ", ".join(genres)

        return {
            "title": data.get("title"),
            "kind": data.get("kind"),          # movie / tv series
            "genres": genres,
            "imdb_url": data.get("url"),
            "tmdb_url": data.get("tmdb_url"),
        }
    except:
        return {}


async def fetch_movie_poster(title: str):
    async with aiohttp.ClientSession() as session:
        url = f"https://jisshuapis.vercel.app/api.php?query={title.replace(' ', '+')}"
        try:
            async with session.get(url, timeout=5) as r:
                if r.status == 200:
                    data = await r.json()
                    for k in ["jisshu-2", "jisshu-3", "jisshu-4"]:
                        if data.get(k):
                            return data[k][0]
        except:
            pass
    return None


# ✅ CLEAN NAME ONLY FOR SEARCH / KEY (NOT DISPLAY)
async def movie_name_format(name: str):
    name = re.sub(r"\.(mkv|mp4|avi|mov)$", "", name, flags=re.I)

    # REMOVE SEASON / EPISODE
    name = re.sub(r'\bS\d{1,2}E?\d{0,2}\b', '', name, flags=re.I)
    name = re.sub(r'\b(E|EP)\d{1,3}\b', '', name, flags=re.I)

    remove_words = [
        "480p","720p","1080p","2160p","4k","8bit","10bit",
        "bluray","brrip","webrip","webdl","web-dl","hdrip",
        "x264","x265","h264","hevc",
        "aac","dd","ddp","ddp5","ddp5.1","dts","atmos",
        "amzn","nf","dsnp",
        "audio","dub","subs","msubs","esub",
        "hindi","english","tamil","telugu","kannada","malayalam",
        "dual","multi","org","proper","repack","bms"
    ]

    for w in remove_words:
        name = re.sub(rf"\b{w}\b", "", name, flags=re.I)

    name = re.sub(r"[._\-]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name
