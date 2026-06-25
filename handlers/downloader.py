"""
handlers/downloader.py — Core download + upload logic (Pyrogram)
Real 2 GB native upload via MTProto — no split needed for most files.
Files > 4 GB are auto-split.
"""

import os
import time
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message

import config
import database as db
import mediafire_dl as mf
from utils import human_size, progress_bar, eta_str, is_mediafire_link, split_file, logger

# uid → True means cancel requested
cancel_flags: dict[int, bool] = {}

_semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_DOWNLOADS)

PROGRESS_INTERVAL = 3   # seconds between edits
TG_MAX_BYTES      = 4 * 1024 ** 3   # Pyrogram supports up to ~4 GB via MTProto


def register_downloader(app: Client):

    @app.on_message(filters.text & filters.private & ~filters.command(""))
    async def on_link(c: Client, m: Message):
        url = m.text.strip()
        if not is_mediafire_link(url):
            return

        user = m.from_user
        u    = await db.get_user(user.id, user.full_name)

        if u["is_banned"]:
            await m.reply("🚫 You are banned.")
            return

        if not u["is_premium"] and u["downloads_today"] >= config.FREE_DAILY_LIMIT:
            await m.reply(
                f"⚠️ **Daily limit reached** ({config.FREE_DAILY_LIMIT}/day for free users).\n\n"
                f"👑 Use /premium to upgrade for unlimited downloads!"
            )
            return

        if user.id in cancel_flags:
            await m.reply("⏳ You already have an active download. Use /cancel to stop it.")
            return

        status = await m.reply("🔍 Resolving link…")
        cancel_flags[user.id] = False

        async with _semaphore:
            try:
                if mf.is_folder_link(url):
                    await _handle_folder(c, m, url, u, status)
                else:
                    await _handle_file(c, m, url, u, status)
            finally:
                cancel_flags.pop(user.id, None)


# ── Single file ───────────────────────────────────────────────────────────────
async def _handle_file(c, m, url, u, status):
    uid = m.from_user.id

    # Resolve info
    try:
        info = await mf.get_info(url)
    except Exception as e:
        await status.edit(f"❌ Could not resolve link.\n`{e}`")
        return

    if not info or not info.get("url"):
        await status.edit("❌ No download link found. File may be private or deleted.")
        return

    # Size check
    size_mb = info["size"] / (1024 * 1024) if info["size"] else 0
    max_mb  = config.PREMIUM_MAX_SIZE_MB if u["is_premium"] else config.FREE_MAX_SIZE_MB
    if size_mb and size_mb > max_mb:
        note = "\n👑 Use /premium to upgrade to 4 GB limit." if not u["is_premium"] else ""
        await status.edit(
            f"❌ File too large: **{human_size(info['size'])}**\n"
            f"Your plan allows max **{max_mb} MB**.{note}"
        )
        return

    filename = info["name"]
    dest     = os.path.join(config.DOWNLOAD_DIR, f"{uid}_{filename}")
    os.makedirs(config.DOWNLOAD_DIR, exist_ok=True)

    # ── Download ──────────────────────────────────────────────────────────────
    await status.edit(
        f"📥 **Starting download…**\n`{filename}`\n"
        f"📦 Size: **{human_size(info['size'])}**"
    )

    start_time = time.time()
    last_edit  = [0.0]

    async def dl_progress(done: int, total: int):
        now = time.time()
        if now - last_edit[0] < PROGRESS_INTERVAL:
            return
        last_edit[0] = now
        elapsed = now - start_time
        speed   = done / elapsed if elapsed else 0
        pct     = done / total * 100 if total else 0
        eta     = int((total - done) / speed) if speed and total else 0
        try:
            await status.edit(
                f"📥 **Downloading…**\n\n"
                f"`{filename}`\n\n"
                f"{progress_bar(pct)} **{pct:.1f}%**\n\n"
                f"⬇️ {human_size(done)} / {human_size(total)}\n"
                f"⚡ {human_size(int(speed))}/s\n"
                f"⏱ ETA: {eta_str(eta)}"
            )
        except Exception:
            pass

    try:
        await mf.download(
            info["url"], dest,
            progress_cb   = dl_progress,
            cancel_check  = lambda: cancel_flags.get(uid, False),
        )
    except asyncio.CancelledError:
        await status.edit("🚫 Download cancelled.")
        _rm(dest); return
    except Exception as e:
        logger.exception(f"Download failed: {url}")
        await status.edit(f"❌ Download failed.\n`{e}`")
        _rm(dest); return

    file_size = os.path.getsize(dest)

    # ── Upload via Pyrogram MTProto ───────────────────────────────────────────
    await _upload(c, m, dest, filename, file_size, status, uid)
    await db.add_history(uid, filename, human_size(file_size))
    _rm(dest)


# ── Pyrogram native uploader ──────────────────────────────────────────────────
async def _upload(c, m, path, name, size, status, uid):
    start_time = time.time()
    last_edit  = [0.0]

    async def up_progress(current: int, total: int):
        now = time.time()
        if now - last_edit[0] < PROGRESS_INTERVAL:
            return
        last_edit[0] = now
        elapsed = now - start_time
        speed   = current / elapsed if elapsed else 0
        pct     = current / total * 100 if total else 0
        eta     = int((total - current) / speed) if speed and total else 0
        try:
            await status.edit(
                f"📤 **Uploading…**\n\n"
                f"`{name}`\n\n"
                f"{progress_bar(pct)} **{pct:.1f}%**\n\n"
                f"⬆️ {human_size(current)} / {human_size(total)}\n"
                f"⚡ {human_size(int(speed))}/s\n"
                f"⏱ ETA: {eta_str(eta)}"
            )
        except Exception:
            pass

    # Files ≤ 4 GB: single upload via MTProto
    if size <= TG_MAX_BYTES:
        await status.edit(f"📤 **Uploading to Telegram…**\n`{name}`")
        try:
            await c.send_document(
                chat_id  = m.chat.id,
                document = path,
                file_name= name,
                caption  = f"✅ **{name}**\n📦 {human_size(size)}",
                progress = up_progress,
            )
            await status.delete()
        except Exception as e:
            await status.edit(f"❌ Upload failed.\n`{e}`")
        return

    # Files > 4 GB: split into 4 GB parts
    await status.edit("✂️ File > 4 GB — splitting into parts…")
    parts = split_file(path, TG_MAX_BYTES)
    for i, part in enumerate(parts, 1):
        pname = os.path.basename(part)
        psize = os.path.getsize(part)
        try:
            await status.edit(f"📤 Uploading part {i}/{len(parts)}: `{pname}`")
            await c.send_document(
                chat_id  = m.chat.id,
                document = part,
                file_name= pname,
                caption  = f"📦 Part {i}/{len(parts)} — {human_size(psize)}",
                progress = up_progress,
            )
        except Exception as e:
            await status.edit(f"❌ Part {i} failed.\n`{e}`")
        finally:
            _rm(part)

    await m.reply(
        f"✅ All {len(parts)} parts uploaded!\n\n"
        f"**Reassemble on Linux/Mac:**\n`cat {name}.part* > {name}`\n\n"
        f"**Windows CMD:**\n`copy /b {name}.part* {name}`"
    )
    await status.delete()


# ── Folder handler ────────────────────────────────────────────────────────────
async def _handle_folder(c, m, url, u, status):
    if not u["is_premium"]:
        await status.edit(
            "📁 **Folder downloads are Premium only.**\n\n"
            "👑 Use /premium to upgrade."
        )
        return

    folder_key = mf.extract_folder_key(url)
    if not folder_key:
        await status.edit("❌ Could not extract folder key.")
        return

    await status.edit("🔍 Scanning folder…")
    try:
        files = await mf.get_folder_files(folder_key)
    except Exception as e:
        await status.edit(f"❌ Folder scan failed.\n`{e}`")
        return

    if not files:
        await status.edit("📭 Folder is empty or private.")
        return

    uid        = m.from_user.id
    total_size = sum(f["size"] for f in files)
    await status.edit(
        f"📁 Found **{len(files)} files** ({human_size(total_size)}). Starting…"
    )

    for idx, finfo in enumerate(files, 1):
        if cancel_flags.get(uid):
            await status.edit(f"🚫 Cancelled after {idx-1}/{len(files)} files.")
            return

        await status.edit(f"📥 File {idx}/{len(files)}: `{finfo['name']}`")

        try:
            page_url = finfo.get("page_url") or f"https://www.mediafire.com/file/{finfo['key']}"
            info     = await mf.get_info(page_url)
            if not info or not info.get("url"):
                await m.reply(f"⚠️ Skipped (no link): `{finfo['name']}`")
                continue
        except Exception as e:
            await m.reply(f"⚠️ Skipped `{finfo['name']}`: `{e}`")
            continue

        dest = os.path.join(config.DOWNLOAD_DIR, f"{uid}_{info['name']}")
        try:
            await mf.download(
                info["url"], dest,
                cancel_check=lambda: cancel_flags.get(uid, False),
            )
            fsize = os.path.getsize(dest)
            await _upload(c, m, dest, info["name"], fsize, status, uid)
            await db.add_history(uid, info["name"], human_size(fsize))
        except asyncio.CancelledError:
            await status.edit("🚫 Cancelled.")
            _rm(dest); return
        except Exception as e:
            await m.reply(f"❌ Failed `{finfo['name']}`: `{e}`")
        finally:
            _rm(dest)

    await m.reply(f"✅ Folder done! {len(files)} files uploaded.")


def _rm(path):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass
