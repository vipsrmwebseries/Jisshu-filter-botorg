# --| This code created by: Jisshu_bots & SilentXBotz |--#

import re
import asyncio
import aiohttp

from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from info import *
from database.users_chats_db import db
from database.ia_filterdb import save_file


POST_DELAY = 10
posted_ids = set()

media_filter = filters.document | filters.video | filters.audio


@Client.on_message(filters.chat(CHANNELS) & media_filter)
async def media(bot, message):
    media = getattr(message, message.media.value, None)
    if not media:
        return

    sts = await save_file(media)
    if sts != "suc":
        return

    name = media.file_name or message.caption or ""
    await asyncio.sleep(POST_DELAY)
    await process_title(bot, name)


async def process_title(bot, raw_name):
    tmdb = await tmdb_search(raw_name)
    if not tmdb:
        return

    # 🔑 UNIQUE KEY (MOVIE / SERIES / SEASON)
    unique_key = f"{tmdb['id']}_{tmdb['season']}"

    if unique_key in posted_ids:
        return
    posted_ids.add(unique_key)

    caption = f"""<b>{tmdb['channel']}</b>

<b>✅ {tmdb['title']} {tmdb['season_tag']} #{tmdb['type']}</b>

<blockquote>🎙 {tmdb['language']}</blockquote>

⭐ <a href="{tmdb['imdb']}">IMDb</a> | 🎭 <a href="{tmdb['tmdb']}">TMDB</a>
🎥 <b>Genre:</b> {tmdb['genres']}
"""

    btn = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔍 Tap to Search", url="https://t.me/Rk2x_Request")]]
    )

    await bot.send_photo(
        chat_id=MOVIE_UPDATE_CHANNEL,
        photo=tmdb["poster"],
        caption=caption,
        reply_markup=btn,
        parse_mode=enums.ParseMode.HTML,
        has_spoiler=True
    )


# ================= TMDB ENGINE ================= #

async def tmdb_search(query):
    season = extract_season(query)

    async with aiohttp.ClientSession() as s:
        for t in ["tv", "movie"]:
            url = f"https://api.themoviedb.org/3/search/{t}?api_key={TMDB_API_KEY}&query={clean(query)}"
            async with s.get(url) as r:
                j = await r.json()
                if not j.get("results"):
                    continue

                m = j["results"][0]
                genres = await tmdb_genres(m["genre_ids"], t)

                return {
                    "id": m["id"],
                    "title": m.get("name") or m.get("title"),
                    "type": "SERIES" if t == "tv" else "MOVIE",
                    "season": season if t == "tv" else "MOVIE",
                    "season_tag": f"S{season:02d}" if season else "",
                    "genres": genres,
                    "tmdb": f"https://themoviedb.org/{t}/{m['id']}",
                    "imdb": f"https://www.imdb.com/find?q={m.get('name') or m.get('title')}",
                    "poster": f"https://image.tmdb.org/t/p/w500{m['poster_path']}",
                    "language": "English, Hindi, Tamil, Telugu",
                    "channel": "<blockquote><b>RK CINEHUB #PREMIUM</b></blockquote>"
                }
    return None


async def tmdb_genres(ids, media):
    url = f"https://api.themoviedb.org/3/genre/{media}/list?api_key={TMDB_API_KEY}"
    async with aiohttp.ClientSession() as s:
        async with s.get(url) as r:
            j = await r.json()
            mp = {g["id"]: g["name"] for g in j["genres"]}
            return ", ".join(mp[i] for i in ids if i in mp)


def extract_season(text):
    m = re.search(r"S(\d{1,2})", text, re.I)
    return int(m.group(1)) if m else None


def clean(text):
    text = re.sub(r"\.(mkv|mp4|avi)", "", text, flags=re.I)
    text = re.sub(r"[._\-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()
