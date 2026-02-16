# Authored By Certified Coders � 2025
import asyncio
import contextlib
import json
import os
import re
import time
from typing import Dict, List, Optional, Tuple, Union

import aiohttp
import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.aio import VideosSearch, Playlist

from siyamedia import app
from siyamedia.logging import LOGGER
from siyamedia.core.mongo import mongodb
from siyamedia.utils.cookie_handler import COOKIE_PATH
from siyamedia.utils.database import is_on_off
from siyamedia.utils.downloader import yt_dlp_download
from siyamedia.utils.errors import capture_internal_err
from siyamedia.utils.formatters import time_to_seconds
from siyamedia.utils.tuning import YTDLP_TIMEOUT, YOUTUBE_META_MAX, YOUTUBE_META_TTL
from config import LOGGER_ID


# === Caches ===
_cache: Dict[str, Tuple[float, List[Dict]]] = {}
_cache_lock = asyncio.Lock()
_formats_cache: Dict[str, Tuple[float, List[Dict], str]] = {}
_formats_lock = asyncio.Lock()


# === Constants ===
YOUTUBE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")

# === API URL Management ===
YOUR_API_URL: Union[str, None] = None
FALLBACK_API_URL = "https://shrutibots.site"

# === MongoDB Cache Collection ===
youtube_cache_db = mongodb.youtube_cache


# === Helpers ===
def _cookiefile_path() -> Optional[str]:
    path = str(COOKIE_PATH)
    try:
        if path and os.path.exists(path) and os.path.getsize(path) > 0:
            return path
    except Exception:
        pass
    return None


def _cookies_args() -> List[str]:
    path = _cookiefile_path()
    return ["--cookies", path] if path else []


async def _exec_proc(*args: str) -> Tuple[bytes, bytes]:
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        return await asyncio.wait_for(proc.communicate(), timeout=YTDLP_TIMEOUT)
    except asyncio.TimeoutError:
        with contextlib.suppress(Exception):
            proc.kill()
        return b"", b"timeout"


async def load_api_url():
    global YOUR_API_URL
    logger = LOGGER("siyamedia.platforms.Youtube")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://pastebin.com/raw/rLsBhAQa",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status == 200:
                    content = await response.text()
                    YOUR_API_URL = content.strip()
                    logger.info("API URL loaded successfully")
                else:
                    YOUR_API_URL = FALLBACK_API_URL
                    logger.info("Using fallback API URL")
    except Exception:
        YOUR_API_URL = FALLBACK_API_URL
        logger.info("Using fallback API URL")


try:
    loop = asyncio.get_event_loop()
    if loop.is_running():
        asyncio.create_task(load_api_url())
    else:
        loop.run_until_complete(load_api_url())
except RuntimeError:
    # Event loop not available at import time; URL will be loaded lazily.
    pass


async def download_song(link: str) -> Union[str, None]:
    """
    Download audio for a YouTube link or raw video_id.
    First checks MongoDB cache, then tries cookies, then API.
    Returns local file path or None on failure.
    """
    global YOUR_API_URL
    logger = LOGGER("siyamedia.platforms.Youtube")

    video_id = link.split("v=")[-1].split("&")[0] if "v=" in link else link
    if not video_id or len(video_id) < 3:
        return None

    download_dir = "downloads"
    os.makedirs(download_dir, exist_ok=True)
    file_path = os.path.join(download_dir, f"{video_id}.mp3")

    # Check if file already exists locally
    if os.path.exists(file_path):
        return file_path

    # Step 1: Check MongoDB cache
    cached_file_id = await get_cached_file_id(video_id, "audio")
    if cached_file_id:
        logger.info(f"Found cached file_id for {video_id}, downloading from Telegram...")
        if await download_from_telegram(cached_file_id, file_path):
            logger.info(f"Successfully downloaded {video_id} from Telegram cache")
            return file_path
        else:
            logger.warning(f"Failed to download from Telegram cache for {video_id}, will try fresh download")

    # Step 2: Try downloading with cookies first
    logger.info(f"Trying to download {video_id} with cookies...")
    cookies_result = await download_with_cookies(link, "audio")
    if cookies_result:
        logger.info(f"Successfully downloaded {video_id} using cookies")
        # Upload to LOGGER group in background and save to cache
        asyncio.create_task(upload_and_cache(video_id, cookies_result, "audio"))
        return cookies_result

    # Step 3: Fallback to API
    logger.info(f"Cookies failed for {video_id}, trying API...")
    if not YOUR_API_URL:
        await load_api_url()
        if not YOUR_API_URL:
            YOUR_API_URL = FALLBACK_API_URL

    try:
        async with aiohttp.ClientSession() as session:
            params = {"url": video_id, "type": "audio"}

            async with session.get(
                f"{YOUR_API_URL}/download",
                params=params,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as response:
                if response.status != 200:
                    return None

                data = await response.json()
                download_token = data.get("download_token")
                if not download_token:
                    return None

                stream_url = f"{YOUR_API_URL}/stream/{video_id}?type=audio"

                async with session.get(
                    stream_url,
                    headers={"X-Download-Token": download_token},
                    timeout=aiohttp.ClientTimeout(total=300),
                ) as file_response:
                    if file_response.status != 200:
                        return None

                    with open(file_path, "wb") as f:
                        async for chunk in file_response.content.iter_chunked(16384):
                            f.write(chunk)

                    logger.info(f"Successfully downloaded {video_id} using API")
                    # Upload to LOGGER group in background and save to cache
                    asyncio.create_task(upload_and_cache(video_id, file_path, "audio"))
                    return file_path
    except Exception as e:
        logger.error(f"API download failed for {video_id}: {e}")
        return None


async def download_video(link: str) -> Union[str, None]:
    """
    Download video for a YouTube link or raw video_id.
    First checks MongoDB cache, then tries cookies, then API.
    Returns local file path or None on failure.
    """
    global YOUR_API_URL
    logger = LOGGER("siyamedia.platforms.Youtube")

    video_id = link.split("v=")[-1].split("&")[0] if "v=" in link else link
    if not video_id or len(video_id) < 3:
        return None

    download_dir = "downloads"
    os.makedirs(download_dir, exist_ok=True)
    file_path = os.path.join(download_dir, f"{video_id}.mp4")

    # Check if file already exists locally
    if os.path.exists(file_path):
        return file_path

    # Step 1: Check MongoDB cache
    cached_file_id = await get_cached_file_id(video_id, "video")
    if cached_file_id:
        logger.info(f"Found cached file_id for {video_id}, downloading from Telegram...")
        if await download_from_telegram(cached_file_id, file_path):
            logger.info(f"Successfully downloaded {video_id} from Telegram cache")
            return file_path
        else:
            logger.warning(f"Failed to download from Telegram cache for {video_id}, will try fresh download")

    # Step 2: Try downloading with cookies first
    logger.info(f"Trying to download {video_id} with cookies...")
    cookies_result = await download_with_cookies(link, "video")
    if cookies_result:
        logger.info(f"Successfully downloaded {video_id} using cookies")
        # Upload to LOGGER group in background and save to cache
        asyncio.create_task(upload_and_cache(video_id, cookies_result, "video"))
        return cookies_result

    # Step 3: Fallback to API
    logger.info(f"Cookies failed for {video_id}, trying API...")
    if not YOUR_API_URL:
        await load_api_url()
        if not YOUR_API_URL:
            YOUR_API_URL = FALLBACK_API_URL

    try:
        async with aiohttp.ClientSession() as session:
            params = {"url": video_id, "type": "video"}

            async with session.get(
                f"{YOUR_API_URL}/download",
                params=params,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as response:
                if response.status != 200:
                    return None

                data = await response.json()
                download_token = data.get("download_token")
                if not download_token:
                    return None

                stream_url = f"{YOUR_API_URL}/stream/{video_id}?type=video"

                async with session.get(
                    stream_url,
                    headers={"X-Download-Token": download_token},
                    timeout=aiohttp.ClientTimeout(total=600),
                ) as file_response:
                    if file_response.status != 200:
                        return None

                    with open(file_path, "wb") as f:
                        async for chunk in file_response.content.iter_chunked(16384):
                            f.write(chunk)

                    logger.info(f"Successfully downloaded {video_id} using API")
                    # Upload to LOGGER group in background and save to cache
                    asyncio.create_task(upload_and_cache(video_id, file_path, "video"))
                    return file_path
    except Exception as e:
        logger.error(f"API download failed for {video_id}: {e}")
        return None


async def shell_cmd(cmd: str) -> str:
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, errorz = await proc.communicate()
    if errorz:
        if "unavailable videos are hidden" in (errorz.decode("utf-8")).lower():
            return out.decode("utf-8")
        else:
            return errorz.decode("utf-8")
    return out.decode("utf-8")


# === MongoDB Cache Functions ===
async def get_cached_file_id(vidid: str, file_type: str) -> Optional[str]:
    """Get cached file_id from MongoDB"""
    try:
        cache_key = f"{vidid}_{file_type}"
        cached = await youtube_cache_db.find_one({"vidid": vidid, "type": file_type})
        if cached:
            return cached.get("file_id")
    except Exception:
        pass
    return None


async def save_cached_file_id(vidid: str, file_id: str, file_type: str):
    """Save file_id to MongoDB cache"""
    try:
        await youtube_cache_db.update_one(
            {"vidid": vidid, "type": file_type},
            {"$set": {"file_id": file_id, "vidid": vidid, "type": file_type}},
            upsert=True,
        )
    except Exception:
        pass


async def download_from_telegram(file_id: str, file_path: str) -> bool:
    """Download file from Telegram using file_id"""
    try:
        await app.download_media(file_id, file_name=file_path)
        return os.path.exists(file_path)
    except Exception:
        return False


async def upload_to_logger_group(file_path: str, vidid: str, file_type: str) -> Optional[str]:
    """Upload file to LOGGER group and return file_id"""
    try:
        if file_type == "audio":
            message = await app.send_audio(
                chat_id=LOGGER_ID,
                audio=file_path,
                caption=f"#Cached\n`{vidid}`",
            )
        else:
            message = await app.send_video(
                chat_id=LOGGER_ID,
                video=file_path,
                caption=f"#Cached\n`{vidid}`",
            )
        
        if message.audio:
            return message.audio.file_id
        elif message.video:
            return message.video.file_id
        elif message.document:
            return message.document.file_id
    except Exception as e:
        logger = LOGGER("siyamedia.platforms.Youtube")
        logger.error(f"Failed to upload to LOGGER group: {e}")
    return None


async def upload_and_cache(vidid: str, file_path: str, file_type: str):
    """Background task to upload file to LOGGER group and save file_id to cache"""
    try:
        logger = LOGGER("siyamedia.platforms.Youtube")
        logger.info(f"Uploading {vidid} to LOGGER group in background...")
        file_id = await upload_to_logger_group(file_path, vidid, file_type)
        if file_id:
            await save_cached_file_id(vidid, file_id, file_type)
            logger.info(f"Successfully cached file_id for {vidid}")
        else:
            logger.warning(f"Failed to upload {vidid} to LOGGER group")
    except Exception as e:
        logger = LOGGER("siyamedia.platforms.Youtube")
        logger.error(f"Error in upload_and_cache for {vidid}: {e}")


async def download_with_cookies(link: str, file_type: str) -> Optional[str]:
    """Try downloading with yt-dlp using cookies"""
    try:
        video_id = link.split("v=")[-1].split("&")[0] if "v=" in link else link
        if not video_id or len(video_id) < 3:
            return None
        
        # Construct full URL if only video_id provided
        if "youtube.com" not in link and "youtu.be" not in link:
            full_link = f"https://www.youtube.com/watch?v={video_id}"
        else:
            full_link = link.split("&")[0]  # Remove extra parameters
        
        download_dir = "downloads"
        os.makedirs(download_dir, exist_ok=True)
        ext = "mp4" if file_type == "video" else "mp3"
        file_path = os.path.join(download_dir, f"{video_id}.{ext}")
        
        if os.path.exists(file_path):
            return file_path
        
        cookies_args = _cookies_args()
        if not cookies_args:
            return None  # No cookies available
        
        format_str = "best[height<=?720][width<=?1280]" if file_type == "video" else "bestaudio[ext=webm][acodec=opus]"
        
        stdout, stderr = await _exec_proc(
            "yt-dlp",
            *cookies_args,
            "-f", format_str,
            "-o", file_path,
            full_link,
        )
        
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            return file_path
    except Exception:
        pass
    return None


@capture_internal_err
async def cached_youtube_search(query: str) -> List[Dict]:
    key = f"q:{query}"
    now = time.time()

    async with _cache_lock:
        if key in _cache:
            ts, val = _cache[key]
            if now - ts < YOUTUBE_META_TTL:
                return val
            _cache.pop(key, None)
        if len(_cache) > YOUTUBE_META_MAX:
            _cache.clear()

    try:
        data = await VideosSearch(query, limit=1).next()
        result = data.get("result", [])
    except Exception:
        result = []

    if result:
        async with _cache_lock:
            _cache[key] = (now, result)

    return result


# === Main Class ===
class YouTubeAPI:
    def __init__(self) -> None:
        self.base_url = "https://www.youtube.com/watch?v="
        self.playlist_url = "https://youtube.com/playlist?list="
        self._url_pattern = re.compile(r"(?:youtube\.com|youtu\.be)")

    def _prepare_link(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        if isinstance(videoid, str) and videoid.strip():
            link = self.base_url + videoid.strip()

        link = link.strip()

        if "youtu.be" in link:
            link = self.base_url + link.split("/")[-1].split("?")[0]
        elif "youtube.com/shorts/" in link or "youtube.com/live/" in link:
            link = self.base_url + link.split("/")[-1].split("?")[0]

        return link.split("&")[0]

    # === URL Handling ===
    @capture_internal_err
    async def exists(self, link: str, videoid: Union[str, bool, None] = None) -> bool:
        return bool(self._url_pattern.search(self._prepare_link(link, videoid)))

    @capture_internal_err
    async def url(self, message: Message) -> Optional[str]:
        msgs = [message] + ([message.reply_to_message] if message.reply_to_message else [])
        for msg in msgs:
            text = msg.text or msg.caption or ""
            entities = (msg.entities or []) + (msg.caption_entities or [])
            for ent in entities:
                if ent.type == MessageEntityType.URL:
                    return text[ent.offset: ent.offset + ent.length].split("&si")[0]
                if ent.type == MessageEntityType.TEXT_LINK:
                    return ent.url.split("&si")[0]
        return None

    async def _ensure_watch_url(self, maybe_query_or_url: str) -> Optional[str]:
        prepared = self._prepare_link(maybe_query_or_url)
        if prepared.startswith("http"):
            return prepared
        data = await cached_youtube_search(prepared)
        if not data:
            return None
        vid = data[0].get("id")
        return self.base_url + vid if vid else None

    # === Metadata Fetching ===
    @capture_internal_err
    async def _fetch_video_info(self, query: str, *, use_cache: bool = True) -> Optional[Dict]:
        q = self._prepare_link(query)
        if use_cache and not q.startswith("http"):
            res = await cached_youtube_search(q)
            return res[0] if res else None
        data = await VideosSearch(q, limit=1).next()
        result = data.get("result", [])
        return result[0] if result else None

    @capture_internal_err
    async def is_live(self, link: str) -> bool:
        prepared = self._prepare_link(link)
        stdout, _ = await _exec_proc("yt-dlp", *(_cookies_args()), "--dump-json", prepared)
        if not stdout:
            return False
        try:
            info = json.loads(stdout.decode())
            return bool(info.get("is_live"))
        except json.JSONDecodeError:
            return False

    @capture_internal_err
    async def details(
        self, link: str, videoid: Union[str, bool, None] = None
    ) -> Tuple[str, Optional[str], int, str, str]:
        prepared_link = self._prepare_link(link, videoid)

        try:
            info = await self._fetch_video_info(prepared_link)
            if not info:
                raise ValueError("No results from youtubesearchpython (VideosSearch)")
        except Exception as search_err:
            raise ValueError("Video not found", {"cause": str(search_err)}) from search_err

        dt = info.get("duration")
        ds = int(time_to_seconds(dt)) if dt else 0
        thumb = (
            info.get("thumbnail")
            or info.get("thumbnails", [{}])[-1].get("url", "")
        ).split("?")[0]

        return info.get("title", ""), dt, ds, thumb, info.get("id", "")

    @capture_internal_err
    async def title(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        return info.get("title", "") if info else ""

    @capture_internal_err
    async def duration(self, link: str, videoid: Union[str, bool, None] = None) -> Optional[str]:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        return info.get("duration") if info else None

    @capture_internal_err
    async def thumbnail(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        return (
            info.get("thumbnail")
            or info.get("thumbnails", [{}])[-1].get("url", "")
        ).split("?")[0] if info else ""

    @capture_internal_err
    async def track(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[Dict, str]:
        prepared_link = self._prepare_link(link, videoid)

        try:
            info = await self._fetch_video_info(prepared_link)
            if not info:
                raise ValueError(
                    f"No results from youtubesearchpython (VideosSearch) "
                    f"for query/URL: '{prepared_link}'"
                )
        except Exception as search_err:
            stdout, stderr = await _exec_proc(
                "yt-dlp", *(_cookies_args()), "--dump-json", "--no-warnings", prepared_link
            )

            def _both_failed(details: str) -> ValueError:
                return ValueError(
                    f"Both methods failed for '{prepared_link}':\n"
                    f"  1. youtubesearchpython error: {search_err}\n"
                    f"{details}"
                )

            if not stdout:
                stderr_msg = stderr.decode().strip() if stderr else "Empty response"
                raise _both_failed(f"  2. yt-dlp error: {stderr_msg}")

            try:
                info = json.loads(stdout.decode())
            except json.JSONDecodeError as json_err:
                raw = stdout.decode()[:400]
                raise _both_failed(
                    f"  2. yt-dlp JSON error: {json_err}\n"
                    f"     Raw: {raw}..."
                ) from json_err

        thumb = (
            info.get("thumbnail")
            or info.get("thumbnails", [{}])[-1].get("url", "")
        ).split("?")[0]

        details = {
            "title": info.get("title", ""),
            "link": info.get("webpage_url", prepared_link),
            "vidid": info.get("id", ""),
            "duration_min": (
                info.get("duration")
                if isinstance(info.get("duration"), str)
                else None
            ),
            "thumb": thumb,
        }
        return details, info.get("id", "")

    # === Media & Formats ===
    @capture_internal_err
    async def video(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[int, str]:
        if videoid:
            link = self.base_url + link
        if "&" in link:
            link = link.split("&")[0]
        try:
            downloaded_file = await download_video(link)
            if downloaded_file:
                return 1, downloaded_file
            else:
                return 0, "Video download failed"
        except Exception as e:
            return 0, f"Video download error: {e}"

    @capture_internal_err
    async def playlist(
        self, link: str, limit: int, user_id, videoid: Union[str, bool, None] = None
    ) -> List[str]:
        if videoid:
            link = self.playlist_url + str(videoid)
        link = self._prepare_link(link).split("&")[0]

        try:
            plist = await Playlist.get(link)
            items = [video.get("id") for video in plist.get("videos", [])[:limit] if video.get("id")]
            if items:
                return items
        except Exception:
            pass

        stdout, _ = await _exec_proc(
            "yt-dlp",
            *(_cookies_args()),
            "-i",
            "--get-id",
            "--flat-playlist",
            "--playlist-end",
            str(limit),
            "--skip-download",
            link,
        )
        items = stdout.decode().strip().split("\n") if stdout else []
        return [i for i in items if i]

    @capture_internal_err
    async def formats(
        self, link: str, videoid: Union[str, bool, None] = None
    ) -> Tuple[List[Dict], str]:
        link = self._prepare_link(link, videoid)
        key = f"f:{link}"
        now = time.time()

        async with _formats_lock:
            cached = _formats_cache.get(key)
            if cached and now - cached[0] < YOUTUBE_META_TTL:
                return cached[1], cached[2]

        opts = {"quiet": True}
        if cf := _cookiefile_path():
            opts["cookiefile"] = cf

        out: List[Dict] = []
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(link, download=False)
                for fmt in info.get("formats", []):
                    if "dash" in str(fmt.get("format", "")).lower():
                        continue
                    if not any(k in fmt for k in ("filesize", "filesize_approx")):
                        continue
                    if not all(k in fmt for k in ("format", "format_id", "ext", "format_note")):
                        continue
                    size = fmt.get("filesize") or fmt.get("filesize_approx")
                    if not size:
                        continue
                    out.append(
                        {
                            "format": fmt["format"],
                            "filesize": size,
                            "format_id": fmt["format_id"],
                            "ext": fmt["ext"],
                            "format_note": fmt["format_note"],
                            "yturl": link,
                        }
                    )
        except Exception:
            pass

        async with _formats_lock:
            if len(_formats_cache) > YOUTUBE_META_MAX:
                _formats_cache.clear()
            _formats_cache[key] = (now, out, link)

        return out, link

    @capture_internal_err
    async def slider(
        self, link: str, query_type: int, videoid: Union[str, bool, None] = None
    ) -> Tuple[str, Optional[str], str, str]:
        data = await VideosSearch(self._prepare_link(link, videoid), limit=10).next()
        results = data.get("result", [])
        if not results or query_type >= len(results):
            raise IndexError(
                f"Query type index {query_type} out of range (found {len(results)} results)"
            )
        r = results[query_type]
        return (
            r.get("title", ""),
            r.get("duration"),
            r.get("thumbnails", [{}])[-1].get("url", "").split("?")[0],
            r.get("id", ""),
        )

    @capture_internal_err
    async def download(
        self,
        link: str,
        mystic,
        *,
        video: Union[bool, str, None] = None,
        videoid: Union[str, bool, None] = None,
        songaudio: Union[bool, str, None] = None,
        songvideo: Union[bool, str, None] = None,
        format_id: Union[bool, str, None] = None,
        title: Union[bool, str, None] = None,
    ) -> Union[Tuple[str, Optional[bool]], Tuple[None, None]]:
        if videoid:
            link = self.base_url + link

        try:
            if video:
                downloaded_file = await download_video(link)
            else:
                downloaded_file = await download_song(link)

            if downloaded_file:
                # We always return a local path, so this is "direct"
                return downloaded_file, True
            else:
                return None, False
        except Exception:
            return None, False
