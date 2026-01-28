# --| RK CINEHUB × SILENTXBOTZ : FINAL STABLE FIX |--#

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


# ================= CONFIG ================= #

CAPTION_LANGUAGES = [
    "Hindi","English","Bengali","Tamil","Telugu","Malayalam",
    "Kannada","Punjabi","Gujarati","French","Spanish","German"
]

FALLBACK_POSTER = "https://graph.org/file/ac3e879a72b7e0c90eb52-0b04163efc1dcbd378.jpg"

UPDATE_CAPTION = """<blockquote><b>RK CINEHUB #PREMIUM</b></blockquote>

<b>Title:</b> <code>{title}</code> <b>#{kind}</b>

<blockquote>🎙 <b>{language}</b></blockquote>

⭐ <a href="{imdb_url}">IMDb</a> | 🎭 <a href="{tmdb_url}">TMDB</a>
🎥 <b>Genres:</b> {genres}
📅 <b>Year:</b> {year}
"""

POST_DELAY = 6

posted_keys = set()
processing_keys = set()
movie_files = defaultdict(list)

media_filter = filters.document | filters.video


# ================= MAIN ================= #

@Client.on_message(filters.chat(CHANNELS) & media_filter)
async def media(bot, message):
    media = message.document or message.video
    if not media:
        return

    media.caption = message.caption or ""
    if await save_file(media) != "suc":
        return

    if not await db.get_send_movie_update_status(bot.me.id):
        return

    await queue_movie(bot, media)


async def queue_movie(bot, media):
    clean_title, year = extract_title_year(media.file_name)

    key = f"{clean_title} {year or ''}".strip()

    language = ", ".join(
        l for l in CAPTION_LANGUAGES if l.lower() in media.caption.lower()
    ) or "Not Available"

    file_id, _ = unpack_new_file_id(media.file_id)
    movie_files[key].append(language)

    if key in posted_keys or key in processing_keys:
        return

    processing_keys.add(key)
    await asyncio.sleep(POST_DELAY)

    await send_movie_update(bot, clean_title, year, movie_files[key])

    movie_files.pop(key, None)
    processing_keys.remove(key)
    posted_keys.add(key)


# ================= POST ================= #

async def send_movie_update(bot, title, year, languages):
    tmdb = await get_tmdb(title, year)

    kind = tmdb.get("kind", "MOVIE")
    genres = tmdb.get("genres", "N/A")
    poster = tmdb.get("poster") or FALLBACK_POSTER

    caption = UPDATE_CAPTION.format(
        title=tmdb.get("title", title),
        kind=kind,
        language=", ".join(set(languages)),
        genres=genres,
        year=tmdb.get("year", year or "N/A"),
        imdb_url=tmdb.get("imdb_url", f"https://www.imdb.com/find?q={title}"),
        tmdb_url=tmdb.get("tmdb_url", f"https://www.themoviedb.org/search?query={title}")
    )

    await bot.send_photo(
        chat_id=MOVIE_UPDATE_CHANNEL,
        photo=poster,
        caption=caption,
        parse_mode=enums.ParseMode.HTML,
        has_spoiler=True,
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔍 Tap to Search", url="https://t.me/Rk2x_Request")]]
        )
    )


# ================= TMDB STRONG SEARCH ================= #

async def get_tmdb(title, year):
    async with aiohttp.ClientSession() as session:
        params = {
            "api_key": TMDB_API_KEY,
            "query": title
        }
        if year:
            params["primary_release_year"] = year

        url = "https://api.themoviedb.org/3/search/movie"

        async with session.get(url, params=params) as r:
            data = await r.json()
            if not data.get("results"):
                return {}

            m = data["results"][0]

            genres = await tmdb_genres(m["genre_ids"])

            return {
                "title": m.get("title"),
                "year": (m.get("release_date") or "")[:4],
                "genres": genres,
                "kind": "MOVIE",
                "poster": f"https://image.tmdb.org/t/p/w780{m['backdrop_path']}" if m.get("backdrop_path") else None,
                "tmdb_url": f"https://www.themoviedb.org/movie/{m['id']}"
            }


async def tmdb_genres(ids):
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"https://api.themoviedb.org/3/genre/movie/list?api_key={TMDB_API_KEY}"
        ) as r:
            data = await r.json()
            mp = {g["id"]: g["name"] for g in data["genres"]}
            return ", ".join(mp[i] for i in ids if i in mp)


# ================= TITLE + YEAR EXTRACT ================= #

def extract_title_year(name: str):
    name = name.replace(".", " ").replace("_", " ")
    year = None

    m = re.search(r"(19\d{2}|20\d{2})", name)
    if m:
        year = m.group(1)
        name = name.replace(year, "")

    junk = [
        "1080p","720p","480p","dvdrip","hdrip","bluray","mkv","mp4",
        "bengali","hindi","tamil","telugu","subs","msubs"
    ]

    for j in junk:
        name = re.sub(rf"\b{j}\b", "", name, flags=re.I)

    name = re.sub(r"\s+", " ", name).strip()
    return name, year
