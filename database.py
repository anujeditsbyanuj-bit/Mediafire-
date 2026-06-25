"""
database.py — MongoDB Atlas async storage via Motor
Collections:
  - users  : user data
  - keys   : redeem keys with expiry
"""

import secrets
import string
from datetime import datetime, date, timedelta
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient
import config

_client = None
_db_obj = None


async def _db():
    global _client, _db_obj
    if _db_obj is None:
        _client = AsyncIOMotorClient(config.MONGO_URI, serverSelectionTimeoutMS=8000)
        _db_obj = _client[config.MONGO_DB]
        await _db_obj[config.MONGO_COL].create_index("uid", unique=True)
        await _db_obj["keys"].create_index("key", unique=True)
    return _db_obj


# ── Helpers ───────────────────────────────────────────────────────────────────
def _default_user(uid: int, name: str = "") -> dict:
    return {
        "uid":              uid,
        "name":             name,
        "is_premium":       False,
        "premium_expiry":   None,   # ISO date string or None
        "is_banned":        False,
        "downloads_today":  0,
        "last_reset":       str(date.today()),
        "total_downloads":  0,
        "history":          [],
        "joined":           datetime.now().strftime("%d %b %Y"),
    }


def _is_premium_active(u: dict) -> bool:
    """Check is_premium flag AND expiry date."""
    if not u.get("is_premium"):
        return False
    exp = u.get("premium_expiry")
    if exp is None:
        return True   # lifetime (set by /addpremium)
    return datetime.fromisoformat(exp) > datetime.now()


# ── Users ─────────────────────────────────────────────────────────────────────
async def get_user(uid: int, name: str = "") -> dict:
    db  = await _db()
    col = db[config.MONGO_COL]
    u   = await col.find_one({"uid": uid}, {"_id": 0})

    if not u:
        u = _default_user(uid, name)
        await col.insert_one({**u})
        return u

    # Update name
    if name and u.get("name") != name:
        await col.update_one({"uid": uid}, {"$set": {"name": name}})
        u["name"] = name

    # Auto-expire premium
    if u.get("is_premium") and u.get("premium_expiry"):
        if datetime.fromisoformat(u["premium_expiry"]) <= datetime.now():
            await col.update_one(
                {"uid": uid},
                {"$set": {"is_premium": False, "premium_expiry": None}},
            )
            u["is_premium"]     = False
            u["premium_expiry"] = None

    # Daily reset
    today = str(date.today())
    if u.get("last_reset") != today:
        await col.update_one(
            {"uid": uid},
            {"$set": {"downloads_today": 0, "last_reset": today}},
        )
        u["downloads_today"] = 0
        u["last_reset"]      = today

    return u


async def add_history(uid: int, filename: str, size_str: str):
    db    = await _db()
    entry = {
        "name": filename,
        "size": size_str,
        "date": datetime.now().strftime("%d %b %Y %H:%M"),
    }
    await db[config.MONGO_COL].update_one(
        {"uid": uid},
        {
            "$push": {"history": {"$each": [entry], "$position": 0, "$slice": 20}},
            "$inc":  {"downloads_today": 1, "total_downloads": 1},
        },
    )


async def get_all_users() -> list[dict]:
    db     = await _db()
    cursor = db[config.MONGO_COL].find({}, {"_id": 0})
    return await cursor.to_list(length=None)


async def set_premium(uid: int, value: bool, expiry: Optional[datetime] = None):
    """
    value=True  → grant premium (expiry=None means lifetime)
    value=False → revoke premium
    """
    db  = await _db()
    upd = {
        "is_premium":     value,
        "premium_expiry": expiry.isoformat() if expiry else None,
    }
    await db[config.MONGO_COL].update_one({"uid": uid}, {"$set": upd})


async def set_banned(uid: int, value: bool):
    db = await _db()
    await db[config.MONGO_COL].update_one({"uid": uid}, {"$set": {"is_banned": value}})


async def get_stats() -> dict:
    db        = await _db()
    col       = db[config.MONGO_COL]
    today_str = str(date.today())
    now       = datetime.now().isoformat()

    total   = await col.count_documents({})
    premium = await col.count_documents({
        "is_premium": True,
        "$or": [
            {"premium_expiry": None},
            {"premium_expiry": {"$gt": now}},
        ],
    })
    banned  = await col.count_documents({"is_banned": True})
    active  = await col.count_documents({
        "last_reset":      today_str,
        "downloads_today": {"$gt": 0},
    })
    pipeline = [{"$group": {"_id": None, "total": {"$sum": "$total_downloads"}}}]
    res      = await col.aggregate(pipeline).to_list(1)
    total_dl = res[0]["total"] if res else 0

    return {
        "total_users":     total,
        "premium_users":   premium,
        "banned_users":    banned,
        "active_today":    active,
        "total_downloads": total_dl,
    }


# ── Keys ──────────────────────────────────────────────────────────────────────
def _make_key() -> str:
    chars = string.ascii_uppercase + string.digits
    part  = lambda n: "".join(secrets.choice(chars) for _ in range(n))
    return f"XYLON-{part(4)}-{part(4)}-{part(4)}"


async def create_key(days: int) -> str:
    """Generate a new redeem key valid for `days` days. Returns the key string."""
    db  = await _db()
    key = _make_key()
    doc = {
        "key":     key,
        "days":    days,
        "used":    False,
        "used_by": None,
        "used_at": None,
        "created": datetime.now().isoformat(),
    }
    await db["keys"].insert_one(doc)
    return key


async def redeem_key(key: str, uid: int) -> dict:
    """
    Try to redeem a key for user uid.
    Returns: {"ok": True, "days": N, "expiry": datetime}
          or {"ok": False, "reason": str}
    """
    db  = await _db()
    doc = await db["keys"].find_one({"key": key})

    if not doc:
        return {"ok": False, "reason": "invalid"}
    if doc["used"]:
        if doc["used_by"] == uid:
            return {"ok": False, "reason": "own"}
        return {"ok": False, "reason": "used"}

    days   = doc["days"]
    expiry = datetime.now() + timedelta(days=days)

    # Mark key as used
    await db["keys"].update_one(
        {"key": key},
        {"$set": {"used": True, "used_by": uid, "used_at": datetime.now().isoformat()}},
    )

    # Grant premium — extend if already premium
    u = await db[config.MONGO_COL].find_one({"uid": uid})
    if u and u.get("is_premium") and u.get("premium_expiry"):
        # Extend existing expiry
        current_exp = datetime.fromisoformat(u["premium_expiry"])
        if current_exp > datetime.now():
            expiry = current_exp + timedelta(days=days)

    await set_premium(uid, True, expiry)
    return {"ok": True, "days": days, "expiry": expiry}


async def list_keys(show_used: bool = False) -> list[dict]:
    db     = await _db()
    query  = {} if show_used else {"used": False}
    cursor = db["keys"].find(query, {"_id": 0})
    return await cursor.to_list(length=None)


async def delete_key(key: str) -> bool:
    db  = await _db()
    res = await db["keys"].delete_one({"key": key, "used": False})
    return res.deleted_count > 0


# ── Close ─────────────────────────────────────────────────────────────────────
async def close():
    global _client, _db_obj
    if _client:
        _client.close()
        _client = None
        _db_obj = None
