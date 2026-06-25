"""
bot.py — Xylon Mediafire Downloader Bot (Pyrogram)
MTProto client — real 2 GB native upload support
"""

from pyrogram import Client, filters, idle
from pyrogram.types import Message, BotCommand

import config
import database as db
from utils import logger
from handlers.commands import register_commands
from handlers.admin    import register_admin
from handlers.downloader import register_downloader


def build_app() -> Client:
    return Client(
        name      = "xylon_bot",
        api_id    = config.API_ID,
        api_hash  = config.API_HASH,
        bot_token = config.BOT_TOKEN,
    )


async def set_commands(app: Client):
    await app.set_bot_commands([
        BotCommand("start",         "Welcome screen"),
        BotCommand("help",          "All commands & usage"),
        BotCommand("profile",       "Your stats & plan"),
        BotCommand("history",       "Last 20 downloads"),
        BotCommand("ping",          "Bot latency check"),
        BotCommand("cancel",        "Cancel active download"),
        BotCommand("premium",       "Premium plans & benefits"),
        BotCommand("redeem",        "Redeem a premium key"),
        BotCommand("genkey",        "🔑 [Admin] Generate redeem key"),
        BotCommand("listkeys",      "📋 [Admin] List all keys"),
        BotCommand("delkey",        "🗑 [Admin] Delete unused key"),
        BotCommand("stats",         "📊 [Admin] Bot statistics"),
        BotCommand("broadcast",     "📢 [Admin] Message all users"),
        BotCommand("ban",           "🚫 [Admin] Ban a user"),
        BotCommand("unban",         "✅ [Admin] Unban a user"),
        BotCommand("addpremium",    "👑 [Admin] Grant premium"),
        BotCommand("revokepremium", "❌ [Admin] Revoke premium"),
        BotCommand("users",         "👥 [Admin] List users"),
    ])


async def main():
    # Validate config
    if config.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌  Set BOT_TOKEN in config.py"); return
    if config.API_ID == 0:
        print("❌  Set API_ID in config.py (get from my.telegram.org)"); return
    if config.API_HASH == "your_api_hash_here":
        print("❌  Set API_HASH in config.py"); return
    if config.OWNER_ID == 0:
        print("⚠️  OWNER_ID is 0 — admin commands won't work!")

    app = build_app()

    # Register all handlers
    register_commands(app)
    register_admin(app)
    register_downloader(app)

    async with app:
        me = await app.get_me()
        await set_commands(app)
        logger.info(f"Bot running: @{me.username} (API_ID: {config.API_ID})")
        await idle()

    await db.close()
    logger.info("Shutdown complete.")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
