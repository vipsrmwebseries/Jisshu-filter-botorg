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
from utils import *
from database.users_chats_db import db
from database.ia_filterdb import save_file, unpack_new_file_id


# ================= CONFIG ================= #

POST_DELAY = 10

CAPTION_LANGUAGES = [
    "hindi","english","tamil","telugu","kannada",
    "malayalam","marathi","bengali","punjabi"
]

UPDATE_CAPTION = """<blockquote><b>💯 NEW FILES ADDED ✅</b></blockquote>

🖥 <b>File name:</b> <code>{title}</code>

♻️ <b>Category:</b> #{category}
🎞 <b>Quality:</b> {qualities}
💿 <b>Format:</b> {formats}
🌍 <b>Audio:</b> {audios}

📁 <b>Recently Added Files:</b> {recent}
🗄 <b>Total Files:</b> {total}
"""

# ================= GLOBAL STORES ================= #

movie_bucket = defaultdict(list)       # title -> file infos
processing = set()                     # titles under processing
posted_messages = {}                   # title -> message_id


# ================= NORMALIZE TITLE ================= #

def normalize_title(name: str) -> str:
    name = name.lower()

    remove_words = [
        "2160p","1080p","720p","480p",
        "hevc","x264","x265","h264","h265",
        "web-dl","webdl","hdrip","bluray","hdtv",
        "aac","aac2","aac5","ddp","esub","mkv","mp4"
    ]

    for w in remove_words:
        name = name.replace(w, "")

    name = re.sub(r"[._\-()\[\]]", " ", name)
    name = re.sub(r"\s+", " ", name)

    return name.strip().title()


# ================= DETECTORS ================= #

def detect_category(text: str) -> str:
    if re.search(r"s\d{1,2}|season|episode|e\d{1,2}", text.lower()):
        return "#Series"
    return "#Movies"


def detect_quality(text: str):
    text = text.lower()
    return [q for q in ["480p","720p","1080p","2160p"] if q in text]


def detect_format(text: str):
    text = text.lower()
    fmts = []
    if "hevc" in text or "x265" in text:
        fmts.append("HEVC")
    if "web-dl" in text or "webdl" in text:
        fmts.append("WEB")
    if "bluray" in text:
        fmts.append("BluRay")
    if "hdrip" in text:
        fmts.append("HDRip")
    return fmts


def detect_audio(text: str):
    text = text.lower()
    return [a.title() for a in CAPTION_LANGUAGES if a in text]


def uniq(items):
    return ", ".join(sorted(set(items))) or "Unknown"


# ================= MEDIA HANDLER ================= #

@Client.on_message(filters.chat(CHANNELS) & (filters.video | filters.document))
async def media_handler(bot, message):
    media = getattr(message, message.media.value, None)
    if not media:
        return

    media.caption = message.caption or ""

    success = await save_file(media)
    if success != "suc":
        return

    await queue_file(bot, media)


# ================= QUEUE ================= #

async def queue_file(bot, media):
    raw_text = f"{media.file_name} {media.caption}"
    title = normalize_title(media.file_name)

    movie_bucket[title].append({
        "qualities": detect_quality(raw_text),
        "formats": detect_format(raw_text),
        "audios": detect_audio(raw_text),
        "category": detect_category(raw_text)
    })

    if title in processing:
        return

    processing.add(title)
    await asyncio.sleep(POST_DELAY)

    files = movie_bucket.pop(title, [])
    processing.discard(title)

    if files:
        await send_or_edit_post(bot, title, files)


# ================= SEND / EDIT ================= #

async def send_or_edit_post(bot, title, files):
    qualities, formats, audios = [], [], []

    for f in files:
        qualities += f["qualities"]
        formats += f["formats"]
        audios += f["audios"]

    category = files[0]["category"]
    recent_files = len(files)

    try:
        total_files = await db.get_movie_files_count(title)
    except:
        total_files = recent_files

    caption = UPDATE_CAPTION.format(
        title=title,
        category=category,
        qualities=uniq(qualities),
        formats=uniq(formats),
        audios=uniq(audios),
        recent=recent_files,
        total=total_files
    )

    buttons = InlineKeyboardMarkup(
        [[InlineKeyboardButton(
            "⍟ᴍᴏᴠɪᴇ ʀᴇǫᴜᴇsᴛ ɢʀᴏᴜᴘ⍟",
            url=f"https://t.me/Rk2x_Request"
        )]]
    )

    poster = await fetch_movie_poster(title)
    photo = poster or "https://te.legra.ph/file/88d845b4f8a024a71465d.jpg"

    chat_id = await db.movies_update_channel_id() or MOVIE_UPDATE_CHANNEL

    # 🔁 EDIT IF EXISTS
    if title in posted_messages:
        try:
            await bot.edit_message_media(
                chat_id=chat_id,
                message_id=posted_messages[title],
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

    # 🆕 SEND NEW
    msg = await bot.send_photo(
        chat_id=chat_id,
        photo=photo,
        caption=caption,
        reply_markup=buttons,
        has_spoiler=True,
        parse_mode=enums.ParseMode.HTML
    )

    posted_messages[title] = msg.id


# ================= HELPERS ================= #

def hash_id(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()[:6]


async def fetch_movie_poster(title: str) -> Optional[str]:
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                f"https://jisshuapis.vercel.app/api.php?query={title.replace(' ','+')}",
                timeout=5
            ) as r:
                data = await r.json()
                for k in ["jisshu-2","jisshu-3","jisshu-4"]:
                    if data.get(k):
                        return data[k][0]
        except:
            return None
