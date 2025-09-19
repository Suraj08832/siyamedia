from pyrogram import filters
from pyrogram.types import Message
from pyrogram.errors import ChatSendPlainForbidden, ChatWriteForbidden, Forbidden

from ANNIEMUSIC import app
from config import OWNER_ID


async def _safe_reply_text(message: Message, *args, **kwargs):
    try:
        await message.reply_text(*args, **kwargs)
    except (ChatSendPlainForbidden, ChatWriteForbidden, Forbidden):
        pass


@app.on_message(filters.video_chat_started)
async def on_voice_chat_started(_, message: Message):
    await _safe_reply_text(message, "🎙 **ᴠᴏɪᴄᴇ ᴄʜᴀᴛ ʜᴀs sᴛᴀʀᴛᴇᴅ!**")


@app.on_message(filters.video_chat_ended)
async def on_voice_chat_ended(_, message: Message):
    await _safe_reply_text(message, "🔕 **ᴠᴏɪᴄᴇ ᴄʜᴀᴛ ᴇɴᴅᴇᴅ.**")


@app.on_message(filters.video_chat_members_invited)
async def on_voice_chat_members_invited(_, message: Message):
    inviter = message.from_user.mention if message.from_user else "Someone"
    invited = []
    vcmi = getattr(message, "video_chat_members_invited", None)
    users = getattr(vcmi, "users", []) if vcmi else []
    for user in users:
        try:
            invited.append(f"[{user.first_name}](tg://user?id={user.id})")
        except:
            pass
    if invited:
        await _safe_reply_text(
            message,
            f"👥 {inviter} ɪɴᴠɪᴛᴇᴅ {', '.join(invited)} ᴛᴏ ᴛʜᴇ ᴠᴏɪᴄᴇ ᴄʜᴀᴛ. 😉",
        )


@app.on_message(filters.command("leavegroup") & filters.user(OWNER_ID))
async def leave_group(_, message: Message):
    await _safe_reply_text(message, "👋 **ʟᴇᴀᴠɪɴɢ ᴛʜɪs ɢʀᴏᴜᴘ...**")
    try:
        await app.leave_chat(chat_id=message.chat.id, delete=True)
    except (ChatWriteForbidden, Forbidden):
        pass