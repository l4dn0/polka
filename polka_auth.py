"""Подключение Last.fm и Discogs через браузер. Токены хранятся в polka-auth.json рядом с программой."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUTH_PATH = HERE / "polka-auth.json"
UA = "PolkaShelf/alpha0.9 (local music folder sorter)"
CALLBACK_BASE = "http://127.0.0.1:47321"
LINKS = {
    "lastfm": "https://www.last.fm/api/account/create",
    "discogs": "https://www.discogs.com/settings/developers",
}
ENV = {
    "lastfm": ("POLKA_LASTFM_KEY", "POLKA_LASTFM_SECRET"),
    "discogs": ("POLKA_DISCOGS_KEY", "POLKA_DISCOGS_SECRET"),
}


def load_auth() -> dict:
    try:
        data = json.loads(AUTH_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_auth(data: dict) -> None:
    AUTH_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def service(name: str) -> dict:
    return dict(load_auth().get(name) or {})


def update_service(name: str, **values) -> dict:
    data = load_auth()
    entry = dict(data.get(name) or {})
    for key, value in values.items():
        if value is None:
            entry.pop(key, None)
        else:
            entry[key] = value
    data[name] = entry
    save_auth(data)
    return entry


def app_keys(name: str) -> tuple[str, str]:
    """Ключ и секрет приложения: свои из настроек важнее переменных окружения."""
    entry = service(name)
    env_key, env_secret = ENV[name]
    key = str(entry.get("app_key") or os.environ.get(env_key) or "").strip()
    secret = str(entry.get("app_secret") or os.environ.get(env_secret) or "").strip()
    return key, secret


def status() -> dict:
    out = {}
    for name in ("lastfm", "discogs"):
        entry = service(name)
        key, secret = app_keys(name)
        connected = bool(entry.get("session") or entry.get("token") or entry.get("personal"))
        out[name] = {
            "connected": connected,
            "user": entry.get("user") or "",
            "method": "личный токен" if entry.get("personal") else ("OAuth" if connected else ""),
            "has_keys": bool(key and secret),
            "own_keys": bool(entry.get("app_key")),
            "app_key": entry.get("app_key") or "",
            "help": LINKS[name],
            "error": entry.get("error") or "",
        }
    return out


def _http(url: str, method: str = "GET", headers: dict | None = None, data: bytes | None = None) -> tuple[int, str]:
    request = urllib.request.Request(url, data=data, method=method, headers={"User-Agent": UA, **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", "replace")


# ---------- Last.fm ----------

def lastfm_sig(params: dict, secret: str) -> str:
    """api_sig: параметры по алфавиту name+value (без format/callback) + секрет, md5."""
    raw = "".join(f"{k}{params[k]}" for k in sorted(params) if k not in {"format", "callback"})
    return hashlib.md5((raw + secret).encode("utf-8")).hexdigest()


def lastfm_start() -> str:
    key, secret = app_keys("lastfm")
    if not (key and secret):
        raise RuntimeError("Нужны API key и secret Last.fm.")
    cb = f"{CALLBACK_BASE}/auth/lastfm/callback"
    return "https://www.last.fm/api/auth/?" + urllib.parse.urlencode({"api_key": key, "cb": cb})


def lastfm_finish(token: str, http=_http) -> dict:
    key, secret = app_keys("lastfm")
    if not (key and secret):
        raise RuntimeError("Нет ключа Last.fm.")
    params = {"method": "auth.getSession", "api_key": key, "token": token}
    params["api_sig"] = lastfm_sig(params, secret)
    params["format"] = "json"
    code, text = http("https://ws.audioscrobbler.com/2.0/?" + urllib.parse.urlencode(params))
    data = json.loads(text or "{}")
    if code != 200 or "session" not in data:
        raise RuntimeError(data.get("message") or f"Last.fm ответил {code}")
    session = data["session"]
    return update_service("lastfm", session=session.get("key"), user=session.get("name") or "", error=None)


# ---------- Discogs (OAuth 1.0a, PLAINTEXT) ----------

def discogs_oauth_header(key: str, secret: str, token: str = "", token_secret: str = "",
                         extra: dict | None = None, nonce: str | None = None, stamp: str | None = None) -> str:
    params = {
        "oauth_consumer_key": key,
        "oauth_nonce": nonce or secrets.token_hex(12),
        "oauth_signature_method": "PLAINTEXT",
        "oauth_timestamp": stamp or str(int(time.time())),
        "oauth_version": "1.0",
    }
    if token:
        params["oauth_token"] = token
    params.update(extra or {})
    params["oauth_signature"] = f"{secret}&{token_secret}"
    quote = lambda value: urllib.parse.quote(str(value), safe="~")  # noqa: E731
    return "OAuth " + ", ".join(f'{k}="{quote(v)}"' for k, v in params.items())


def discogs_start(http=_http) -> str:
    key, secret = app_keys("discogs")
    if not (key and secret):
        raise RuntimeError("Нужны Consumer Key и Consumer Secret Discogs.")
    header = discogs_oauth_header(key, secret, extra={"oauth_callback": f"{CALLBACK_BASE}/auth/discogs/callback"})
    code, text = http("https://api.discogs.com/oauth/request_token", "GET",
                      {"Authorization": header, "Content-Type": "application/x-www-form-urlencoded"})
    got = dict(urllib.parse.parse_qsl(text))
    if code != 200 or "oauth_token" not in got:
        raise RuntimeError(f"Discogs ответил {code}: {text[:160]}")
    update_service("discogs", pending_token=got["oauth_token"], pending_secret=got.get("oauth_token_secret", ""))
    return "https://discogs.com/oauth/authorize?" + urllib.parse.urlencode({"oauth_token": got["oauth_token"]})


def discogs_identity(headers: dict, http=_http) -> str:
    code, text = http("https://api.discogs.com/oauth/identity", "GET", headers)
    if code != 200:
        raise RuntimeError(f"Discogs не узнал пользователя ({code}).")
    return json.loads(text).get("username") or ""


def discogs_finish(oauth_token: str, verifier: str, http=_http) -> dict:
    key, secret = app_keys("discogs")
    entry = service("discogs")
    if not entry.get("pending_token") or entry["pending_token"] != oauth_token:
        raise RuntimeError("Неизвестный запрос Discogs, начни подключение заново.")
    header = discogs_oauth_header(key, secret, oauth_token, entry.get("pending_secret", ""),
                                  extra={"oauth_verifier": verifier})
    code, text = http("https://api.discogs.com/oauth/access_token", "POST",
                      {"Authorization": header, "Content-Type": "application/x-www-form-urlencoded"}, b"")
    got = dict(urllib.parse.parse_qsl(text))
    if code != 200 or "oauth_token" not in got:
        raise RuntimeError(f"Discogs ответил {code}: {text[:160]}")
    update_service("discogs", token=got["oauth_token"], token_secret=got.get("oauth_token_secret", ""),
                   pending_token=None, pending_secret=None, personal=None)
    user = discogs_identity(discogs_headers(), http)
    return update_service("discogs", user=user, error=None)


def discogs_personal(token: str, http=_http) -> dict:
    token = token.strip()
    user = discogs_identity({"Authorization": f"Discogs token={token}"}, http)
    return update_service("discogs", personal=token, user=user, token=None, token_secret=None, error=None)


def discogs_headers() -> dict:
    """Заголовок авторизации для запросов Discogs (личный токен или OAuth), либо пусто."""
    entry = service("discogs")
    if entry.get("personal"):
        return {"Authorization": f"Discogs token={entry['personal']}"}
    if entry.get("token"):
        key, secret = app_keys("discogs")
        if key and secret:
            return {"Authorization": discogs_oauth_header(key, secret, entry["token"], entry.get("token_secret", ""))}
    return {}


def logout(name: str) -> None:
    data = load_auth()
    entry = dict(data.get(name) or {})
    keep = {k: entry[k] for k in ("app_key", "app_secret") if k in entry}
    data[name] = keep
    save_auth(data)


def selftest() -> None:
    sig = lastfm_sig({"method": "auth.getSession", "api_key": "KEY", "token": "TOK", "format": "json"}, "SECRET")
    assert sig == hashlib.md5(b"api_keyKEYmethodauth.getSessiontokenTOKSECRET").hexdigest()
    header = discogs_oauth_header("ck", "cs", "tk", "ts", {"oauth_verifier": "v 1"}, nonce="n", stamp="1")
    assert header.startswith("OAuth ") and 'oauth_signature="cs%26ts"' in header
    assert 'oauth_verifier="v%201"' in header and 'oauth_token="tk"' in header
