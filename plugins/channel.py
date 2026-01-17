# --| Netflix Style Auto Poster System |--#
# --| Created by: Jisshu_bots & SilentXBotz |--#

import re
import asyncio
import hashlib
import aiohttp
from collections import defaultdict
from typing import Optional

from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from info import *
from utils import get_poster
from database.users_chats_db import db
from database.ia_filterdb import save_file


# ================= CONFIG ================= #

POST_DELAY = 10

UPDATE_CAPTION = """<blockquote><b>💯 NEW FILES ADDED ✅</b></blockquote>

🖥 <b>File name:</b> <code>{title}</code>

♻️ <b>Category:</b> {category}

🎞 <b>Quality: {quality}</b>

💿 <b>Format: {format}</b>

🌍 <b>Audio: {audio}</b>

📁 <b>Recently Added Files:</b> {recent}
🗄 <b>Total Files:</b> {total}
"""

LANGS = [
    "hindi","english","tamil","telugu","kannada",
    "malayalam","marathi","bengali","punjabi"
]

bucket = defaultdict(list)
LOCKED = set()
POSTED = {}


# ================= TITLE CLEAN ================= #

def normalize_title(name: str) -> str:
    name = name.lower()

    remove = [
        "2160p","1080p","720p","480p",
        "hevc","x264","x265","h264","h265",
        "web","web-dl","webdl","hdrip","bluray",
        "aac","aac2","aac5","dd","ddp","5.1","2.0",
        "hindi","english","tamil","telugu","kannada",
        "malayalam","marathi","bengali","punjabi",
        "esub","sub","mkv","mp4"
    ]

    for r in remove:
        name = re.sub(rf"\b{r}\b", "", name)

    year = re.search(r"(19|20)\d{2}", name)
    year = year.group(0) if year else ""

    name = re.sub(r"(19|20)\d{2}.*", "", name)
    name = re.sub(r"[._\-()\[\]]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()

    return f"{name.title()} {year}".strip()


# ================= AUTO DETECT ================= #

def detect_category(text: str):
    if re.search(r"s\d{1,2}|season|episode|e\d{1,2}", text.lower()):
        return "#Series"
    return "#Movies"


def detect_quality(text: str):
    return [q for q in ["480p","720p","1080p","2160p"] if q in text.lower()]


def detect_format(text: str):
    t = text.lower()
    f = []
    if "hevc" in t or "x265" in t:
        f.append("HEVC")
    if "web" in t:
        f.append("WEB")
    if "bluray" in t:
        f.append("BluRay")
    if "hdrip" in t:
        f.append("HDRip")
    return f


def detect_audio(text: str):
    t = text.lower()
    return [l.title() for l in LANGS if l in t]


def merge(v):
    return ", ".join(sorted(set(v))) or "Unknown"


def hid(text):
    return hashlib.md5(text.encode()).hexdigest()[:6]


# ================= NETFLIX STYLE POSTER ================= #

async def fetch_movie_poster(title: str) -> str:
    """
    NETFLIX RULE:
    ✔ fanart / backdrop only (16:9)
    ❌ portrait posters blocked
    """
    try:
        imdb = await get_poster(title)
        if imdb:
            if imdb.get("fanart"):
                return imdb["fanart"]   # ✅ BEST 16:9
            if imdb.get("cover"):
                return imdb["cover"]    # ✅ LANDSCAPE
    except:
        pass

    # Backup (mostly landscape)
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://jisshuapis.vercel.app/api.php?query={title.replace(' ', '+')}"
            async with session.get(url, timeout=5) as r:
                if r.status == 200:
                    data = await r.json()
                    for k in ("jisshu-4","jisshu-3"):
                        if data.get(k):
                            return data[k][0]
    except:
        pass

    return "https://graph.org/file/ac3e879a72b7e0c90eb52-0b04163efc1dcbd378.jpg"


# ================= MEDIA HANDLER ================= #

@Client.on_message(filters.chat(CHANNELS) & (filters.video | filters.document))
async def media_handler(bot, message):
    media = getattr(message, message.media.value, None)
    if not media:
        return

    media.caption = message.caption or ""
    ok = await save_file(media)
    if ok != "suc":
        return

    await queue(bot, media)


# ================= QUEUE ================= #

async def queue(bot, media):
    raw = f"{media.file_name} {media.caption}"
    title = normalize_title(media.file_name)

    bucket[title].append({
        "q": detect_quality(raw),
        "f": detect_format(raw),
        "a": detect_audio(raw),
        "c": detect_category(raw)
    })

    if title in LOCKED:
        return

    LOCKED.add(title)
    await asyncio.sleep(POST_DELAY)

    files = bucket.pop(title, [])
    LOCKED.discard(title)

    if files:
        await send_or_edit(bot, title, files)


# ================= SEND / EDIT ================= #

async def send_or_edit(bot, title, files):
    q,f,a = [],[],[]
    for x in files:
        q += x["q"]
        f += x["f"]
        a += x["a"]

    category = files[0]["c"]
    recent = len(files)

    try:
        total = await db.get_movie_files_count(title)
    except:
        total = recent

    caption = UPDATE_CAPTION.format(
        title=title,
        category=category,
        quality=merge(q),
        format=merge(f),
        audio=merge(a),
        recent=recent,
        total=total
    )

    buttons = InlineKeyboardMarkup(
        [[InlineKeyboardButton(
            "⍟ᴍᴏᴠɪᴇ ʀᴇǫᴜᴇsᴛ ɢʀᴏᴜᴘ⍟",
            url=f"https://t.me/Rk2x_Request"
        )]]
    )

    poster = await fetch_movie_poster(title)
    chat_id = await db.movies_update_channel_id() or MOVIE_UPDATE_CHANNEL

    if title in POSTED:
        try:
            await bot.edit_message_media(
                chat_id,
                POSTED[title],
                enums.InputMediaPhoto(
                    media=poster,
                    caption=caption,
                    parse_mode=enums.ParseMode.HTML,
                    has_spoiler=True
                ),
                reply_markup=buttons
            )
            return
        except:
            pass

    msg = await bot.send_photo(
        chat_id=chat_id,
        photo=poster,
        caption=caption,
        reply_markup=buttons,
        has_spoiler=True,
        parse_mode=enums.ParseMode.HTML
    )

    POSTED[title] = msg.id
