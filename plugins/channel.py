# --| This code created by: Jisshu_bots & SilentXBotz |--#

import re
import hashlib
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


POST_DELAY = 40   # IMPORTANT for single post batching

CAPTION_LANGUAGES = [
    "Hindi","English","Bengali","Tamil","Telugu","Malayalam",
    "Kannada","Marathi","Punjabi","Gujarati","Korean","Spanish",
    "French","German","Chinese","Arabic","Portuguese","Russian",
    "Japanese","Odia","Assamese","Urdu"
]

UPDATE_CAPTION = """<b>💯 NEW FILES ADDED ✅</b>

📁 <b>File name:</b> {title}

♻️ <b>Category:</b> #{category}
🎞 <b>Quality:</b> {quality}
💿 <b>Format:</b> {format}
🌍 <b>Audio:</b> {language}

{extra}📂 <b>Recently Added Files:</b> {recent}
🗄 <b>Total Files:</b> {total}
"""


media_filter = filters.document | filters.video

movie_files = defaultdict(list)
processing_movies = set()


# ================= MEDIA HANDLER ================= #

@Client.on_message(filters.chat(CHANNELS) & media_filter)
async def media(bot, message):
    media = getattr(message, message.media.value, None)
    if not media:
        return

    if media.mime_type not in ["video/mp4", "video/x-matroska", "document/mp4"]:
        return

    media.caption = message.caption or ""
    success = await save_file(media)

    if success == "suc" and await db.get_send_movie_update_status(bot.me.id):
        await queue_movie_file(bot, media)


# ================= QUEUE HANDLER ================= #

async def queue_movie_file(bot, media):
    file_name = await movie_name_format(media.file_name)

    movie_files[file_name].append({
        "file_id": unpack_new_file_id(media.file_id)[0],
        "caption": media.caption,
        "size": media.file_size
    })

    if file_name in processing_movies:
        return

    processing_movies.add(file_name)
    await asyncio.sleep(POST_DELAY)

    files = movie_files.pop(file_name, [])
    processing_movies.discard(file_name)

    if files:
        await send_movie_update(bot, file_name, files)


# ================= SEND UPDATE ================= #

async def send_movie_update(bot, file_name, files):
    imdb = await get_imdb(file_name)
    title = imdb.get("title", file_name)

    kind = imdb.get("kind", "Movie").upper()
    if kind == "TV_SERIES":
        kind = "SERIES"

    category = "Series" if kind == "SERIES" else "Movies"

    # Languages
    langs = set()
    for f in files:
        for l in CAPTION_LANGUAGES:
            if l.lower() in f["caption"].lower():
                langs.add(l)
    language = ", ".join(sorted(langs)) or "Unknown"

    # Quality
    qualities = set()
    for f in files:
        q = extract_quality(f["caption"])
        if q:
            qualities.add(q)
    quality = ", ".join(sorted(qualities)) or "720p"

    # Format
    format_ = extract_format(" ".join(f["caption"] for f in files))

    # Episode Range (Series)
    episodes = []
    for f in files:
        m = re.search(r"E(\d{2})", f["caption"], re.I)
        if m:
            episodes.append(int(m.group(1)))

    extra = ""
    if category == "Series" and episodes:
        extra = f"🆕 <b>New Episode:</b> E{min(episodes):02d} to E{max(episodes):02d}\n\n"

    poster = await fetch_movie_poster(title)
    image = poster or "https://te.legra.ph/file/88d845b4f8a024a71465d.jpg"

    caption = UPDATE_CAPTION.format(
        title=title,
        category=category,
        quality=quality,
        format=format_,
        language=language,
        extra=extra,
        recent=len(files),
        total=len(files)
    )

    buttons = InlineKeyboardMarkup(
        [[InlineKeyboardButton(
            "📥 Get Files",
            url=f"https://t.me/{temp.U_NAME}?start=all_{generate_unique_id(file_name)}"
        )]]
    )

    channel = await db.movies_update_channel_id()

    await bot.send_photo(
        chat_id=channel or MOVIE_UPDATE_CHANNEL,
        photo=image,
        caption=caption,
        reply_markup=buttons,
        parse_mode=enums.ParseMode.HTML
    )


# ================= HELPERS ================= #

async def get_imdb(name):
    try:
        data = await get_poster(name)
        if not data:
            return {}
        return {
            "title": data.get("title", name),
            "kind": data.get("kind", "Movie")
        }
    except:
        return {}


async def fetch_movie_poster(title: str):
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


def extract_quality(text):
    for q in ["2160p","1080p","720p","480p"]:
        if q.lower() in text.lower():
            return q
    return None


def extract_format(text):
    text = text.lower()
    if "web-dl" in text or "web dl" in text:
        return "WEB-DL"
    if "bluray" in text:
        return "BluRay"
    if "hdrip" in text:
        return "HDRip"
    if "dvdrip" in text:
        return "DVDRip"
    return "HDRip"


async def movie_name_format(name):
    name = name.lower()
    remove = [
        "1080p","720p","480p","2160p","web","web-dl","bluray",
        "hdrip","dvdrip","x264","x265","aac","hevc","mkv","mp4",
        "hindi","english","bengali","tamil","telugu"
    ]
    for r in remove:
        name = name.replace(r, "")
    name = re.sub(r"[.\-_@\[\]\(\)]", " ", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip().title()


def generate_unique_id(name):
    return hashlib.md5(name.encode()).hexdigest()[:6]
