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


CAPTION_LANGUAGES = [
    "Bhojpuri","Hindi","Bengali","Tamil","English","Bangla","Telugu",
    "Malayalam","Kannada","Marathi","Punjabi","Gujarati","Korean",
    "Spanish","French","German","Chinese","Arabic","Portuguese",
    "Russian","Japanese","Odia","Assamese","Urdu",
]

UPDATE_CAPTION = """<blockquote><b>💯 NEW FILES ADDED ✅</b></blockquote>

🗂 <b>File name:</b><code>{title}</code>

♻️ <b>Category:</b> #{category}
🎞 <b>Quality: {quality}</b>
📀 <b>Format: {format}</b>
🌍 <b>Audio: {language}</b>

{extra}📁 <b>Recently Added Files:</b> {recent}
🗄 <b>Total Files:</b> {total}
"""

POST_DELAY = 10

media_filter = filters.document | filters.video | filters.audio

movie_files = defaultdict(list)
processing_movies = set()
notified_movies = set()


@Client.on_message(filters.chat(CHANNELS) & media_filter)
async def media(bot, message):
    media = getattr(message, message.media.value, None)
    if not media:
        return

    if media.mime_type not in ["video/mp4", "video/x-matroska", "document/mp4"]:
        return

    media.file_type = message.media.value
    media.caption = message.caption or ""

    success = await save_file(media)
    if success == "suc" and await db.get_send_movie_update_status(bot.me.id):
        await queue_movie_file(bot, media)


async def queue_movie_file(bot, media):
    try:
        file_name = await movie_name_format(media.file_name)
        caption = await movie_name_format(media.caption)

        year_match = re.search(r"\b(19|20)\d{2}\b", caption)
        year = year_match.group(0) if year_match else None

        quality = await get_qualities(caption)
        jisshuquality = await Jisshu_qualities(caption, media.file_name)

        language = (
            ", ".join([l for l in CAPTION_LANGUAGES if l.lower() in caption.lower()])
            or "Not Idea"
        )

        size = format_file_size(media.file_size)
        file_id, _ = unpack_new_file_id(media.file_id)

        movie_files[file_name].append({
            "file_id": file_id,
            "caption": caption,
            "quality": quality,
            "jisshuquality": jisshuquality,
            "language": language,
            "file_size": size,
            "year": year
        })

        if file_name in processing_movies:
            return

        processing_movies.add(file_name)
        await asyncio.sleep(POST_DELAY)

        await send_movie_update(bot, file_name, movie_files[file_name])
        movie_files.pop(file_name, None)
        processing_movies.remove(file_name)

    except Exception as e:
        processing_movies.discard(file_name)
        await bot.send_message(LOG_CHANNEL, f"Movie Update Error:\n{e}")


async def send_movie_update(bot, file_name, files):
    if file_name in notified_movies:
        return
    notified_movies.add(file_name)

    imdb = await get_imdb(file_name)
    title = imdb.get("title", file_name)

    kind = imdb.get("kind", "MOVIE").upper()
    if kind == "TV_SERIES":
        kind = "SERIES"

    category = "Series" if kind == "SERIES" else "Movies"

    # Languages
    langs = set()
    for f in files:
        if f["language"] != "Not Idea":
            langs.update(f["language"].split(", "))
    language = ", ".join(sorted(langs)) or "Not Idea"

    # Qualities
    qualities = sorted({f["jisshuquality"] for f in files})

    # Episode range (Series only)
    episodes = []
    for f in files:
        m = re.search(r"E(\d{2})", f["caption"], re.I)
        if m:
            episodes.append(int(m.group(1)))

    extra = ""
    if category == "Series" and episodes:
        extra = f"🆕 <b>New Episode:</b> E{min(episodes):02d} to E{max(episodes):02d}\n\n"

    poster = await fetch_movie_poster(title, files[0]["year"])
    image = poster or "https://te.legra.ph/file/88d845b4f8a024a71465d.jpg"

    caption = UPDATE_CAPTION.format(
        title=title,
        category=category,
        quality=", ".join(qualities),
        format=files[0]["quality"],
        language=language,
        extra=extra,
        recent=len(files),
        total=len(files)
    )

    buttons = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton(
                "📥 Get Files",
                url=f"https://t.me/{temp.U_NAME}?start=all_{generate_unique_id(file_name)}"
            )
        ]]
    )

    channel = await db.movies_update_channel_id()

    await bot.send_photo(
        chat_id=channel or MOVIE_UPDATE_CHANNEL,
        photo=image,
        caption=caption,
        reply_markup=buttons,
        parse_mode=enums.ParseMode.HTML,
        has_spoiler=True
    )


async def get_imdb(file_name):
    try:
        name = await movie_name_format(file_name)
        imdb = await get_poster(name)
        if not imdb:
            return {}
        return {
            "title": imdb.get("title", name),
            "kind": imdb.get("kind", "Movie"),
            "year": imdb.get("year"),
        }
    except:
        return {}


async def fetch_movie_poster(title: str, year: Optional[int] = None):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                f"https://jisshuapis.vercel.app/api.php?query={title.replace(' ','+')}",
                timeout=5
            ) as r:
                data = await r.json()
                for k in ["jisshu-2", "jisshu-3", "jisshu-4"]:
                    if data.get(k):
                        return data[k][0]
        except:
            return None


def generate_unique_id(name):
    return hashlib.md5(name.encode()).hexdigest()[:6]


async def get_qualities(text):
    for q in ["2160p","1080p","720p","480p","HDRip","WEB-DL","CAMRip"]:
        if q.lower() in text.lower():
            return q
    return "HDRip"


async def Jisshu_qualities(text, fname):
    for q in ["2160p","1080p","720p","480p"]:
        if q in (text + fname):
            return q
    return "720p"


async def movie_name_format(name):
    return re.sub(r"[.@_\-\[\]\(\)]", " ", name).strip()


def format_file_size(size):
    for u in ["B","KB","MB","GB","TB"]:
        if size < 1024:
            return f"{size:.2f} {u}"
        size /= 1024
    return "N/A"
