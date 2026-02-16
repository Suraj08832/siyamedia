# Authored By Certified Coders © 2025
from pyrogram.enums import ParseMode

from siyamedia import app
from siyamedia.utils.database import is_on_off
from config import LOGGER_ID


async def play_logs(message, streamtype, query: str = None):
    if await is_on_off(2):
        if query is None:
            try:
                query = message.text.split(None, 1)[1]
            except Exception:
                query = "—"

        logger_text = f"""
<b>{app.mention} ???? ???</b>

<b>???? ?? :</b> <code>{message.chat.id}</code>
<b>???? ???? :</b> {message.chat.title}
<b>???? ?s?????? :</b> @{message.chat.username}

<b>?s?? ?? :</b> <code>{message.from_user.id}</code>
<b>???? :</b> {message.from_user.mention}
<b>?s?????? :</b> @{message.from_user.username}

<b>o???? :</b> {query}
<b>s????????? :</b> {streamtype}"""
        if message.chat.id != LOGGER_ID:
            try:
                await app.send_message(
                    chat_id=LOGGER_ID,
                    text=logger_text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                )
            except:
                pass
        return
