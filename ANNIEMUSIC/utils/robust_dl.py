import asyncio
import os
import random
from typing import Any, Callable, Optional

from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import RPCError, FloodWait

_ORIG_CLIENT_DOWNLOAD_MEDIA: Optional[Callable[..., Any]] = None
_ORIG_MESSAGE_DOWNLOAD: Optional[Callable[..., Any]] = None
_ORIG_CLIENT_GET_FILE: Optional[Callable[..., Any]] = None
_PATCHED = False

DEFAULT_TRIES = int(os.getenv("AXM_DOWNLOAD_TRIES", "4"))
BASE_DELAY = float(os.getenv("AXM_DOWNLOAD_BASE_DELAY", "1.0"))


async def _retry_call(fn: Callable[..., Any], *args, **kwargs):
    tries = kwargs.pop("_tries", DEFAULT_TRIES)
    last_exc = None
    for attempt in range(1, tries + 1):
        try:
            return await fn(*args, **kwargs)
        except FloodWait as e:
            await asyncio.sleep(e.value + random.uniform(0.1, 0.5))
            last_exc = e
        except (RPCError, KeyError, TimeoutError, OSError, ValueError) as e:
            last_exc = e
            if attempt < tries:
                await asyncio.sleep(BASE_DELAY * (2 ** (attempt - 1)) + random.uniform(0.05, 0.25))
            else:
                break
    raise last_exc if last_exc else RuntimeError("retry failed")


async def robust_download_media(client: Client, *args, **kwargs):
    if _ORIG_CLIENT_DOWNLOAD_MEDIA is None:
        return await client.download_media(*args, **kwargs)
    return await _retry_call(_ORIG_CLIENT_DOWNLOAD_MEDIA, client, *args, **kwargs)


async def robust_message_download(msg: Message, *args, **kwargs):
    if _ORIG_MESSAGE_DOWNLOAD is None:
        return await msg.download(*args, **kwargs)
    return await _retry_call(_ORIG_MESSAGE_DOWNLOAD, msg, *args, **kwargs)


async def robust_get_file(client: Client, *args, **kwargs):
    if _ORIG_CLIENT_GET_FILE is None:
        return await client.get_file(*args, **kwargs)
    return await _retry_call(_ORIG_CLIENT_GET_FILE, client, *args, **kwargs)


def install_pyrogram_download_patches():
    global _PATCHED, _ORIG_CLIENT_DOWNLOAD_MEDIA, _ORIG_MESSAGE_DOWNLOAD, _ORIG_CLIENT_GET_FILE
    if _PATCHED:
        return

    _ORIG_CLIENT_DOWNLOAD_MEDIA = Client.download_media
    _ORIG_MESSAGE_DOWNLOAD = Message.download
    _ORIG_CLIENT_GET_FILE = Client.get_file

    async def _client_download_media_patched(self: Client, *args, **kwargs):
        return await _retry_call(_ORIG_CLIENT_DOWNLOAD_MEDIA, self, *args, **kwargs)

    async def _message_download_patched(self: Message, *args, **kwargs):
        return await _retry_call(_ORIG_MESSAGE_DOWNLOAD, self, *args, **kwargs)

    async def _client_get_file_patched(self: Client, *args, **kwargs):
        return await _retry_call(_ORIG_CLIENT_GET_FILE, self, *args, **kwargs)

    Client.download_media = _client_download_media_patched  # type: ignore
    Message.download = _message_download_patched  # type: ignore
    Client.get_file = _client_get_file_patched  # type: ignore

    _PATCHED = True