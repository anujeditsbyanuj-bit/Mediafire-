# 🤖 Xylon Mediafire Downloader Bot

A powerful Telegram bot to download files & folders from Mediafire — with 2GB+ support, live progress, queue system, premium plans, and full admin controls.

---

## ✨ Features

| Feature | Free | Premium |
|---|---|---|
| Single file download | ✅ | ✅ |
| Max file size | 500 MB | 4 GB |
| Daily downloads | 7/day | Unlimited |
| Folder download | ❌ | ✅ |
| 2 GB+ auto-split | ✅ | ✅ |
| Priority queue | ❌ | ✅ |
| Download history | ✅ | ✅ |

---

## ⚡ Quick Setup

### 1. Clone & install
```bash
git clone https://github.com/yourrepo/xylon-bot
cd xylon-bot
pip install -r requirements.txt
```

### 2. Configure
Edit `config.py`:
```python
BOT_TOKEN  = "your_token_from_BotFather"
OWNER_ID   = 123456789   # your Telegram user ID (get it from @userinfobot)
```

### 3. Run
```bash
python bot.py
```

---

## 🔧 Project Structure

```
xylon-bot/
├── bot.py               # Entry point — registers all handlers
├── config.py            # All settings (token, limits, paths)
├── mediafire_dl.py      # Async Mediafire resolver + downloader
├── database.py          # Persistent JSON user storage
├── utils.py             # Shared helpers (progress bar, size, ETA)
├── requirements.txt
├── handlers/
│   ├── commands.py      # /start /help /profile /history /ping etc.
│   ├── admin.py         # /stats /broadcast /ban /unban /addpremium etc.
│   └── downloader.py    # Core download logic, queue, progress, split
├── downloads/           # Temp download dir (auto-created)
├── data/
│   └── users.json       # User database (auto-created)
└── logs/
    └── bot.log          # Log file (auto-created)
```

---

## 👤 User Commands

| Command | Description |
|---|---|
| `/start` | Welcome screen |
| `/help` | All commands |
| `/profile` | Your stats & plan |
| `/history` | Last 20 downloads |
| `/ping` | Bot latency |
| `/cancel` | Cancel active download |
| `/premium` | Premium plans |
| `/redeem KEY` | Activate a premium key |

---

## 🛡 Admin Commands (Owner only)

| Command | Description |
|---|---|
| `/stats` | Bot statistics |
| `/broadcast MSG` | Send message to all users |
| `/ban USER_ID` | Ban a user |
| `/unban USER_ID` | Unban a user |
| `/addpremium USER_ID` | Grant premium |
| `/revokepremium USER_ID` | Revoke premium |
| `/users` | List recent users |

---

## 📦 2 GB+ File Handling

Files over 2 GB are automatically split into 2 GB parts and uploaded sequentially. The bot then sends a **reassembly guide** so users can merge them back:

```bash
# Linux / Mac
cat filename.part* > filename

# Windows CMD
copy /b filename.part* filename
```

---

## 🔑 Premium Keys

Add keys to `config.py`:
```python
PREMIUM_KEYS = {
    "XYLON-PREMIUM-2024": False,
    "XYLON-VIP-9999":     False,
}
```
Users redeem with `/redeem XYLON-PREMIUM-2024`.

You can also grant premium directly with `/addpremium USER_ID`.

---

## 🚀 Deploy on a VPS

```bash
# Install screen or use systemd
screen -S xylon
python bot.py
# Ctrl+A D to detach
```

Or create `/etc/systemd/system/xylon.service`:
```ini
[Unit]
Description=Xylon Mediafire Bot
After=network.target

[Service]
WorkingDirectory=/path/to/xylon-bot
ExecStart=/usr/bin/python3 bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable xylon
systemctl start xylon
```
