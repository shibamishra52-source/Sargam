 import os
import requests
import aiohttp
import aiofiles
import ffmpeg

from typing import Callable

from PIL import Image, ImageFont, ImageDraw

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import UserAlreadyParticipant

from youtube_search import YoutubeSearch

from callsmusic import callsmusic
from callsmusic.callsmusic import client as USER

from queues import queues
from cache.admins import admins as a

from helpers.admins import get_administrators
from helpers.filters import command, other_filters
from helpers.decorators import authorized_users_only

import converter
from downloaders import youtube
from config import BOT_USERNAME as bn, DURATION_LIMIT, que


# ============================================================
# ADMIN CHECK
# ============================================================

def cb_admin_check(func: Callable) -> Callable:
    async def decorator(client, cb):
        admins = a.get(cb.message.chat.id, [])

        if cb.from_user and cb.from_user.id in admins:
            return await func(client, cb)

        await cb.answer(
            "You ain't allowed!",
            show_alert=True
        )

    return decorator


# ============================================================
# TRANSCODE
# ============================================================

def transcode(filename):
    ffmpeg.input(filename).output(
        "input.raw",
        format="s16le",
        acodec="pcm_s16le",
        ac=2,
        ar="48k"
    ).overwrite_output().run()

    if os.path.exists(filename):
        os.remove(filename)


# ============================================================
# TIME HELPERS
# ============================================================

def convert_seconds(seconds):
    seconds = int(seconds)
    seconds = seconds % (24 * 3600)
    seconds %= 3600

    minutes = seconds // 60
    seconds %= 60

    return "%02d:%02d" % (minutes, seconds)


def time_to_seconds(time):
    stringt = str(time)

    return sum(
        int(x) * 60 ** i
        for i, x in enumerate(
            reversed(stringt.split(":"))
        )
    )


# ============================================================
# IMAGE HELPERS
# ============================================================

def changeImageSize(maxWidth, maxHeight, image):
    widthRatio = maxWidth / image.size[0]
    heightRatio = maxHeight / image.size[1]

    newWidth = int(widthRatio * image.size[0])
    newHeight = int(heightRatio * image.size[1])

    return image.resize((newWidth, newHeight))


async def generate_cover(
    requested_by,
    title,
    views,
    duration,
    thumbnail
):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail) as resp:

                if resp.status != 200:
                    raise Exception(
                        f"Thumbnail download failed: {resp.status}"
                    )

                async with aiofiles.open(
                    "background.png",
                    mode="wb"
                ) as f:
                    await f.write(await resp.read())

        image1 = Image.open("./background.png").convert("RGBA")
        image2 = Image.open(
            "etc/foreground.png"
        ).convert("RGBA")

        image3 = changeImageSize(
            1280,
            720,
            image1
        )

        image4 = changeImageSize(
            1280,
            720,
            image2
        )

        image5 = image3.convert("RGBA")
        image6 = image4.convert("RGBA")

        Image.alpha_composite(
            image5,
            image6
        ).save("temp.png")

        img = Image.open("temp.png")
        draw = ImageDraw.Draw(img)

        font = ImageFont.truetype(
            "etc/font.otf",
            32
        )

        draw.text(
            (205, 550),
            f"Title: {title}",
            (51, 215, 255),
            font=font
        )

        draw.text(
            (205, 590),
            f"Duration: {duration}",
            (255, 255, 255),
            font=font
        )

        draw.text(
            (205, 630),
            f"Views: {views}",
            (255, 255, 255),
            font=font
        )

        draw.text(
            (205, 670),
            f"Added By: {requested_by}",
            (255, 255, 255),
            font=font
        )

        img.save("final.png")

    finally:
        if os.path.exists("temp.png"):
            os.remove("temp.png")

        if os.path.exists("background.png"):
            os.remove("background.png")


# ============================================================
# PLAYLIST
# ============================================================

@Client.on_message(
    filters.command("playlist") &
    filters.group
)
async def playlist(client, message):

    global que

    queue = que.get(message.chat.id)

    if not queue:
        await message.reply_text(
            "Player is idle"
        )
        return

    temp = list(queue)

    if not temp:
        await message.reply_text(
            "Player is idle"
        )
        return

    now_playing = temp[0][0]

    by = temp[0][1].mention(
        style="md"
    )

    msg = "*Now Playing* in {}".format(
        message.chat.title
    )

    msg += "\n" + now_playing
    msg += "\n- Req by " + by

    temp.pop(0)

    if temp:

        msg += "\n\n"
        msg += "*Queue*"

        for song in temp:

            name = song[0]

            usr = song[1].mention(
                style="md"
            )

            msg += f"\n- {name}"
            msg += f"\n- Req by {usr}\n"

    await message.reply_text(msg)


# ============================================================
# UPDATED STATS
# ============================================================

def updated_stats(chat, queue, vol=100):

    if chat.id in callsmusic.pytgcalls.active_calls:

        stats = "Settings of *{}*".format(
            chat.title
        )

        if queue and len(queue) > 0:

            stats += "\n\n"

            stats += "Volume : {}%\n".format(
                vol
            )

            stats += "Songs in queue : {}\n".format(
                len(queue)
            )

            stats += "Now Playing : *{}*\n".format(
                queue[0][0]
            )

            stats += "Requested by : {}".format(
                queue[0][1].mention
            )

    else:
        stats = None

    return stats


# ============================================================
# PLAYER BUTTONS
# ============================================================

def r_ply(type_):

    mar = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "⏹️",
                    callback_data="leave"
                ),
                InlineKeyboardButton(
                    "⏸️",
                    callback_data="puse"
                ),
                InlineKeyboardButton(
                    "▶️",
                    callback_data="resume"
                ),
                InlineKeyboardButton(
                    "⏭️",
                    callback_data="skip"
                )
            ],
            [
                InlineKeyboardButton(
                    "Playlist 📖",
                    callback_data="playlist"
                )
            ],
            [
                InlineKeyboardButton(
                    "❌ Close",
                    callback_data="cls"
                )
            ]
        ]
    )

    return mar


# ============================================================
# CURRENT
# ============================================================

@Client.on_message(
    filters.command("current") &
    filters.group
)
async def ee(client, message):

    queue = que.get(
        message.chat.id,
        []
    )

    stats = updated_stats(
        message.chat,
        queue
    )

    if stats:
        await message.reply_text(stats)
    else:
        await message.reply_text(
            "No VoiceChat instances running in this chat"
        )


# ============================================================
# PLAYER SETTINGS
# ============================================================

@Client.on_message(
    filters.command("player") &
    filters.group
)
@authorized_users_only
async def settings(client, message):

    playing = False

    if message.chat.id in callsmusic.pytgcalls.active_calls:
        playing = True

    queue = que.get(
        message.chat.id,
        []
    )

    stats = updated_stats(
        message.chat,
        queue
    )

    if stats:

        if playing:
            await message.reply(
                stats,
                reply_markup=r_ply("pause")
            )

        else:
            await message.reply(
                stats,
                reply_markup=r_ply("play")
            )

    else:
        await message.reply(
            "No VC instances running in this chat"
        )


# ============================================================
# PLAYLIST CALLBACK
# ============================================================

@Client.on_callback_query(
    filters.regex(
        pattern=r"^(playlist)$"
    )
)
async def p_cb(client, cb):

    queue = que.get(
        cb.message.chat.id,
        []
    )

    if not queue:
        await cb.answer(
            "Player is idle",
            show_alert=True
        )
        return

    temp = list(queue)

    now_playing = temp[0][0]

    by = temp[0][1].mention(
        style="md"
    )

    msg = "*Now Playing* in {}".format(
        cb.message.chat.title
    )

    msg += "\n- " + now_playing
    msg += "\n- Req by " + by

    temp.pop(0)

    if temp:

        msg += "\n\n"
        msg += "*Queue*"

        for song in temp:

            name = song[0]

            usr = song[1].mention(
                style="md"
            )

            msg += f"\n- {name}"
            msg += f"\n- Req by {usr}\n"

    await cb.message.edit_text(msg)

    await cb.answer()


# ============================================================
# MAIN PLAYER CALLBACK
# ============================================================

@Client.on_callback_query(
    filters.regex(
        pattern=r"^(play|pause|skip|leave|puse|resume|menu|cls|playlist)$"
    )
)
@cb_admin_check
async def m_cb(client, cb):

    chat_id = cb.message.chat.id

    queue = que.get(
        chat_id,
        []
    )

    type_ = cb.matches[0].group(1)

    # --------------------------------------------------------
    # PLAYLIST
    # --------------------------------------------------------

    if type_ == "playlist":

        if not queue:
            await cb.answer(
                "Player is idle",
                show_alert=True
            )
            return

        temp = list(queue)

        now_playing = temp[0][0]

        by = temp[0][1].mention(
            style="md"
        )

        msg = "*Now Playing* in {}".format(
            cb.message.chat.title
        )

        msg += "\n- " + now_playing
        msg += "\n- Req by " + by

        temp.pop(0)

        if temp:

            msg += "\n\n"
            msg += "*Queue*"

            for song in temp:

                name = song[0]

                usr = song[1].mention(
                    style="md"
                )

                msg += f"\n- {name}"
                msg += f"\n- Req by {usr}\n"

        await cb.message.edit_text(msg)
        await cb.answer()

    # --------------------------------------------------------
    # PAUSE
    # --------------------------------------------------------

    elif type_ == "pause" or type_ == "puse":

        if (
            chat_id not in
            callsmusic.pytgcalls.active_calls
        ):
            await cb.answer(
                "Chat is not connected!",
                show_alert=True
            )
            return

        try:
            callsmusic.pytgcalls.pause_stream(
                chat_id
            )

            await cb.answer(
                "Music Paused!"
            )

            stats = updated_stats(
                cb.message.chat,
                queue
            )

            if stats:
                await cb.message.edit(
                    stats,
                    reply_markup=r_ply("play")
                )

        except Exception as e:

            await cb.answer(
                "Unable to pause!",
                show_alert=True
            )

            print(
                "Pause error:",
                e
            )

    # --------------------------------------------------------
    # RESUME / PLAY
    # --------------------------------------------------------

    elif type_ == "resume" or type_ == "play":

        if (
            chat_id not in
            callsmusic.pytgcalls.active_calls
        ):
            await cb.answer(
                "Chat is not connected!",
                show_alert=True
            )
            return

        try:

            callsmusic.pytgcalls.resume_stream(
                chat_id
            )

            await cb.answer(
                "Music Resumed!"
            )

            stats = updated_stats(
                cb.message.chat,
                queue
            )

            if stats:
                await cb.message.edit(
                    stats,
                    reply_markup=r_ply("pause")
                )

        except Exception as e:

            await cb.answer(
                "Unable to resume!",
                show_alert=True
            )

            print(
                "Resume error:",
                e
            )

    # --------------------------------------------------------
    # CLOSE
    # --------------------------------------------------------

    elif type_ == "cls":

        await cb.answer(
            "Closed menu"
        )

        await cb.message.delete()

    # --------------------------------------------------------
    # MENU
    # --------------------------------------------------------

    elif type_ == "menu":

        stats = updated_stats(
            cb.message.chat,
            queue
        )

        if not stats:
            stats = "No VC instances running in this chat"

        await cb.answer(
            "Menu opened"
        )

        await cb.message.edit(
            stats,
            reply_markup=r_ply("pause")
        )

    # --------------------------------------------------------
    # SKIP
    # --------------------------------------------------------

    elif type_ == "skip":

        if not queue:

            await cb.answer(
                "Queue is empty!",
                show_alert=True
            )
            return

        if (
            chat_id not in
            callsmusic.pytgcalls.active_calls
        ):

            await cb.answer(
                "Chat is not connected!",
                show_alert=True
            )
            return

        try:

            queue.pop(0)

            if queues.is_empty(chat_id):

                callsmusic.pytgcalls.leave_group_call(
                    chat_id
                )

                await cb.message.edit(
                    "- No More Playlist..\n"
                    "- Leaving VC!"
                )

            else:

                next_song = queues.get(
                    chat_id
                )["file"]

                callsmusic.pytgcalls.change_stream(
                    chat_id,
                    next_song
                )

                await cb.answer(
                    "Skipped"
                )

                new_queue = que.get(
                    chat_id,
                    []
                )

                if new_queue:

                    await cb.message.edit(
                        updated_stats(
                            cb.message.chat,
                            new_queue
                        ),
                        reply_markup=r_ply("pause")
                    )

                    await cb.message.reply_text(
                        "- Skipped track\n"
                        "- Now Playing *{}*".format(
                            new_queue[0][0]
                        )
                    )

        except Exception as e:

            print(
                "Skip error:",
                e
            )

            await cb.answer(
                "Unable to skip!",
                show_alert=True
            )

    # --------------------------------------------------------
    # LEAVE
    # --------------------------------------------------------

    elif type_ == "leave":

        try:

            try:
                queues.clear(chat_id)
            except Exception:
                pass

            que.pop(
                chat_id,
                None
            )

            if (
                chat_id in
                callsmusic.pytgcalls.active_calls
            ):
                callsmusic.pytgcalls.leave_group_call(
                    chat_id
                )

            await cb.message.edit(
                "Successfully Left the Chat!"
            )

            await cb.answer(
                "Left voice chat"
            )

        except Exception as e:

            print(
                "Leave error:",
                e
            )

            await cb.answer(
                "Unable to leave!",
                show_alert=True
            )


# ============================================================
# PLAY COMMAND
# ============================================================

@Client.on_message(
    command("play") &
    other_filters
)
async def play(_, message: Message):

    global que

    lel = await message.reply(
        "*_Processing_*"
    )

    administrators = await get_administrators(
        message.chat
    )

    chid = message.chat.id

    # --------------------------------------------------------
    # GET USERBOT
    # --------------------------------------------------------

    try:

        user = await USER.get_me()

    except Exception:

        await lel.edit(
            "Unable to connect to userbot."
        )

        return

    usar = user
    wew = usar.id

    # --------------------------------------------------------
    # CHECK USERBOT MEMBER
    # --------------------------------------------------------

    try:

        await _.get_chat_member(
            chid,
            wew
        )

    except Exception:

        if message.from_user:

            for administrator in administrators:

                if administrator == message.from_user.id:

                    try:

                        invitelink = (
                            await _.export_chat_invite_link(
                                chid
                            )
                        )

                    except Exception:

                        await lel.edit(
                            "<b>Add me as admin of your group first</b>"
                        )

                        return

                    try:

                        await USER.join_chat(
                            invitelink
                        )

                        await USER.send_message(
                            message.chat.id,
                            "I joined this group for playing music in VC"
                        )

                        await lel.edit(
                            "<b>Bot joined your chat</b>"
                        )

                    except UserAlreadyParticipant:

                        pass

                    except Exception as e:

                        print(
                            "Userbot join error:",
                            e
                        )

                        await lel.edit(
                            "<b>🔴 Userbot could          
