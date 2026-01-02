# day_trading_bot/license.py
"""
Ed25519 license verification with optional device/MT5 binding and replay guard.
Supports TWO token formats:
  1) Old:  "<payload_b64url>.<signature_b64url>"  where signature = Ed25519(minified_json)
  2) New:  base64url(signed_message) where signed_message = sig||msg (NaCl style)

Enforced claims (if present):
  - exp (ISO8601 '...Z' or epoch seconds), or valid_from/valid_to (ISO8601)
  - app_id (must equal APP_ID)
  - hwid (must match current machine)
  - mt5_login (must match current MT5 account if available)
  - nonce (cannot be reused the same UTC day)

Public API (used by GUI):
  is_license_valid(code: str) -> bool
  is_token_valid_now() -> bool
  seconds_until_next_rollover_utc() -> int
  license_diagnostics() -> dict
"""

from __future__ import annotations
import os, sys, json, base64, time, datetime as dt, hashlib, platform, uuid
from typing import Optional, Tuple, List, Dict

# Optional MetaTrader5 (for server time / account # when already initialized)
try:
    import MetaTrader5 as mt5
except Exception:
    mt5 = None

# Optional PyNaCl (for Ed25519). If missing, verification will fail safely.
try:
    from nacl.signing import VerifyKey
    from nacl.exceptions import BadSignatureError
except Exception:  # pragma: no cover
    VerifyKey = None  # type: ignore
    BadSignatureError = Exception  # type: ignore

# ─── Configure your public verify keys (newest first) ────────────────────────
VERIFY_KEYS_HEX: List[str] = [
    # TODO: replace with your current public verify key (hex); older ones after it for overlap
    "9beba9fd7ca87a1a1046f5c7cf28748681ef69250fe68887cd15f48f4d344eb5",
]

APP_ID = "forexbot-v1"  # bump if you ship an incompatible major

# ─── Paths ───────────────────────────────────────────────────────────────────
def _app_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".forex_bot")
    path = os.path.join(base, "ForexBot")
    os.makedirs(path, exist_ok=True)
    return path

CACHE_FILE   = os.path.join(_app_dir(), "license_cache.json")  # stores last token + nonces
ALIASES_FILE = os.path.join(os.path.dirname(__file__), "aliases.json")

# Optional permanent whitelisted codes (exact match, rarely needed)
PERMANENT_LICENSE_KEYS = {
    # "ABC123-XYZ789",
}

_cache: Optional[Dict] = None

# ─── Helpers ─────────────────────────────────────────────────────────────────
def _load_json(path: str) -> Dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_json(path: str, data: Dict) -> None:
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        pass

def _load_cache() -> Dict:
    global _cache
    if _cache is None:
        _cache = _load_json(CACHE_FILE) or {}
        _cache.setdefault("last_token", "")
        _cache.setdefault("claims", {})
        _cache.setdefault("nonces", {})  # {"YYYY-MM-DD": ["nonce1", ...]}
        _cache.setdefault("last_sys_utc", None)
        _cache.setdefault("last_server_utc", None)
        _cache.setdefault("last_monotonic", None)
    return _cache

def _save_cache() -> None:
    if _cache is not None:
        _save_json(CACHE_FILE, _cache)

def _urlsafe_b64decode(s: str) -> bytes:
    s = s.strip().replace("\n", "")
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)

def _json_min_bytes(obj: Dict) -> bytes:
    return json.dumps(obj, separators=(",", ":"), sort_keys=True).encode("utf-8")

def _load_aliases() -> dict:
    return _load_json(ALIASES_FILE) or {"aliases": {}}

def _resolve_alias(code: str) -> Optional[str]:
    c = (code or "").strip()
    if c and "." not in c and len(c) <= 16 and c.upper() == c and c.isalnum():
        return (_load_aliases().get("aliases") or {}).get(c)
    return None

# ─── Time sources ────────────────────────────────────────────────────────────
def _now_utc_try_mt5() -> Optional[dt.datetime]:
    # Only use MT5 server time if MT5 is already initialized by the app.
    try:
        if mt5 is None:
            return None
        info = mt5.terminal_info()
        if not info:  # not initialized
            return None
        # any symbol tick time gives us server UTC
        for sym in ("EURUSD", "XAUUSD", "GBPUSD", "USDJPY"):
            t = mt5.symbol_info_tick(sym)
            if t and getattr(t, "time", None):
                return dt.datetime.utcfromtimestamp(int(t.time))
    except Exception:
        return None
    return None

def _now_utc() -> dt.datetime:
    c = _load_cache()
    srv = _now_utc_try_mt5()
    if srv:
        c["last_server_utc"] = srv.isoformat() + "Z"
        c["last_monotonic"] = time.monotonic()
        c["last_sys_utc"] = dt.datetime.utcnow().isoformat() + "Z"
        _save_cache()
        return srv

    # If no server time, extend last known server time by monotonic delta
    last_srv = c.get("last_server_utc")
    last_mono = c.get("last_monotonic")
    if last_srv and last_mono is not None:
        try:
            base = dt.datetime.fromisoformat(last_srv.rstrip("Z"))
            delta = max(0.0, time.monotonic() - float(last_mono))
            return base + dt.timedelta(seconds=delta)
        except Exception:
            pass

    # final fallback: system UTC
    c["last_sys_utc"] = dt.datetime.utcnow().isoformat() + "Z"
    _save_cache()
    return dt.datetime.utcnow()

def _parse_iso_or_epoch(v) -> Optional[dt.datetime]:
    try:
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return dt.datetime.utcfromtimestamp(int(v))
        if isinstance(v, str):
            if v.endswith("Z"):
                v = v[:-1] + "+00:00"
            return dt.datetime.fromisoformat(v).astimezone(dt.timezone.utc).replace(tzinfo=None)
    except Exception:
        return None
    return None

# ─── Bindings ────────────────────────────────────────────────────────────────
def _get_hwid() -> str:
    try:
        if platform.system() == "Windows":
            import winreg  # type: ignore
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
            val, _ = winreg.QueryValueEx(key, "MachineGuid")
            src = f"win|{val}"
        else:
            src = f"unix|{platform.node()}|{uuid.getnode()}"
    except Exception:
        src = f"generic|{platform.node()}|{uuid.getnode()}"
    return hashlib.sha256(src.encode("utf-8")).hexdigest()

def _get_mt5_login() -> Optional[str]:
    try:
        if mt5 is None:
            return None
        info = mt5.account_info()
        if info and getattr(info, "login", None):
            return str(info.login)
    except Exception:
        return None
    return None

# ─── Verification ────────────────────────────────────────────────────────────
def _verify_old_format(token: str) -> Optional[Dict]:
    """Old format: 'payload.signature' (both base64url)."""
    if not VerifyKey or "." not in token:
        return None
    try:
        p_b64, s_b64 = token.split(".", 1)
        payload = json.loads(_urlsafe_b64decode(p_b64).decode("utf-8"))
        sig = _urlsafe_b64decode(s_b64)
        msg = _json_min_bytes(payload)
        for k in VERIFY_KEYS_HEX:
            try:
                VerifyKey(bytes.fromhex(k)).verify(msg, sig)
                return payload
            except Exception:
                continue
    except Exception:
        return None
    return None

def _verify_new_format(token: str) -> Optional[Dict]:
    """New format: base64url(signed_message = sig||msg)."""
    if not VerifyKey or "." in token:
        return None
    try:
        signed = _urlsafe_b64decode(token)
        for k in VERIFY_KEYS_HEX:
            try:
                msg = VerifyKey(bytes.fromhex(k)).verify(signed)
                return json.loads(msg.decode("utf-8"))
            except Exception:
                continue
    except Exception:
        return None
    return None

def _check_claims(claims: Dict) -> Tuple[bool, str]:
    now = _now_utc()

    # Time window: support 'exp' OR ('valid_from','valid_to')
    exp = _parse_iso_or_epoch(claims.get("exp"))
    vf = _parse_iso_or_epoch(claims.get("valid_from"))
    vt = _parse_iso_or_epoch(claims.get("valid_to"))

    if exp is not None:
        if now > exp:
            return False, "Token expired"
    elif vf is not None and vt is not None:
        if not (vf <= now < vt):
            return False, "Token not in window"
    else:
        return False, "Token has no expiry"

    # app_id binding (optional)
    app = claims.get("app_id")
    if app and app != APP_ID:
        return False, "App mismatch"

    # device binding (optional)
    hwid = claims.get("hwid")
    if hwid and hwid != _get_hwid():
        return False, "Device mismatch"

    # MT5 account binding (optional, enforced when account is known)
    want_login = claims.get("mt5_login")
    have_login = _get_mt5_login()
    if want_login and have_login and str(want_login) != str(have_login):
        return False, "MT5 login mismatch"

    # Replay protection (optional)
    nonce = claims.get("nonce")
    if nonce:
        cache = _load_cache()
        day = now.strftime("%Y-%m-%d")
        used = set(cache.get("nonces", {}).get(day, []))
        if nonce in used:
            return False, "Nonce already used"
        used.add(nonce)
        cache.setdefault("nonces", {})[day] = list(used)
        _save_cache()

    return True, "OK"

def _store_token(token: str, claims: Dict) -> None:
    c = _load_cache()
    c["last_token"] = token
    c["claims"] = claims
    c["last_sys_utc"] = dt.datetime.utcnow().isoformat() + "Z"
    _save_cache()

# ─── Public API ──────────────────────────────────────────────────────────────
def is_license_valid(user_input: str) -> bool:
    """
    Accepts either:
      - Short ALIAS (uppercase ≤16) that maps to a real token in aliases.json
      - Full token in old or new format
    Verifies signature and enforces claims. On success, caches token+claims.
    """
    u = (user_input or "").strip()
    if not u:
        return False

    if u in PERMANENT_LICENSE_KEYS:
        # Permits “VIP” codes without signature (use sparingly)
        _store_token(u, {"exp": (dt.datetime.utcnow()+dt.timedelta(days=3650)).isoformat()+"Z"})
        return True

    # Resolve alias if looks like one
    resolved = _resolve_alias(u)
    token = resolved or u

    # Try both formats
    claims = _verify_old_format(token)
    if claims is None:
        claims = _verify_new_format(token)
    if claims is None:
        return False

    ok, _ = _check_claims(claims)
    if not ok:
        return False

    _store_token(token, claims)
    return True

def is_token_valid_now() -> bool:
    """
    Fast path: re-check cached claims (time, device, mt5, app, nonce *not* re-used).
    Signature is not re-verified here for speed; call is_license_valid() to refresh.
    """
    c = _load_cache()
    token = c.get("last_token")
    claims = c.get("claims")
    if not token or not claims:
        return False

    # anti clock-tamper: if system time moved backwards vs last stored
    last_sys = c.get("last_sys_utc")
    if last_sys:
        try:
            if dt.datetime.utcnow() < dt.datetime.fromisoformat(last_sys.rstrip("Z")):
                return False
        except Exception:
            pass

    return _check_claims(claims)[0]

def seconds_until_next_rollover_utc() -> int:
    now = _now_utc()
    tomorrow = (now + dt.timedelta(days=1)).date()
    midnight = dt.datetime.combine(tomorrow, dt.time(0, 0, 0))
    return max(0, int((midnight - now).total_seconds()))

def license_diagnostics() -> dict:
    d = {
        "module_file": __file__,
        "aliases_path": ALIASES_FILE,
        "aliases_exists": os.path.exists(ALIASES_FILE),
        "verify_keys_loaded": [k[:8] + "…" for k in VERIFY_KEYS_HEX if k],
        "cache_file": CACHE_FILE,
        "app_id": APP_ID,
        "hwid": _get_hwid(),
        "mt5_login": _get_mt5_login(),
    }
    c = _load_cache()
    d["has_cached_token"] = bool(c.get("last_token"))
    d["claims"] = c.get("claims", {})
    return d
