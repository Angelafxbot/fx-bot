# day_trading_bot/auth.py
# Local auth with salted hashing + session tokens, and safe migration of legacy users_db.json

from __future__ import annotations
import os, json, time, secrets, hashlib
from typing import Dict, Optional

# ---- Storage location (Windows-friendly; works on Linux/Mac too) ----
APP_DIR = (os.getenv("APPDATA") or os.path.expanduser("~"))
APP_DIR = os.path.join(APP_DIR, "ForexBot")
os.makedirs(APP_DIR, exist_ok=True)

USERS_DB_PATH = os.path.join(APP_DIR, "users_db.json")

# ---- Constants ----
HASH_ALGO = "sha256"
ITERATIONS = 120_000
SESSION_TTL_SECONDS = 7 * 24 * 3600  # 7 days

# ---- Helpers ----
def _pbkdf2_hash(password: str, salt: bytes) -> str:
    pwd = password.encode("utf-8")
    dk = hashlib.pbkdf2_hmac(HASH_ALGO, pwd, salt, ITERATIONS, dklen=32)
    return dk.hex()

def _new_salt() -> bytes:
    return secrets.token_bytes(16)

def _load_db() -> Dict:
    if not os.path.exists(USERS_DB_PATH):
        return {"users": {}, "sessions": {}}
    try:
        with open(USERS_DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"users": {}, "sessions": {}}

def _save_db(db: Dict) -> None:
    tmp = USERS_DB_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2)
    os.replace(tmp, USERS_DB_PATH)

def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

# ---- Public API ----
def has_any_user() -> bool:
    return bool(_load_db().get("users"))

def create_user(username: str, password: str) -> None:
    username = username.strip().lower()
    if not username or not password:
        raise ValueError("Username and password required.")
    db = _load_db()
    if username in db["users"]:
        raise ValueError("User already exists.")
    salt = _new_salt().hex()
    pwd_hash = _pbkdf2_hash(password, bytes.fromhex(salt))
    db["users"][username] = {
        "salt": salt,
        "pwd": pwd_hash,
        "created": int(time.time()),
        "version": 2,  # schema version tag (optional)
    }
    _save_db(db)

def _migrate_legacy_user(db: Dict, username: str, provided_password: str) -> bool:
    """
    Upgrade legacy records to salted PBKDF2.
    Legacy formats seen:
      - {"password": "<plain>"}                (very old)
      - {"pwd": "<plain or sha256 hex>"}       (unsalted)
    If the provided password matches, upgrade in-place and return True.
    """
    u = db["users"].get(username) or {}
    ok = False

    # Case 1: explicit plain 'password'
    legacy_plain = u.get("password")
    if isinstance(legacy_plain, str):
        if legacy_plain == provided_password or _sha256_hex(provided_password) == legacy_plain:
            ok = True

    # Case 2: unsalted 'pwd' only (could be plain or sha256)
    if not ok and "pwd" in u and "salt" not in u:
        stored = u.get("pwd", "")
        if stored == provided_password or stored == _sha256_hex(provided_password):
            ok = True

    if not ok:
        return False

    # Perform upgrade to salted PBKDF2
    salt = _new_salt().hex()
    pwd_hash = _pbkdf2_hash(provided_password, bytes.fromhex(salt))
    db["users"][username] = {
        "salt": salt,
        "pwd": pwd_hash,
        "created": u.get("created", int(time.time())),
        "version": 2,
    }
    _save_db(db)
    return True

def verify_credentials(username: str, password: str) -> bool:
    username = username.strip().lower()
    db = _load_db()
    u = db["users"].get(username)

    if not u:
        return False

    # New schema
    if "salt" in u and "pwd" in u:
        try:
            salt = bytes.fromhex(u["salt"])
        except Exception:
            # Corrupt salt → try legacy migration path as last resort
            return _migrate_legacy_user(db, username, password)
        return _pbkdf2_hash(password, salt) == u["pwd"]

    # Legacy schemas → attempt migration
    return _migrate_legacy_user(db, username, password)

def issue_session(username: str) -> str:
    """Create a time-limited session token (so we don't store plain passwords)."""
    username = username.strip().lower()
    token = secrets.token_hex(16)
    db = _load_db()
    db.setdefault("sessions", {})
    db["sessions"][token] = {"user": username, "exp": int(time.time()) + SESSION_TTL_SECONDS}
    _save_db(db)
    return token

def validate_session(token: str) -> Optional[str]:
    if not token:
        return None
    db = _load_db()
    s = db.get("sessions", {}).get(token)
    now = int(time.time())
    if not s:
        return None
    if s["exp"] < now:
        # expire
        db["sessions"].pop(token, None)
        _save_db(db)
        return None
    return s["user"]

def revoke_session(token: str) -> None:
    db = _load_db()
    if token and token in db.get("sessions", {}):
        db["sessions"].pop(token, None)
        _save_db(db)

def ensure_admin_seed() -> None:
    """UI handles first-user creation; kept for compatibility."""
    return
