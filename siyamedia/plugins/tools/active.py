# Authored By Certified Coders © 2025
from pyrogram import filters, Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from unidecode import unidecode

from siyamedia import app
from siyamedia.misc import SUDOERS
from siyamedia.utils.database import (
    get_active_chats,
    get_active_video_chats,
    remove_active_chat,
    remove_active_video_chat,
)

@app.on_message(filters.command(["activevc", "activevoice", "vc"]) & SUDOERS)
async def activevc(_, message: Message):
    mystic = await message.reply_text("» ??????? ?????? ????? ????s ??s?...")
    served_chats = await get_active_chats()
    text = ""
    j = 0
    for x in served_chats:
        try:
            chat = await app.get_chat(x)
            title = unidecode(chat.title).upper()
            link = f"<a href=https://t.me/{chat.username}>{title}</a>" if chat.username else title
            text += f"<b>{j + 1}.</b> {link}\n"
            j += 1
        except:
            await remove_active_chat(x)
    if not text:
        await mystic.edit_text(f"» ?? ?????? ????? ????s ?? {app.mention}.")
    else:
        await mystic.edit_text(
            f"<b>» ??s? ?? ????????? ?????? ????? ????s :</b>\n\n{text}",
            disable_web_page_preview=True,
        )

@app.on_message(filters.command(["activev", "activevideo", "avc"]) & SUDOERS)
async def activevi_(_, message: Message):
    mystic = await message.reply_text("» ??????? ?????? ????? ????s ??s?...")
    served_chats = await get_active_video_chats()
    text = ""
    j = 0
    for x in served_chats:
        try:
            chat = await app.get_chat(x)
            title = unidecode(chat.title).upper()
            link = f"<a href=https://t.me/{chat.username}>{title}</a>" if chat.username else title
            text += f"<b>{j + 1}.</b> {link} [<code>{x}</code>]\n"
            j += 1
        except:
            await remove_active_video_chat(x)
    if not text:
        await mystic.edit_text(f"» ?? ?????? ????? ????s ?? {app.mention}.")
    else:
        await mystic.edit_text(
            f"<b>» ??s? ?? ????????? ?????? ????? ????s :</b>\n\n{text}",
            disable_web_page_preview=True,
        )

@app.on_message(filters.command(["ac", "av"]) & SUDOERS)
async def active_count(client: Client, message: Message):
    ac_audio = str(len(await get_active_chats()))
    ac_video = str(len(await get_active_video_chats()))
    await message.reply_text(
        f"? <b><u>?????? ????s ????</u></b> :\n\n????? : {ac_audio}\n?????  : {ac_video}",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("? ???s? ?", callback_data="close")]]
        )
    )
