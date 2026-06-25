"""
handlers/commands.py — User commands (Pyrogram)
Bot by Anuj (@anujedits76)
"""

import time
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

import config
import database as db
from utils import human_size, logger


def register_commands(app: Client):

    # ── /start ────────────────────────────────────────────────────────────────
    @app.on_message(filters.command("start") & filters.private)
    async def cmd_start(c: Client, m: Message):
        u    = await db.get_user(m.from_user.id, m.from_user.full_name)
        plan = "👑 Premium" if u["is_premium"] else "🆓 Free"
        dl   = "♾ Unlimited" if u["is_premium"] else f"{u['downloads_today']} / {config.FREE_DAILY_LIMIT}"

        exp_line = ""
        if u.get("is_premium") and u.get("premium_expiry"):
            exp = datetime.fromisoformat(u["premium_expiry"])
            exp_line = f"\n**Premium expires:** {exp.strftime('%d %b %Y')}"

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📖 Help",        callback_data="cb_help"),
             InlineKeyboardButton("👤 Profile",     callback_data="cb_profile")],
            [InlineKeyboardButton("👑 Get Premium", callback_data="cb_premium"),
             InlineKeyboardButton("📢 Channel",     url=f"https://t.me/{config.CHANNEL_USERNAME.lstrip('@')}")],
        ])

        await m.reply(
            f"👋 **Welcome to {config.BOT_NAME}!**\n\n"
            f"Download files & folders from **Mediafire** directly to Telegram.\n"
            f"Made with ❤️ by **{config.ADMIN_NAME}**\n\n"
            f"🔗 Just send me any Mediafire link!\n\n"
            f"**What I support:**\n"
            f"• 📄 Single file downloads (up to 4 GB)\n"
            f"• 📁 Full folder downloads (Premium)\n"
            f"• ⚡ Live speed + ETA progress bar\n"
            f"• 🚫 Cancel anytime with /cancel\n\n"
            f"**Your Plan:** {plan}{exp_line}\n"
            f"**Downloads today:** {dl}\n\n"
            f"Use /help for all commands.",
            reply_markup=kb,
        )

    # ── /help ─────────────────────────────────────────────────────────────────
    @app.on_message(filters.command("help") & filters.private)
    async def cmd_help(c: Client, m: Message):
        await m.reply(
            f"📖 **{config.BOT_NAME} — Help**\n\n"
            f"🔗 **How to download:**\n"
            f"Send any `mediafire.com/file/` or `mediafire.com/folder/` link.\n\n"
            f"📋 **Commands:**\n"
            f"• /start — Welcome screen\n"
            f"• /help — This page\n"
            f"• /profile — Your stats & plan\n"
            f"• /history — Last 20 downloads\n"
            f"• /cancel — Cancel active download\n"
            f"• /ping — Bot latency\n"
            f"• /premium — Plans & benefits\n"
            f"• /redeem `KEY` — Activate a premium key\n\n"
            f"⚡ **Premium Benefits:**\n"
            f"• Unlimited daily downloads (free: {config.FREE_DAILY_LIMIT}/day)\n"
            f"• Files up to {config.PREMIUM_MAX_SIZE_MB} MB (4 GB)\n"
            f"• Folder downloads\n"
            f"• Priority queue\n\n"
            f"👨‍💻 **Admin:** {config.ADMIN_NAME}\n"
            f"💬 **Support:** {config.CHANNEL_USERNAME}"
        )

    # ── /profile ──────────────────────────────────────────────────────────────
    @app.on_message(filters.command("profile") & filters.private)
    async def cmd_profile(c: Client, m: Message):
        u    = await db.get_user(m.from_user.id, m.from_user.full_name)
        plan = "👑 Premium" if u["is_premium"] else "🆓 Free"
        dl   = "♾ Unlimited" if u["is_premium"] else f"{u['downloads_today']} / {config.FREE_DAILY_LIMIT}"

        exp_line = ""
        if u.get("is_premium") and u.get("premium_expiry"):
            exp = datetime.fromisoformat(u["premium_expiry"])
            exp_line = f"\n**Expires:** {exp.strftime('%d %b %Y %H:%M')}"
        elif u.get("is_premium"):
            exp_line = "\n**Expires:** Never (Lifetime)"

        await m.reply(
            f"👤 **Your Profile**\n\n"
            f"**Name:** {m.from_user.full_name}\n"
            f"**ID:** `{m.from_user.id}`\n"
            f"**Plan:** {plan}{exp_line}\n"
            f"**Downloads today:** {dl}\n"
            f"**Total downloads:** {u['total_downloads']}\n"
            f"**Joined:** {u.get('joined', 'N/A')}\n\n"
            f"👨‍💻 Bot by **{config.ADMIN_NAME}** | {config.CHANNEL_USERNAME}"
        )

    # ── /history ──────────────────────────────────────────────────────────────
    @app.on_message(filters.command("history") & filters.private)
    async def cmd_history(c: Client, m: Message):
        u = await db.get_user(m.from_user.id)
        if not u["history"]:
            await m.reply("📭 You haven't downloaded anything yet.")
            return
        lines = ["📋 **Your last 20 downloads:**\n"]
        for i, h in enumerate(u["history"][:20], 1):
            lines.append(f"{i}. `{h['name']}` — {h['size']} — {h['date']}")
        await m.reply("\n".join(lines))

    # ── /ping ─────────────────────────────────────────────────────────────────
    @app.on_message(filters.command("ping") & filters.private)
    async def cmd_ping(c: Client, m: Message):
        t0  = time.time()
        msg = await m.reply("🏓 Pinging…")
        ms  = int((time.time() - t0) * 1000)
        await msg.edit(f"🏓 **Pong!**\n⚡ Latency: **{ms}ms**\n\n👨‍💻 {config.BOT_NAME}")

    # ── /cancel ───────────────────────────────────────────────────────────────
    @app.on_message(filters.command("cancel") & filters.private)
    async def cmd_cancel(c: Client, m: Message):
        from handlers.downloader import cancel_flags
        uid = m.from_user.id
        if uid in cancel_flags:
            cancel_flags[uid] = True
            await m.reply("🚫 Cancelling… please wait.")
        else:
            await m.reply("❌ No active download to cancel.")

    # ── /premium ──────────────────────────────────────────────────────────────
    @app.on_message(filters.command("premium") & filters.private)
    async def cmd_premium(c: Client, m: Message):
        await m.reply(
            f"👑 **{config.BOT_NAME} — Premium Plans**\n\n"
            f"**🆓 Free Plan:**\n"
            f"• {config.FREE_DAILY_LIMIT} downloads / day\n"
            f"• Max file: {config.FREE_MAX_SIZE_MB} MB\n\n"
            f"**👑 Premium Plan:**\n"
            f"• ♾ Unlimited downloads\n"
            f"• Max file: {config.PREMIUM_MAX_SIZE_MB} MB (4 GB)\n"
            f"• Folder downloads\n"
            f"• Priority queue\n\n"
            f"🔑 Have a key? `/redeem YOUR_KEY`\n\n"
            f"📩 **Buy from {config.ADMIN_NAME}:** {config.OWNER_USERNAME}"
        )

    # ── /redeem ───────────────────────────────────────────────────────────────
    @app.on_message(filters.command("redeem") & filters.private)
    async def cmd_redeem(c: Client, m: Message):
        uid  = m.from_user.id
        args = m.text.split(maxsplit=1)
        if len(args) < 2:
            await m.reply(
                f"❌ **Usage:** `/redeem YOUR_KEY`\n\n"
                f"📩 Key khareedne ke liye contact karo: {config.OWNER_USERNAME}"
            )
            return

        key    = args[1].strip().upper()
        result = await db.redeem_key(key, uid)

        if not result["ok"]:
            msgs = {
                "invalid": f"❌ Invalid key.\n📩 Valid key ke liye contact karo: {config.OWNER_USERNAME}",
                "used":    "⚠️ Ye key kisi aur ne already use kar li hai.",
                "own":     "⚠️ Aapne ye key pehle se use kar rakhi hai.",
            }
            await m.reply(msgs.get(result["reason"], "❌ Key redeem nahi ho saki."))
            return

        days   = result["days"]
        expiry = result["expiry"]
        await m.reply(
            f"✅ **Premium Activated!**\n\n"
            f"⏳ Duration: **{days} day{'s' if days > 1 else ''}**\n"
            f"📅 Expires: **{expiry.strftime('%d %b %Y %H:%M')}**\n\n"
            f"Enjoy karo! 🎉\n"
            f"👨‍💻 **{config.ADMIN_NAME}** ki taraf se 💙"
        )
        logger.info(f"User {uid} redeemed key {key} ({days} days)")

    # ── Callbacks ─────────────────────────────────────────────────────────────
    @app.on_callback_query()
    async def on_callback(c: Client, cb: CallbackQuery):
        await cb.answer()
        if cb.data == "cb_help":
            await cb.message.reply(
                f"📖 Send any `mediafire.com` link to download.\n"
                f"Use /help for full details.\n\n"
                f"👨‍💻 Bot by **{config.ADMIN_NAME}**"
            )
        elif cb.data == "cb_profile":
            u    = await db.get_user(cb.from_user.id, cb.from_user.full_name)
            plan = "👑 Premium" if u["is_premium"] else "🆓 Free"
            await cb.message.reply(
                f"👤 **Plan:** {plan}\n"
                f"**Total downloads:** {u['total_downloads']}"
            )
        elif cb.data == "cb_premium":
            await cb.message.reply(
                f"👑 Use /premium for plans.\n"
                f"📩 Buy from **{config.ADMIN_NAME}**: {config.OWNER_USERNAME}"
            )
