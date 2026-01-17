# --| This code created by: Jisshu_bots & SilentXBotz |--#

import re
import hashlib
import asyncio
import aiohttp
from collections import defaultdict
from typing import Optional

from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from info import *
from utils import get_poster   # ⚠️ IMDB poster function
from database.users_chats_db import db
from database.ia_filterdb import save_file


# ================= SETTINGS ================= #

POST_DELAY = 10

UPDATE_CAPTION = """<blockquote><b>💯 NEW FILES ADDED ✅</b></blockquote>

🖥 <b>File name:</b> <code>{title}</code>

♻️ <b>Category:</b> {category}

🎞 <b>Quality: {qualities}</b>

💿 <b>Format: {formats}</b>

🌍 <b>Audio: {audios}</b>

📁 <b>Recently Added Files:</b> {recent}
🗄 <b>Total Files:</b> {total}
"""

LANGS = [
    "hindi","english","tamil","telugu","kannada",
    "malayalam","marathi","bengali","punjabi"
]


# ================= GLOBAL ================= #

bucket = defaultdict(list)       # title -> files
processing = set()
posted = {}                      # title -> message_id


# ================= HELPERS ================= #

def normalize_title(name: str) -> str:
    name = name.lower()
    remove = [
        "2160p","1080p","720p","480p",
        "hevc","x264","x265","h264","h265",
        "web-dl","webdl","hdrip","bluray","hdtv",
        "aac","aac2","aac5","ddp","esub","mkv","mp4"
    ]
    for r in remove:
        name = name.replace(r, "")
    name = re.sub(r"[._\-()\[\]]", " ", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip().title()


def detect_category(text: str) -> str:
    if re.search(r"s\d{1,2}|season|episode|e\d{1,2}", text.lower()):
        return "#Series"
    return "#Movies"


def detect_quality(text: str):
    return [q for q in ["480p","720p","1080p","2160p"] if q in text.lower()]


def detect_format(text: str):
    t = text.lower()
    fm = []
    if "hevc" in t or "x265" in t:
        fm.append("HEVC")
    if "web-dl" in t or "webdl" in t:
        fm.append("WEB")
    if "bluray" in t:
        fm.append("BluRay")
    if "hdrip" in t:
        fm.append("HDRip")
    return fm


def detect_audio(text: str):
    t = text.lower()
    return [l.title() for l in LANGS if l in t]


def uniq(values):
    return ", ".join(sorted(set(values))) or "Unknown"


def hash_id(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()[:6]


# ================= IMDB LANDSCAPE POSTER ================= #

async def fetch_movie_poster(title: str) -> Optional[str]:
    """
    Priority:
    1. IMDB landscape poster / fanart
    2. Backup API
    """
    # 🔥 IMDB FIRST
    try:
        imdb = await get_poster(title)
        if imdb:
            if imdb.get("fanart"):
                return imdb["fanart"]      # landscape
            if imdb.get("poster"):
                return imdb["poster"]
    except:
        pass

    # 🟡 BACKUP API
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://jisshuapis.vercel.app/api.php?query={title.replace(' ', '+')}"
            async with session.get(url, timeout=5) as r:
                if r.status == 200:
                    data = await r.json()
                    for k in ("jisshu-4","jisshu-3","jisshu-2"):
                        if data.get(k):
                            return data[k][0]
    except:
        pass

    return None


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

    await queue_file(bot, media)


# ================= QUEUE ================= #

async def queue_file(bot, media):
    raw = f"{media.file_name} {media.caption}"
    title = normalize_title(media.file_name)

    bucket[title].append({
        "qualities": detect_quality(raw),
        "formats": detect_format(raw),
        "audios": detect_audio(raw),
        "category": detect_category(raw)
    })

    if title in processing:
        return

    processing.add(title)
    await asyncio.sleep(POST_DELAY)
    files = bucket.pop(title, [])
    processing.discard(title)

    if files:
        await send_or_edit(bot, title, files)


# ================= SEND / EDIT ================= #

async def send_or_edit(bot, title, files):
    q, f, a = [], [], []

    for x in files:
        q += x["qualities"]
        f += x["formats"]
        a += x["audios"]

    category = files[0]["category"]
    recent = len(files)

    try:
        total = await db.get_movie_files_count(title)
    except:
        total = recent

    caption = UPDATE_CAPTION.format(
        title=title,
        category=category,
        qualities=uniq(q),
        formats=uniq(f),
        audios=uniq(a),
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
    photo = poster or "https://graph.org/file/ac3e879a72b7e0c90eb52-0b04163efc1dcbd378.jpg"

    chat_id = await db.movies_update_channel_id() or MOVIE_UPDATE_CHANNEL

    # 🔁 EDIT IF EXISTS
    if title in posted:
        try:
            await bot.edit_message_media(
                chat_id=chat_id,
                message_id=posted[title],
                media=enums.InputMediaPhoto(
                    media=photo,
                    caption=caption,
                    parse_mode=enums.ParseMode.HTML,
                    has_spoiler=True
                ),
                reply_markup=buttons
            )
            return
        except:
            pass

    # 🆕 SEND
    msg = await bot.send_photo(
        chat_id=chat_id,
        photo=photo,
        caption=caption,
        reply_markup=buttons,
        has_spoiler=True,
        parse_mode=enums.ParseMode.HTML
    )

    posted[title] = msg.id
