# Authored By Certified Coders © 2025
import aiohttp
from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message

from siyamedia import app

API_KEY = "f66950368a61ebad3cba9b5924b4532d"
API_URL = "http://apilayer.net/api/validate"


@app.on_message(filters.command("phone"))
async def check_phone(_, message: Message):

    if len(message.command) < 2:
        return await message.reply_text(
            "?? **?????? ??????? ? ????? ??????.**\n"
            "**?????:** `/phone <number>`",
            parse_mode=ParseMode.MARKDOWN
        )

    number = message.command[1]

    params = {
        "access_key": API_KEY,
        "number": number,
        "country_code": "",
        "format": 1
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(API_URL, params=params) as response:
                if response.status != 200:
                    return await message.reply_text(
                        "? **??????? ?????. ??? ??? ?????????.**",
                        parse_mode=ParseMode.MARKDOWN
                    )

                data = await response.json()

                if not data.get("valid"):
                    return await message.reply_text(
                        "? **??????? ????? ??????.**",
                        parse_mode=ParseMode.MARKDOWN
                    )

                result = (
                    "?? **????? ????? ???????:**\n"
                    f"? **??????:** `{number}`\n"
                    f"? **???????:** `{data.get('country_name', 'N/A')} ({data.get('country_code', 'N/A')})`\n"
                    f"? **????????:** `{data.get('location', 'N/A')}`\n"
                    f"? **???????:** `{data.get('carrier', 'N/A')}`\n"
                    f"? **?????? ????:** `{data.get('line_type', 'N/A')}`"
                )

                return await message.reply_text(result, parse_mode=ParseMode.MARKDOWN)

    except aiohttp.ClientError as e:
        return await message.reply_text(
            f"?? **??????? ?????:** `{str(e)}`",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        return await message.reply_text(
            f"?? **??????? ?????:** `{str(e)}`",
            parse_mode=ParseMode.MARKDOWN
        )
