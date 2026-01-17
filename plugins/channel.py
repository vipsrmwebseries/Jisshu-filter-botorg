# --| Netflix Style Auto Poster System |--#
# --| Created by: Jisshu_bots & SilentXBotz |--#
# --| Fixed by: Jarvis |--#

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
from database.ia_filterdb import save_file, Media   # 🔥 SAME DB
from database.users_chats_db import db


# ================= CONFIG ================= #

POST_DELAY = 10

UPDATE_CAPTION = """<blockquote><b>💯 NEW FILES ADDED ✅</b></blockquote>

🖥 𝙁𝙞𝙡𝙚 𝙉𝙖𝙢𝙚: <code>{title}</code>

♻️ 𝘾𝙖𝙩𝙚𝙜𝙤𝙧𝙮: {category}

🎞 𝙌𝙪𝙖𝙡𝙞𝙩𝙮: <b>{quality}</b>

💿 𝙁𝙤𝙧𝙢𝙖𝙩: <b>{format}</b>

🌍 𝘼𝙪𝙙𝙞𝙤: <b>{audio}</b>

📁 𝙍𝙚𝙘𝙚𝙣𝙩𝙡𝙮 𝘼𝙙𝙙𝙚𝙙 𝙁𝙞𝙡𝙚𝙨: <b>{recent}</b>

🗄 𝙏𝙤𝙩𝙖𝙡 𝙁𝙞𝙡𝙚𝙨: <b>{total}</b>
"""

LANGS = [
    "hindi","english","tamil","telugu","kannada",
    "malayalam","marathi","bengali","punjabi"
]

bucket = defaultdict(list)
LOCKED = set()
POSTED = {}


# ================= DB KEY ================= #

def db_key(title: str) -> str:
    title = title.lower()
    title = re.sub(r"(19|20)\d{2}", "", title)
    title = re.sub(r"[^a-z0-9]", "", title)
    return title


# ================= HELPERS ================= #

def normalize_title(name: str) -> str:
    name = name.lower()
    remove = [
        "2160p","1080p","720p","480p",
        "hevc","x264","x265","h264","h265",
        "web","web-dl","webdl","hdrip","bluray","hdtv",
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


def detect_category(text: str):
    if re.search(r"s\d{1,2}|season|episode|e\d{1,2}", text.lower()):
        return "#Series"
    return "#Movies"


def detect_quality(text: str):
    t = text.lower()
    return [q for q in ["480p","720p","1080p","2160p"] if q in t]


def detect_format(text: str):
    t = text.lower()
    if "hdts" in t:
        return ["HDTS"]
    if "hdtc" in t:
        return ["HDTC"]
    if "cam" in t:
        return ["CAM"]

    f = []
    if "web" in t:
        f.append("WEB")
    if "bluray" in t or "bdrip" in t:
        f.append("BluRay")
    if "hdrip" in t:
        f.append("HDRip")
    if "hevc" in t or "x265" in t:
        f.append("HEVC")

    return f or ["I don't know 😅"]


def detect_audio(text: str):
    t = text.lower()
    return [l.title() for l in LANGS if l in t]


def merge(v):
    return ", ".join(sorted(set(v))) or "I don't know😅"


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
    raw = f"{media.file_name} {media.caption or ''}"
    title = normalize_title(media.file_name)

    bucket[title].append({
        "q": detect_quality(raw),
        "f": detect_format(raw),
        "a": detect_audio(raw),
        "c": detect_category(raw),
        "k": db_key(raw)   # 🔥 REAL DB KEY
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
    q, f, a = [], [], []
    for x in files:
        q += x["q"]
        f += x["f"]
        a += x["a"]

    category = files[0]["c"]
    recent = len(files)

    db_real_key = files[0]["k"]  # 🔥 EXACT SAME KEY AS SAVE

    try:
        total = await Media.count_documents({"file_name": db_real_key})
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
            url="https://t.me/Rk2x_Request"
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
