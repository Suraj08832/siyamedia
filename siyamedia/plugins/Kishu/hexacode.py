# Authored By Certified Coders © 2025
from pyrogram import filters
from siyamedia import app
from config import BOT_USERNAME


def hex_to_text(hex_string):
    try:
        text = bytes.fromhex(hex_string).decode("utf-8")
        return text
    except Exception as e:
        return f"Error decoding hex: {str(e)}"


def text_to_hex(text):
    return " ".join(format(ord(char), "x") for char in text)


@app.on_message(filters.command("encode"))
async def encode_text(_, message):
    if len(message.command) > 1:
        input_text = " ".join(message.command[1:])
        hex_representation = text_to_hex(input_text)

        response_text = (
            f"?????????? ???????? ?\n{input_text}\n\n"
            f"?????? ???????????????????????????? ?\n`{hex_representation}`\n\n"
            f"???? ? @{BOT_USERNAME}"
        )

        await message.reply_text(response_text)
    else:
        await message.reply_text("Please provide text to encode.\nUsage: `/encode Hello`")


@app.on_message(filters.command("decode"))
async def decode_hex(_, message):
    if len(message.command) > 1:
        hex_input = "".join(message.command[1:]).replace(" ", "")
        decoded_text = hex_to_text(hex_input)

        response_text = (
            f"?????? ?????????? ?\n{hex_input}\n\n"
            f"?????????????? ???????? ?\n`{decoded_text}`\n\n"
            f"???? ? @{BOT_USERNAME}"
        )

        await message.reply_text(response_text)
    else:
        await message.reply_text("Please provide hex to decode.\nUsage: `/decode 48656c6c6f`")
