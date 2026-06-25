"""
config.py — Bot configuration (edit before running)
"""

# ── Telegram credentials ───────────────────────────────────────────────────────
BOT_TOKEN   = "YOUR_BOT_TOKEN_HERE"   # @BotFather se lo
API_ID      = 0                        # my.telegram.org
API_HASH    = "your_api_hash_here"     # my.telegram.org
OWNER_ID    = 0                        # @userinfobot se apna ID lo

# ── Bot branding ───────────────────────────────────────────────────────────────
BOT_NAME         = "Anuj Mediafire Bot"
ADMIN_NAME       = "Anuj"
CHANNEL_USERNAME = "@AnujBots"
OWNER_USERNAME   = "@anujedits76"

# ── Download limits ────────────────────────────────────────────────────────────
FREE_DAILY_LIMIT    = 7
FREE_MAX_SIZE_MB    = 500
PREMIUM_MAX_SIZE_MB = 4096

# ── Paths ──────────────────────────────────────────────────────────────────────
DOWNLOAD_DIR = "downloads"
LOG_FILE     = "logs/bot.log"

# ── Queue ──────────────────────────────────────────────────────────────────────
MAX_CONCURRENT_DOWNLOADS = 3

# ── MongoDB Atlas ──────────────────────────────────────────────────────────────
MONGO_URI = "mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/"
MONGO_DB  = "anuj_bot"
MONGO_COL = "users"

# ── Premium keys ───────────────────────────────────────────────────────────────
PREMIUM_KEYS: dict[str, bool] = {}
