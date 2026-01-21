# --| This code created by: Jisshu_bots & SilentXBotz |--#
# --| Final Enhanced & Verified by: Jarvis |--#

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
    "Bhojpuri","Hindi","Bengali","Tamil","English","Bangla",
    "Telugu","Malayalam","Kannada","Marathi","Punjabi","Gujarati",
    "Spanish","French","German","Chinese","Arabic","Portuguese",
    "Russian","Japanese","Urdu"
]

POST_DELAY = 10

UPDATE_CAPTION = """<blockquote><b>𝖭𝖤𝖶 {} 𝖠𝖣𝖣𝖤𝖣 ✅</b></blockquote>

🎬 <code>{}</code> | {}
🔰 <b>Quality: {}</b>
🎧 <b>Audio: {}</b>

<blockquote><b>✨ Telegram Files ✨</b></blockquote>

{}

<blockquote><b>〽️ Powered by➠ @RkCineHub</b></blockquote>
"""

REQUEST_BUTTON = InlineKeyboardMarkup(
    [[InlineKeyboardButton("🎬 MOVIE REQUEST GROUP", url="https://t.me/Rk2x_Request")]]
)

media_filter = filters.document | filters.video | filters.audio

notified_movies = set()
movie_files = defaultdict(list)
processing_movies = set()


# ================= MEDIA HANDLER ================= #

@Client.on_message(filters.chat(CHANNELS) & media_filter)
async def media_handler(bot, message):
    media = getattr(message, message.media.value, None)
    if not media:
        return

    media.file_type = message.media.value
    media.caption = message.caption

    if await save_file(media) == "suc" and await db.get_send_movie_update_status(bot.me.id):
        await queue_movie_file(bot, media)


# ================= QUEUE FILE ================= #

async def queue_movie_file(bot, media):
    file_name = await movie_name_format(media.file_name)
    caption = await movie_name_format(media.caption or "")

    year_match = re.search(r"\b(19|20)\d{2}\b", caption)
    year = year_match.group(0) if year_match else None

    quality = detect_quality(caption + " " + media.file_name)
    language = ", ".join([l for l in CAPTION_LANGUAGES if l.lower() in caption.lower()]) or "Not Idea"

    file_id, _ = unpack_new_file_id(media.file_id)

    movie_files[file_name].append({
        "file_id": file_id,
        "quality": quality,
        "file_size": format_file_size(media.file_size),
        "language": language,
        "year": year
    })

    if file_name in processing_movies:
        return

    processing_movies.add(file_name)
    await asyncio.sleep(POST_DELAY)

    await send_movie_update(bot, file_name, movie_files[file_name])

    movie_files.pop(file_name, None)
    processing_movies.discard(file_name)


# ================= SEND UPDATE ================= #

async def send_movie_update(bot, file_name, files):
    if file_name in notified_movies:
        return
    notified_movies.add(file_name)

    imdb = await get_imdb(file_name)
    title = imdb.get("title", file_name)
    kind = imdb.get("kind", "MOVIE").upper()
    kind = "SERIES" if kind == "TV_SERIES" else "MOVIE"

    tmdb = await fetch_tmdb_hd(title, files[0]["year"])
    poster = tmdb.get("poster")

    quality_text = ""
    for f in files:
        quality_text += (
            f"📦 {f['quality']} : "
            f"<a href='https://t.me/{temp.U_NAME}?start=file_0_{f['file_id']}'>"
            f"{f['file_size']}</a>\n"
        )

    caption = UPDATE_CAPTION.format(
        kind,
        title,
        files[0]["year"] or "",
        files[0]["quality"],
        files[0]["language"],
        quality_text
    )

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("☑ VIEW HD PHOTO", callback_data=f"hdphoto|{title}|{files[0]['year']}")],
        [InlineKeyboardButton("🎬 MOVIE REQUEST GROUP", url="https://t.me/Rk2x_Request")]
    ])

    await bot.send_photo(
        chat_id=await db.movies_update_channel_id() or MOVIE_UPDATE_CHANNEL,
        photo=poster or "https://te.legra.ph/file/88d845b4f8a024a71465d.jpg",
        caption=caption,
        parse_mode=enums.ParseMode.HTML,
        reply_markup=buttons
    )


# ================= CALLBACK (HD PHOTO) ================= #

@Client.on_callback_query(filters.regex("^hdphoto"))
async def hd_photo_handler(bot, query):
    _, title, year = query.data.split("|")

    tmdb = await fetch_tmdb_hd(title, year)
    image = tmdb.get("backdrop") or tmdb.get("poster")

    if not image:
        return await query.answer("HD photo not found ❌", show_alert=True)

    await query.message.reply_photo(
        photo=image,
        caption="🎬 TMDB ORIGINAL HD PHOTO"
    )


# ================= TMDB FETCH ================= #

async def fetch_tmdb_hd(title, year=None):
    params = {
        "api_key": TMDB_API_KEY,
        "query": title,
        "year": year
    }

    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.themoviedb.org/3/search/movie", params=params) as r:
            data = await r.json()

    if not data.get("results"):
        return {}

    m = data["results"][0]
    return {
        "poster": f"https://image.tmdb.org/t/p/original{m['poster_path']}" if m.get("poster_path") else None,
        "backdrop": f"https://image.tmdb.org/t/p/original{m['backdrop_path']}" if m.get("backdrop_path") else None
    }


# ================= HELPERS ================= #

async def get_imdb(name):
    try:
        return await get_poster(await movie_name_format(name)) or {}
    except:
        return {}

def detect_quality(text):
    text = text.lower()
    for q in ["2160p","1080p","720p","480p"]:
        if q in text:
            return q
    return "720p"

async def movie_name_format(name):
    return re.sub(r"[^\w\s]", " ", name or "").replace("_"," ").strip()

def format_file_size(size):
    for u in ["B","KB","MB","GB","TB"]:
        if size < 1024:
            return f"{size:.2f} {u}"
        size /= 1024
