# --| SUPER MERGED CODE : RK CINEHUB × SILENTXBOTZ |--#

import re
import asyncio
import aiohttp
from collections import defaultdict
from typing import Optional

from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from info import *
from utils import *
from database.users_chats_db import db
from database.ia_filterdb import save_file, unpack_new_file_id


# ================= CONFIG ================= #

CAPTION_LANGUAGES = [
    "Bhojpuri","Hindi","Bengali","Tamil","English","Bangla","Telugu",
    "Malayalam","Kannada","Marathi","Punjabi","Gujarati","Korean",
    "Spanish","French","German","Chinese","Arabic","Portuguese",
    "Russian","Japanese","Odia","Assamese","Urdu"
]

FALLBACK_POSTER = "https://graph.org/file/ac3e879a72b7e0c90eb52-0b04163efc1dcbd378.jpg"

UPDATE_CAPTION = """<blockquote><b>RK CINEHUB #PREMIUM</b></blockquote>

<b>Title</b>: <code>✅ {title}</code> <b>#{kind}</b>

<blockquote>🎙 <b>{language}</b></blockquote>

⭐ <a href="{imdb_url}"><b>IMDb</b></a> | 🎭 <a href="{tmdb_url}"><b>TMDB</b></a>
🎥 <b>Genres:</b> {genres}
"""

POST_DELAY = 8

posted_keys = set()
processing_keys = set()
movie_files = defaultdict(list)

media_filter = filters.document | filters.video | filters.audio


# ================= MAIN ================= #

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
    key = await make_clean_key(media.file_name or "")
    caption = media.caption or ""

    language = (
        ", ".join(l for l in CAPTION_LANGUAGES if l.lower() in caption.lower())
        or "Not Available"
    )

    file_id, _ = unpack_new_file_id(media.file_id)
    movie_files[key].append({"file_id": file_id, "language": language})

    if key in posted_keys or key in processing_keys:
        return

    processing_keys.add(key)
    await asyncio.sleep(POST_DELAY)

    await send_movie_update(bot, key, movie_files[key])

    movie_files.pop(key, None)
    processing_keys.remove(key)
    posted_keys.add(key)


# ================= POST ================= #

async def send_movie_update(bot, key, files):
    imdb = await get_imdb(key)
    tmdb = await get_tmdb(key)

    base_title = tmdb.get("title") or imdb.get("title") or await extract_clean_title(key)

    kind_raw = (tmdb.get("kind") or imdb.get("kind") or "").lower()
    kind = "SERIES" if ("tv" in kind_raw or "series" in kind_raw) else "MOVIE"

    # SERIES → season only
    if kind == "SERIES":
        m = re.search(r"S(\d{1,2})", key, re.I)
        season = f" S{int(m.group(1)):02d}" if m else ""
        title = f"{base_title}{season}"
    else:
        title = base_title

    genres = tmdb.get("genres") or imdb.get("genres") or "N/A"

    imdb_url = imdb.get("url") or f"https://www.imdb.com/find?q={title.replace(' ', '+')}"
    tmdb_url = tmdb.get("url") or f"https://www.themoviedb.org/search?query={title.replace(' ', '+')}"

    languages = {f["language"] for f in files if f["language"] != "Not Available"}
    language = ", ".join(sorted(languages)) or "Not Available"

    poster = await get_best_poster(tmdb, imdb)

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


# ================= POSTER (SILENTX STYLE) ================= #

async def get_best_poster(tmdb: dict, imdb: dict) -> str:
    if tmdb.get("backdrop"):
        return tmdb["backdrop"]
    if imdb.get("poster"):
        return imdb["poster"]
    return FALLBACK_POSTER


# ================= TMDB ================= #

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
                    "backdrop": f"https://image.tmdb.org/t/p/w780{item['backdrop_path']}" if item.get("backdrop_path") else None
                }
    return {}


async def tmdb_genres(ids, media_type):
    url = f"https://api.themoviedb.org/3/genre/{media_type}/list?api_key={TMDB_API_KEY}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as r:
            data = await r.json()
            mp = {g["id"]: g["name"] for g in data.get("genres", [])}
            return ", ".join(mp[i] for i in ids if i in mp)


# ================= IMDb ================= #

async def get_imdb(name):
    try:
        clean = await extract_clean_title(name)
        imdb = await get_poster(clean)
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
            "poster": imdb.get("poster") or imdb.get("cover url")
        }
    except:
        return {}


# ================= TITLE CLEAN ================= #

async def extract_clean_title(name: str):
    name = re.sub(r"\.(mkv|mp4|avi|mov)$", "", name, flags=re.I)
    name = re.sub(r'\bS\d{1,2}E\d{1,3}\b', '', name, flags=re.I)
    name = re.sub(r'\b(E|EP)\d{1,3}\b', '', name, flags=re.I)

    junk = [
        "480p","720p","1080p","2160p","4k","amzn","web","webdl","webrip",
        "hdrip","bluray","brrip","x264","x265","h264","h265","hevc",
        "dd","ddp","aac","2ch","5.1","subs","dual","multi","dl","esub"
    ]

    for j in junk:
        name = re.sub(rf"\b{j}\b", "", name, flags=re.I)

    name = re.sub(r"[._\-]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()

    return name


async def make_clean_key(name: str):
    m = re.search(r'\bS(\d{1,2})\b', name, flags=re.I)
    season = f" S{int(m.group(1)):02d}" if m else ""
    name = await extract_clean_title(name)
    return f"{name}{season}".strip()
