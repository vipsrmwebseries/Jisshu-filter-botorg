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

# ✅ PREMIUM CAPTION
UPDATE_CAPTION = """<b>RK CINEHUB #PREMIUM</b>

<b>✅ {title} {season_tag} #{kind}</b>

🎙 <b>{language}</b>

⭐ <b>IMDb</b> | 🎭 <b>TMDB</b>
🎥 <b>Genre:</b> {genre}

{quality_text}
"""

POST_DELAY = 10
notified_movies = set()
processing_movies = set()
movie_files = defaultdict(list)

media_filter = filters.document | filters.video | filters.audio


@Client.on_message(filters.chat(CHANNELS) & media_filter)
async def media(bot, message):
    media = getattr(message, message.media.value, None)
    if not media:
        return

    if media.mime_type in ["video/mp4", "video/x-matroska", "document/mp4"]:
        media.caption = message.caption or ""
        sts = await save_file(media)
        if sts == "suc" and await db.get_send_movie_update_status(bot.me.id):
            await queue_movie_file(bot, media)


async def queue_movie_file(bot, media):
    try:
        file_name = await movie_name_format(media.file_name or "")
        caption = await movie_name_format(media.caption or "")

        quality = await get_qualities(caption)
        jquality = await Jisshu_qualities(caption, media.file_name)

        language = (
            ", ".join(l for l in CAPTION_LANGUAGES if l.lower() in caption.lower())
            or "Not Available"
        )

        size = format_file_size(media.file_size)
        file_id, _ = unpack_new_file_id(media.file_id)

        movie_files[file_name].append({
            "file_id": file_id,
            "quality": jquality or quality,
            "file_size": size,
            "caption": caption,
            "language": language,
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
        await bot.send_message(LOG_CHANNEL, f"Update Error:\n<code>{e}</code>")


async def send_movie_update(bot, file_name, files):
    if file_name in notified_movies:
        return
    notified_movies.add(file_name)

    imdb = await get_imdb(file_name)

    title = imdb.get("title", file_name)
    kind = imdb.get("kind", "MOVIE").upper().replace(" ", "_")
    if kind == "TV_SERIES":
        kind = "SERIES"

    genre = imdb.get("genres", "Drama")

    season_tag = ""
    sm = re.search(r"S(\d{1,2})", file_name, re.I)
    if sm:
        season_tag = f"S{int(sm.group(1)):02d}"

    languages = set()
    for f in files:
        languages.update(f["language"].split(", "))
    language = ", ".join(sorted(languages))

    quality_text = ""
    for f in files:
        link = f"<a href='https://t.me/{temp.U_NAME}?start=file_0_{f['file_id']}'>{f['file_size']}</a>"
        quality_text += f"📦 {f['quality']} : {link}\n"

    poster = await fetch_movie_poster(title)
    poster = poster or "https://te.legra.ph/file/88d845b4f8a024a71465d.jpg"

    caption = UPDATE_CAPTION.format(
        title=title,
        season_tag=season_tag,
        kind=kind,
        language=language,
        genre=genre,
        quality_text=quality_text
    )

    # ✅ INLINE BUTTON (Tap to Search)
    buttons = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton(
                "🔍 Tap to Search",
                url=f"https://t.me/Rk2x_Request"
            )
        ]]
    )

    channel = await db.movies_update_channel_id() or MOVIE_UPDATE_CHANNEL

    await bot.send_photo(
        chat_id=channel,
        photo=poster,
        caption=caption,
        reply_markup=buttons,
        parse_mode=enums.ParseMode.HTML,
        has_spoiler=True
    )


async def get_imdb(name):
    try:
        data = await get_poster(await movie_name_format(name))
        if not data:
            return {}
        return {
            "title": data.get("title"),
            "kind": data.get("kind"),
            "genres": ", ".join(data.get("genres", []))
        }
    except:
        return {}


async def fetch_movie_poster(title: str):
    async with aiohttp.ClientSession() as session:
        url = f"https://jisshuapis.vercel.app/api.php?query={title.replace(' ', '+')}"
        try:
            async with session.get(url, timeout=5) as r:
                if r.status == 200:
                    data = await r.json()
                    for k in ["jisshu-2","jisshu-3","jisshu-4"]:
                        if data.get(k):
                            return data[k][0]
        except:
            pass
    return None


async def get_qualities(text):
    for q in ["2160p","1080p","720p","480p","HDRip","WEB-DL","CAMRip"]:
        if q.lower() in text.lower():
            return q
    return "720p"


async def Jisshu_qualities(text, name):
    for q in ["2160p","1080p","720p","480p"]:
        if q in text or q in name:
            return q
    return "720p"


async def movie_name_format(name):
    return re.sub(r"[.@#_\-\[\]\(\)]", " ", name).strip()


def format_file_size(size):
    for u in ["B","KB","MB","GB","TB"]:
        if size < 1024:
            return f"{size:.2f} {u}"
        size /= 1024
    return "N/A"
