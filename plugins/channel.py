# --| Netflix Style Auto Poster System |--#
# --| Created by: Jisshu_bots & SilentXBotz |--#
# --| Final Enhanced by: Jarvis |--#

import re
import asyncio
import aiohttp
from collections import defaultdict

from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from info import *
from utils import get_poster
from database.users_chats_db import db
from database.ia_filterdb import save_file


# ================= CONFIG ================= #

POST_DELAY = 10

UPDATE_CAPTION = """<blockquote><b>💯 NEW FILES ADDED ✅</b></blockquote>

🖥 𝙁𝙞𝙡𝙚 𝙉𝙖𝙢𝙚: <code>{title}</code>

♻️ 𝘾𝙖𝙩𝙚𝙜𝙤𝙧𝙮: {category}
{season_block}
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


# ================= HELPERS ================= #

def normalize_movie_title(name: str) -> str:
    name = name.lower()
    name = re.sub(r"(19|20)\d{2}.*", "", name)
    name = re.sub(r"[._\-()\[\]]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name.title()


def normalize_series_title(name: str):
    """
    Show Name S01E01 -> Show Name S01
    """
    name = name.lower()

    s = re.search(r"s(\d{1,2})", name)
    season = f"S{s.group(1)}" if s else ""

    name = re.sub(r"s\d{1,2}e\d{1,2}", "", name)
    name = re.sub(r"[._\-()\[\]]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()

    return f"{name.title()} {season}".strip(), season


def detect_category(text: str):
    if re.search(r"s\d{1,2}e\d{1,2}", text.lower()):
        return "#Series"
    return "#Movies"


def detect_quality(text: str):
    return [q for q in ["480p","720p","1080p","2160p"] if q in text.lower()]


def detect_format(text: str):
    t = text.lower()
    f = []
    if "web" in t: f.append("WEB")
    if "bluray" in t: f.append("BluRay")
    if "hdrip" in t: f.append("HDRip")
    if "x265" in t or "hevc" in t: f.append("HEVC")
    return f or ["I Don't Know 😅"]


def detect_audio(text: str):
    return [l.title() for l in LANGS if l in text.lower()]


def merge(v):
    return ", ".join(sorted(set(v))) or "I don't know 😅"


# ================= POSTER ================= #

async def fetch_movie_poster(title: str):
    try:
        imdb = await get_poster(title)
        if imdb and imdb.get("fanart"):
            return imdb["fanart"]
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
    if await save_file(media) != "suc":
        return

    await queue(bot, media)


# ================= QUEUE ================= #

async def queue(bot, media):
    raw = f"{media.file_name} {media.caption or ''}"

    if detect_category(raw) == "#Series":
        title, season = normalize_series_title(media.file_name)
    else:
        title = normalize_movie_title(media.file_name)
        season = ""

    bucket[title].append({
        "q": detect_quality(raw),
        "f": detect_format(raw),
        "a": detect_audio(raw),
        "c": detect_category(raw),
        "s": season
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
    season = files[0]["s"]
    recent = len(files)

    season_block = ""
    if category == "#Series" and season:
        season_block = f"\n📺 <b>Season:</b> {season}\n🎬 <b>Episodes Added:</b> {recent}\n"

    caption = UPDATE_CAPTION.format(
        title=title,
        category=category,
        season_block=season_block,
        quality=merge(q),
        format=merge(f),
        audio=merge(a),
        recent=recent,
        total=recent
    )

    buttons = InlineKeyboardMarkup(
        [[InlineKeyboardButton("⍟ᴍᴏᴠɪᴇ ʀᴇǫᴜᴇsᴛ ɢʀᴏᴜᴘ⍟", url="https://t.me/Rk2x_Request")]]
    )

    poster = await fetch_movie_poster(title)
    chat_id = MOVIE_UPDATE_CHANNEL

    if title in POSTED:
        await bot.edit_message_caption(
            chat_id,
            POSTED[title],
            caption,
            reply_markup=buttons,
            parse_mode=enums.ParseMode.HTML
        )
        return

    msg = await bot.send_photo(
        chat_id,
        poster,
        caption=caption,
        reply_markup=buttons,
        parse_mode=enums.ParseMode.HTML
    )

    POSTED[title] = msg.id
