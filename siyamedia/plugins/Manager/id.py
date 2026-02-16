# Authored By Certified Coders © 2025
from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message

from siyamedia import app


@app.on_message(filters.command("id"))
async def get_id(client, message: Message):
    chat, user, reply = message.chat, message.from_user, message.reply_to_message
    out = []

    if message.link:
        out.append(f"**[??ss??? ??:]({message.link})** `{message.id}`")
    else:
        out.append(f"**??ss??? ??:** `{message.id}`")

    out.append(f"**[???? ??:](tg://user?id={user.id})** `{user.id}`")

    if len(message.command) == 2:
        try:
            target = message.text.split(maxsplit=1)[1]
            tgt_user = await client.get_users(target)
            out.append(f"**[?s?? ??:](tg://user?id={tgt_user.id})** `{tgt_user.id}`")
        except Exception:
            return await message.reply_text("**???s ?s?? ???s?'? ?x?s?.**", quote=True)

    if chat.username and chat.type != "private":
        out.append(f"**[???? ??:](https://t.me/{chat.username})** `{chat.id}`")
    else:
        out.append(f"**???? ??:** `{chat.id}`")

    if reply:
        if reply.link:
            out.append(f"**[??????? ??ss??? ??:]({reply.link})** `{reply.id}`")
        else:
            out.append(f"**??????? ??ss??? ??:** `{reply.id}`")

        if reply.from_user:
            out.append(
                f"**[??????? ?s?? ??:](tg://user?id={reply.from_user.id})** "
                f"`{reply.from_user.id}`"
            )

        if reply.forward_from_chat:
            out.append(
                f"??? ????????? ??????? **{reply.forward_from_chat.title}** "
                f"??s ?? `{reply.forward_from_chat.id}`"
            )

        if reply.sender_chat:
            out.append(f"?? ?? ??? ??????? ????/???????: `{reply.sender_chat.id}`")

    await message.reply_text(
        "\n".join(out),
        disable_web_page_preview=True,
        parse_mode=ParseMode.MARKDOWN,
    )
