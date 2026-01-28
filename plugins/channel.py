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
posted_keys = set()

media_filter = filters.document | filters.video | filters.audio


@Client.on_message(filters.chat(CHANNELS) & media_filter)
async def media(bot, message):
    media = getattr(message, message.media.value, None)
    if not media:
        return

    if await save_file(media) != "suc":
        return

    raw = media.file_name or message.caption or ""
    await asyncio.sleep(POST_DELAY)
    await process(bot, raw)


async def process(bot, raw):
    data = await tmdb_engine(raw)
    if not data:
        return

    # 🔐 UNIQUE KEY (movie = id, series = id+season)
    ukey = f"{data['id']}_{data['season'] or 'MOVIE'}"
    if ukey in posted_keys:
        return
    posted_keys.add(ukey)

    caption = f"""
<blockquote><b>👉 RK CINEHUB #PREMIUM</b></blockquote>

<b>✅ {data['title']} {data['tag']} #{data['type']}</b>

<blockquote>🎙 <b>{data['language']}</b></blockquote>

⭐ <a href="{data['imdb']}"><b>IMDb</b></a> | 🎭 <a href="{data['tmdb']}"><b>TMDB</b></a>
🎥 <b>Genre:</b> {data['genres']}
"""

    btn = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔍 Tap to Search", url=SEARCH_LINK)]]
    )

    await bot.send_photo(
        chat_id=MOVIE_UPDATE_CHANNEL,
        photo=data["poster"],
        caption=caption.strip(),
        reply_markup=btn,
        parse_mode=enums.ParseMode.HTML,
        has_spoiler=True
    )


# ================= TMDB CORE ================= #

async def tmdb_engine(query):
    q = clean(query)
    season = get_season(q)

    async with aiohttp.ClientSession() as s:
        for mtype in ["movie", "tv"]:
            url = f"https://api.themoviedb.org/3/search/{mtype}?api_key={TMDB_API_KEY}&query={q}"
            async with s.get(url) as r:
                js = await r.json()
                if not js.get("results"):
                    continue

                it = js["results"][0]
                genres = await tmdb_genres(it["genre_ids"], mtype)
                title = it.get("title") or it.get("name")
                year = (it.get("release_date") or it.get("first_air_date") or "")[:4]

                return {
                    "id": it["id"],
                    "title": f"{title} {year}".strip() if mtype == "movie" else title,
                    "type": "SERIES" if mtype == "tv" else "MOVIE",
                    "season": season if mtype == "tv" else None,
                    "tag": f"S{season:02d}" if season and mtype == "tv" else "",
                    "genres": genres,
                    "tmdb": f"https://www.themoviedb.org/{mtype}/{it['id']}",
                    "imdb": f"https://www.imdb.com/find?q={title}",
                    "poster": f"https://image.tmdb.org/t/p/w500{it['poster_path']}",
                    "language": detect_lang(query),
                }
    return None


async def tmdb_genres(ids, mtype):
    url = f"https://api.themoviedb.org/3/genre/{mtype}/list?api_key={TMDB_API_KEY}"
    async with aiohttp.ClientSession() as s:
        async with s.get(url) as r:
            js = await r.json()
            mp = {g["id"]: g["name"] for g in js["genres"]}
            return ", ".join(mp[i] for i in ids if i in mp)


# ================= HELPERS ================= #

def get_season(text):
    m = re.search(r"S(\d{1,2})", text, re.I)
    return int(m.group(1)) if m else None


def clean(t):
    t = re.sub(r"\.(mkv|mp4|avi|mov)", "", t, flags=re.I)
    t = re.sub(r"[._\-]", " ", t)
    t = re.sub(
        r"\b(480p|720p|1080p|2160p|4k|webdl|webrip|bluray|x264|x265|aac|ddp|atmos|subs|dual|multi)\b",
        "",
        t,
        flags=re.I,
    )
    return re.sub(r"\s+", " ", t).strip()


def detect_lang(t):
    langs = ["Hindi","English","Tamil","Telugu","Malayalam","Kannada","Punjabi","Tagalog"]
    found = [l for l in langs if l.lower() in t.lower()]
    return ", ".join(found) if found else "Not Available"
