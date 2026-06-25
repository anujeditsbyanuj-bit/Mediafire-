"""
handlers/admin.py — Admin commands (Pyrogram, owner only)
NEW: /genkey, /listkeys, /delkey with expiry support
"""

from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message

import config
import database as db
from utils import logger


# ── Owner check decorator ─────────────────────────────────────────────────────
def owner_only(func):
    async def wrapper(c: Client, m: Message):
        if m.from_user.id != config.OWNER_ID:
            await m.reply("⛔ Owner only.")
            return
        await func(c, m)
    return wrapper


def register_admin(app: Client):

    # ── /stats ────────────────────────────────────────────────────────────────
    @app.on_message(filters.command("stats") & filters.private)
    @owner_only
    async def cmd_stats(c: Client, m: Message):
        s = await db.get_stats()
        await m.reply(
            f"📊 **Bot Statistics**\n\n"
            f"👥 Total users: **{s['total_users']}**\n"
            f"👑 Premium active: **{s['premium_users']}**\n"
            f"🚫 Banned: **{s['banned_users']}**\n"
            f"🟢 Active today: **{s['active_today']}**\n"
            f"📥 Total downloads: **{s['total_downloads']}**"
        )

    # ── /genkey ───────────────────────────────────────────────────────────────
    @app.on_message(filters.command("genkey") & filters.private)
    @owner_only
    async def cmd_genkey(c: Client, m: Message):
        """
        Usage:
          /genkey 1    → 1 day key
          /genkey 2    → 2 day key
          /genkey 7    → 7 day key
          /genkey 30   → 30 day key
          /genkey 3 5  → 5 keys of 3 days each
        """
        args = m.text.split()
        if len(args) < 2 or not args[1].isdigit():
            await m.reply(
                "❌ **Usage:**\n"
                "`/genkey 1`   — 1 day key\n"
                "`/genkey 7`   — 7 day key\n"
                "`/genkey 30`  — 30 day key\n"
                "`/genkey 7 3` — 3 keys of 7 days"
            )
            return

        days  = int(args[1])
        count = int(args[2]) if len(args) >= 3 and args[2].isdigit() else 1
        count = min(count, 20)   # max 20 at once

        keys = []
        for _ in range(count):
            k = await db.create_key(days)
            keys.append(k)

        day_label = f"{days} day{'s' if days > 1 else ''}"
        lines     = [f"🔑 **Generated {count} key(s) — {day_label} each:**\n"]
        for k in keys:
            lines.append(f"`{k}`")

        lines.append(f"\n📋 User ko ye bhejo, woh `/redeem KEY` se activate karega.")
        await m.reply("\n".join(lines))
        logger.info(f"Admin generated {count}x {days}-day keys")

    # ── /listkeys ─────────────────────────────────────────────────────────────
    @app.on_message(filters.command("listkeys") & filters.private)
    @owner_only
    async def cmd_listkeys(c: Client, m: Message):
        args      = m.text.split()
        show_used = "all" in args

        keys = await db.list_keys(show_used=show_used)
        if not keys:
            await m.reply("📭 Koi key nahi mili." + (" (unused)" if not show_used else ""))
            return

        lines = [f"🔑 **Keys** ({'all' if show_used else 'unused only'}):\n"]
        for k in keys[-30:]:   # max 30 show
            status = "✅ Used" if k["used"] else "🟢 Available"
            used_info = f" → `{k['used_by']}`" if k["used"] else ""
            lines.append(f"{status} | **{k['days']}d** | `{k['key']}`{used_info}")

        lines.append(f"\nTotal: {len(keys)}")
        if not show_used:
            lines.append("_Use `/listkeys all` to see used keys too_")

        await m.reply("\n".join(lines))

    # ── /delkey ───────────────────────────────────────────────────────────────
    @app.on_message(filters.command("delkey") & filters.private)
    @owner_only
    async def cmd_delkey(c: Client, m: Message):
        args = m.text.split()
        if len(args) < 2:
            await m.reply("❌ Usage: `/delkey XYLON-XXXX-XXXX-XXXX`")
            return
        key = args[1].strip()
        ok  = await db.delete_key(key)
        if ok:
            await m.reply(f"🗑 Key deleted:\n`{key}`")
        else:
            await m.reply("❌ Key nahi mili ya already used hai.")

    # ── /addpremium ───────────────────────────────────────────────────────────
    @app.on_message(filters.command("addpremium") & filters.private)
    @owner_only
    async def cmd_addpremium(c: Client, m: Message):
        """
        /addpremium USER_ID        → lifetime premium
        /addpremium USER_ID 7      → 7 day premium
        /addpremium USER_ID 30     → 30 day premium
        """
        args = m.text.split()
        if len(args) < 2 or not args[1].isdigit():
            await m.reply(
                "❌ **Usage:**\n"
                "`/addpremium USER_ID`     — lifetime\n"
                "`/addpremium USER_ID 7`   — 7 days\n"
                "`/addpremium USER_ID 30`  — 30 days"
            )
            return

        uid  = int(args[1])
        days = int(args[2]) if len(args) >= 3 and args[2].isdigit() else None

        if days:
            from datetime import timedelta
            expiry = datetime.now() + timedelta(days=days)
            await db.set_premium(uid, True, expiry)
            exp_str    = expiry.strftime("%d %b %Y")
            plan_label = f"**{days} days** (expires {exp_str})"
            notify_msg = f"🎉 You've been granted **{days}-day Premium** by the admin!\nExpires: {exp_str}"
        else:
            await db.set_premium(uid, True, None)
            plan_label = "**Lifetime**"
            notify_msg = "🎉 You've been granted **Lifetime Premium** by the admin!"

        await m.reply(f"👑 User `{uid}` → Premium {plan_label}")
        try:
            await c.send_message(uid, notify_msg)
        except Exception:
            pass
        logger.info(f"Admin granted premium to {uid}, days={days}")

    # ── /revokepremium ────────────────────────────────────────────────────────
    @app.on_message(filters.command("revokepremium") & filters.private)
    @owner_only
    async def cmd_revokepremium(c: Client, m: Message):
        args = m.text.split()
        if len(args) < 2 or not args[1].isdigit():
            await m.reply("❌ Usage: `/revokepremium USER_ID`")
            return
        uid = int(args[1])
        await db.set_premium(uid, False)
        await m.reply(f"❌ Premium revoked for `{uid}`.")
        try:
            await c.send_message(uid, "⚠️ ⚠️ Anuj ne aapka premium access revoke kar diya hai.")
        except Exception:
            pass

    # ── /broadcast ────────────────────────────────────────────────────────────
    @app.on_message(filters.command("broadcast") & filters.private)
    @owner_only
    async def cmd_broadcast(c: Client, m: Message):
        args = m.text.split(maxsplit=1)
        if len(args) < 2:
            await m.reply("❌ Usage: `/broadcast Your message`")
            return
        msg    = args[1]
        users  = await db.get_all_users()
        sent   = failed = 0
        status = await m.reply(f"📢 Broadcasting to {len(users)} users…")
        for u in users:
            if u.get("is_banned"):
                continue
            try:
                await c.send_message(u["uid"], f"📢 **Announcement by Anuj**\n\n{msg}")
                sent += 1
            except Exception:
                failed += 1
        await status.edit(f"📢 **Done**\n✅ Sent: {sent}\n❌ Failed: {failed}")

    # ── /ban / /unban ─────────────────────────────────────────────────────────
    @app.on_message(filters.command("ban") & filters.private)
    @owner_only
    async def cmd_ban(c: Client, m: Message):
        args = m.text.split()
        if len(args) < 2 or not args[1].isdigit():
            await m.reply("❌ Usage: `/ban USER_ID`"); return
        uid = int(args[1])
        await db.set_banned(uid, True)
        await m.reply(f"🚫 User `{uid}` banned.")

    @app.on_message(filters.command("unban") & filters.private)
    @owner_only
    async def cmd_unban(c: Client, m: Message):
        args = m.text.split()
        if len(args) < 2 or not args[1].isdigit():
            await m.reply("❌ Usage: `/unban USER_ID`"); return
        uid = int(args[1])
        await db.set_banned(uid, False)
        await m.reply(f"✅ User `{uid}` unbanned.")

    # ── /users ────────────────────────────────────────────────────────────────
    @app.on_message(filters.command("users") & filters.private)
    @owner_only
    async def cmd_users(c: Client, m: Message):
        users = await db.get_all_users()
        if not users:
            await m.reply("No users yet."); return
        lines = ["👥 **User List** (last 20):\n"]
        for u in users[-20:]:
            badge = "👑" if u.get("is_premium") else ("🚫" if u.get("is_banned") else "👤")
            exp   = f" — exp: {u['premium_expiry'][:10]}" if u.get("premium_expiry") else ""
            lines.append(f"{badge} `{u['uid']}` — {u.get('name','?')} — {u.get('total_downloads',0)} DLs{exp}")
        await m.reply("\n".join(lines))
