# --| This code created by: Jisshu_bots & SilentXBotz |--#

import re
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


CAPTION_LANGUAGES = [
    "Bhojpuri","Hindi","Bengali","Tamil","English","Bangla","Telugu",
    "Malayalam","Kannada","Marathi","Punjabi","Gujarati","Korean",
    "Spanish","French","German","Chinese","Arabic","Portuguese",
    "Russian","Japanese","Odia","Assamese","Urdu",
]

# 🔥 FINAL CAPTION (GENRES – PLURAL)
UPDATE_CAPTION = """<blockquote><b>👉 RK CINEHUB #PREMIUM</b></blockquote>

<b>✅ {title} | #{kind}</b>

<blockquote>🎙 <b>{language}</b></blockquote>

⭐ <a href="{imdb_url}"><b>IMDb</b></a> | 🎭 <a href="{tmdb_url}"><b>TMDB</b></a>
🎥 <b>Genres:</b> {genres}
"""

POST_DELAY = 8

# 🔒 DUPLICATE CONTROL
posted_titles = set()
processing_titles = set()
movie_files = defaultdict(list)

media_filter = filters.document | filters.video | filters.audio


# ================= MAIN ================= #

@Client.on_message(filters.chat(CHANNELS) & media_filter)
async def media(bot, message):
    bot_id = bot.me.id
    media = getattr(message, message.media.value, None)
    if not media:
        return

    if media.mime_type not in ["video/mp4", "video/x-matroska", "document/mp4"]:
        return

    media.caption = message.caption or ""
    sts = await save_file(media)
    if sts != "suc" or not await db.get_send_movie_update_status(bot_id):
        return

    await queue_movie_file(bot, media)


async def queue_movie_file(bot, media):
    raw_name = media.file_name or ""
    clean_key = await movie_name_format(raw_name)
    caption = media.caption or ""

    language = (
        ", ".join(l for l in CAPTION_LANGUAGES if l.lower() in caption.lower())
        or "Not Available"
    )

    file_id, _ = unpack_new_file_id(media.file_id)

    movie_files[clean_key].append({
        "file_id": file_id,
        "language": language
    })

    # ❌ Already posted / processing → ignore
    if clean_key in posted_titles or clean_key in processing_titles:
        return

    processing_titles.add(clean_key)
    await asyncio.sleep(POST_DELAY)

    await send_movie_update(bot, clean_key, movie_files[clean_key])

    movie_files.pop(clean_key, None)
    processing_titles.remove(clean_key)
    posted_titles.add(clean_key)


# ================= POST ================= #

async def send_movie_update(bot, key, files):
    imdb_data = await get_imdb(key)
    tmdb_data = await get_tmdb(key)

    # 🔥 TITLE
    title = tmdb_data.get("title") or imdb_data.get("title") or key

    # 🔥 TYPE
    kind = tmdb_data.get("kind") or imdb_data.get("kind") or "MOVIE"
    kind = kind.upper().replace(" ", "_")
    if kind == "TV_SERIES":
        kind = "SERIES"

    # 🔥 GENRES (PLURAL)
    genres = tmdb_data.get("genres") or imdb_data.get("genres") or "N/A"

    imdb_url = imdb_data.get("url") or f"https://www.imdb.com/find?q={title.replace(' ', '+')}"
    tmdb_url = tmdb_data.get("url") or f"https://www.themoviedb.org/search?query={title.replace(' ', '+')}"

    season_tag = ""
    if kind == "SERIES":
        sm = re.search(r"S(\d{1,2})", key, re.I)
        if sm:
            season_tag = f" S{int(sm.group(1)):02d}"

    languages = set(f["language"] for f in files if f["language"] != "Not Available")
    language = ", ".join(sorted(languages)) or "Not Available"

    poster = tmdb_data.get("poster") or await fetch_movie_poster(title)
    if not poster:
        poster = "https://te.legra.ph/file/88d845b4f8a024a71465d.jpg"

    caption = UPDATE_CAPTION.format(
        title=title,
        kind=kind,
        language=language,
        genres=genres,
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


# ================= TMDB (PRIMARY GENRES) ================= #

async def get_tmdb(query):
    async with aiohttp.ClientSession() as session:
        for media_type in ["movie", "tv"]:
            url = f"https://api.themoviedb.org/3/search/{media_type}?api_key={TMDB_API_KEY}&query={query}"
            async with session.get(url) as r:
                if r.status != 200:
                    continue
                data = await r.json()
                if not data.get("results"):
                    continue

                item = data["results"][0]
                genres = await tmdb_genres(item["genre_ids"], media_type)

                return {
                    "title": item.get("title") or item.get("name"),
                    "kind": "SERIES" if media_type == "tv" else "MOVIE",
                    "genres": genres,
                    "url": f"https://www.themoviedb.org/{media_type}/{item['id']}",
                    "poster": f"https://image.tmdb.org/t/p/w500{item.get('poster_path')}"
                }
    return {}


async def tmdb_genres(ids, media_type):
    url = f"https://api.themoviedb.org/3/genre/{media_type}/list?api_key={TMDB_API_KEY}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as r:
            data = await r.json()
            mapping = {g["id"]: g["name"] for g in data.get("genres", [])}
            return ", ".join(mapping[i] for i in ids if i in mapping)


# ================= IMDb (FALLBACK) ================= #

async def get_imdb(name):
    try:
        formatted = await movie_name_format(name)
        imdb = await get_poster(formatted)
        if not imdb:
            return {}
        genres = imdb.get("genres")
        if isinstance(genres, list):
            genres = ", ".join(genres)
        return {
            "title": imdb.get("title"),
            "kind": imdb.get("kind"),
            "genres": genres,
            "url": imdb.get("url"),
        }
    except:
        return {}


# ================= HELPERS ================= #

async def fetch_movie_poster(title: str) -> Optional[str]:
    async with aiohttp.ClientSession() as session:
        url = f"https://jisshuapis.vercel.app/api.php?query={title.replace(' ', '+')}"
        try:
            async with session.get(url, timeout=5) as res:
                if res.status == 200:
                    data = await res.json()
                    for k in ["jisshu-2", "jisshu-3", "jisshu-4"]:
                        if data.get(k):
                            return data[k][0]
        except:
            pass
    return None


# 🔥 CLEAN TITLE
async def movie_name_format(name: str):
    name = name or ""
    name = re.sub(r"\.(mkv|mp4|avi|mov)$", "", name, flags=re.I)

    remove_words = [
        "480p","720p","1080p","2160p","4k",
        "amzn","web","webdl","web-dl","webrip",
        "hdrip","bluray","brrip",
        "x264","x265","h264","h265","hevc",
        "ddp","dd","aac","atmos","2 0","5 1",
        "punjabi","hindi","english","tamil","telugu",
        "subs","esub","cc","multi","dual","mkv"
    ]

    for w in remove_words:
        name = re.sub(rf"\b{w}\b", "", name, flags=re.I)

    name = re.sub(r"[._\-]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()

    m = re.search(r"(19\d{2}|20\d{2})", name)
    if m:
        name = name[: name.find(m.group(1)) + 4]

    return name.strip()
