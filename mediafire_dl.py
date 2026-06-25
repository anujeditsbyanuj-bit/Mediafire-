"""
mediafire_dl.py — Async Mediafire resolver + downloader
Features: retry logic, timeout handling, subfolder recursion, 2GB+ support
"""

import re
import asyncio
import aiohttp
import aiofiles
from typing import Callable, Optional

# ── Constants ─────────────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

FILE_API    = "https://www.mediafire.com/api/1.5/file/get_info.php?quick_key={key}&response_format=json"
LINKS_API   = "https://www.mediafire.com/api/1.5/file/get_links.php?quick_key={key}&link_type=normal_download&response_format=json"
FOLDER_API  = "https://www.mediafire.com/api/1.5/folder/get_content.php?folder_key={key}&content_type={ctype}&chunk_size=100&chunk={chunk}&response_format=json"

MAX_RETRIES   = 4
RETRY_DELAY   = 2      # seconds
CHUNK_SIZE    = 524288 # 512 KB per chunk for fast streaming
TIMEOUT       = aiohttp.ClientTimeout(total=60, connect=15)


# ── URL Helpers ───────────────────────────────────────────────────────────────
def is_folder_link(url: str) -> bool:
    return bool(re.search(r"mediafire\.com/folder/", url, re.I))


def extract_folder_key(url: str) -> str:
    m = re.search(r"mediafire\.com/folder/([a-zA-Z0-9]+)", url, re.I)
    if m:
        return m.group(1)
    h = re.search(r"#([a-zA-Z0-9]+)", url)
    return h.group(1) if h else ""


def extract_file_key(url: str) -> str:
    m = re.search(r"mediafire\.com/file/([a-zA-Z0-9]+)", url, re.I)
    return m.group(1) if m else ""


# ── Retry-aware fetch ─────────────────────────────────────────────────────────
async def _fetch(session: aiohttp.ClientSession, url: str, **kwargs) -> aiohttp.ClientResponse:
    last_exc = Exception("Unknown error")
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = await session.get(url, timeout=TIMEOUT, allow_redirects=True, **kwargs)
            resp.raise_for_status()
            return resp
        except Exception as e:
            last_exc = e
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY * attempt)
    raise last_exc


# ── File Info ─────────────────────────────────────────────────────────────────
async def get_info(url: str) -> Optional[dict]:
    """
    Resolve a Mediafire file page or direct link.
    Returns: {'name': str, 'size': int (bytes), 'url': str, 'key': str}
    """
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        # Try API route first
        key = extract_file_key(url)
        if key:
            try:
                async with await _fetch(session, FILE_API.format(key=key)) as r:
                    data = await r.json(content_type=None)
                if data.get("response", {}).get("result") == "Success":
                    fi = data["response"]["file_info"]
                    # Get direct download link via links API
                    async with await _fetch(session, LINKS_API.format(key=key)) as lr:
                        ldata = await lr.json(content_type=None)
                    dl_url = (
                        ldata.get("response", {})
                             .get("links", [{}])[0]
                             .get("normal_download", "")
                    )
                    size_str = fi.get("size", "0")
                    return {
                        "name": fi.get("filename", "file"),
                        "size": _parse_size(size_str),
                        "url":  dl_url or url,
                        "key":  key,
                    }
            except Exception:
                pass  # Fall through to HTML scraping

        # HTML scraping fallback
        async with await _fetch(session, url) as resp:
            html = await resp.text()

        dl_match = (
            re.search(r'"(https://download\d+\.mediafire\.com/[^"]+?)"', html)
            or re.search(r"(https://download\d+\.mediafire\.com/[^\s\"'<>]+)", html)
        )
        if not dl_match:
            return None

        dl_url = dl_match.group(1)

        name_match = (
            re.search(r'id="downloadButton"[^>]*>\s*([^<]+?)\s*<', html)
            or re.search(r'"filename"\s*:\s*"([^"]+)"', html)
            or re.search(r'<title>([^<]+?)\s*[-|]', html)
        )
        filename = (
            name_match.group(1).strip()
            if name_match
            else (url.split("/")[-1] or "file")
        )

        size = 0
        sz = re.search(r'"fileSize"\s*:\s*"?(\d+)"?', html)
        if sz:
            size = int(sz.group(1))
        else:
            sz = re.search(r'(\d+(?:\.\d+)?)\s*(KB|MB|GB)', html, re.I)
            if sz:
                size = _human_to_bytes(float(sz.group(1)), sz.group(2).upper())

        return {"name": filename, "size": size, "url": dl_url, "key": key}


# ── Folder Resolver ───────────────────────────────────────────────────────────
async def get_folder_files(folder_key: str) -> list[dict]:
    """
    Recursively resolve all files in a folder + subfolders.
    Returns list of {'name', 'size', 'page_url', 'key'}.
    """
    files = []
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        await _collect_files(session, folder_key, files)
    return files


async def _collect_files(
    session: aiohttp.ClientSession, folder_key: str, result: list
):
    # ── Files (paginated) ─────────────────────────────────────────────────────
    chunk = 1
    while True:
        url = FOLDER_API.format(key=folder_key, ctype="files", chunk=chunk)
        try:
            async with await _fetch(session, url) as r:
                data = await r.json(content_type=None)
        except Exception:
            break

        fc = data.get("response", {}).get("folder_content", {})
        for f in fc.get("files") or []:
            result.append({
                "name":     f.get("filename", "file"),
                "size":     _parse_size(f.get("size", "0")),
                "page_url": (f.get("links") or {}).get("normal_download", ""),
                "key":      f.get("quickkey", ""),
            })

        if fc.get("more_chunks") == "yes":
            chunk += 1
        else:
            break

    # ── Subfolders ────────────────────────────────────────────────────────────
    sub_chunk = 1
    while True:
        url = FOLDER_API.format(key=folder_key, ctype="folders", chunk=sub_chunk)
        try:
            async with await _fetch(session, url) as r:
                data = await r.json(content_type=None)
        except Exception:
            break

        fc = data.get("response", {}).get("folder_content", {})
        for sf in fc.get("folders") or []:
            sub_key = sf.get("folderkey", "")
            if sub_key:
                await _collect_files(session, sub_key, result)

        if fc.get("more_chunks") == "yes":
            sub_chunk += 1
        else:
            break


# ── Downloader ────────────────────────────────────────────────────────────────
async def download(
    url: str,
    dest: str,
    progress_cb: Optional[Callable] = None,
    cancel_check: Optional[Callable] = None,
    chunk: int = CHUNK_SIZE,
):
    """
    Stream-download url → dest.
    progress_cb(bytes_done, total_bytes) called each chunk.
    cancel_check() → bool: if True, raises asyncio.CancelledError.
    Supports files of any size (2 GB+).
    """
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with await _fetch(session, url) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            done  = 0

            async with aiofiles.open(dest, "wb") as f:
                async for data in resp.content.iter_chunked(chunk):
                    if cancel_check and cancel_check():
                        raise asyncio.CancelledError("User cancelled")
                    await f.write(data)
                    done += len(data)
                    if progress_cb:
                        await progress_cb(done, total)


# ── Internal Helpers ──────────────────────────────────────────────────────────
def _parse_size(val) -> int:
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0


def _human_to_bytes(n: float, unit: str) -> int:
    mul = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
    return int(n * mul.get(unit, 1))
