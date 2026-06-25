"""
config.py — Bot configuration (edit before running)
"""

# ── Telegram credentials ───────────────────────────────────────────────────────
BOT_TOKEN   = "8667684753:AAFbJbj4VWBZHvMlZ525elePDU-cdKasu7o"   # @BotFather se lo
API_ID      = 37476811                        # my.telegram.org
API_HASH    = "7aa60670b871050820086c6267371ee6"     # my.telegram.org
OWNER_ID    = 8730393744                       # @userinfobot se apna ID lo

# ── Bot branding ───────────────────────────────────────────────────────────────
BOT_NAME         = "Anuj Mediafire Bot"
ADMIN_NAME       = "Anuj"
CHANNEL_USERNAME = "@log_ak_bots"
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
MONGO_URI = "mongodb+srv://Anujedit:Anujedit@cluster0.7cs2nhd.mongodb.net/?appName=Cluster0"
MONGO_DB  = "Anujedit"
MONGO_COL = "Anujedit"

# ── Premium keys ───────────────────────────────────────────────────────────────
PREMIUM_KEYS: dict[str, bool] = {}
