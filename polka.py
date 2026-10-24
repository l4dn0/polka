#!/usr/bin/env python3
"""Полка — локальная раскладка альбомов по папкам каталога.

Нужен только Python 3.10+ (на Windows ставь с python.org, с галочкой tcl/tk).
Запуск: двойной щелчок по «Запустить Полку.bat» или `python polka.py`.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import ssl
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

AUDIO = {".mp3", ".flac", ".m4a", ".mp4", ".ogg", ".oga", ".opus", ".wav", ".aiff", ".aif", ".wma", ".aac", ".alac", ".webm", ".mka"}
# форматы yt-dlp -x; best = исходная дорожка без перекодирования
YT_FORMATS = ("mp3", "m4a", "aac", "opus", "ogg", "flac", "wav", "alac", "best")
# --embed-thumbnail надёжно работает только для этих (wav/aac/ogg/opus/best — пропускаем)
YT_THUMB_FORMATS = {"mp3", "m4a", "alac", "flac"}
VERSION = "alpha 0.9"
UA = f"PolkaShelf/{VERSION} (local music folder sorter)"
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
HERE = Path(__file__).resolve().parent
CACHE_PATH = HERE / "polka-cache.json"
PREFS_PATH = HERE / "polka-prefs.json"
OLD_SETTINGS_PATH = HERE / "polka-settings.json"
CTX = ssl.create_default_context()

DEFAULT_PREFS = {
    "version": VERSION,
    "discogs": "",
    "lastfm": "",
    "show_log": False,
    "tag_files": True,
    "fetch_covers": True,
    "dark": False,
    "source": "",
    "catalog": "",
    "download_dir": "",
    "move": True,
    "place_unclear": False,
    "use_youtube_folder": False,
    "youtube_kind": "video",
    "youtube_format": "mp3",
    "youtube_split": True,
    "search_workers": 5,
    "request_timeout": 12,
    "use_discogs": True,
    "use_lastfm": True,
    "use_musicbrainz": True,
    "use_wikipedia": True,
    "use_itunes": True,
    "watch_enabled": False,
    "watch_minutes": 15,
    "cookies": "",
    "watches": [],
    "lists": [],
}

NOISE = {
    "seen live", "favorites", "favourites", "favorite", "favourite",
    "favorite albums", "favourite albums", "beautiful", "awesome", "love",
    "loved", "sexy", "cool", "fun", "sad", "great", "amazing", "best",
    "classic", "masterpiece", "female vocals", "male vocals", "vocals",
    "instrumental", "under 2000 listeners", "all", "music", "albums i own",
    "i own this", "owned", "my music", "canadian", "american", "british",
    "german", "french", "russian", "serbia", "serbian", "belgrade", "canada",
    "usa", "uk", "england", "europe", "european", "latin", "world", "female",
    "male", "singer-songwriter", "singer songwriter", "album", "albums", "cd",
    "ep", "lp", "single",
}

RU = [
    ("прогрессивный рок", "progressive rock"),
    ("психоделический рок", "psychedelic rock"),
    ("альтернативный рок", "alternative rock"),
    ("экспериментальный рок", "experimental rock"),
    ("симфонический метал", "symphonic metal"),
    ("симфонический рок", "symphonic rock"),
    ("атмосферный блэк", "atmospheric black metal"),
    ("блэк метал", "black metal"),
    ("блек метал", "black metal"),
    ("дэт метал", "death metal"),
    ("дум метал", "doom metal"),
    ("трэш метал", "thrash metal"),
    ("треш метал", "thrash metal"),
    ("хеви метал", "heavy metal"),
    ("пауэр метал", "power metal"),
    ("павер метал", "power metal"),
    ("фолк метал", "folk metal"),
    ("дарк эмбиент", "dark ambient"),
    ("темный эмбиент", "dark ambient"),
    ("драм н бейс", "drum and bass"),
    ("драм энд бейс", "drum and bass"),
    ("хип хоп", "hip hop"),
    ("арт рок", "art rock"),
    ("фолк рок", "folk rock"),
    ("хард рок", "hard rock"),
    ("поп рок", "pop rock"),
    ("синтвейв", "synthwave"),
    ("вейпорвейв", "vaporwave"),
    ("саундтрек", "soundtrack"),
    ("электроника", "electronic"),
    ("электронная", "electronic"),
    ("электронный", "electronic"),
    ("эмбиент", "ambient"),
    ("техно", "techno"),
    ("хаус", "house"),
    ("джаз", "jazz"),
    ("блюз", "blues"),
    ("классическая", "classical"),
    ("классика", "classical"),
    ("панк", "punk"),
    ("фолк", "folk"),
    ("поп", "pop"),
    ("рэп", "rap"),
    ("металл", "metal"),
    ("метал", "metal"),
    ("рок", "rock"),
]
RU.sort(key=lambda pair: len(pair[0]), reverse=True)

def shelf(keys, main, sub, rank, exact=False):
    return [(key, main, sub, rank, exact) for key in keys]

PHRASES = [
    *shelf(["atmospheric black metal", "depressive black metal", "raw black metal", "black metal", "blackgaze"], "Metal", "Black Metal", 4),
    *shelf(["melodic death metal", "technical death metal", "brutal death metal", "death metal", "deathcore"], "Metal", "Death Metal", 4),
    *shelf(["funeral doom", "doom metal", "death doom", "sludge metal", "stoner doom", "funeral doom metal"], "Metal", "Doom Metal", 4),
    *shelf(["sludge"], "Metal", "Doom Metal", 4, True),
    *shelf(["thrash metal", "speed metal"], "Metal", "Thrash Metal", 4),
    *shelf(["thrash"], "Metal", "Thrash Metal", 4, True),
    *shelf(["folk metal", "viking metal", "pagan metal"], "Metal", "Folk Metal", 4),
    *shelf(["power metal", "symphonic metal"], "Metal", "Power Metal", 4),
    *shelf(["heavy metal", "traditional metal", "groove metal", "nu metal"], "Metal", "Heavy Metal", 4),
    *shelf(["metalcore", "grindcore"], "Metal", "Metalcore", 4),
    *shelf(["progressive rock", "prog rock", "progressive metal", "prog metal", "art rock", "experimental rock", "symphonic rock", "eclectic progressive"], "Rock", "Prog Rock", 4),
    *shelf(["progressive", "prog"], "Rock", "Prog Rock", 4, True),
    *shelf(["occult rock", "magic metal", "witch rock"], "Rock", "Occult Rock", 5),
    *shelf(["jazz fusion", "jazz rock"], "Rock", "Jazz Rock (Fusion)", 5),
    *shelf(["alternative rock", "alt rock", "post britpop", "britpop"], "Rock", "Alternative Rock", 3),
    *shelf(["indie rock"], "Rock", "Indie Rock", 3),
    *shelf(["folk rock"], "Rock", "Folk Rock", 3),
    *shelf(["pop rock", "soft rock"], "Rock", "Pop Rock", 3),
    *shelf(["hard rock", "classic rock", "blues rock"], "Rock", "Hard Rock", 3),
    *shelf(["psychedelic rock", "space rock", "neo psychedelia", "space rock revival"], "Rock", "Psychedelic Rock", 3),
    *shelf(["garage rock", "punk rock"], "Rock", "Garage Rock", 3),
    *shelf(["post rock", "math rock", "noise rock", "krautrock"], "Rock", "Post-Rock", 3),
    *shelf(["shoegaze", "dream pop"], "Rock", "Shoegaze", 3),
    *shelf(["gothic rock", "new wave", "post punk"], "Rock", "Post-Punk", 3),
    *shelf(["stoner rock"], "Rock", "Stoner Rock", 3),
    *shelf(["paleosynth", "paleo synth", "cenozoic", "paleozoic", "prehistoric", "megafauna", "ritual ambient", "shamanic", "tribal ambient"], "Electronic", "Paleosynth", 5),
    *shelf(["barberbeats", "barber beats", "chillhop", "jazzhop", "lofi hip hop", "lo fi hip hop", "study beats"], "Electronic", "Barberbeats", 5),
    *shelf(["dark ambient", "drone ambient"], "Electronic", "Dark Ambient", 5),
    *shelf(["dungeon synth"], "Electronic", "Dungeon Synth", 5),
    *shelf(["comfy synth"], "Electronic", "Comfy Synth", 5),
    *shelf(["synthwave", "vaporwave", "outrun"], "Electronic", "Synthwave", 5),
    *shelf(["drum and bass", "drum n bass", "dnb", "jungle", "liquid funk"], "Electronic", "Drum and Bass", 4),
    *shelf(["progressive house", "progressive trance"], "Electronic", "Progressive House", 4),
    *shelf(["deep house", "tech house", "acid house", "french house", "house"], "Electronic", "House", 3),
    *shelf(["minimal techno", "techno"], "Electronic", "Techno", 3),
    *shelf(["trance", "psytrance"], "Electronic", "Trance", 3),
    *shelf(["idm", "glitch"], "Electronic", "IDM", 3),
    *shelf(["dubstep", "brostep"], "Electronic", "Dubstep", 3),
    *shelf(["industrial", "ebm", "electro industrial", "power noise"], "Electronic", "Industrial", 3),
    *shelf(["trip hop", "downtempo", "chillout"], "Electronic", "Downtempo", 3),
    *shelf(["breakbeat", "big beat"], "Electronic", "Breakbeat", 3),
    *shelf(["ambient", "drone"], "Electronic", "Ambient", 3),
    *shelf(["synth pop", "synthpop", "electropop"], "Pop", "Synth Pop", 3),
    *shelf(["dance pop", "art pop", "indie pop", "k pop", "hyperpop", "pop"], "Pop", "Pop", 3),
    *shelf(["trap", "boom bap", "grime", "phonk", "cloud rap", "hip hop", "rap"], "Hip-Hop", "Hip-Hop", 3),
    *shelf(["free jazz", "avant garde jazz"], "Jazz", "Free Jazz", 4),
    *shelf(["bebop", "cool jazz", "vocal jazz", "smooth jazz", "bossa nova", "swing", "jazz"], "Jazz", "Jazz", 3),
    *shelf(["electric blues", "delta blues", "chicago blues", "blues"], "Blues", "Blues", 3),
    *shelf(["contemporary classical", "baroque", "romantic era", "orchestral", "opera", "chamber", "classical"], "Classical", "Classical", 3),
    *shelf(["indie folk", "freak folk", "neofolk", "traditional folk", "folk"], "Folk", "Folk", 3),
    *shelf(["bluegrass", "country"], "Folk", "Country", 3),
    *shelf(["hardcore punk", "pop punk", "crust punk", "street punk", "punk"], "Punk", "Punk", 3),
    *shelf(["original soundtrack", "film score", "video game music", "soundtrack"], "OST", "Soundtrack", 5),
    *shelf(["ost", "score"], "OST", "Soundtrack", 5, True),
    *shelf(["dancehall", "reggae", "ska", "dub"], "Reggae", "Reggae", 3),
    *shelf(["rhythm and blues", "rnb", "soul", "funk", "disco", "gospel"], "Soul", "Soul", 3),
    ("rock", "Rock", "Rock", 1, False),
    ("metal", "Metal", "Metal", 1, False),
    ("electronic", "Electronic", "Electronic", 1, False),
]
PHRASES.sort(key=lambda item: (len(item[0]), item[3]), reverse=True)

ECLIPSED_BY = {
    "Ambient": ["Dark Ambient", "Dungeon Synth", "Comfy Synth", "Paleosynth"],
    "Dark Ambient": ["Dungeon Synth"],
    "Electronic": ["Ambient", "Dark Ambient", "Dungeon Synth", "Comfy Synth", "Paleosynth", "Barberbeats", "Synthwave", "House", "Techno", "Trance", "IDM", "Dubstep", "Industrial", "Downtempo", "Breakbeat", "Drum and Bass", "Progressive House"],
    "Rock": ["Prog Rock", "Alternative Rock", "Indie Rock", "Folk Rock", "Pop Rock", "Hard Rock", "Psychedelic Rock", "Garage Rock", "Post-Rock", "Shoegaze", "Post-Punk", "Stoner Rock", "Occult Rock", "Jazz Rock (Fusion)"],
    "Metal": ["Black Metal", "Death Metal", "Doom Metal", "Thrash Metal", "Folk Metal", "Power Metal", "Heavy Metal", "Metalcore"],
}


def esc(value: str) -> str:
    return re.escape(value)


def keyword_in(text: str, keyword: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){esc(keyword)}(?![a-z0-9])", text, re.I) is not None


def normalize_tag(tag: str) -> str:
    text = tag.strip().lower().replace("ё", "е")
    text = re.sub(r"\br\s*&\s*b\b", "rnb", text)
    text = text.replace("&", " and ")
    text = re.sub(r"[–—−]", "-", text)
    text = re.sub(r"[-_/]+", " ", text)
    for src, dst in RU:
        text = re.sub(rf"(?<![а-яёa-z0-9]){esc(src)}(?![а-яёa-z0-9])", dst, text, flags=re.I)
    text = re.sub(r"[^a-z0-9а-я\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def is_noise(tag: str) -> bool:
    text = normalize_tag(tag)
    if not text or len(text) < 2 or len(text) > 60:
        return True
    if text in NOISE or text.replace(" ", "") in NOISE:
        return True
    if text.isdigit() or re.fullmatch(r"(19|20)\d{2}", text) or re.fullmatch(r"\d{2}s", text):
        return True
    return False


def explode(name: str) -> list[str]:
    return [part.strip() for part in re.split(r"\s*[/|;]\s*", name) if part.strip()]


def match_tag(raw: str):
    tag = normalize_tag(raw)
    if not tag or is_noise(tag):
        return None
    for key, main, sub, rank, exact in PHRASES:
        if exact:
            if tag == key:
                return key, main, sub, rank, tag
            continue
        if keyword_in(tag, key):
            return key, main, sub, rank, tag
    return None


def title_case(value: str) -> str:
    small = {"and", "of", "the", "n"}
    out = []
    for index, word in enumerate(value.split()):
        if index and word in small:
            out.append(word)
        elif word in {"idm", "edm", "ebm", "dnb", "ost"}:
            out.append(word.upper())
        elif word == "rnb":
            out.append("R&B")
        else:
            out.append(word[:1].upper() + word[1:])
    return " ".join(out)


def eclipse_factor(sub, source, weight, by_source, weight_of, sources_of) -> float:
    children = ECLIPSED_BY.get(sub)
    if not children:
        return 1.0
    siblings = by_source.get(source, set())
    parent_sources = len(sources_of.get(sub, ()))
    for child in children:
        if child in siblings:
            return 0.25
        child_sources = len(sources_of.get(child, ()))
        child_weight = weight_of.get(child, 0)
        if child_sources and child_sources >= parent_sources and child_weight >= weight * 0.45 and child_weight >= 3:
            return 0.25
    return 1.0


def should_place(verdict: dict, keep_unclear: bool) -> bool:
    """A named shelf is enough. Only Other stays put, unless the user asked to file those too."""
    if verdict.get("sub") not in (None, "", "Other"):
        return True
    return verdict.get("confidence") != "low" or keep_unclear


def classify_weighted(hits: list[dict]) -> dict:
    contribs = []
    for order, hit in enumerate(hits):
        if not hit.get("name") or not hit.get("weight"):
            continue
        for part_index, part in enumerate(explode(hit["name"])):
            matched = match_tag(part)
            if not matched:
                continue
            _key, main, sub, rank, tag = matched
            factor = 0.4 if rank <= 1 else 1
            contribs.append({
                "main": main,
                "sub": sub,
                "rank": rank,
                "weight": hit["weight"] * factor,
                "index": hit.get("index", order * 10 + part_index),
                "tag": tag,
                "source": hit.get("source") or "",
            })
    by_source: dict[str, set[str]] = {}
    weight_of: dict[str, float] = {}
    sources_of: dict[str, set[str]] = {}
    for contrib in contribs:
        by_source.setdefault(contrib["source"], set()).add(contrib["sub"])
        weight_of[contrib["sub"]] = weight_of.get(contrib["sub"], 0) + contrib["weight"]
        if contrib["source"]:
            sources_of.setdefault(contrib["sub"], set()).add(contrib["source"])
    buckets: dict[str, dict] = {}
    for contrib in contribs:
        weight = contrib["weight"] * eclipse_factor(
            contrib["sub"], contrib["source"], contrib["weight"], by_source, weight_of, sources_of
        )
        bucket = buckets.setdefault(f"{contrib['main']}|{contrib['sub']}", {
            "main": contrib["main"], "sub": contrib["sub"], "weight": 0,
            "rank": 0, "index": contrib["index"], "tags": [], "sources": [],
        })
        bucket["weight"] += weight
        bucket["rank"] = max(bucket["rank"], contrib["rank"])
        bucket["index"] = min(bucket["index"], contrib["index"])
        if contrib["tag"] not in bucket["tags"]:
            bucket["tags"].append(contrib["tag"])
        if contrib["source"] and contrib["source"] not in bucket["sources"]:
            bucket["sources"].append(contrib["source"])
    if not buckets:
        return {"main": "Other", "sub": "Other", "reason": "В тегах нет узнаваемого жанра.", "confidence": "low"}
    ranked = sorted(buckets.values(), key=lambda bucket: (
        -round(bucket["weight"], 3) if False else 0,
    ))
    def sort_key(bucket):
        return bucket
    ranked = list(buckets.values())
    ranked.sort(key=lambda a: (-a["weight"], a["rank"] <= 1, -len(a["sources"]), a["index"]))
    # Re-rank close weights the same way as the app: big gap by weight, else specificity.
    def better(a, b):
        if abs(a["weight"] - b["weight"]) > 0.35:
            return a["weight"] > b["weight"]
        if (a["rank"] <= 1) != (b["rank"] <= 1):
            return a["rank"] > 1
        if len(a["sources"]) != len(b["sources"]):
            return len(a["sources"]) > len(b["sources"])
        return a["index"] < b["index"]
    top = ranked[0]
    for candidate in ranked[1:]:
        if better(candidate, top):
            top = candidate
    sub = top["sub"]
    if top["rank"] <= 1:
        richer = sorted((tag for tag in top["tags"] if len(tag.split()) >= 2), key=len, reverse=True)
        if richer:
            sub = title_case(richer[0])
    second = None
    for candidate in ranked:
        if candidate is not top and (second is None or better(candidate, second)):
            second = candidate
    ratio = top["weight"] / max(second["weight"], 0.01) if second else 3
    if top["rank"] >= 2 and top["weight"] >= 8 and ratio >= 1.3:
        confidence = "high"
    elif top["rank"] >= 3 and top["weight"] >= 1.5:
        confidence = "medium"
    elif top["rank"] >= 2 and top["weight"] >= 3.2 or top["weight"] >= 5:
        confidence = "medium"
    else:
        confidence = "low"
    lead = ", ".join(title_case(tag) for tag in top["tags"][:3])
    via = ", ".join(source for source in top["sources"] if source)
    reason = f"Полка «{sub}» — теги {lead}" + (f" ({via})." if via else ".")
    return {"main": top["main"], "sub": sub, "reason": reason, "confidence": confidence}


def name_score(title: str, artist: str, album: str) -> int:
    hay = normalize_tag(title)
    artist_name = normalize_tag(artist)
    album_name = normalize_tag(album)
    if not hay or not album_name:
        return 0
    score = 0
    if artist_name and (artist_name in hay or hay in artist_name):
        score += 3
    if album_name in hay or hay in album_name:
        score += 5
    return score


RELEASE_NOISE = (
    r"(?:full\s*albums?|complete\s*albums?|полн(?:ый|ого)?\s+альбом|весь\s+альбом|"
    r"flac|mp3|aac|ogg|alac|wav|cue|cds?|web|vinyl|deluxe|remasters?(?:ed)?|"
    r"expanded|bonus|explicit|digital|16\s?bit|24\s?bit|320(?:\s?kbps)?|v0|v2|(?:19|20)\d{2})"
)


def strip_release_noise(value: str) -> str:
    text = value.strip()
    text = re.sub(r"\.(mp3|flac|m4a|ogg|wav|opus|zip|rar)$", "", text, flags=re.I)
    for _ in range(4):
        nxt = re.sub(rf"\s*[\[({{][^\[\](){{}}]{{0,80}}?{RELEASE_NOISE}[^\[\](){{}}]{{0,80}}?[\]}})]", " ", text, flags=re.I)
        nxt = re.sub(r"\bfull\s+albums?\b", " ", nxt, flags=re.I)
        nxt = re.sub(r"\bполн(?:ый|ого)?\s+альбом\b", " ", nxt, flags=re.I)
        nxt = re.sub(r"\s+", " ", nxt).strip()
        nxt = re.sub(r"^[-–—\s]+|[-–—\s]+$", "", nxt).strip()
        if nxt == text:
            break
        text = nxt
    return text


def parse_release_line(line: str):
    text = re.sub(r"^(?:19|20)\d{2}\s*[-–—]\s*", "", strip_release_noise(line))
    if not text:
        return None
    parts = [
        part for part in (strip_release_noise(piece) for piece in re.split(r"\s+[-–—]\s+", text))
        if part and not re.fullmatch(r"(?:19|20)\d{2}", part)
    ]
    if len(parts) < 2:
        return None
    return parts[0], " - ".join(parts[1:]).strip()


def _coerce_prefs(raw: dict) -> dict:
    prefs = dict(DEFAULT_PREFS)
    prefs["download_dir"] = str(HERE / "Downloads")
    if isinstance(raw, dict):
        for key, value in raw.items():
            if key in prefs and value is not None:
                prefs[key] = value
    prefs["version"] = VERSION
    prefs["discogs"] = str(prefs.get("discogs") or "").strip()
    prefs["lastfm"] = str(prefs.get("lastfm") or "").strip()
    prefs["source"] = str(prefs.get("source") or "").strip()
    prefs["catalog"] = str(prefs.get("catalog") or "").strip()
    prefs["download_dir"] = str(prefs.get("download_dir") or HERE / "Downloads").strip()
    for key in (
        "show_log", "tag_files", "fetch_covers", "dark", "move", "place_unclear",
        "use_youtube_folder", "use_discogs", "use_lastfm", "use_musicbrainz",
        "use_wikipedia", "use_itunes", "watch_enabled",
    ):
        prefs[key] = bool(prefs.get(key))
    try:
        prefs["watch_minutes"] = max(5, min(240, int(prefs.get("watch_minutes") or 15)))
    except (TypeError, ValueError):
        prefs["watch_minutes"] = 15
    prefs["cookies"] = str(prefs.get("cookies") or "").strip()
    watches = []
    raw_watches = prefs.get("watches") if isinstance(prefs.get("watches"), list) else []
    for item in raw_watches:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            continue
        mode = "sort" if str(item.get("mode") or "") == "sort" else "folder"
        watches.append({"url": url, "name": str(item.get("name") or "").strip(), "mode": mode,
                        "split": item.get("split") not in (False, 0, "0", "false", "off"),
                        "content": str(item.get("content") or "auto") if str(item.get("content") or "auto") in ("auto", "tracks", "albums") else "auto"})
    prefs["watches"] = watches
    lists = []
    for raw_list in prefs.get("lists") if isinstance(prefs.get("lists"), list) else []:
        if not isinstance(raw_list, dict) or not str(raw_list.get("name") or "").strip():
            continue
        items, seen = [], set()
        for item in raw_list.get("items") if isinstance(raw_list.get("items"), list) else []:
            if not isinstance(item, dict) or not str(item.get("id") or "").strip() or item["id"] in seen:
                continue
            seen.add(item["id"])
            items.append({key: str(item.get(key) or "") for key in ("id", "title", "channel", "duration", "url", "thumb")})
        lists.append({"name": str(raw_list["name"]).strip(), "watch": str(raw_list.get("watch") or ""), "items": items[:500]})
    prefs["lists"] = lists[:50]
    try:
        prefs["search_workers"] = max(1, min(8, int(prefs.get("search_workers") or 5)))
    except (TypeError, ValueError):
        prefs["search_workers"] = 5
    try:
        prefs["request_timeout"] = max(4, min(60, int(prefs.get("request_timeout") or 12)))
    except (TypeError, ValueError):
        prefs["request_timeout"] = 12
    if str(prefs.get("youtube_format") or "").lower() not in YT_FORMATS:
        prefs["youtube_format"] = "mp3"
    else:
        prefs["youtube_format"] = str(prefs["youtube_format"]).lower()
    kind = str(prefs.get("youtube_kind") or "video").lower()
    prefs["youtube_kind"] = "playlist" if kind in {"2", "playlist"} else "video"
    prefs["youtube_split"] = prefs.get("youtube_split") not in (False, 0, "0", "false", "off")
    return prefs


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_prefs(prefs: dict) -> None:
    ordered = {key: prefs.get(key, value) for key, value in DEFAULT_PREFS.items()}
    ordered["download_dir"] = prefs.get("download_dir") or str(HERE / "Downloads")
    PREFS_PATH.write_text(json.dumps(ordered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_settings(write_missing: bool = True) -> dict:
    raw = _read_json(PREFS_PATH) if PREFS_PATH.is_file() else _read_json(OLD_SETTINGS_PATH)
    prefs = _coerce_prefs(raw)
    if write_missing and (not PREFS_PATH.is_file() or any(key not in raw for key in DEFAULT_PREFS)):
        _write_prefs(prefs)
    return prefs


def save_settings(**updates) -> dict:
    updates = {key: value for key, value in updates.items() if value is not None}
    prefs = _coerce_prefs({**load_settings(write_missing=False), **updates})
    _write_prefs(prefs)
    return prefs


def _auth():
    try:
        import polka_auth
        return polka_auth
    except Exception:
        return None


def discogs_token() -> str:
    return load_settings()["discogs"]


def discogs_auth_headers() -> dict:
    """Подключённый Discogs (личный токен/OAuth из polka-auth.json), иначе токен из настроек."""
    auth = _auth()
    headers = auth.discogs_headers() if auth else {}
    if not headers and discogs_token():
        headers = {"Authorization": f"Discogs token={discogs_token()}"}
    return headers


def lastfm_key() -> str:
    key = load_settings()["lastfm"]
    auth = _auth()
    if not key and auth:
        key = auth.app_keys("lastfm")[0]
    return key


def safe_part(value: str) -> str:
    value = re.sub(r'[\\/:*?"<>|]+', " ", value or "")
    value = re.sub(r"\s+", " ", value).strip().rstrip(". ")
    return value or "Unknown"


def http_text(url: str, headers: dict | None = None, timeout: int | None = None) -> tuple[int, str]:
    if timeout is None:
        timeout = int(load_settings()["request_timeout"])
    request = urllib.request.Request(url, headers=headers or {"User-Agent": UA})
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=CTX) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", "replace")
        return error.code, body


def year_in_text(value: str) -> str:
    found = [int(item) for item in re.findall(r"(?:19|20)\d{2}", value or "")]
    found = [item for item in found if 1900 <= item <= 2035]
    return str(min(found)) if found else ""


def choose_year(options: list[tuple[int, int, str]]) -> tuple[str, str]:
    """Highest-trust source wins. Several years from it: the earliest is the original."""
    if not options:
        return "", ""
    trust = max(item[1] for item in options)
    pool = [item for item in options if item[1] == trust]
    year, _trust, source = min(pool, key=lambda item: item[0])
    return str(year), source


def lookup_album(artist: str, album: str, file_genres: list[str], hint_year: str = "") -> dict:
    hits = []
    log = []
    file_names = [genre for genre in file_genres if genre and not is_noise(genre)]
    for index, genre in enumerate(file_names):
        hits.append({"name": genre, "weight": 5, "source": "файл", "index": index})
    log.append("файл: " + (", ".join(file_names) if file_names else "в тегах жанра нет"))
    options = load_settings()
    jobs = [
        ("Discogs", "use_discogs", lambda: discogs_hits(artist, album)),
        ("Last.fm", "use_lastfm", lambda: lastfm_hits(artist, album)),
        ("MusicBrainz", "use_musicbrainz", lambda: musicbrainz_hits(artist, album)),
        ("Wikipedia", "use_wikipedia", lambda: wikipedia_hits(artist, album)),
        ("iTunes", "use_itunes", lambda: itunes_hits(artist, album)),
    ]
    jobs = [(label, fn) for label, flag, fn in jobs if options.get(flag, True)]
    found_remote = False
    years: list[tuple[int, int, str]] = []
    trust = {"MusicBrainz": 5, "Discogs": 4, "iTunes": 2}
    notes = {}
    if jobs:
        with ThreadPoolExecutor(max_workers=int(options["search_workers"])) as pool:
            futures = {pool.submit(fn): label for label, fn in jobs}
            for future in as_completed(futures):
                label = futures[future]
                try:
                    result = future.result()
                    notes[label] = result[1]
                    if result[0]:
                        found_remote = True
                        hits.extend(result[0])
                    if len(result) > 2 and result[2] and label in trust:
                        years.append((int(result[2]), trust[label], label))
                except Exception as error:
                    notes[label] = f"ошибка — {error}"
    for label, _fn in jobs:
        log.append(f"{label}: {notes.get(label, 'нет ответа')}")
    if not found_remote:
        try:
            got, note = web_hits(artist, album)
            hits.extend(got or [])
            log.append(f"Веб: {note}")
        except Exception as error:
            log.append(f"Веб: ошибка — {error}")
    verdict = classify_weighted(hits)
    verdict["artist"] = artist
    verdict["album"] = album
    year, year_source = choose_year(years)
    if not year and hint_year:
        year, year_source = hint_year, "название"
    verdict["year"] = year
    verdict["year_source"] = year_source
    if year:
        log.append(f"год оригинала: {year} ({year_source})")
    else:
        log.append("год оригинала: не нашёлся")
    verdict["log"] = log
    return verdict


def discogs_hits(artist: str, album: str) -> tuple[list[dict], str]:
    status, text = discogs_search(artist, album, True)
    note = ""
    if status == 401:
        note = "токен не подошёл, поиск без него. "
        status, text = discogs_search(artist, album, False)
    if status != 200 or not text.startswith("{"):
        return [], f"{note}Discogs {status}".strip(), ""
    results = json.loads(text).get("results") or []
    best = None
    best_score = -1
    years = []
    for row in results:
        score = name_score(row.get("title") or "", artist, album)
        fmt = " ".join(row.get("format") or [])
        if re.search("album", fmt, re.I):
            score += 1
        unofficial = bool(re.search("unofficial|compilation", fmt, re.I))
        if unofficial:
            score -= 2
        found = re.search(r"(19|20)\d{2}", str(row.get("year") or ""))
        if found and score >= 5 and not unofficial:
            years.append(int(found.group(0)))
        if score > best_score:
            best, best_score = row, score
    year = str(min(years)) if years else ""
    if not best or best_score < 5:
        return [], f"{note}релиз не найден".strip(), year
    hits = []
    for index, name in enumerate(best.get("style") or []):
        hits.append({"name": name, "weight": 6 + (2 if index == 0 else 0), "source": "Discogs", "index": 10 + index})
    for index, name in enumerate(best.get("genre") or []):
        hits.append({"name": name, "weight": 1, "source": "Discogs", "index": 20 + index})
    names = []
    for hit in hits:
        if hit["name"] not in names:
            names.append(hit["name"])
    if not names:
        return [], f"{note}у релиза нет стилей".strip(), year
    title = best.get("title") or "релиз"
    return hits, f"{note}{title}: {', '.join(names)}".strip(), year


def discogs_search(artist: str, album: str, with_token: bool):
    query = urllib.parse.urlencode({
        "artist": artist, "release_title": album, "type": "release", "per_page": "6",
    })
    headers = {"User-Agent": UA + " +https://grok.me"}
    if with_token:
        headers.update(discogs_auth_headers())
    return http_text("https://api.discogs.com/database/search?" + query, headers)


def lastfm_hits(artist: str, album: str) -> tuple[list[dict], str]:
    if not lastfm_key():
        return [], "нет ключа"
    try:
        tags = lastfm_tags("album.getTopTags", {"artist": artist, "album": album})
    except Exception as error:
        return [], str(error)
    source = "альбом"
    scale = 1.0
    index_base = 0
    if not tags:
        try:
            tags = lastfm_tags("artist.getTopTags", {"artist": artist})[:5]
        except Exception as error:
            return [], str(error)
        source = "артист"
        scale = 0.55
        index_base = 40
    if not tags:
        return [], "пусто"
    top = tags[0]["count"] or 1
    hits = []
    kept = []
    for index, tag in enumerate(tags[:8]):
        ratio = tag["count"] / top
        if index and ratio < (0.2 if scale < 1 else 0.12):
            continue
        weight = (2 + 4 * ratio + (1 if index == 0 else 0)) * scale
        hits.append({"name": tag["name"], "weight": weight, "source": "Last.fm" if source == "альбом" else "Last.fm · артист", "index": index_base + index})
        kept.append(tag["name"])
    return hits, f"{source}: {', '.join(kept)}"


def lastfm_tags(method: str, params: dict) -> list[dict]:
    query = urllib.parse.urlencode({
        "method": method, "api_key": lastfm_key(), "format": "json", "autocorrect": "1", **params,
    })
    status, text = http_text("https://ws.audioscrobbler.com/2.0/?" + query)
    if status != 200:
        raise RuntimeError(f"Last.fm {status}")
    data = json.loads(text)
    if data.get("error"):
        raise RuntimeError(data.get("message") or f"Last.fm {data.get('error')}")
    raw = (data.get("toptags") or {}).get("tag") or []
    if isinstance(raw, dict):
        raw = [raw]
    tags = []
    for item in raw:
        name = item.get("name")
        if not name or is_noise(name):
            continue
        tags.append({"name": name, "count": float(item.get("count") or 0)})
    return tags


def musicbrainz_hits(artist: str, album: str) -> tuple[list[dict], str]:
    headers = {"User-Agent": UA + " (local)", "Accept": "application/json"}
    query = urllib.parse.urlencode({
        "query": f'release:"{album}" AND artist:"{artist}"', "fmt": "json", "limit": "5",
    })
    status, text = http_text("https://musicbrainz.org/ws/2/release-group?" + query, headers)
    if status != 200:
        return [], f"MusicBrainz {status}", ""
    groups = json.loads(text).get("release-groups") or []
    best = None
    best_score = -1
    for row in groups:
        credit = " ".join(
            (item.get("name") or (item.get("artist") or {}).get("name") or "")
            for item in (row.get("artist-credit") or [])
        )
        score = name_score(f"{credit} {row.get('title') or ''}", artist, album)
        if normalize_tag(row.get("title") or "") == normalize_tag(album):
            score += 2
        if score > best_score:
            best, best_score = row, score
    origin = year_in_text((best or {}).get("first-release-date") or "") if best_score >= 5 else ""
    if not best or best_score < 5 or not best.get("id"):
        return [], "релиз не найден", origin
    status, text = http_text(
        f"https://musicbrainz.org/ws/2/release-group/{best['id']}?inc=genres+tags&fmt=json",
        headers,
    )
    if status != 200:
        return [], f"MusicBrainz {status}", origin
    genres = [
        genre for genre in (json.loads(text).get("genres") or [])
        if genre.get("name") and (genre.get("count") or 0) >= 2 and not is_noise(genre["name"])
    ]
    genres.sort(key=lambda genre: genre.get("count") or 0, reverse=True)
    hits = []
    for index, genre in enumerate(genres[:8]):
        count = genre.get("count") or 0
        weight = 5 if count >= 10 else 3.5 if count >= 4 else 2
        hits.append({
            "name": genre["name"],
            "weight": weight + (1.5 if index == 0 else 0),
            "source": "MusicBrainz",
            "index": 30 + index,
        })
    if not hits:
        return [], "жанры не проставлены", origin
    return hits, ", ".join(hit["name"] for hit in hits), origin


def wikipedia_hits(artist: str, album: str) -> tuple[list[dict], str]:
    for lang in ("en", "ru"):
        genres = wiki_genres(lang, artist, album)
        if genres:
            return [
                {"name": name, "weight": 5 + (2 if index == 0 else 0), "source": "Wikipedia", "index": 15 + index}
                for index, name in enumerate(genres[:6])
            ], ", ".join(genres[:6])
    return [], "пусто"


def wiki_genres(lang: str, artist: str, album: str) -> list[str]:
    headers = {"User-Agent": UA}
    query = urllib.parse.urlencode({
        "action": "query", "list": "search", "srsearch": f"{album} {artist}",
        "srlimit": "5", "format": "json",
    })
    status, text = http_text(f"https://{lang}.wikipedia.org/w/api.php?{query}", headers)
    if status != 200:
        return []
    pages = ((json.loads(text).get("query") or {}).get("search") or [])
    title = ""
    best = 0
    for page in pages:
        score = name_score(page.get("title") or "", artist, album)
        if score > best:
            best = score
            title = page.get("title") or ""
    if not title or best < 3:
        return []
    query = urllib.parse.urlencode({
        "action": "parse", "page": title, "prop": "wikitext", "format": "json", "redirects": "1",
    })
    status, text = http_text(f"https://{lang}.wikipedia.org/w/api.php?{query}", headers)
    if status != 200:
        return []
    wikitext = (((json.loads(text).get("parse") or {}).get("wikitext") or {}).get("*") or "")
    return extract_wiki_genres(wikitext)


def extract_wiki_genres(wikitext: str) -> list[str]:
    match = re.search(r"\|\s*genre\s*=([\s\S]*?)(?=\n\s*\|)", wikitext, re.I)
    if not match:
        return []
    raw = match.group(1)
    raw = re.sub(r"<ref[\s\S]*?</ref>", " ", raw, flags=re.I)
    raw = re.sub(r"<!--[\s\S]*?-->", " ", raw)
    raw = re.sub(r"\{\{nowrap\|([^{}|]+)\}\}", r"\1", raw, flags=re.I)
    raw = re.sub(r"\{\{hlist\|([\s\S]*?)\}\}", lambda m: m.group(1).replace("|", ", "), raw, flags=re.I)
    raw = re.sub(r"\{\{[^{}]*\}\}", " ", raw)
    raw = re.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"\2", raw)
    raw = re.sub(r"\[\[([^\]]+)\]\]", r"\1", raw)
    raw = re.sub(r"<br\s*/?>", ",", raw, flags=re.I)
    parts = []
    for part in re.split(r"[,;\n*]", raw):
        part = re.sub(r"\s+", " ", part).strip()
        if 1 < len(part) < 48 and part.lower() != "genre":
            parts.append(part)
    return list(dict.fromkeys(parts))


def itunes_hits(artist: str, album: str) -> tuple[list[dict], str]:
    query = urllib.parse.urlencode({
        "term": f"{artist} {album}", "entity": "album", "limit": "8", "country": "US",
    })
    status, text = http_text("https://itunes.apple.com/search?" + query)
    if status != 200:
        return [], f"iTunes {status}", ""
    best = None
    best_score = -1
    for row in json.loads(text).get("results") or []:
        found = normalize_tag(row.get("artistName") or "")
        wanted = normalize_tag(artist)
        if not found or not wanted:
            continue
        if found == wanted:
            artist_fit = 4
        elif wanted in found or found in wanted:
            artist_fit = 3
        else:
            continue
        score = artist_fit + name_score(row.get("collectionName") or "", artist, album)
        if score > best_score:
            best, best_score = row, score
    if not best or best_score < 7 or not best.get("primaryGenreName"):
        released = year_in_text((best or {}).get("releaseDate") or "") if best_score >= 7 else ""
        return [], "точного альбома нет", released
    hits = [
        {"name": name, "weight": 2.2, "source": "iTunes", "index": 50 + index}
        for index, name in enumerate(re.split(r"\s*[/|]\s*", best["primaryGenreName"]))
        if name
    ]
    who = f"{best.get('artistName') or ''} — {best.get('collectionName') or ''}".strip(" —")
    return hits, f"{who}: {', '.join(hit['name'] for hit in hits)}", year_in_text(best.get("releaseDate") or "")


def web_hits(artist: str, album: str) -> tuple[list[dict], str]:
    query = urllib.parse.urlencode({"q": f"{artist} {album} genre"})
    status, text = http_text("https://html.duckduckgo.com/html/?" + query, {"User-Agent": BROWSER_UA})
    if status != 200 or re.search(r"client challenge|captcha", text[:1500], re.I):
        return [], "поисковик не отдал страницу"
    blob = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>|<[^>]+>", " ", text, flags=re.I)
    found = phrases_in_text(blob)[:6]
    if not found:
        return [], "в сниппетах жанра нет"
    return [{"name": name, "weight": 1, "source": "Веб", "index": 80 + index} for index, name in enumerate(found)], ", ".join(found)


def phrases_in_text(raw: str) -> list[str]:
    text = normalize_tag(raw)
    found = []
    for key, _main, _sub, rank, exact in PHRASES:
        if exact or rank < 2:
            continue
        if " " not in key and key not in {"shoegaze", "dubstep", "synthwave", "dungeon synth"}:
            if " " not in key:
                continue
        if keyword_in(text, key):
            found.append(key)
            text = re.sub(rf"(?<![a-z0-9]){esc(key)}(?![a-z0-9])", " ", text, flags=re.I)
    return list(dict.fromkeys(found))


def load_cache() -> dict:
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_cache(cache: dict) -> None:
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def cache_key(artist: str, album: str) -> str:
    return normalize_tag(f"{artist} {album}")


def is_audio(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in AUDIO


def contains_audio(folder: Path, levels: int = 2) -> bool:
    try:
        for child in folder.iterdir():
            if is_audio(child):
                return True
            if child.is_dir() and levels > 0 and not child.name.startswith(".") and contains_audio(child, levels - 1):
                return True
    except OSError:
        return False
    return False


def find_albums(root: Path) -> list[Path]:
    albums = []
    try:
        entries = list(root.iterdir())
    except OSError:
        return albums
    if any(is_audio(path) for path in entries):
        albums.append(root)
    for child in sorted(path for path in entries if path.is_dir() and not path.name.startswith(".")):
        try:
            kids = list(child.iterdir())
        except OSError:
            continue
        if any(is_audio(path) for path in kids):
            albums.append(child)
            continue
        nested = []
        for sub in kids:
            if not sub.is_dir() or sub.name.startswith("."):
                continue
            try:
                if any(is_audio(path) for path in sub.iterdir()):
                    nested.append(sub)
            except OSError:
                continue
        if nested:
            albums.extend(sorted(nested))
        elif contains_audio(child, 2):
            albums.append(child)
    return albums


def read_audio_tags(folder: Path) -> tuple[str | None, str | None, list[str]]:
    artist = album = None
    genres: list[str] = []
    seen = 0
    for path in folder.rglob("*"):
        if not is_audio(path):
            continue
        seen += 1
        if seen > 12:
            break
        try:
            got = read_file_tags(path)
        except Exception:
            continue
        if not got:
            continue
        artist = artist or got.get("artist")
        album = album or got.get("album")
        for genre in got.get("genres") or []:
            if genre and genre not in genres:
                genres.append(genre)
        if artist and album and genres:
            break
    return artist, album, genres


def read_file_tags(path: Path) -> dict | None:
    try:
        import mutagen
        audio = mutagen.File(path, easy=True)
        if audio:
            def first(key):
                values = audio.get(key) or []
                return values[0] if values else None
            return {"artist": first("artist"), "album": first("album"), "genres": list(audio.get("genre") or [])}
    except Exception:
        pass
    suffix = path.suffix.lower()
    if suffix == ".mp3":
        return read_id3(path)
    if suffix == ".flac":
        return read_flac(path)
    if suffix in {".m4a", ".mp4"}:
        return read_mp4(path)
    return None


def read_id3(path: Path) -> dict | None:
    with path.open("rb") as handle:
        header = handle.read(10)
        if header[:3] != b"ID3" or len(header) < 10:
            return None
        version = header[3]
        size = synchsafe(header[6:10])
        data = handle.read(size)
    if version < 3:
        return None
    cursor = 0
    if header[5] & 0x40 and len(data) >= 4:
        ext = synchsafe(data[:4]) if version >= 4 else int.from_bytes(data[:4], "big")
        cursor = 4 + ext if version >= 4 else ext
    found = {}
    while cursor + 10 <= len(data):
        frame_id = data[cursor:cursor + 4]
        if frame_id == b"\x00\x00\x00\x00" or not frame_id[0]:
            break
        frame_size = synchsafe(data[cursor + 4:cursor + 8]) if version >= 4 else int.from_bytes(data[cursor + 4:cursor + 8], "big")
        start = cursor + 10
        end = start + frame_size
        if frame_size <= 0 or end > len(data):
            break
        key = frame_id.decode("latin1", "replace")
        if key in {"TPE1", "TALB", "TCON", "TIT2", "TRCK", "TDRC", "TYER", "TORY", "TDOR"}:
            found[key] = decode_id3_text(data[start:end])
        cursor = end
    if not found:
        return None
    genres = split_genre(found.get("TCON") or "")
    return {
        "artist": found.get("TPE1"),
        "album": found.get("TALB"),
        "genres": genres,
        "title": found.get("TIT2"),
        "track": found.get("TRCK"),
        "year": year_in_text(found.get("TDRC") or found.get("TYER") or found.get("TORY") or ""),
    }


def synchsafe(raw: bytes) -> int:
    return ((raw[0] & 0x7F) << 21) | ((raw[1] & 0x7F) << 14) | ((raw[2] & 0x7F) << 7) | (raw[3] & 0x7F)


def decode_id3_text(payload: bytes) -> str:
    if not payload:
        return ""
    encoding, body = payload[0], payload[1:]
    body = body.split(b"\x00\x00" if encoding in {1, 2} else b"\x00", 1)[0]
    if encoding == 0:
        return body.decode("latin1", "replace").strip()
    if encoding == 1:
        return body.decode("utf-16", "replace").strip("\x00").strip()
    if encoding == 2:
        return body.decode("utf-16-be", "replace").strip("\x00").strip()
    return body.decode("utf-8", "replace").strip("\x00").strip()


def split_genre(value: str) -> list[str]:
    value = re.sub(r"\(\d+\)", " ", value)
    return [part.strip() for part in re.split(r"\s*[/;,]\s*", value) if part.strip()]


def read_flac(path: Path) -> dict | None:
    with path.open("rb") as handle:
        if handle.read(4) != b"fLaC":
            return None
        comments = []
        for _ in range(16):
            head = handle.read(4)
            if len(head) < 4:
                break
            block_type = head[0] & 0x7F
            length = int.from_bytes(head[1:4], "big")
            block = handle.read(length)
            if block_type == 4 and len(block) >= 8:
                vendor = int.from_bytes(block[:4], "little")
                cursor = 4 + vendor
                if cursor + 4 > len(block):
                    break
                count = int.from_bytes(block[cursor:cursor + 4], "little")
                cursor += 4
                for _comment in range(count):
                    if cursor + 4 > len(block):
                        break
                    size = int.from_bytes(block[cursor:cursor + 4], "little")
                    cursor += 4
                    comments.append(block[cursor:cursor + size].decode("utf-8", "replace"))
                    cursor += size
                break
            if head[0] & 0x80:
                break
    fields = {}
    for comment in comments:
        if "=" not in comment:
            continue
        key, value = comment.split("=", 1)
        fields.setdefault(key.upper(), []).append(value.strip())
    if not fields:
        return None
    return {
        "artist": (fields.get("ARTIST") or [None])[0],
        "album": (fields.get("ALBUM") or [None])[0],
        "genres": fields.get("GENRE") or [],
    }


def read_mp4(path: Path) -> dict | None:
    chunks = []
    with path.open("rb") as handle:
        chunks.append(handle.read(1_500_000))
        size = path.stat().st_size
        if size > 1_500_000:
            handle.seek(max(0, size - 1_500_000))
            chunks.append(handle.read(1_500_000))
    blob = b"".join(chunks)
    def grab(atom: bytes) -> str | None:
        start = 0
        while True:
            index = blob.find(atom, start)
            if index < 0:
                return None
            data_at = blob.find(b"data", index, index + 80)
            if data_at < 4:
                start = index + 4
                continue
            atom_size = int.from_bytes(blob[data_at - 4:data_at], "big")
            text_at = data_at + 16
            text_end = data_at - 4 + atom_size
            if atom_size < 16 or text_end > len(blob) or text_end <= text_at:
                start = index + 4
                continue
            try:
                return blob[text_at:text_end].decode("utf-8").strip("\x00").strip()
            except UnicodeDecodeError:
                return None
    artist = grab(b"\xa9ART")
    album = grab(b"\xa9alb")
    genre = grab(b"\xa9gen")
    if not any((artist, album, genre)):
        return None
    return {"artist": artist, "album": album, "genres": split_genre(genre or "")}


def describe_album(folder: Path, inbox: Path) -> dict:
    tag_artist, tag_album, genres = read_audio_tags(folder)
    parsed = parse_release_line(folder.name)
    tag_artist = clean_identity(tag_artist, folder.name)
    tag_album = clean_identity(tag_album, folder.name)
    if parsed:
        # Folder is the video title: "Artist - Album". File tags from YouTube
        # are the channel name, so they lose unless they say the same thing.
        artist, album = parsed
        if tag_album and _same_name(tag_album, album) and len(tag_album) > len(album):
            album = tag_album
    else:
        artist = tag_artist
        album = tag_album
        if not album:
            album = strip_release_noise(folder.name) or folder.name
        if not artist and folder.parent != inbox and folder != inbox:
            parent = folder.parent.name
            if parent.lower() not in {"music", "downloads", "inbox", "unsorted"}:
                artist = strip_release_noise(parent) or parent
        if not artist:
            artist = strip_release_noise(folder.name) or folder.name
    return {"path": folder, "artist": artist.strip(), "album": album.strip(), "genres": genres, "hint_year": year_in_text(folder.name)}


def _same_tag(left: str | None, right: str | None) -> bool:
    """Точное совпадение тега (без учёта регистра и пробелов) — для записи тегов."""
    if not left or not right:
        return False
    return " ".join(left.split()).casefold() == " ".join(right.split()).casefold()


def clean_track_title(title: str, number: str) -> str:
    """'3. Bathsalts' при треке 3 -> 'Bathsalts'."""
    match = re.match(r"^\s*0*(\d{1,3})\s*[.)\-–—:]\s*(.+)$", title)
    if match and (not number or int(match.group(1)) == int(number)):
        return match.group(2).strip()
    return title


def _same_name(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False
    a, b = normalize_tag(left), normalize_tag(right)
    return bool(a and b and (a == b or a in b or b in a))


def clean_identity(value: str | None, folder_name: str) -> str | None:
    if not value:
        return None
    cleaned = strip_release_noise(value)
    if not cleaned:
        return None
    if normalize_tag(cleaned) == normalize_tag(folder_name):
        return None
    return cleaned


def reuse_name(parent: Path, name: str) -> str:
    safe = safe_part(name)
    key = normalize_tag(safe)
    if parent.is_dir() and key:
        for child in parent.iterdir():
            if child.is_dir() and normalize_tag(child.name) == key:
                return child.name
    return safe


def find_group_folder(catalog: Path, artist: str) -> Path | None:
    """Artist folder already inside the catalog, not a new root next to Rock/Electronic."""
    key = normalize_tag(artist)
    if not key or not catalog.is_dir():
        return None
    found: list[Path] = []
    for path in catalog.rglob("*"):
        if not path.is_dir():
            continue
        try:
            depth = len(path.relative_to(catalog).parts)
        except ValueError:
            continue
        if depth < 2 or depth > 4 or normalize_tag(path.name) != key:
            continue
        try:
            if any(is_audio(child) for child in path.iterdir()):
                continue
        except OSError:
            continue
        found.append(path)
    if not found:
        return None
    found.sort(key=lambda path: len(path.relative_to(catalog).parts))
    return found[0]


def destination(catalog: Path, verdict: dict) -> Path:
    album = safe_part(verdict["album"])
    home = find_group_folder(catalog, verdict["artist"])
    if home:
        return home / album
    main = reuse_name(catalog, verdict["main"])
    sub = reuse_name(catalog / main, verdict["sub"])
    artist = reuse_name(catalog / main / sub, verdict["artist"])
    return catalog / main / sub / artist / album


def sort_one(item: dict, cache: dict, use_net: bool) -> dict:
    key = cache_key(item["artist"], item["album"])
    cached = cache.get(key)
    if cached and "year" in cached:
        verdict = dict(cached)
        verdict["log"] = ["из кэша, источники заново не спрашивались"]
    elif use_net:
        verdict = lookup_album(item["artist"], item["album"], item["genres"], item.get("hint_year") or "")
        cache[key] = {
            field: verdict.get(field, "")
            for field in ("main", "sub", "reason", "confidence", "year", "year_source")
        }
    else:
        verdict = classify_weighted([
            {"name": genre, "weight": 5, "source": "файл", "index": index}
            for index, genre in enumerate(item["genres"])
        ])
        verdict["artist"] = item["artist"]
        verdict["album"] = item["album"]
        verdict["log"] = ["сеть выключена, только теги файла"]
    verdict["path"] = item["path"]
    verdict["artist"] = item["artist"]
    verdict["album"] = item["album"]
    return verdict


def encode_synchsafe(size: int) -> bytes:
    return bytes([(size >> 21) & 0x7F, (size >> 14) & 0x7F, (size >> 7) & 0x7F, size & 0x7F])


def id3_text_frame(frame_id: str, text: str, version: int) -> bytes:
    body = b"\x01" + text.encode("utf-16")
    size = encode_synchsafe(len(body)) if version >= 4 else len(body).to_bytes(4, "big")
    return frame_id.encode("ascii") + size + b"\x00\x00" + body


def id3_apic_frame(picture: bytes, mime: str, version: int) -> bytes:
    body = b"\x00" + mime.encode("ascii") + b"\x00\x03\x00" + picture
    size = encode_synchsafe(len(body)) if version >= 4 else len(body).to_bytes(4, "big")
    return b"APIC" + size + b"\x00\x00" + body


def stamp_id3(
    path: Path, artist: str, album: str, genre: str, picture: bytes | None, mime: str,
    title: str = "", track: str = "", year: str = "",
) -> set[str]:
    data = path.read_bytes()
    version = 3
    frames: list[bytes] = []
    have: set[str] = set()
    audio = data
    if data[:3] == b"ID3" and len(data) >= 10 and data[3] in (3, 4):
        if data[5] & 0x80:
            return set()
        version = data[3]
        tag_size = synchsafe(data[6:10])
        tag = data[10:10 + tag_size]
        audio = data[10 + tag_size:]
        cursor = 0
        if data[5] & 0x40 and len(tag) >= 4:
            extra = synchsafe(tag[:4]) if version >= 4 else int.from_bytes(tag[:4], "big")
            cursor = extra if version < 4 else 4 + extra
        while cursor + 10 <= len(tag):
            frame_id = tag[cursor:cursor + 4]
            if frame_id == b"\x00\x00\x00\x00" or not frame_id[0]:
                break
            frame_size = synchsafe(tag[cursor + 4:cursor + 8]) if version >= 4 else int.from_bytes(tag[cursor + 4:cursor + 8], "big")
            end = cursor + 10 + frame_size
            if frame_size <= 0 or end > len(tag):
                break
            frames.append(tag[cursor:end])
            have.add(frame_id.decode("latin1", "replace"))
            cursor = end
    elif data[:3] == b"ID3":
        return set()
    texts: dict[str, str] = {}
    kept: list[bytes] = []
    for raw in frames:
        fid = raw[:4].decode("latin1", "replace")
        if fid in {"TPE1", "TALB", "TCON", "TIT2", "TRCK", "TDRC", "TYER", "TORY", "TDOR"}:
            texts[fid] = decode_id3_text(raw[10:])
        if artist and fid == "TPE1" and not _same_tag(texts.get("TPE1"), artist):
            continue
        if album and fid == "TALB" and not _same_tag(texts.get("TALB"), album):
            continue
        if title and fid == "TIT2" and not _same_tag(texts.get("TIT2"), title):
            continue
        if track and fid == "TRCK" and not _same_tag(texts.get("TRCK"), track):
            continue
        if year and fid in {"TDRC", "TYER", "TORY", "TDOR"} and year_in_text(texts.get(fid) or "") != year:
            continue
        kept.append(raw)
    done: set[str] = set()
    extra = b""
    if artist and not _same_tag(texts.get("TPE1"), artist):
        extra += id3_text_frame("TPE1", artist, version)
        done.add("artist")
    if album and not _same_tag(texts.get("TALB"), album):
        extra += id3_text_frame("TALB", album, version)
        done.add("album")
    if title and not _same_tag(texts.get("TIT2"), title):
        extra += id3_text_frame("TIT2", title, version)
        done.add("title")
    if track and not _same_tag(texts.get("TRCK"), track):
        extra += id3_text_frame("TRCK", track, version)
        done.add("track")
    current_year = year_in_text(texts.get("TDRC") or texts.get("TYER") or texts.get("TORY") or "")
    if year and current_year != year:
        for frame_id in ("TDRC", "TYER", "TORY"):
            extra += id3_text_frame(frame_id, year, version)
        done.add("year")
    if genre and "TCON" not in have:
        extra += id3_text_frame("TCON", genre, version)
        done.add("genre")
    if picture and "APIC" not in have:
        extra += id3_apic_frame(picture, mime, version)
        done.add("cover")
    if not extra:
        return set()
    blob = b"".join(kept) + extra
    header = b"ID3" + bytes([version, 0, 0]) + encode_synchsafe(len(blob))
    path.write_bytes(header + blob + audio)
    return done


def parse_vorbis_comments(block: bytes) -> list[str]:
    if len(block) < 8:
        return []
    vendor = int.from_bytes(block[:4], "little")
    cursor = 4 + vendor
    if cursor + 4 > len(block):
        return []
    count = int.from_bytes(block[cursor:cursor + 4], "little")
    cursor += 4
    comments = []
    for _ in range(count):
        if cursor + 4 > len(block):
            break
        size = int.from_bytes(block[cursor:cursor + 4], "little")
        cursor += 4
        comments.append(block[cursor:cursor + size].decode("utf-8", "replace"))
        cursor += size
    return comments


def build_vorbis_comments(comments: list[str]) -> bytes:
    vendor = b"Polka"
    out = len(vendor).to_bytes(4, "little") + vendor + len(comments).to_bytes(4, "little")
    for comment in comments:
        raw = comment.encode("utf-8")
        out += len(raw).to_bytes(4, "little") + raw
    return out


def flac_picture_block(picture: bytes, mime: str) -> bytes:
    mime_raw = mime.encode("ascii")
    return b"".join([
        (3).to_bytes(4, "big"),
        len(mime_raw).to_bytes(4, "big"),
        mime_raw,
        (0).to_bytes(4, "big"),
        (0).to_bytes(4, "big"),
        (0).to_bytes(4, "big"),
        (0).to_bytes(4, "big"),
        (0).to_bytes(4, "big"),
        len(picture).to_bytes(4, "big"),
        picture,
    ])


def stamp_flac(
    path: Path, artist: str, album: str, genre: str, picture: bytes | None, mime: str,
    title: str = "", track: str = "", year: str = "",
) -> set[str]:
    data = path.read_bytes()
    if data[:4] != b"fLaC":
        return set()
    blocks = []
    cursor = 4
    rest = b""
    while cursor + 4 <= len(data):
        header = data[cursor]
        size = int.from_bytes(data[cursor + 1:cursor + 4], "big")
        body = data[cursor + 4:cursor + 4 + size]
        if len(body) != size:
            return set()
        blocks.append([header & 0x7F, body])
        cursor += 4 + size
        if header & 0x80:
            rest = data[cursor:]
            break
    else:
        return set()
    done: set[str] = set()
    keys = set()
    comment_at = None
    for index, (kind, body) in enumerate(blocks):
        if kind == 4:
            comment_at = index
            for comment in parse_vorbis_comments(body):
                if "=" in comment:
                    keys.add(comment.split("=", 1)[0].upper())
    comments = parse_vorbis_comments(blocks[comment_at][1]) if comment_at is not None else []

    def comment_value(key: str) -> str:
        for comment in comments:
            if comment.upper().startswith(key + "="):
                return comment.split("=", 1)[1]
        return ""

    if artist and not _same_tag(comment_value("ARTIST"), artist):
        comments = [comment for comment in comments if not comment.upper().startswith("ARTIST=")]
        comments.append(f"ARTIST={artist}")
        done.add("artist")
    if album and not _same_tag(comment_value("ALBUM"), album):
        comments = [comment for comment in comments if not comment.upper().startswith("ALBUM=")]
        comments.append(f"ALBUM={album}")
        done.add("album")
    if title and not _same_tag(comment_value("TITLE"), title):
        comments = [comment for comment in comments if not comment.upper().startswith("TITLE=")]
        comments.append(f"TITLE={title}")
        done.add("title")
    if track and not _same_tag(comment_value("TRACKNUMBER"), track):
        comments = [comment for comment in comments if not comment.upper().startswith("TRACKNUMBER=")]
        comments.append(f"TRACKNUMBER={track}")
        done.add("track")
    if year and year_in_text(comment_value("ORIGINALDATE") or comment_value("DATE")) != year:
        comments = [
            comment for comment in comments
            if not comment.upper().startswith(("DATE=", "ORIGINALDATE="))
        ]
        comments.append(f"DATE={year}")
        comments.append(f"ORIGINALDATE={year}")
        done.add("year")
    if genre and "GENRE" not in keys:
        comments.append(f"GENRE={genre}")
        done.add("genre")
    if comment_at is None and comments:
        blocks.append([4, build_vorbis_comments(comments)])
    elif comment_at is not None and done:
        blocks[comment_at][1] = build_vorbis_comments(comments)
    if picture and not any(kind == 6 for kind, _body in blocks):
        blocks.append([6, flac_picture_block(picture, mime)])
        done.add("cover")
    if not done:
        return set()
    out = bytearray(b"fLaC")
    for index, (kind, body) in enumerate(blocks):
        last = 0x80 if index == len(blocks) - 1 else 0
        out += bytes([kind | last]) + len(body).to_bytes(3, "big") + body
    out += rest
    path.write_bytes(out)
    return done


def stamp_mutagen(
    path: Path, artist: str, album: str, genre: str, picture: bytes | None, mime: str,
    title: str = "", track: str = "", year: str = "",
) -> set[str] | None:
    try:
        from mutagen.flac import Picture
        from mutagen.mp4 import MP4, MP4Cover
        from mutagen.oggopus import OggOpus
        from mutagen.oggvorbis import OggVorbis
    except Exception:
        return None
    suffix = path.suffix.lower()
    try:
        if suffix in {".m4a", ".mp4"}:
            audio = MP4(path)
        elif suffix == ".opus":
            audio = OggOpus(path)
        elif suffix == ".ogg":
            audio = OggVorbis(path)
        else:
            return None
    except Exception:
        return set()
    done: set[str] = set()

    def current(key: str) -> str:
        value = audio.get(key)
        if isinstance(value, list):
            return str(value[0]) if value else ""
        return str(value or "")

    if suffix in {".m4a", ".mp4"}:
        if artist and not _same_tag(current("\xa9ART"), artist):
            audio["\xa9ART"] = [artist]
            done.add("artist")
        if album and not _same_tag(current("\xa9alb"), album):
            audio["\xa9alb"] = [album]
            done.add("album")
        if title and not _same_tag(current("\xa9nam"), title):
            audio["\xa9nam"] = [title]
            done.add("title")
        if track:
            audio["trkn"] = [(int(track), 0)]
            done.add("track")
        if year and year_in_text(current("\xa9day")) != year:
            audio["\xa9day"] = [year]
            done.add("year")
        if genre and "\xa9gen" not in audio:
            audio["\xa9gen"] = [genre]
            done.add("genre")
        if picture and "covr" not in audio:
            imageformat = MP4Cover.FORMAT_PNG if "png" in mime else MP4Cover.FORMAT_JPEG
            audio["covr"] = [MP4Cover(picture, imageformat=imageformat)]
            done.add("cover")
    else:
        if artist and not _same_tag(current("ARTIST"), artist):
            audio["ARTIST"] = [artist]
            done.add("artist")
        if album and not _same_tag(current("ALBUM"), album):
            audio["ALBUM"] = [album]
            done.add("album")
        if title and not _same_tag(current("TITLE"), title):
            audio["TITLE"] = [title]
            done.add("title")
        if track and not _same_tag(current("TRACKNUMBER"), track):
            audio["TRACKNUMBER"] = [track]
            done.add("track")
        if year and year_in_text(current("DATE") or current("ORIGINALDATE")) != year:
            audio["DATE"] = [year]
            audio["ORIGINALDATE"] = [year]
            done.add("year")
        if genre and "GENRE" not in audio:
            audio["GENRE"] = [genre]
            done.add("genre")
        if picture and "METADATA_BLOCK_PICTURE" not in audio:
            pic = Picture()
            pic.type = 3
            pic.mime = mime
            pic.data = picture
            import base64
            audio["METADATA_BLOCK_PICTURE"] = [base64.b64encode(pic.write()).decode("ascii")]
            done.add("cover")
    if done:
        audio.save()
    return done


def stamp_file(
    path: Path, artist: str, album: str, genre: str, picture: bytes | None, mime: str,
    title: str = "", track: str = "", year: str = "",
) -> set[str]:
    suffix = path.suffix.lower()
    try:
        if suffix == ".mp3":
            return stamp_id3(path, artist, album, genre, picture, mime, title, track, year)
        if suffix == ".flac":
            return stamp_flac(path, artist, album, genre, picture, mime, title, track, year)
        other = stamp_mutagen(path, artist, album, genre, picture, mime, title, track, year)
        return other or set()
    except Exception:
        return set()


def _ensure_mutagen_cli() -> bool:
    try:
        import mutagen  # noqa: F401
        return True
    except ImportError:
        pass
    print("Ставлю библиотеку mutagen…")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--quiet", "mutagen"],
            check=True, timeout=300,
        )
        import importlib
        importlib.invalidate_caches()
        import mutagen  # noqa: F401,F811
        return True
    except Exception as error:
        print(f"mutagen не установился ({error}); m4a/opus/ogg останутся без тегов.")
        return False


def stamp_download_tree(root: Path) -> int:
    if not root.is_dir():
        print("папка не открылась")
        return 0
    fix_bare_names(root)
    folders = [path for path in root.iterdir() if path.is_dir() and path.name != "_full"]
    if not folders:
        folders = [root]
    has_mutagen: bool | None = None
    total = 0
    for folder in folders:
        parsed = parse_release_line(folder.name)
        if not parsed:
            continue
        artist, album = parsed
        changed = 0
        skipped = 0
        for path in sorted(folder.rglob("*")):
            if not is_audio(path):
                continue
            if path.suffix.lower() not in {".mp3", ".flac"}:
                if has_mutagen is None:
                    has_mutagen = _ensure_mutagen_cli()
                if not has_mutagen:
                    skipped += 1
                    total += 1
                    continue
            match = re.match(r"^(\d{1,3})\s*-\s*(.+)$", path.stem)
            number = str(int(match.group(1))) if match else ""
            title = clean_track_title(match.group(2).strip(), number) if match else ""
            if match and title != match.group(2).strip():
                target = path.with_name(f"{match.group(1)} - {safe_part(title)}{path.suffix}")
                if not target.exists():
                    path = path.rename(target)
            if stamp_file(path, artist, album, "", None, "image/jpeg", title, number):
                changed += 1
            total += 1
        clean_name = safe_part(f"{artist} - {album}")
        if clean_name and clean_name != folder.name and not (folder.parent / clean_name).exists():
            folder.rename(folder.parent / clean_name)
            print(f"папка: {folder.name} -> {clean_name}")
        note = f", без тегов (нет mutagen): {skipped}" if skipped else ""
        print(f"{artist} — {album}: изменено {changed}{note}")
    return total


def find_folder_cover(folder: Path) -> Path | None:
    names = {"cover", "folder", "front", "album", "artwork", "thumb"}
    images = []
    try:
        children = list(folder.iterdir())
    except OSError:
        return None
    for child in children:
        if child.is_file() and child.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
            images.append(child)
    for image in images:
        if image.stem.lower() in names:
            return image
    return images[0] if images else None


def fetch_image(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(request, timeout=15, context=CTX) as response:
            data = response.read(8_000_000)
            ctype = (response.headers.get("Content-Type") or "").lower()
    except Exception:
        return None
    if not data or len(data) < 32:
        return None
    if data[:3] == b"\xff\xd8\xff":
        return data, "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return data, "image/png"
    if "png" in ctype:
        return data, "image/png"
    if "jpeg" in ctype or "jpg" in ctype:
        return data, "image/jpeg"
    return None


def itunes_artwork_url(artist: str, album: str) -> str | None:
    query = urllib.parse.urlencode({
        "term": f"{artist} {album}", "entity": "album", "limit": "8", "country": "US",
    })
    status, text = http_text("https://itunes.apple.com/search?" + query)
    if status != 200 or not text.startswith("{"):
        return None
    best = None
    best_score = -1
    for row in json.loads(text).get("results") or []:
        found = normalize_tag(row.get("artistName") or "")
        wanted = normalize_tag(artist)
        if not found or not wanted:
            continue
        if found == wanted:
            artist_fit = 4
        elif wanted in found or found in wanted:
            artist_fit = 3
        else:
            continue
        score = artist_fit + name_score(row.get("collectionName") or "", artist, album)
        if score > best_score:
            best, best_score = row, score
    if not best or best_score < 7:
        return None
    art = best.get("artworkUrl100") or ""
    if not art:
        return None
    return art.replace("100x100bb", "600x600bb")


def download_cover(artist: str, album: str):
    url = itunes_artwork_url(artist, album)
    if url:
        got = fetch_image(url)
        if got:
            return got
    headers = {"User-Agent": UA + " (local)", "Accept": "application/json"}
    query = urllib.parse.urlencode({
        "query": f'release:"{album}" AND artist:"{artist}"', "fmt": "json", "limit": "5",
    })
    status, text = http_text("https://musicbrainz.org/ws/2/release-group?" + query, headers)
    if status != 200 or not text.startswith("{"):
        return None
    best_id = ""
    best_score = -1
    for row in json.loads(text).get("release-groups") or []:
        credit = " ".join(
            (item.get("name") or (item.get("artist") or {}).get("name") or "")
            for item in (row.get("artist-credit") or [])
        )
        score = name_score(f"{credit} {row.get('title') or ''}", artist, album)
        if score > best_score:
            best_score = score
            best_id = row.get("id") or ""
    if not best_id or best_score < 5:
        return None
    return fetch_image(f"https://coverartarchive.org/release-group/{best_id}/front-500")


def enrich_album(
    folder: Path,
    artist: str,
    album: str,
    genre: str,
    fetch_cover=None,
    write_tags: bool = True,
    fetch_covers: bool = True,
    year: str = "",
) -> list[str]:
    if not folder.is_dir():
        return ["теги: папка не открылась"]
    picture = None
    mime = "image/jpeg"
    lines = []
    if fetch_covers:
        cover = find_folder_cover(folder)
        if cover:
            try:
                picture = cover.read_bytes()
                mime = "image/png" if cover.suffix.lower() == ".png" else "image/jpeg"
                lines.append(f"обложка: уже лежит {cover.name}")
            except OSError:
                picture = None
        if picture is None:
            getter = fetch_cover or download_cover
            try:
                got = getter(artist, album)
            except Exception as error:
                got = None
                lines.append(f"обложка: ошибка — {error}")
            if got:
                picture, mime = got
                name = "cover.png" if mime == "image/png" else "cover.jpg"
                try:
                    (folder / name).write_bytes(picture)
                    lines.append(f"обложка: скачана {name}")
                except OSError as error:
                    lines.append(f"обложка: не сохранилась — {error}")
                    picture = None
            elif not any(line.startswith("обложка:") for line in lines):
                lines.append("обложка: не нашлась")
    files = [path for path in folder.rglob("*") if is_audio(path)][:80]
    tag_artist = artist if write_tags else ""
    tag_album = album if write_tags else ""
    tag_genre = genre if write_tags else ""
    tag_year = year if write_tags else ""
    genre_n = artist_n = cover_n = year_n = 0
    for path in files:
        done = stamp_file(path, tag_artist, tag_album, tag_genre, picture if fetch_covers else None, mime, year=tag_year)
        genre_n += "genre" in done
        artist_n += "artist" in done or "album" in done
        cover_n += "cover" in done
        year_n += "year" in done
    if write_tags:
        if not files:
            lines.append("теги: аудиофайлов нет")
        elif genre_n or artist_n or year_n:
            bits = []
            if genre_n:
                bits.append(f"жанр «{genre}» в {genre_n}")
            if artist_n:
                bits.append(f"артист/альбом в {artist_n}")
            if year_n:
                bits.append(f"год {year} в {year_n}")
            lines.append("теги: дописаны " + ", ".join(bits))
        else:
            lines.append("теги: уже стояли")
    if fetch_covers and cover_n:
        lines.append(f"обложка: вшита в {cover_n} файлов")
    return lines


def album_log(item: dict) -> str:
    lines = [f"{item.get('artist') or '?'} — {item.get('album') or '?'}"]
    for line in item.get("log") or []:
        lines.append(f"  {line}")
    lines.append(f"  → {item.get('main')} / {item.get('sub')} ({item.get('confidence') or 'low'})")
    if item.get("reason"):
        lines.append(f"  {item['reason']}")
    if item.get("placed"):
        lines.append(f"  {item['placed']}")
    return "\n".join(lines)


def place(verdict: dict, catalog: Path, move: bool) -> str:
    src = Path(verdict["path"]).resolve()
    dest = destination(catalog, verdict).resolve()
    catalog_resolved = catalog.resolve()
    if catalog_resolved == src or catalog_resolved in src.parents:
        return "каталог внутри альбома — пропуск"
    if src == dest:
        return "уже на месте"
    if dest.exists():
        return "такая папка в каталоге уже есть"
    try:
        dest.relative_to(src)
        return "нельзя перенести папку саму в себя"
    except ValueError:
        pass
    dest.parent.mkdir(parents=True, exist_ok=True)
    if move:
        shutil.move(str(src), str(dest))
    else:
        shutil.copytree(src, dest)
    return "ok"


DOWNLOADED_NAME = "downloaded.json"


def downloaded_path(prefs: dict) -> Path:
    """Список скачанных ID: <каталог>/downloaded.json, по одному ID YouTube в строке."""
    base = str(prefs.get("catalog") or "").strip() or str(prefs.get("download_dir") or "").strip()
    return Path(base or HERE / "Downloads") / DOWNLOADED_NAME


def read_downloaded_ids(path: Path) -> set[str]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return set()
    return {line.strip() for line in lines if line.strip()}


def append_downloaded_id(path: Path, video_id: str) -> bool:
    video_id = video_id.strip()
    if not video_id or video_id in read_downloaded_ids(path):
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(video_id + "\n")
    return True


def skip_archive(ids_path: Path) -> Path:
    """Временный архив yt-dlp из downloaded.json: yt-dlp пропустит уже скачанные ID."""
    archive = HERE / "_skip-archive.txt"
    ids = sorted(read_downloaded_ids(ids_path))
    archive.write_text("".join(f"youtube {video_id}\n" for video_id in ids), encoding="utf-8")
    return archive


def skip_args(prefs: dict) -> list[str]:
    """yt-dlp пропускает ID из downloaded.json и дописывает туда ID каждого скачанного видео."""
    ids_path = downloaded_path(prefs)
    ids_path.parent.mkdir(parents=True, exist_ok=True)
    return [
        "--download-archive", str(skip_archive(ids_path)),
        "--print-to-file", "after_move:id", str(ids_path),
    ]


def new_ids(rows: list[dict], done: set[str]) -> list[str]:
    return [row["id"] for row in rows if row.get("id") and row["id"] not in done]


def yt_format(fmt) -> str:
    fmt = str(fmt or "mp3").lower()
    return fmt if fmt in YT_FORMATS else "mp3"


def yt_audio_args(fmt) -> list[str]:
    """То же, что делает Downloader.bat: ogg → vorbis, обложка только где поддерживается."""
    fmt = yt_format(fmt)
    args = ["-x", "--audio-format", "vorbis" if fmt == "ogg" else fmt, "--audio-quality", "0"]
    if fmt in YT_THUMB_FORMATS:
        args.append("--embed-thumbnail")
    return args + ["--embed-metadata", "--ignore-errors"]


def yt_download_args(url: str, kind: str, fmt: str, outdir: str, split: bool = True) -> list[str]:
    """Аргументы yt-dlp, которые соберёт Downloader.bat (для проверки без Windows)."""
    sep = "\\"
    args = yt_audio_args(fmt) + ["--yes-playlist" if str(kind) == "2" else "--no-playlist"]
    meta = ["--parse-metadata", "%(title)s:%(artist)s - %(album)s"]
    if split:
        return args + ["--split-chapters", *meta, "-o", f"{outdir}{sep}_full{sep}%(title)s.%(ext)s",
                       "-o", f"chapter:{outdir}{sep}%(title)s{sep}%(section_number)02d - %(section_title)s.%(ext)s", url]
    if str(kind) == "2":
        return args + ["-o", f"{outdir}{sep}%(playlist_title)s{sep}%(playlist_index)02d - %(title)s.%(ext)s", url]
    return args + [*meta, "-o", f"{outdir}{sep}%(title)s{sep}%(title)s.%(ext)s", url]


def downloader_command(url: str, kind: str, fmt: str, outdir: str, prefs: dict, split: bool | None = None) -> str:
    ids_path = downloaded_path(prefs)
    ids_path.parent.mkdir(parents=True, exist_ok=True)
    archive = skip_archive(ids_path)
    if split is None:
        split = bool(prefs.get("youtube_split", True))
    parts = (str(HERE / "Downloader.bat"), url, kind, yt_format(fmt), outdir, str(ids_path), str(archive), "1" if split else "0")
    return "call " + " ".join('"' + part.replace('"', "") + '"' for part in parts)


def run_playlist(entry: dict, prefs: dict, log, cache: dict | None = None) -> None:
    """«Куда класть»: sort — скачать и разложить по жанрам в каталог; folder — папка с именем плейлиста."""
    def run(command, shell=False):
        process = subprocess.Popen(command, shell=shell, cwd=str(HERE), stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        assert process.stdout is not None
        for raw in process.stdout:
            log(raw.decode("utf-8", "replace").rstrip("\n"))
        process.wait()

    content = entry.get("content") or "auto"
    rows: list[dict] = []
    try:
        rows = fetch_playlist(entry["url"], str(prefs.get("cookies") or ""))[2]
    except Exception as error:
        log(f"список плейлиста не прочитался: {error}")
    if content == "tracks" or (content == "auto" and is_track_list([row.get("seconds") for row in rows])):
        run_tracks(entry, prefs, log, run, cache)
        return
    if entry.get("mode") != "sort":
        command, dest = watch_plan(entry, prefs)
        dest.mkdir(parents=True, exist_ok=True)
        run(command)
        if entry.get("split", True):
            settle_full(dest, log)
        fix_bare_names(dest, log)
        base = downloaded_path(prefs).parent
        remember_album_paths(rows, {re.sub(r'^\d{2,3} - ', '', p.stem): p for p in dest.iterdir()}, base, prefs)
        for child in dest.iterdir():
            log(placed_line(re.sub(r'^\d{2,3} - ', '', child.stem), child))
        return
    catalog = require_root(prefs)
    staging = staging_dir(prefs)
    staging.mkdir(parents=True, exist_ok=True)
    kind = "2" if "list=" in entry["url"] else "1"
    run(downloader_command(entry["url"], kind, str(prefs.get("youtube_format") or "mp3"), str(staging), prefs,
                           bool(entry.get("split", True))), shell=True)
    placed = sort_staging(staging, catalog, prefs, log, cache)
    remember_album_paths(rows, placed, downloaded_path(prefs).parent, prefs)


def sort_staging(staging: Path, catalog: Path, prefs: dict, log=print, cache: dict | None = None,
                 use_net: bool = True) -> dict:
    """Раскладывает ВСЁ, что лежит во временной папке, — и свежее, и остатки прошлых запусков."""
    cache = cache if cache is not None else load_cache()
    placed: dict = {}
    full = staging / "_full"
    if full.is_dir():
        settle_full(staging, log)
    for folder in sorted(p for p in staging.iterdir() if p.is_dir() and p.name != "_full"):
        if not any(is_audio(item) for item in folder.rglob("*")):
            shutil.rmtree(folder, ignore_errors=True)
            continue
        try:
            fix_bare_names(folder, log)
            item = describe_album(folder, staging)
            verdict = sort_one(item, cache, use_net=use_net)
            verdict.update(path=str(folder), artist=item["artist"], album=item["album"])
            if not should_place(verdict, bool(prefs.get("place_unclear"))):
                log(f"{item['artist']} — {item['album']}: жанр не ясен, оставлено в {folder}")
                placed[folder.name] = folder
                continue
            status, dest = place_merge(verdict, catalog)
            placed[folder.name] = dest
            log(f"{item['artist']} — {item['album']} → {catalog_relative(dest, catalog)} ({status})")
            log(placed_line(folder.name, dest))
        except Exception as error:
            log(f"{folder.name}: {error}")
    save_cache(cache)
    return placed


def place_merge(verdict: dict, catalog: Path) -> tuple[str, Path]:
    """Кладёт альбом в каталог. Папка этого альбома уже есть — докладываем недостающие файлы.
    «Уже есть» — только если там лежат те же файлы (имя и размер), а не просто папка артиста."""
    src = Path(verdict["path"])
    dest = destination(catalog, verdict)
    dest.mkdir(parents=True, exist_ok=True)
    moved = same = 0
    for path in sorted(src.rglob("*")):
        if not path.is_file():
            continue
        target = dest / path.relative_to(src)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.stat().st_size == path.stat().st_size:
            path.unlink()
            same += 1
            continue
        if target.exists():
            target = target.with_name(f"{target.stem} (2){target.suffix}")
        shutil.move(str(path), str(target))
        moved += 1
    shutil.rmtree(src, ignore_errors=True)
    if moved:
        return ("ok" if not same else f"добавлено {moved}, уже было {same}"), dest
    return "уже был в каталоге — те же файлы", dest


# ---- плейлисты из отдельных треков ----
TRACK_MAX_SECONDS = 15 * 60
PATHS_NAME = "polka-paths.json"
SINGLES = "Singles"


def ru_plural(n: int, one: str, few: str, many: str) -> str:
    """ru_plural(2, "трек", "трека", "треков") → «2 трека»."""
    a = abs(n) % 100
    b = a % 10
    word = many if 10 < a < 20 else one if b == 1 else few if 2 <= b <= 4 else many
    return f"{n} {word}"


def paths_file(prefs: dict) -> Path:
    """Куда легли скачанные видео: <каталог>/polka-paths.json, {id: путь относительно каталога}."""
    return downloaded_path(prefs).parent / PATHS_NAME


def read_paths(prefs: dict) -> dict:
    try:
        data = json.loads(paths_file(prefs).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def remember_paths(prefs: dict, mapping: dict) -> None:
    if not mapping:
        return
    data = read_paths(prefs)
    data.update({str(k): str(v).replace("\\", "/") for k, v in mapping.items() if k and v})
    path = paths_file(prefs)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def catalog_relative(path: Path, base: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return str(path)


def is_track_list(seconds: list) -> bool:
    """Плейлист треков: все известные длительности короче 15 минут."""
    known = [int(s) for s in seconds if isinstance(s, (int, float)) and s > 0]
    return bool(known) and max(known) < TRACK_MAX_SECONDS


def _provided_meta(description: str) -> dict:
    """YouTube Music «Provided to YouTube by …»: строка «Название · Артист», затем альбом."""
    lines = [line.strip() for line in str(description or "").splitlines() if line.strip()]
    if not lines or not lines[0].lower().startswith("provided to youtube"):
        return {}
    out: dict = {}
    if len(lines) > 1 and " · " in lines[1]:
        parts = [p.strip() for p in lines[1].split(" · ")]
        out["title"], out["artist"] = parts[0], parts[1]
        if len(lines) > 2 and not lines[2].startswith(("℗", "Released on", "Auto-generated")):
            out["album"] = lines[2]
    for line in lines:
        match = re.match(r"Released on:\s*(\d{4})", line)
        if match:
            out["year"] = match.group(1)
    return out


def track_meta(info: dict) -> dict:
    """artist/title/album/track/year из info.json yt-dlp (+ описание YouTube Music, + «Артист - Название»)."""
    provided = _provided_meta(info.get("description") or "")
    title = str(info.get("title") or "").strip()
    artist = str(info.get("artist") or info.get("creator") or provided.get("artist") or "").split(",")[0].strip()
    track = str(info.get("track") or provided.get("title") or "").strip()
    if not artist or not track:
        parsed = parse_release_line(title)
        if parsed:
            artist = artist or parsed[0]
            track = track or strip_release_noise(parsed[1]) or parsed[1]
    if not artist:
        artist = re.sub(r"\s*-\s*Topic$", "", str(info.get("channel") or info.get("uploader") or "")).strip()
    year = str(info.get("release_year") or provided.get("year") or "")[:4]
    number = info.get("track_number")
    return {"artist": artist or "Unknown", "title": track or title or str(info.get("id") or ""),
            "album": str(info.get("album") or provided.get("album") or "").strip(),
            "track": str(number) if number else "", "year": year}


def lookup_track_album(artist: str, title: str) -> dict:
    """Альбом по артисту и названию: Last.fm track.getInfo, затем MusicBrainz (без ключа)."""
    title = re.sub(r"\s*[\(\[][^)\]]*(remaster|official|video|audio|lyric|mono|stereo|version|hd|hq)[^)\]]*[\)\]]", "", title, flags=re.I).strip() or title
    if lastfm_key():
        try:
            query = urllib.parse.urlencode({"method": "track.getInfo", "artist": artist, "track": title,
                                            "api_key": lastfm_key(), "format": "json", "autocorrect": "1"})
            status, text = http_text("https://ws.audioscrobbler.com/2.0/?" + query)
            album = (json.loads(text).get("track") or {}).get("album") or {} if status == 200 else {}
            if album.get("title"):
                pos = (album.get("@attr") or {}).get("position") or ""
                return {"album": album["title"], "track": str(pos), "source": "Last.fm"}
        except Exception:
            pass
    try:
        headers = {"User-Agent": UA + " (local)", "Accept": "application/json"}
        query = urllib.parse.urlencode({"query": f'recording:"{title}" AND artist:"{artist}" AND status:official',
                                        "fmt": "json", "limit": "25"})
        status, text = http_text("https://musicbrainz.org/ws/2/recording?" + query, headers)
        if status == 200 and text.startswith("{"):
            best = None
            for rec in json.loads(text).get("recordings") or []:
                if int(rec.get("score") or 0) < 90:
                    continue
                for rel in rec.get("releases") or []:
                    group = rel.get("release-group") or {}
                    kind = group.get("primary-type") or ""
                    rank = {"Album": 0, "EP": 1, "Single": 2}.get(kind, 3) + (2 if group.get("secondary-types") else 0)
                    date = str(rel.get("date") or "9999")
                    number = ""
                    for medium in rel.get("media") or []:
                        for item in medium.get("track") or []:
                            number = str(item.get("number") or "")
                            if not number.isdigit() and isinstance(medium.get("track-offset"), int):
                                number = str(medium["track-offset"] + 1)
                    if best is None or (rank, date) < best[0]:
                        best = ((rank, date), {"album": rel.get("title") or "", "track": number if number.isdigit() else "",
                                               "year": date[:4] if date[:4].isdigit() else "", "single": kind == "Single",
                                               "source": "MusicBrainz"})
            if best and best[1]["album"]:
                return best[1]
    except Exception:
        pass
    return {}


def track_file_name(meta: dict, ext: str, index: str = "") -> str:
    """«NN - Название.ext»; без номера — «Название.ext». Никогда не голый номер."""
    title = safe_part(meta.get("title") or "")
    number = str(index or meta.get("track") or "").strip()
    if number.isdigit():
        return f"{int(number):02d} - {title}{ext}"
    return f"{title}{ext}"


def fix_bare_names(root: Path, log=print) -> int:
    """Страховка: «1.mp3» → «01 - Название.mp3» по тегу title (или по названию папки)."""
    fixed = 0
    if not root.is_dir():
        return 0
    for path in sorted(root.rglob("*")):
        if not is_audio(path) or not re.fullmatch(r"\d{1,3}", path.stem):
            continue
        title = ""
        try:
            import mutagen
            audio = mutagen.File(path, easy=True)
            title = ((audio or {}).get("title") or [""])[0]
        except Exception:
            pass
        title = title or path.parent.name
        target = path.with_name(f"{int(path.stem):02d} - {safe_part(title)}{path.suffix}")
        if not target.exists():
            path.rename(target)
            fixed += 1
            log(f"имя без названия: {path.name} → {target.name}")
    return fixed


def tracks_command(entry: dict, prefs: dict, tmp: Path) -> list[str]:
    command = [tool_path("yt-dlp"), *yt_audio_args(prefs.get("youtube_format")), "--newline",
               "--ffmpeg-location", ffmpeg_dir(), *skip_args(prefs), "--windows-filenames", "--no-overwrites",
               "--yes-playlist", "--write-info-json", "--no-write-playlist-metafiles",
               "-o", str(tmp / "%(title).80B [%(id)s].%(ext)s"), "-o", "infojson:" + str(tmp / "%(id)s")]
    cookies = str(prefs.get("cookies") or "").strip()
    if cookies:
        command += ["--cookies", cookies]
    return command + [str(entry["url"])]


def settle_tracks(tmp: Path, entry: dict, prefs: dict, log=print, cache: dict | None = None, use_net: bool = True) -> dict:
    """Треки из tmp: теги, альбом (метаданные → Last.fm/MusicBrainz), раскладка. Возвращает {id: путь}."""
    sort_mode = entry.get("mode") == "sort"
    catalog = require_root(prefs)
    base = downloaded_path(prefs).parent
    items = []
    for info_path in sorted(tmp.glob("*.info.json")):
        try:
            info = json.loads(info_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        vid = str(info.get("id") or info_path.name.split(".")[0])
        audio = next((p for p in tmp.glob(f"*[[]{glob_escape(vid)}].*") if is_audio(p)), None)
        if not audio:
            continue
        meta = track_meta(info)
        if not meta["album"] and use_net:
            found = lookup_track_album(meta["artist"], meta["title"])
            if found.get("album") and not found.get("single"):
                meta["album"] = found["album"]
                meta["track"] = meta["track"] or found.get("track", "")
                meta["year"] = meta["year"] or found.get("year", "")
                log(f"{meta['artist']} — {meta['title']}: альбом «{meta['album']}» ({found.get('source')})")
        elif meta["album"] and not meta["track"] and use_net:
            found = lookup_track_album(meta["artist"], meta["title"])
            if normalize_tag(found.get("album") or "") == normalize_tag(meta["album"]):
                meta["track"] = found.get("track", "")
        meta["album"] = meta["album"] or SINGLES
        if meta["album"] == SINGLES:
            meta["track"] = ""
        items.append((vid, audio, meta, info))
    mapping: dict = {}
    groups: dict = {}
    for vid, audio, meta, info in items:
        stamp_file(audio, meta["artist"], meta["album"], "", None, "image/jpeg", meta["title"], meta["track"], meta["year"])
        if sort_mode:
            groups.setdefault((meta["artist"], meta["album"]), []).append((vid, audio, meta))
        else:
            dest = base / "Плейлисты" / safe_part(str(entry.get("name") or "Плейлист"))
            dest.mkdir(parents=True, exist_ok=True)
            index = str(info.get("playlist_index") or "")
            name = track_file_name({"title": f"{meta['artist']} - {meta['title']}"}, audio.suffix, index)
            target = dest / name
            if not target.exists():
                shutil.move(str(audio), str(target))
            mapping[vid] = catalog_relative(target, base)
            log(f"{meta['title']} → {mapping[vid]}")
            log(placed_line(audio.stem, target))
    cache = cache if cache is not None else load_cache()
    for (artist, album), tracks in groups.items():
        probe = album if album != SINGLES else tracks[0][2]["title"]
        verdict = sort_one({"path": tmp, "artist": artist, "album": probe, "genres": [],
                            "hint_year": tracks[0][2]["year"]}, cache, use_net) if use_net else \
            {"main": "Разное", "sub": "Разное", "confidence": "low"}
        verdict.update(artist=artist, album=album)
        if verdict.get("main") and should_place(verdict, bool(prefs.get("place_unclear"))):
            dest = destination(catalog, verdict)
        else:
            dest = catalog / "Разобрать" / safe_part(artist) / safe_part(album)
        dest.mkdir(parents=True, exist_ok=True)
        for vid, audio, meta in tracks:
            target = dest / track_file_name(meta, audio.suffix)
            if not target.exists():
                shutil.move(str(audio), str(target))
            mapping[vid] = catalog_relative(target, base)
            log(f"{artist} — {meta['title']} → {mapping[vid]}")
            log(placed_line(audio.stem, target))
    save_cache(cache)
    remember_paths(prefs, mapping)
    return mapping


def glob_escape(text: str) -> str:
    return re.sub(r"([\[\]*?])", r"[\1]", text)


def run_tracks(entry: dict, prefs: dict, log, run, cache: dict | None = None) -> dict:
    """Плейлист отдельных треков: без разбиения на главы, группировка по альбомам."""
    tmp = staging_dir(prefs) / "_tracks"
    tmp.mkdir(parents=True, exist_ok=True)
    log("Плейлист треков: качаю целиком и раскладываю по альбомам.")
    run(tracks_command(entry, prefs, tmp))
    mapping = settle_tracks(tmp, entry, prefs, log, cache)
    for leftover in tmp.glob("*.info.json"):
        leftover.unlink(missing_ok=True)
    try:
        tmp.rmdir()
    except OSError:
        pass
    return mapping


def remember_album_paths(rows: list[dict], placed: dict, base: Path, prefs: dict) -> None:
    """Альбомы из .bat: папка = название видео; сопоставляем с ID плейлиста."""
    mapping = {}
    for row in rows:
        key = normalize_tag(safe_part(row.get("title") or ""))
        for name, path in placed.items():
            if key and normalize_tag(name) == key:
                mapping[row["id"]] = catalog_relative(Path(path), base)
    remember_paths(prefs, mapping)


def watch_plan(entry: dict, prefs: dict) -> tuple[list[str], Path]:
    """Папка плейлиста. split (по умолчанию да): главы → «NN - видео/NN - глава», без глав — целый файл."""
    command = [
        tool_path("yt-dlp"),
        *yt_audio_args(prefs.get("youtube_format")),
        "--newline",
        "--ffmpeg-location", ffmpeg_dir(),
        *skip_args(prefs),
        "--windows-filenames",
        "--no-overwrites",
    ]
    cookies = str(prefs.get("cookies") or "").strip()
    if cookies:
        command += ["--cookies", cookies]
    base = require_root(prefs)
    name = safe_part(str(entry.get("name") or "Плейлист"))
    dest = base / "Плейлисты" / name
    command.append("--yes-playlist")
    if entry.get("split", True):
        command += [
            "--split-chapters",
            "-o", str(dest / "_full" / "%(playlist_index)02d - %(title)s.%(ext)s"),
            "-o", "chapter:" + str(dest / "%(playlist_index)02d - %(title)s" / "%(section_number)02d - %(section_title)s.%(ext)s"),
        ]
    else:
        command += ["-o", str(dest / "%(playlist_index)02d - %(title)s.%(ext)s")]
    command.append(str(entry["url"]))
    return command, dest


def settle_full(dest: Path, log=print) -> list[str]:
    """После --split-chapters: если главы нарезаны — целый файл удаляем, иначе кладём его в папку плейлиста."""
    full = dest / "_full"
    whole: list[str] = []
    if not full.is_dir():
        return whole
    for path in sorted(full.iterdir()):
        if not is_audio(path):
            continue
        tracks = dest / path.stem
        if tracks.is_dir() and any(is_audio(item) for item in tracks.iterdir()):
            path.unlink(missing_ok=True)
            continue
        target = dest / path.name
        if not target.exists():
            path.replace(target)
        else:
            path.unlink(missing_ok=True)
        whole.append(path.stem)
        log(f"{re.sub(r'^\d{2,3} - ', '', path.stem)}: нет таймкодов — скачан целиком")
    try:
        full.rmdir()
    except OSError:
        pass
    return whole


# ---- ход скачивания: разбор строк yt-dlp (--newline) ----
_PCT = re.compile(r"^\[download\]\s+(\d+(?:\.\d+)?)%")
_ITEM = re.compile(r"^\[download\] Downloading (?:item|video) (\d+) of (\d+)")
_DEST = re.compile(r"^\[download\] Destination: (.+)$")
_DONE = re.compile(r"^\[download\] (.+?) has already been (?:downloaded|recorded in the archive)")
_CHAP = re.compile(r"^\[SplitChapters\] Splitting video by chapters; (\d+) chapters found")


def progress_new() -> dict:
    return {"title": "", "item": 0, "total": 0, "percent": 0.0, "stage": "", "chapters": 0,
            "done": 0, "skipped": 0, "whole": [], "error": "", "items": [], "failed": 0}


ROOT_MISSING = "Не выбрана корневая папка"
PLACED_MARK = "@@placed\t"


def require_root(prefs: dict) -> Path:
    """Корневая папка обязательна: без неё ничего не качаем (никаких запасных Downloads)."""
    root = str(prefs.get("catalog") or "").strip()
    if not root:
        raise RuntimeError(ROOT_MISSING)
    return Path(root)


def link_dir(prefs: dict) -> Path:
    """Скачанное по ссылке/из поиска: <корневая>/Скачанное с YouTube."""
    return require_root(prefs) / "Скачанное с YouTube"


def staging_dir(prefs: dict) -> Path:
    """Временная папка внутри корневой: всё, что в ней лежит, — ещё не разложено."""
    return require_root(prefs) / "_Полка-загрузка"


def friendly_error(text: str) -> str:
    """Короткое русское объяснение вместо сырой ошибки yt-dlp."""
    low = text.lower()
    if "blocked it in your country" in low or "copyright grounds" in low or "not available in your country" in low:
        return "недоступно в вашей стране (авторские права)"
    if "copyright" in low:
        return "удалено по жалобе правообладателя"
    if "private video" in low:
        return "приватное видео"
    if "sign in to confirm your age" in low or "age-restricted" in low:
        return "нужен вход: ограничение по возрасту (укажи cookies)"
    if "video unavailable" in low or "has been removed" in low or "no longer available" in low:
        return "видео недоступно"
    if "members-only" in low or "join this channel" in low:
        return "только для спонсоров канала"
    if "http error 429" in low or "too many requests" in low:
        return "YouTube временно ограничил запросы — попробуй позже"
    if "ffmpeg" in low and "not found" in low:
        return "не найден ffmpeg"
    return re.sub(r"^\[[^\]]+\]\s*[\w-]+:\s*", "", text).strip()[:140]


def _current_item(state: dict) -> dict:
    if not state["items"]:
        state["items"].append({"title": state.get("title") or "", "state": "скачиваю", "percent": 0.0, "path": "", "note": ""})
    return state["items"][-1]


def placed_line(title: str, path) -> str:
    """Строка для лога: куда лёг альбом/трек (UI показывает её в списке, а не в логе)."""
    return f"{PLACED_MARK}{title}\t{path}"


def _title_from_path(raw: str) -> str:
    name = Path(raw.strip().replace("\\", "/")).stem
    name = re.sub(r"\.f\d+$", "", name)
    return re.sub(r"^\d{2,3} - ", "", name)


def progress_update(state: dict, line: str) -> dict:
    """Обновляет state по одной строке вывода yt-dlp/Downloader.bat."""
    line = line.strip()
    if not line:
        return state
    if line.startswith(PLACED_MARK):
        _mark, title, path = (line.split("\t") + ["", ""])[:3]
        key = normalize_tag(title)
        target = next((it for it in state["items"] if key and (normalize_tag(it["title"]) == key
                       or key in normalize_tag(it["title"]) or normalize_tag(it["title"]) in key) and not it["path"]), None)
        if target is None:
            target = {"title": title, "state": "готово", "percent": 100.0, "path": "", "note": ""}
            state["items"].append(target)
        target["path"] = path
        if target["state"] not in ("ошибка", "недоступно"):
            target["state"] = "готово"
        return state
    match = _ITEM.match(line)
    if match:
        state.update(item=int(match.group(1)), total=int(match.group(2)), percent=0.0, stage="скачиваю", chapters=0)
        if state["items"] and state["items"][-1]["state"] in ("скачиваю", "конвертирую", "теги", "разбиваю"):
            state["items"][-1]["state"] = "готово"
        state["items"].append({"title": "", "state": "скачиваю", "percent": 0.0, "path": "", "note": "", "n": int(match.group(1))})
        return state
    match = _DEST.match(line)
    if match:
        if "_full" in match.group(1) or not state["title"] or state["stage"] in ("", "готово", "скачиваю"):
            state["title"] = re.sub(r"\s*\[[\w-]{11}\]$", "", _title_from_path(match.group(1)))
            item = _current_item(state)
            if not item["title"] or item["state"] == "скачиваю":
                item["title"] = state["title"]
        state["stage"] = "скачиваю"
        return state
    match = _PCT.match(line)
    if match:
        state["percent"] = float(match.group(1))
        state["stage"] = "скачиваю"
        _current_item(state)["percent"] = state["percent"]
        return state
    match = _DONE.match(line)
    if match:
        state["skipped"] += 1
        state["percent"] = 100.0
        item = _current_item(state)
        item.update(state="уже есть", percent=100.0, title=item["title"] or _title_from_path(match.group(1)))
        return state
    if line.startswith("[ExtractAudio]"):
        state.update(stage="конвертирую", percent=100.0)
        if state["items"]:
            state["items"][-1].update(state="конвертирую", percent=100.0)
    elif line.startswith(("[EmbedThumbnail]", "[Metadata]")):
        state["stage"] = "теги"
    match = _CHAP.match(line)
    if match:
        state.update(stage="разбиваю", chapters=int(match.group(1)))
    elif line.startswith("[SplitChapters]") and "unavailable" in line.lower():
        state["stage"] = "без глав"
        if state["title"] and state["title"] not in state["whole"]:
            state["whole"].append(state["title"])
    elif "нет таймкодов" in line:
        title = line.split(": нет таймкодов")[0]
        if title and title not in state["whole"]:
            state["whole"].append(title)
    elif line.startswith("ERROR:"):
        reason = friendly_error(line[6:].strip())
        state["failed"] += 1
        state["error"] = reason if state["failed"] == 1 else f"{state['failed']} видео не скачались, остальные — да"
        item = _current_item(state)
        if item["state"] in ("готово", "уже есть") and item.get("path"):
            item = {"title": "", "state": "", "percent": 0.0, "path": "", "note": ""}
            state["items"].append(item)
        vid = re.search(r"\[youtube\]\s*([\w-]{11})", line)
        item.update(state="недоступно" if "стране" in reason or "недоступно" in reason else "ошибка", note=reason,
                    title=item["title"] or (vid.group(1) if vid else "видео"))
    elif line.startswith("[MoveFiles]") or line.startswith("Deleting original file"):
        pass
    return state


def read_archive_ids() -> set[str]:
    ids: set[str] = read_downloaded_ids(downloaded_path(load_settings()))
    path = HERE / "polka-watch.txt"
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ids
    for line in lines:
        parts = line.split()
        if len(parts) >= 2:
            ids.add(parts[-1])
    return ids


def clock_text(seconds) -> str:
    try:
        whole = int(seconds)
    except (TypeError, ValueError):
        return ""
    if whole <= 0:
        return ""
    return f"{whole // 60}:{whole % 60:02d}"


def playlist_rows(data: dict) -> tuple[str, str, list[dict]]:
    if not isinstance(data, dict):
        return "", "", []
    title = str(data.get("title") or "").strip()
    owner = str(data.get("channel") or data.get("uploader") or data.get("playlist_uploader") or "").strip()
    raw_entries = data.get("entries")
    if not raw_entries and data.get("id"):
        raw_entries = [data]
    rows = []
    for item in raw_entries or []:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        video_id = str(item["id"])
        thumb = ""
        for shot in item.get("thumbnails") or []:
            if isinstance(shot, dict) and shot.get("url"):
                thumb = str(shot["url"])
        if not thumb and re.fullmatch(r"[\w-]{6,}", video_id):
            thumb = f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg"
        link = str(item.get("webpage_url") or item.get("url") or "")
        if not link.startswith("http"):
            link = f"https://www.youtube.com/watch?v={video_id}"
        rows.append({
            "id": video_id,
            "title": str(item.get("title") or video_id),
            "channel": str(item.get("channel") or item.get("uploader") or ""),
            "duration": clock_text(item.get("duration")),
            "seconds": item.get("duration") if isinstance(item.get("duration"), (int, float)) else 0,
            "url": link,
            "thumb": thumb,
        })
    return title, owner, rows


def youtube_search(query: str, limit: int = 20) -> list[dict]:
    """Поиск на YouTube через yt-dlp: ytsearchN:<запрос>, без скачивания."""
    query = " ".join(str(query or "").split())
    if not query:
        return []
    command = [tool_path("yt-dlp"), "-J", "--flat-playlist", "--no-warnings", "--ignore-errors", f"ytsearch{limit}:{query}"]
    raw = subprocess.check_output(command, stderr=subprocess.STDOUT, timeout=90)
    text = raw.decode("utf-8", "replace")
    start = text.find("{")
    if start < 0:
        raise RuntimeError(text.strip()[-240:] or "пустой ответ")
    return playlist_rows(json.loads(text[start:]))[2]


def fetch_playlist(url: str, cookies: str) -> tuple[str, str, list[dict]]:
    command = [
        tool_path("yt-dlp"),
        "-J",
        "--flat-playlist",
        "--no-warnings",
        "--ignore-errors",
        url,
    ]
    if cookies and Path(cookies).is_file():
        command[1:1] = ["--cookies", cookies]
    raw = subprocess.check_output(command, stderr=subprocess.STDOUT, timeout=120)
    text = raw.decode("utf-8", "replace")
    start = text.find("{")
    if start < 0:
        raise RuntimeError(text.strip()[-240:] or "пустой ответ")
    return playlist_rows(json.loads(text[start:]))


def audio_stream_command(url: str) -> list[str]:
    return [
        tool_path("yt-dlp"),
        "-f", "ba/b",
        "-g",
        "--no-playlist",
        "--no-warnings",
        url,
    ]


def audio_stream(url: str) -> str:
    raw = subprocess.check_output(audio_stream_command(url), stderr=subprocess.DEVNULL, timeout=45)
    lines = [line.strip() for line in raw.decode("utf-8", "replace").splitlines() if line.strip()]
    if not lines or not lines[0].startswith("http"):
        raise RuntimeError("поток не открылся")
    return lines[0]


def selftest() -> None:
    assert _coerce_prefs({"lists": [{"name": "Мой", "items": [{"id": "a", "title": "A"}, {"id": "a"}, {"x": 1}]}, {"name": ""}]})["lists"] == [
        {"name": "Мой", "watch": "", "items": [{"id": "a", "title": "A", "channel": "", "duration": "", "url": "", "thumb": ""}]}]
    if _auth():
        _auth().selftest()
    verdict = classify_weighted([
        {"name": "Ambient", "weight": 8, "source": "Discogs", "index": 10},
        {"name": "Comfy Synth", "weight": 6, "source": "Discogs", "index": 11},
        {"name": "Dungeon Synth", "weight": 6, "source": "Discogs", "index": 12},
        {"name": "Electronic", "weight": 1, "source": "Discogs", "index": 20},
        {"name": "dungeon synth", "weight": 7, "source": "Last.fm", "index": 0},
    ])
    assert verdict["sub"] == "Dungeon Synth", verdict
    assert choose_year([(2019, 4, "Discogs"), (1996, 5, "MusicBrainz")]) == ("1996", "MusicBrainz")
    assert choose_year([(2019, 4, "Discogs"), (1992, 4, "Discogs")]) == ("1992", "Discogs")
    assert year_in_text("Imperial Doom (1992) [HQ]") == "1992"
    assert should_place({"sub": "Dungeon Synth", "confidence": "low"}, False)
    assert not should_place({"sub": "Other", "confidence": "low"}, False)
    assert should_place({"sub": "Other", "confidence": "low"}, True)
    assert classify_weighted([
        {"name": "Black Metal", "weight": 8, "source": "Discogs", "index": 0},
        {"name": "Ambient", "weight": 6, "source": "Discogs", "index": 1},
    ])["sub"] == "Black Metal"
    frames = b""
    for frame_id, text in (("TPE1", "Burzum"), ("TALB", "Filosofem"), ("TCON", "Black Metal")):
        body = b"\x00" + text.encode("latin1")
        frames += frame_id.encode() + len(body).to_bytes(4, "big") + b"\x00\x00" + body
    size = len(frames)
    synch = bytes([(size >> 21) & 0x7F, (size >> 14) & 0x7F, (size >> 7) & 0x7F, size & 0x7F])
    import tempfile
    root = Path(tempfile.mkdtemp())
    inbox = root / "inbox"
    album = inbox / "Burzum - Filosofem"
    album.mkdir(parents=True)
    (album / "01.mp3").write_bytes(b"ID3" + bytes([3, 0, 0]) + synch + frames)
    found = find_albums(inbox)
    assert found == [album], found
    described = describe_album(album, inbox)
    assert described["artist"] == "Burzum", described
    assert described["album"] == "Filosofem", described
    assert described["genres"] == ["Black Metal"], described
    catalog = root / "catalog"
    verdict = {"path": album, "main": "Metal", "sub": "Black Metal", "artist": "Burzum", "album": "Filosofem"}
    assert place(verdict, catalog, move=True) == "ok"
    target = catalog / "Metal" / "Black Metal" / "Burzum" / "Filosofem"
    assert target.is_dir() and (target / "01.mp3").is_file()
    assert not album.exists()
    (catalog / "Rock").mkdir()
    other = inbox / "Edelweiss - 205 (full album, 2019)"
    other.mkdir()
    (other / "01.mp3").write_bytes(b"no-tags")
    described_other = describe_album(other, inbox)
    assert described_other["artist"] == "Edelweiss", described_other
    assert described_other["album"] == "205", described_other
    channel = inbox / "tagged-channel"
    channel.mkdir()
    body = b"\x00" + "DEATH FETISH".encode("latin1")
    frames = b"TPE1" + len(body).to_bytes(4, "big") + b"\x00\x00" + body
    body = b"\x00" + "205".encode("latin1")
    frames += b"TALB" + len(body).to_bytes(4, "big") + b"\x00\x00" + body
    size = len(frames)
    synch = bytes([(size >> 21) & 0x7F, (size >> 14) & 0x7F, (size >> 7) & 0x7F, size & 0x7F])
    (channel / "01.mp3").write_bytes(b"ID3" + bytes([3, 0, 0]) + synch + frames)
    channel_named = inbox / "Edelweiss - 205 (full album, 2019)"
    # same folder already created below; check a dedicated one
    named = inbox / "Wizards of Aldur - Queen of Sorcery"
    named.mkdir()
    (named / "01.mp3").write_bytes((channel / "01.mp3").read_bytes())
    from_title = describe_album(named, inbox)
    assert from_title["artist"] == "Wizards of Aldur", from_title
    assert from_title["album"] == "Queen of Sorcery", from_title
    assert stamp_id3(named / "01.mp3", "Wizards of Aldur", "Queen of Sorcery", "", None, "image/jpeg", year="1992") >= {"artist", "album", "year"}
    rewritten = read_id3(named / "01.mp3")
    assert rewritten["artist"] == "Wizards of Aldur", rewritten
    assert rewritten["album"] == "Queen of Sorcery", rewritten
    assert rewritten["year"] == "1992", rewritten
    fresh = inbox / "downloads"
    album_dir = fresh / "Wizards of Aldur - Queen of Sorcery (Fantasy Synth)"
    album_dir.mkdir(parents=True)
    (album_dir / "04 - Vo Mimbire.mp3").write_bytes((named / "01.mp3").read_bytes())
    assert stamp_download_tree(fresh) == 1
    tagged = read_id3(album_dir / "04 - Vo Mimbire.mp3")
    assert tagged["artist"] == "Wizards of Aldur", tagged
    assert "Queen of Sorcery" in (tagged["album"] or ""), tagged
    assert tagged["title"] == "Vo Mimbire", tagged
    assert tagged["track"] == "4", tagged
    assert parse_release_line("Edelweiss — 205 [FLAC] (2018)") == ("Edelweiss", "205")
    first = {"path": other, "main": "Rock", "sub": "Psychedelic Rock", "artist": "Edelweiss", "album": "205"}
    second_dir = inbox / "later"
    second_dir.mkdir()
    (second_dir / "02.mp3").write_bytes(b"x")
    second = {"path": second_dir, "main": "Electronic", "sub": "Ambient", "artist": "edelweiss", "album": "Другой"}
    assert place(first, catalog, move=True) == "ok"
    assert place(second, catalog, move=True) == "ok"
    group = catalog / "Rock" / "Psychedelic Rock" / "Edelweiss"
    assert (group / "205").is_dir()
    assert (group / "Другой").is_dir()
    assert not (catalog / "Edelweiss").exists()
    tagged = root / "tagged"
    tagged.mkdir()
    (tagged / "01.mp3").write_bytes(b"audio-bytes")
    comment = build_vorbis_comments(["ARTIST=Edelweiss"])
    (tagged / "02.flac").write_bytes(b"fLaC" + bytes([0x84]) + len(comment).to_bytes(3, "big") + comment)
    tiny = bytes.fromhex(
        "ffd8ffe000104a46494600010100000100010000ffdb004300080606070605080707070909080a0c140d0c0b0b0c"
        "1912130f141d1a1f1e1d1a1c1c20242e2720222c231c1c2837292c30313434341f27393d38323c2e333432ffc0000b"
        "080001000101011100ffc40014100100000000000000000000000000000000ffda00080001000100003f00fbffd9"
    )
    notes = enrich_album(tagged, "Edelweiss", "205", "Psychedelic Rock", fetch_cover=lambda _a, _b: (tiny, "image/jpeg"))
    assert (tagged / "cover.jpg").is_file(), notes
    mp3_tags = read_id3(tagged / "01.mp3")
    assert mp3_tags and "Psychedelic Rock" in (mp3_tags.get("genres") or []), mp3_tags
    assert mp3_tags["artist"] == "Edelweiss"
    assert mp3_tags["album"] == "205"
    assert b"APIC" in (tagged / "01.mp3").read_bytes()
    flac_tags = read_flac(tagged / "02.flac")
    assert flac_tags and "Psychedelic Rock" in (flac_tags.get("genres") or []), flac_tags
    again = enrich_album(tagged, "Edelweiss", "205", "Psychedelic Rock", fetch_cover=lambda _a, _b: (tiny, "image/jpeg"))
    assert any("уже" in line for line in again), again
    tags_only = root / "tags-only"
    tags_only.mkdir()
    (tags_only / "01.mp3").write_bytes(b"audio-bytes")
    notes = enrich_album(
        tags_only, "Edelweiss", "205", "Rock",
        fetch_cover=lambda _a, _b: (tiny, "image/jpeg"),
        write_tags=True, fetch_covers=False,
    )
    assert not (tags_only / "cover.jpg").exists(), notes
    assert "Rock" in (read_id3(tags_only / "01.mp3") or {}).get("genres", [])
    assert b"APIC" not in (tags_only / "01.mp3").read_bytes()
    folder_cmd, folder = watch_plan(
        {"url": "https://www.youtube.com/playlist?list=PL123", "name": "Night Drive", "mode": "folder"},
        {"youtube_format": "mp3", "catalog": str(catalog), "download_dir": "", "cookies": ""},
    )
    assert folder.name == "Night Drive"
    assert "--download-archive" in folder_cmd
    assert "after_move:id" in folder_cmd
    ids_file = catalog / DOWNLOADED_NAME
    assert ids_file.parent == catalog
    ids_file.write_text("abc123xyz\n", encoding="utf-8")
    assert append_downloaded_id(ids_file, "new000id") and not append_downloaded_id(ids_file, "abc123xyz")
    assert ids_file.read_text(encoding="utf-8") == "abc123xyz\nnew000id\n"
    assert new_ids([{"id": "abc123xyz"}, {"id": "zzz"}], read_downloaded_ids(ids_file)) == ["zzz"]
    assert "youtube abc123xyz" in skip_archive(ids_file).read_text(encoding="utf-8")
    assert "--yes-playlist" in folder_cmd and "--split-chapters" in folder_cmd and "--newline" in folder_cmd
    plain_cmd, _ = watch_plan({"url": "https://x/list=PL1", "name": "N", "mode": "folder", "split": False},
                              {"youtube_format": "mp3", "catalog": str(catalog), "download_dir": "", "cookies": ""})
    assert "--split-chapters" not in plain_cmd
    assert _coerce_prefs({"watches": [{"url": "https://x/list=PL1", "split": False}]})["watches"][0]["split"] is False
    pr = progress_new()
    for text in ["[download] Downloading item 2 of 6",
                 "[download] Destination: C:\\M\\_full\\02 - Edelweiss - 205.webm",
                 "[download]  42.5% of   30.00MiB at 2.00MiB/s ETA 00:09"]:
        progress_update(pr, text)
    assert (pr["item"], pr["total"], pr["percent"], pr["title"]) == (2, 6, 42.5, "Edelweiss - 205"), pr
    progress_update(pr, "[SplitChapters] Splitting video by chapters; 6 chapters found")
    assert pr["stage"] == "разбиваю" and pr["chapters"] == 6
    progress_update(pr, "[SplitChapters] Chapter information is unavailable")
    assert pr["whole"] == ["Edelweiss - 205"]
    pl_dest = catalog / "Плейлисты" / "T"
    (pl_dest / "_full").mkdir(parents=True)
    (pl_dest / "_full" / "01 - A.mp3").write_bytes(b"x")
    (pl_dest / "_full" / "02 - B.mp3").write_bytes(b"x")
    (pl_dest / "01 - A").mkdir()
    (pl_dest / "01 - A" / "01 - one.mp3").write_bytes(b"x")
    assert settle_full(pl_dest, lambda _t: None) == ["02 - B"]
    assert (pl_dest / "02 - B.mp3").exists() and not (pl_dest / "_full").exists()
    assert "list=PL123" in folder_cmd[-1]
    title, owner, rows = playlist_rows({
        "title": "Night Drive",
        "uploader": "Night Desk",
        "entries": [{"id": "abc123xyz", "title": "Song", "channel": "Driver", "duration": 65}],
    })
    assert title == "Night Drive"
    assert owner == "Night Desk"
    assert rows[0]["channel"] == "Driver"
    assert rows[0]["duration"] == "1:05"
    assert rows[0]["thumb"].endswith("/abc123xyz/mqdefault.jpg")
    assert "-g" in audio_stream_command("https://www.youtube.com/watch?v=abc")
    covers_only = root / "covers-only"
    covers_only.mkdir()
    (covers_only / "01.mp3").write_bytes(b"audio-bytes")
    notes = enrich_album(
        covers_only, "Edelweiss", "205", "Rock",
        fetch_cover=lambda _a, _b: (tiny, "image/jpeg"),
        write_tags=False, fetch_covers=True,
    )
    assert (covers_only / "cover.jpg").is_file(), notes
    assert not (read_id3(covers_only / "01.mp3") or {}).get("genres")
    assert b"APIC" in (covers_only / "01.mp3").read_bytes()
    for fmt in YT_FORMATS:
        args = yt_audio_args(fmt)
        assert ("--embed-thumbnail" in args) == (fmt in {"mp3", "m4a", "alac", "flac"}), fmt
    assert yt_audio_args("ogg")[2] == "vorbis" and yt_format("xyz") == "mp3"
    assert "--split-chapters" in yt_download_args("u", "1", "mp3", "D", True)
    assert "--split-chapters" not in yt_download_args("u", "2", "wav", "D", False)
    assert _coerce_prefs({"youtube_split": "0"})["youtube_split"] is False
    assert downloader_command("u", "1", "flac", "D", {"cookies": ""}, False).endswith('"0"')
    # треки: имена, метаданные, страховка от «1.mp3»
    assert [ru_plural(n, "трек", "трека", "треков") for n in (1, 2, 5, 11, 21, 22, 112)] == [
        "1 трек", "2 трека", "5 треков", "11 треков", "21 трек", "22 трека", "112 треков"]
    assert track_file_name({"title": "Song: A/B", "track": "3"}, ".mp3") == "03 - Song A B.mp3"
    assert track_file_name({"title": "Song", "track": ""}, ".mp3") == "Song.mp3"
    assert track_file_name({"title": "", "track": "1"}, ".mp3") == "01 - Unknown.mp3"
    assert is_track_list([200, 300]) and not is_track_list([200, 2400]) and not is_track_list([])
    music = track_meta({"id": "x", "title": "Song", "description": "Provided to YouTube by X\n\nSong · Band\n\nThe Album\n\n℗ 2001\n\nReleased on: 2001-02-03"})
    assert music == {"artist": "Band", "title": "Song", "album": "The Album", "track": "", "year": "2001"}, music
    plain = track_meta({"id": "x", "title": "Band - Song (Official Video)", "channel": "BandVEVO"})
    assert plain["artist"] == "Band" and plain["album"] == "", plain
    topic = track_meta({"id": "x", "title": "Song", "channel": "Band - Topic", "track": "Song", "album": "LP", "track_number": 4})
    assert topic["artist"] == "Band" and topic["track"] == "4"
    with tempfile.TemporaryDirectory() as raw:
        folder = Path(raw) / "Band - LP"
        folder.mkdir()
        (folder / "1.mp3").write_bytes(b"\xff\xfb" + b"\0" * 400)
        assert fix_bare_names(Path(raw), lambda _t: None) == 1
        assert (folder / "01 - Band - LP.mp3").exists()
        prefs_t = {"catalog": raw}
        remember_paths(prefs_t, {"abc": "Rock/Band/LP/01 - X.mp3"})
        assert read_paths(prefs_t)["abc"].endswith("01 - X.mp3")
    # v13: остатки во временной папке раскладываются; тот же артист с другим альбомом — не «уже есть»
    with tempfile.TemporaryDirectory() as raw:
        cat = Path(raw) / "Music"
        other = cat / "Electronic" / "Synthwave" / "O62B" / "Other Album"
        other.mkdir(parents=True)
        (other / "01 - x.opus").write_bytes(b"x" * 10)
        stage = staging_dir({"catalog": str(cat)})
        old = stage / "O62B - Minecraft Volume Alpha"
        old.mkdir(parents=True)
        (old / "O62B - Minecraft Volume Alpha.opus").write_bytes(b"y" * 20)
        fake = {"main": "Electronic", "sub": "Synthwave", "confidence": "high", "reason": "", "year": ""}
        got = sort_staging(stage, cat, {"place_unclear": True}, lambda _t: None,
                           {cache_key("O62B", "Minecraft Volume Alpha"): fake})
        dest = got["O62B - Minecraft Volume Alpha"]
        assert dest.name == "Minecraft Volume Alpha" and (dest / "O62B - Minecraft Volume Alpha.opus").exists(), dest
        assert (other / "01 - x.opus").exists() and not old.exists()
        again = stage / "O62B - Minecraft Volume Alpha"
        again.mkdir()
        (again / "O62B - Minecraft Volume Alpha.opus").write_bytes(b"y" * 20)
        log_lines = []
        sort_staging(stage, cat, {"place_unclear": True}, log_lines.append, {cache_key("O62B", "Minecraft Volume Alpha"): fake})
        assert any("те же файлы" in line for line in log_lines), log_lines
    try:
        require_root({"catalog": ""})
        raise AssertionError("root")
    except RuntimeError as error:
        assert str(error) == ROOT_MISSING
    blocked = "ERROR: [youtube] abcdefghijk: Video unavailable. This video contains content from WMG, who has blocked it in your country on copyright grounds"
    assert friendly_error(blocked.split("ERROR: ")[1]) == "недоступно в вашей стране (авторские права)"
    pr = progress_new()
    for line in ["[download] Downloading item 1 of 3", "[download] Destination: C:\\M\\_full\\Album One.webm",
                 "[download]  50.0% of 3MiB", "[ExtractAudio] Destination: x", "[download] Downloading item 2 of 3",
                 blocked, "[download] Downloading item 3 of 3", "[download] Destination: C:\\M\\_full\\Album Three.webm",
                 placed_line("Album One", "D:\\Music\\E\\Album One"), placed_line("Album Three", "D:\\Music\\E\\Album Three")]:
        progress_update(pr, line)
    states = [(it["title"], it["state"], it["path"][-9:]) for it in pr["items"]]
    assert states == [("Album One", "готово", "Album One"), ("abcdefghijk", "недоступно", ""),
                      ("Album Three", "готово", "bum Three")], states
    assert pr["error"] == "недоступно в вашей стране (авторские права)"
    assert "--ignore-errors" in yt_audio_args("mp3")
    print("selftest ok")


class App:
    def __init__(self) -> None:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk

        self.tk = tk
        self.filedialog = filedialog
        self.messagebox = messagebox
        self.root = tk.Tk()
        self.root.title(f"Полка {VERSION}")
        self.root.minsize(900, 780)
        self.root.geometry("1000x920")
        self.root.configure(bg="#f6f1e8")
        style = ttk.Style()
        self.style = style
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        self.font_ui = "Calibri"
        self.font_title = "Constantia"
        self.font_mono = "Consolas"
        self.dark_var = tk.BooleanVar(value=load_settings().get("dark", False))
        self.busy = False
        self.yt_busy = False
        self._angle = 0.0
        self._phase = 0.0
        self._anim = None
        self.header = tk.Canvas(self.root, height=96, highlightthickness=0, bd=0)
        self.header.pack(fill="x")
        self.rail = tk.Canvas(self.root, height=4, highlightthickness=0, bd=0)
        self.rail.pack(fill="x")
        self.header.bind("<Configure>", lambda _event: self._draw_header())

        self.notebook = None
        self._buttons = []
        self._pills = []
        self._playlist_views = {}
        self._sliding = False
        self.page_name = "Сортировка"
        self.tab_bar = tk.Frame(self.root, highlightthickness=0, bd=0)
        self.tab_bar.pack(fill="x", padx=18, pady=(12, 0))
        self.tab_mark = tk.Canvas(self.root, height=3, highlightthickness=0, bd=0)
        self.tab_mark.pack(fill="x", padx=18)
        self.deck = tk.Frame(self.root, highlightthickness=0, bd=0)
        self.deck.pack(fill="both", expand=True, padx=18, pady=(8, 16))
        sort = ttk.Frame(self.deck, padding=16)
        extra = ttk.Frame(self.deck, padding=16)
        settings = ttk.Frame(self.deck, padding=16)
        self.pages = {"Сортировка": sort, "Скачать": extra, "Настройки": settings}
        for index, name in enumerate(self.pages):
            self._make_button(self.tab_bar, name, lambda n=name: self._open_page(n), accent=index == 0).pack(side="left", padx=(0, 8))
        sort.place(x=0, y=0, relwidth=1, relheight=1)
        self.extra_tab = extra

        ttk.Label(sort, text="Полка", style="Title.TLabel").pack(anchor="w")
        ttk.Label(sort, text=VERSION, style="Hint.TLabel").pack(anchor="w")
        ttk.Label(
            sort,
            text="Жанр, поджанр, группа, альбом. Новая пластинка группы ложится в уже существующую папку.",
            style="Hint.TLabel",
        ).pack(anchor="w", pady=(0, 12))

        prefs = load_settings()
        self.source = tk.StringVar(value=prefs["source"])
        self.catalog = tk.StringVar(value=prefs["catalog"])
        self.move = tk.BooleanVar(value=prefs["move"])
        self.keep_unclear = tk.BooleanVar(value=prefs["place_unclear"])
        self.yt_dir = tk.StringVar(value=prefs["download_dir"])
        self.use_downloads = tk.BooleanVar(value=prefs["use_youtube_folder"])
        self._row(sort, "Откуда альбомы", self.source, self.pick_source)
        from_row = ttk.Frame(sort)
        from_row.pack(fill="x", pady=(0, 4))
        self._toggle(
            from_row, "Брать из папки, скачанного с YouTube", self.use_downloads, self.toggle_download_source,
        ).pack(anchor="w")
        self.download_source_label = tk.StringVar(value=self.yt_dir.get())
        ttk.Label(from_row, textvariable=self.download_source_label).pack(anchor="w", padx=(30, 0))
        self.yt_dir.trace_add("write", lambda *_: self.sync_download_source())
        self._row(sort, "Каталог", self.catalog, self.pick_catalog)
        checks = ttk.Frame(sort)
        checks.pack(fill="x", pady=8)
        self._toggle(checks, "Переносить (иначе копировать)", self.move).pack(side="left", padx=(0, 18))
        self._toggle(checks, "Переносить и неясные в Other", self.keep_unclear).pack(side="left")

        buttons = ttk.Frame(sort)
        buttons.pack(fill="x", pady=(0, 8))
        self._make_button(buttons, "Разобрать", self.scan, accent=True).pack(side="left", padx=(0, 8))
        self._make_button(buttons, "Разложить по папкам", self.apply, accent=True).pack(side="left")
        self.sort_live = tk.StringVar(value="")
        ttk.Label(buttons, textvariable=self.sort_live, style="Live.TLabel").pack(side="left", padx=16)
        self.status = tk.StringVar(value="Выбери папку с альбомами и папку каталога.")
        ttk.Label(sort, textvariable=self.status).pack(anchor="w", pady=(0, 6))
        self.loader = tk.Canvas(sort, height=22, highlightthickness=0, bd=0)
        self.loader.pack(fill="x", pady=(0, 8))

        self.list = tk.Listbox(
            sort, font=(self.font_ui, 12), activestyle="none", relief="flat",
            highlightthickness=0, bd=0, selectborderwidth=0,
        )
        self.list.pack(fill="both", expand=True)
        self.log_frame, self.log_box = self._scrolled(sort, 12)
        self.results: list[dict] = []
        self.busy = False
        self.cache = load_cache()
        self.apply_log_visibility()

        ttk.Label(extra, text="Скачать с YouTube", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            extra,
            text="Папка — название видео. Главы становятся треками. Если yt-dlp или ffmpeg нет рядом, Полка скачает их сама.",
            style="Hint.TLabel",
        ).pack(anchor="w", pady=(0, 12))
        self.yt_url = tk.StringVar()
        self.yt_kind = tk.StringVar(value="2" if load_settings()["youtube_kind"] == "playlist" else "1")
        self.yt_format = tk.StringVar(value=load_settings()["youtube_format"])
        self.yt_busy = False
        self._row(extra, "Ссылка", self.yt_url, None)
        kind_row = ttk.Frame(extra)
        kind_row.pack(fill="x", pady=6)
        ttk.Label(kind_row, text="Тип", width=16, anchor="w").pack(side="left")
        self._segments(kind_row, self.yt_kind, (("1", "Видео"), ("2", "Плейлист"))).pack(side="left", fill="y")
        format_row = ttk.Frame(extra)
        format_row.pack(fill="x", pady=6)
        ttk.Label(format_row, text="Формат", width=16, anchor="w").pack(side="left")
        self._segments(format_row, self.yt_format, tuple((fmt, "как есть" if fmt == "best" else fmt) for fmt in YT_FORMATS)).pack(side="left")
        self.yt_split = tk.BooleanVar(value=bool(load_settings().get("youtube_split", True)))
        split_row = ttk.Frame(extra)
        split_row.pack(fill="x", pady=6)
        ttk.Label(split_row, text="Треки", width=16, anchor="w").pack(side="left")
        ttk.Checkbutton(split_row, text="Разбить на треки по главам", variable=self.yt_split).pack(side="left")
        self._row(extra, "Папка", self.yt_dir, self.pick_download_dir)
        yt_buttons = ttk.Frame(extra)
        yt_buttons.pack(fill="x", pady=(8, 8))
        self._make_button(yt_buttons, "Скачать", self.start_download, accent=True).pack(side="left")
        self.yt_live = tk.StringVar(value="")
        ttk.Label(yt_buttons, textvariable=self.yt_live, style="Live.TLabel").pack(side="left", padx=16)
        ttk.Label(extra, text="Слежка", style="Title.TLabel").pack(anchor="w", pady=(16, 0))
        ttk.Label(
            extra,
            text="Пока Полка открыта, она сама проверяет ссылки. Отдельная папка только дописывает новые видео. В каталог — разбирает новые альбомы по жанрам.",
            style="Hint.TLabel",
        ).pack(anchor="w", pady=(4, 8))
        self.watch_name = tk.StringVar()
        self._row(extra, "Имя папки", self.watch_name, None)
        mode_row = ttk.Frame(extra)
        mode_row.pack(fill="x", pady=6)
        ttk.Label(mode_row, text="Куда", width=16, anchor="w").pack(side="left")
        self.watch_mode = tk.StringVar(value="folder")
        self._segments(mode_row, self.watch_mode, (("folder", "Отдельная папка"), ("sort", "В каталог"))).pack(side="left")
        watch_buttons = ttk.Frame(extra)
        watch_buttons.pack(fill="x", pady=(4, 6))
        self._make_button(watch_buttons, "Следить за ссылкой", self.add_watch, accent=True).pack(side="left", padx=(0, 8))
        self._make_button(watch_buttons, "Убрать", self.remove_watch).pack(side="left", padx=(0, 8))
        self._make_button(watch_buttons, "Проверить сейчас", self.check_watches_now).pack(side="left")
        self.watch_on = tk.BooleanVar(value=bool(load_settings().get("watch_enabled")))
        self._toggle(extra, "Проверять, пока Полка открыта", self.watch_on, self.save_watch_toggle).pack(anchor="w", pady=(4, 6))
        self.watch_list = tk.Listbox(
            extra, height=4, font=(self.font_ui, 11), activestyle="none", relief="flat",
            highlightthickness=0, bd=0, selectborderwidth=0,
        )
        self.watch_list.pack(fill="x", pady=(0, 8))
        self.refresh_watches()
        self.yt_status = tk.StringVar(value="Ссылка на видео или плейлист.")
        ttk.Label(extra, textvariable=self.yt_status).pack(anchor="w", pady=(0, 8))
        self.yt_frame, self.yt_log = self._scrolled(extra, 8)
        self.yt_frame.pack(fill="both", expand=True)

        current = load_settings()
        self.discogs_key = tk.StringVar(value=current["discogs"])
        self.lastfm_key = tk.StringVar(value=current["lastfm"])
        self.show_secrets = tk.BooleanVar(value=False)
        self.show_log_var = tk.BooleanVar(value=current["show_log"])
        self.tag_files_var = tk.BooleanVar(value=current.get("tag_files", True))
        self.fetch_covers_var = tk.BooleanVar(value=current.get("fetch_covers", True))
        ttk.Label(settings, text="Настройки", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            settings,
            text="Файл polka-prefs.json создаётся рядом с программой при первом запуске. Его можно править в блокноте: ключи, папки, источники и таймаут.",
        ).pack(anchor="w", pady=(4, 12))
        ttk.Label(settings, text="Discogs token").pack(anchor="w")
        ttk.Label(settings, text="https://www.discogs.com/settings/developers").pack(anchor="w", pady=(0, 4))
        self.discogs_entry = ttk.Entry(settings, textvariable=self.discogs_key, width=64, show="*")
        self.discogs_entry.pack(anchor="w", pady=(0, 10))
        ttk.Label(settings, text="Last.fm API key").pack(anchor="w")
        ttk.Label(settings, text="https://www.last.fm/api/account/create").pack(anchor="w", pady=(0, 4))
        self.lastfm_entry = ttk.Entry(settings, textvariable=self.lastfm_key, width=64, show="*")
        self.lastfm_entry.pack(anchor="w", pady=(0, 8))
        self.cookies_var = tk.StringVar(value=current.get("cookies") or "")
        self._row(settings, "Cookies", self.cookies_var, self.pick_cookies)
        self._toggle(settings, "Показать ключи", self.show_secrets, self.toggle_secrets).pack(anchor="w", pady=(8, 0))
        self._toggle(settings, "Показывать лог поиска", self.show_log_var).pack(anchor="w", pady=(8, 0))
        self._toggle(settings, "Записывать в файлы артиста, альбом, год и жанр", self.tag_files_var).pack(anchor="w", pady=(8, 0))
        self._toggle(settings, "Скачивать обложку, если ее нет", self.fetch_covers_var).pack(anchor="w", pady=(8, 0))
        self._toggle(settings, "Тёмная тема", self.dark_var, self.apply_theme).pack(anchor="w", pady=(8, 14))
        self._make_button(settings, "Сохранить", self.save_settings_ui, accent=True).pack(anchor="w")
        self._make_button(settings, "Открыть файл настроек", self.open_prefs).pack(anchor="w", pady=(8, 0))
        self.settings_status = tk.StringVar(value="")
        ttk.Label(settings, textvariable=self.settings_status).pack(anchor="w", pady=(8, 0))
        self.apply_theme()
        self._tick()
        self._ensure_mutagen()
        self._watch_stop = threading.Event()
        self._watch_thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._watch_thread.start()

    def palette(self) -> dict:
        if self.dark_var.get():
            return {
                "bg": "#14110e", "fg": "#f6f0e6", "muted": "#b3a89a", "paper": "#241c16",
                "accent": "#e07a45", "gold": "#e7b15a", "disc": "#0c0a08", "header": "#1b1612",
                "tab": "#2c241c", "tab_on": "#3d3127", "line": "#3a3028",
            }
        return {
            "bg": "#f6f1e8", "fg": "#2a2118", "muted": "#7a6a5a", "paper": "#fffdf8",
            "accent": "#c4512c", "gold": "#c9922a", "disc": "#1a120e", "header": "#efe4d2",
            "tab": "#e7dccb", "tab_on": "#fffdf8", "line": "#e0d3c0",
        }

    def apply_theme(self) -> None:
        color = self.palette()
        style = self.style
        bg, fg, paper = color["bg"], color["fg"], color["paper"]
        self.root.configure(bg=bg)
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=fg, font=(self.font_ui, 11))
        style.configure("Hint.TLabel", background=bg, foreground=color["muted"], font=(self.font_ui, 10))
        style.configure("Title.TLabel", background=bg, foreground=fg, font=(self.font_title, 28))
        style.configure("TButton", font=(self.font_ui, 11), padding=(12, 8), background=color["tab"], foreground=fg, borderwidth=0)
        style.map("TButton", background=[("active", color["tab"]), ("pressed", color["tab"])], foreground=[("active", fg)])
        style.configure(
            "TCheckbutton", background=bg, foreground=fg, font=(self.font_ui, 11),
            indicatorcolor=paper, focuscolor=bg, borderwidth=0,
        )
        style.map(
            "TCheckbutton",
            background=[("active", bg), ("pressed", bg), ("selected", bg)],
            foreground=[("active", fg), ("disabled", color["muted"])],
            indicatorcolor=[("selected", color["accent"]), ("pressed", color["gold"]), ("active", paper)],
        )
        style.configure(
            "TRadiobutton", background=bg, foreground=fg, font=(self.font_ui, 11),
            indicatorcolor=paper, focuscolor=bg, borderwidth=0,
        )
        style.map(
            "TRadiobutton",
            background=[("active", bg), ("pressed", bg), ("selected", bg)],
            foreground=[("active", fg)],
            indicatorcolor=[("selected", color["accent"]), ("pressed", color["gold"]), ("active", paper)],
        )
        style.configure(
            "Polka.Vertical.TScrollbar",
            background=color["tab"], troughcolor=paper, bordercolor=paper, arrowcolor=fg,
            lightcolor=color["tab"], darkcolor=color["tab"], arrowsize=12,
        )
        style.map(
            "Polka.Vertical.TScrollbar",
            background=[("active", color["accent"]), ("pressed", color["gold"])],
            arrowcolor=[("active", "#fffaf6")],
        )
        style.configure("Live.TLabel", background=bg, foreground=color["accent"], font=(self.font_title, 16))
        style.configure("TEntry", fieldbackground=paper, foreground=fg, bordercolor=color["line"], lightcolor=paper, darkcolor=paper, padding=(8, 7), font=(self.font_ui, 11))
        style.configure("TCombobox", fieldbackground=paper, foreground=fg, bordercolor=color["line"], arrowcolor=fg, padding=4, font=(self.font_ui, 11))
        style.map("TCombobox", fieldbackground=[("readonly", paper)], foreground=[("readonly", fg)])
        self.list.configure(bg=paper, fg=fg, selectbackground=color["accent"], selectforeground="#fffaf6", font=(self.font_ui, 12))
        if hasattr(self, "watch_list"):
            self.watch_list.configure(bg=paper, fg=fg, selectbackground=color["accent"], selectforeground="#fffaf6", font=(self.font_ui, 11))
        for view in getattr(self, "_playlist_views", {}).values():
            view["canvas"].configure(bg=bg)
        for widget in (self.log_box, self.yt_log):
            widget.configure(
                bg=paper, fg=fg, insertbackground=fg,
                selectbackground=color["accent"], selectforeground="#fffaf6",
            )
        self.tab_bar.configure(bg=bg)
        self.deck.configure(bg=bg)
        self.tab_mark.configure(bg=color["gold"])
        self._paint_buttons()
        for paint in self._pills:
            paint()
        self._draw_header()
        self._draw_rail()

    def _draw_header(self) -> None:
        color = self.palette()
        canvas = self.header
        width = max(canvas.winfo_width(), 860)
        height = 96
        canvas.configure(bg=color["header"], height=height)
        canvas.delete("all")
        canvas.create_rectangle(0, 0, width, height, fill=color["header"], outline="")
        cx, cy, radius = 58, 48, 32
        canvas.create_oval(cx - radius - 3, cy - radius - 3, cx + radius + 3, cy + radius + 3, fill=color["gold"], outline="")
        canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, fill=color["disc"], outline="")
        for groove in (24, 18, 12):
            canvas.create_oval(cx - groove, cy - groove, cx + groove, cy + groove, outline=color["header"], width=1)
        angle = math.radians(self._angle)
        canvas.create_line(
            cx, cy,
            cx + math.cos(angle) * 22, cy + math.sin(angle) * 22,
            fill=color["accent"], width=2,
        )
        canvas.create_oval(cx - 7, cy - 7, cx + 7, cy + 7, fill=color["gold"], outline="")
        canvas.create_oval(cx - 2, cy - 2, cx + 2, cy + 2, fill=color["disc"], outline="")
        canvas.create_text(108, 36, text="Полка", anchor="w", fill=color["fg"], font=(self.font_title, 32))
        canvas.create_text(250, 40, text=VERSION, anchor="w", fill=color["muted"], font=(self.font_ui, 12))
        canvas.create_text(110, 68, text="пластинки сами находят свою полку", anchor="w", fill=color["muted"], font=(self.font_ui, 11))
        busy = self.busy or getattr(self, "yt_busy", False)
        base_x = width - 150
        for index in range(7):
            level = abs(math.sin(self._phase + index * 0.55))
            bar = 8 + level * (46 if busy else 22)
            x = base_x + index * 16
            canvas.create_rectangle(x, 74 - bar, x + 8, 74, fill=color["accent"] if index % 2 == 0 else color["gold"], outline="")

    def _draw_rail(self) -> None:
        color = self.palette()
        canvas = self.rail
        width = max(canvas.winfo_width(), 860)
        canvas.configure(bg=color["line"])
        canvas.delete("all")
        canvas.create_rectangle(0, 0, width, 4, fill=color["line"], outline="")
        if self.busy or getattr(self, "yt_busy", False):
            span = max(90, width // 5)
            travel = (self._angle / 360) * (width + span)
            canvas.create_rectangle(travel - span, 0, travel, 4, fill=color["accent"], outline="")
        else:
            canvas.create_rectangle(0, 3, width, 4, fill=color["gold"], outline="")

    def _tick(self) -> None:
        busy = self.busy or getattr(self, "yt_busy", False)
        self._angle = (self._angle + (8 if busy else 1.4)) % 360
        self._phase += 0.22 if busy else 0.08
        self._draw_header()
        self._draw_rail()
        self._draw_loader()
        self._pulse_live()
        self._anim = self.root.after(40, self._tick)

    def _pulse_live(self) -> None:
        dots = int(self._phase * 1.3) % 4
        tail = "." * dots + " " * (3 - dots)
        glow = self._mix(self.palette()["muted"], self.palette()["accent"], 0.35 + 0.65 * abs(math.sin(self._phase)))
        self.style.configure("Live.TLabel", foreground=glow)
        if hasattr(self, "sort_live"):
            self.sort_live.set(("Сортирую" + tail) if self.busy else "")
        if hasattr(self, "yt_live"):
            self.yt_live.set(("Скачиваю" + tail) if self.yt_busy else "")

    def _toggle(self, parent, text, variable, command=None):
        row = self.tk.Frame(parent, highlightthickness=0, bd=0)
        canvas = self.tk.Canvas(row, width=22, height=22, highlightthickness=0, bd=0, cursor="hand2")
        label = self.tk.Label(row, text=text, font=(self.font_ui, 12), cursor="hand2")
        canvas.pack(side="left")
        label.pack(side="left", padx=(10, 0))

        def paint() -> None:
            color = self.palette()
            on = bool(variable.get())
            row.configure(bg=color["bg"])
            canvas.configure(width=22, height=22, bg=color["bg"])
            label.configure(bg=color["bg"], fg=color["fg"])
            canvas.delete("all")
            edge = color["accent"] if on else color["muted"]
            fill = color["accent"] if on else color["bg"]
            canvas.create_rectangle(3, 3, 19, 19, fill=fill, outline=edge, width=1)
            if on:
                canvas.create_line(6, 11, 16, 11, fill="#fffaf6", width=2)
                canvas.create_line(11, 6, 11, 16, fill="#fffaf6", width=2)

        def flip(_event=None) -> None:
            variable.set(not bool(variable.get()))
            if command:
                command()

        canvas.bind("<Button-1>", flip)
        label.bind("<Button-1>", flip)
        variable.trace_add("write", lambda *_args: paint())
        self._pills.append(paint)
        paint()
        return row

    def _segments(self, parent, variable, options):
        wrap = self.tk.Frame(parent, highlightthickness=0, bd=0)
        chips = []

        def paint() -> None:
            color = self.palette()
            wrap.configure(bg=color["bg"])
            current = str(variable.get())
            for value, chip in chips:
                chosen = value == current
                chip.configure(
                    bg=color["accent"] if chosen else color["tab"],
                    fg="#fffaf6" if chosen else color["fg"],
                )

        def choose(value: str) -> None:
            variable.set(value)
            paint()

        for value, title in options:
            chip = self.tk.Label(
                wrap, text=title, font=(self.font_ui, 11), padx=16, pady=7, cursor="hand2",
            )
            chip.pack(side="left", padx=(0, 6))
            chip.bind("<Button-1>", lambda _event, item=value: choose(item))
            chip.bind("<Enter>", lambda _event, item=chip, key=value: item.configure(
                bg=self.palette()["gold"] if str(variable.get()) == key else self.palette()["tab_on"],
            ))
            chip.bind("<Leave>", lambda _event: paint())
            chips.append((value, chip))
        variable.trace_add("write", lambda *_: paint())
        self._pills.append(paint)
        paint()
        return wrap

    def _scrolled(self, parent, height: int):
        from tkinter import ttk
        frame = ttk.Frame(parent)
        text = self.tk.Text(
            frame, height=height, font=(self.font_mono, 10), relief="flat", wrap="word",
            highlightthickness=0, bd=0, padx=10, pady=8,
        )
        bar = ttk.Scrollbar(frame, command=text.yview, style="Polka.Vertical.TScrollbar")
        text.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True)
        return frame, text

    def _make_button(self, parent, text, command, accent=False):
        button = self.tk.Button(
            parent, text=text, command=command, relief="flat", bd=0,
            padx=18, pady=7, cursor="hand2", font=(self.font_ui, 12),
            highlightthickness=0,
        )
        button.accent = accent
        button.hover_phase = 0.0
        button.hover_target = 0.0
        button.press_phase = 0.0
        button.press_target = 0.0
        button.hover_job = None
        button.bind("<Enter>", lambda _event, item=button: self._aim(item, hover=1))
        button.bind("<Leave>", lambda _event, item=button: self._aim(item, hover=0))
        button.bind("<ButtonPress-1>", lambda _event, item=button: self._aim(item, press=1))
        button.bind("<ButtonRelease-1>", lambda _event, item=button: self._aim(item, press=0))
        self._buttons.append(button)
        return button

    def _mix(self, start: str, end: str, amount: float) -> str:
        def channel(color: str, offset: int) -> int:
            return int(color[offset:offset + 2], 16)
        amount = max(0.0, min(1.0, amount))
        mixed = []
        for offset in (1, 3, 5):
            value = round(channel(start, offset) + (channel(end, offset) - channel(start, offset)) * amount)
            mixed.append(f"{value:02x}")
        return "#" + "".join(mixed)

    def _paint_buttons(self) -> None:
        color = self.palette()
        for button in list(self._buttons):
            try:
                if not button.winfo_exists():
                    self._buttons.remove(button)
                    continue
            except self.tk.TclError:
                self._buttons.remove(button)
                continue
            base = color["accent"] if button.accent else color["tab"]
            hot = color["gold"] if button.accent else color["tab_on"]
            ink = "#fffaf6" if button.accent else color["fg"]
            button.base_color = base
            button.hot_color = hot
            shade = self._mix(base, hot, button.hover_phase)
            shade = self._mix(shade, color["disc"], button.press_phase * 0.45)
            button.configure(bg=shade, fg=ink, activebackground=shade, activeforeground=ink)

    def _aim(self, button, hover=None, press=None) -> None:
        if hover is not None:
            button.hover_target = float(hover)
        if press is not None:
            button.press_target = float(press)
        if not button.hover_job:
            self._glide(button)

    def _glide(self, button) -> None:
        button.hover_job = None
        button.hover_phase += (button.hover_target - button.hover_phase) * 0.22
        button.press_phase += (button.press_target - button.press_phase) * 0.34
        if abs(button.hover_phase - button.hover_target) < 0.015:
            button.hover_phase = button.hover_target
        if abs(button.press_phase - button.press_target) < 0.015:
            button.press_phase = button.press_target
        if hasattr(button, "base_color"):
            shade = self._mix(button.base_color, button.hot_color, button.hover_phase)
            shade = self._mix(shade, self.palette()["disc"], button.press_phase * 0.45)
            button.configure(bg=shade, activebackground=shade)
        if button.hover_phase != button.hover_target or button.press_phase != button.press_target:
            button.hover_job = self.root.after(16, lambda item=button: self._glide(item))

    def _hover(self, button, target: int) -> None:
        self._aim(button, hover=target)

    def _open_page(self, name: str) -> None:
        if name == self.page_name or self._sliding:
            return
        names = list(self.pages)
        direction = 1 if names.index(name) > names.index(self.page_name) else -1
        old = self.pages[self.page_name]
        new = self.pages[name]
        self.page_name = name
        for button in self._buttons:
            if getattr(button, "page_name", None):
                button.accent = button.page_name == name
        self._paint_buttons()
        if name.startswith("pl:"):
            view = self._playlist_views.get(name[3:])
            if view is not None and str(view["status"].get()).startswith("Нажми"):
                self.load_playlist(name[3:])
        self._sliding = True
        self._slide(old, new, direction, 0)

    def _slide(self, old, new, direction: int, step: int) -> None:
        steps = 24
        width = max(self.deck.winfo_width(), 1)
        t = step / steps
        ease = t * t * (3 - 2 * t)
        new.place(x=int(direction * width * (1 - ease)), y=0, relwidth=1, relheight=1)
        old.place(x=int(-direction * width * ease), y=0, relwidth=1, relheight=1)
        new.lift()
        if step < steps:
            self.root.after(16, lambda: self._slide(old, new, direction, step + 1))
            return
        old.place_forget()
        new.place(x=0, y=0, relwidth=1, relheight=1)
        self._sliding = False

    def _draw_loader(self) -> None:
        if not hasattr(self, "loader"):
            return
        color = self.palette()
        canvas = self.loader
        width = max(canvas.winfo_width(), 200)
        canvas.configure(bg=color["bg"])
        canvas.delete("all")
        if not (self.busy or self.yt_busy):
            return
        canvas.create_arc(4, 2, 20, 18, start=self._angle, extent=110, style="arc", outline=color["accent"], width=3)
        dots = "." * (int(self._phase) % 4)
        label = "Скачиваю" if self.yt_busy and not self.busy else "Сверяю источники"
        canvas.create_text(28, 11, text=label + dots, anchor="w", fill=color["muted"], font=(self.font_ui, 10))
        travel = (self._angle / 360) * max(width - 260, 1)
        canvas.create_rectangle(180, 8, width - 8, 14, fill=color["line"], outline="")
        canvas.create_rectangle(180 + travel, 8, min(width - 8, 180 + travel + 70), 14, fill=color["accent"], outline="")

    def toggle_secrets(self) -> None:
        secret = "" if self.show_secrets.get() else "*"
        self.discogs_entry.configure(show=secret)
        self.lastfm_entry.configure(show=secret)

    def remember_session(self) -> None:
        save_settings(
            discogs=self.discogs_key.get().strip(),
            lastfm=self.lastfm_key.get().strip(),
            show_log=bool(self.show_log_var.get()),
            tag_files=bool(self.tag_files_var.get()),
            fetch_covers=bool(self.fetch_covers_var.get()),
            dark=bool(self.dark_var.get()),
            source=self.source.get().strip(),
            catalog=self.catalog.get().strip(),
            download_dir=self.yt_dir.get().strip(),
            move=bool(self.move.get()),
            place_unclear=bool(self.keep_unclear.get()),
            use_youtube_folder=bool(self.use_downloads.get()),
            youtube_kind="playlist" if self.yt_kind.get() == "2" else "video",
            youtube_format=self.yt_format.get().strip() or "mp3",
            youtube_split=bool(self.yt_split.get()),
            watch_enabled=bool(self.watch_on.get()) if hasattr(self, "watch_on") else None,
            cookies=self.cookies_var.get().strip() if hasattr(self, "cookies_var") else None,
        )

    def open_prefs(self) -> None:
        load_settings()
        try:
            open_path(PREFS_PATH)
        except OSError:
            self.settings_status.set(str(PREFS_PATH))

    def save_settings_ui(self) -> None:
        self.remember_session()
        self.apply_log_visibility()
        self.apply_theme()
        self.settings_status.set("Сохранено в polka-prefs.json.")
        self.status.set("Настройки сохранены.")

    def apply_log_visibility(self) -> None:
        if load_settings().get("show_log"):
            if not self.log_box.winfo_ismapped():
                self.log_frame.pack(fill="both", expand=True, pady=(8, 0))
        else:
            self.log_frame.pack_forget()

    def clear_log(self) -> None:
        self.log_box.delete("1.0", "end")

    def append_log(self, text: str) -> None:
        if not load_settings().get("show_log"):
            return
        self.log_box.insert("end", text.rstrip() + "\n\n")
        self.log_box.see("end")

    def _row(self, parent, label, variable, command) -> None:
        from tkinter import ttk
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=6)
        ttk.Label(row, text=label, width=16, anchor="w").pack(side="left")
        ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True, padx=(0, 8), ipady=3)
        if command:
            self._make_button(row, "Обзор", command).pack(side="left")

    def pick_download_dir(self) -> None:
        path = self.filedialog.askdirectory(title="Куда скачивать")
        if path:
            self.yt_dir.set(path)

    def sync_download_source(self) -> None:
        folder = self.yt_dir.get().strip() or str(HERE / "Downloads")
        self.download_source_label.set(folder)
        if self.use_downloads.get():
            self.source.set(folder)

    def toggle_download_source(self) -> None:
        if self.use_downloads.get():
            self._source_before_downloads = self.source.get()
            folder = self.yt_dir.get().strip() or str(HERE / "Downloads")
            Path(folder).mkdir(parents=True, exist_ok=True)
            self.source.set(folder)
        else:
            self.source.set(getattr(self, "_source_before_downloads", ""))

    def start_download(self) -> None:
        if self.yt_busy:
            return
        url = self.yt_url.get().strip().replace('"', "")
        if not url.startswith(("http://", "https://")):
            self.messagebox.showinfo("Полка", "Нужна ссылка на YouTube, с http или https.")
            return
        bat = HERE / "Downloader.bat"
        if not bat.is_file():
            self.messagebox.showerror("Полка", "Рядом с программой нет Downloader.bat.")
            return
        if sys.platform != "win32":
            self.messagebox.showinfo("Полка", "Скачивание запускает Downloader.bat и работает на Windows.")
            return
        outdir = self.yt_dir.get().strip() or str(HERE / "Downloads")
        fmt = yt_format(self.yt_format.get().strip())
        kind = "2" if self.yt_kind.get() == "2" else "1"
        self.remember_session()
        self.yt_busy = True
        self.yt_status.set("Проверяю программы…")
        self.yt_log.delete("1.0", "end")
        threading.Thread(target=self._yt_worker, args=(bat, url, kind, fmt, outdir), daemon=True).start()

    def _yt_line(self, text: str) -> None:
        self.yt_log.insert("end", text)
        self.yt_log.see("end")

    def _yt_worker(self, bat: Path, url: str, kind: str, fmt: str, outdir: str) -> None:
        def quote(value: str) -> str:
            return '"' + value.replace('"', "") + '"'

        command = downloader_command(url, kind, fmt, outdir, load_settings(), bool(self.yt_split.get()))
        try:
            ensure_media_tools(lambda text: self.root.after(0, lambda line=text: self._yt_line(line)))
            self.root.after(0, lambda: self.yt_status.set("Скачиваю…"))
            process = subprocess.Popen(
                command,
                shell=True,
                cwd=str(HERE),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
            )
            assert process.stdout is not None
            for raw in process.stdout:
                line = raw.decode("utf-8", "replace")
                self.root.after(0, lambda text=line: self._yt_line(text))
            code = process.wait()
        except Exception as error:
            self.root.after(0, lambda: self._yt_done(f"Не запустился: {error}", True))
            return
        self.root.after(0, lambda: self._yt_done("Готово." if code == 0 else f"Ошибка, код {code}.", False))

    def _yt_done(self, text: str, failed: bool) -> None:
        self.yt_busy = False
        self.yt_status.set(text)
        if failed:
            self.yt_log.insert("end", text + "\n")

    def pick_cookies(self) -> None:
        path = self.filedialog.askopenfilename(
            title="cookies.txt из браузера",
            filetypes=[("Текст", "*.txt"), ("Все файлы", "*.*")],
        )
        if path:
            self.cookies_var.set(path)

    def refresh_watches(self) -> None:
        self.watch_list.delete(0, "end")
        for item in load_settings()["watches"]:
            mark = "папка" if item["mode"] == "folder" else "каталог"
            title = item["name"] or item["url"]
            self.watch_list.insert("end", f"{mark}   {title}")
        self.rebuild_playlist_tabs()

    def add_watch(self) -> None:
        url = self.yt_url.get().strip().replace('"', "")
        if not url.startswith(("http://", "https://")):
            self.messagebox.showinfo("Полка", "Сначала вставь ссылку на видео или плейлист.")
            return
        name = self.watch_name.get().strip()
        if not name and "list=LL" in url:
            name = "Понравившиеся"
        mode = "sort" if self.watch_mode.get() == "sort" else "folder"
        watches = [item for item in load_settings()["watches"] if item["url"] != url]
        watches.append({"url": url, "name": name, "mode": mode})
        save_settings(watches=watches, watch_enabled=True, cookies=self.cookies_var.get().strip())
        self.watch_on.set(True)
        self.refresh_watches()
        self.yt_status.set("Ссылка в слежке. Для неё появилась отдельная вкладка.")

    def remove_watch(self) -> None:
        picked = self.watch_list.curselection()
        watches = list(load_settings()["watches"])
        if not picked or picked[0] >= len(watches):
            return
        del watches[picked[0]]
        save_settings(watches=watches)
        self.refresh_watches()

    def save_watch_toggle(self) -> None:
        save_settings(watch_enabled=bool(self.watch_on.get()))

    def check_watches_now(self) -> None:
        if self.yt_busy:
            self.yt_status.set("Сначала закончится текущее скачивание.")
            return
        threading.Thread(target=self._watch_once, daemon=True).start()

    def _watch_loop(self) -> None:
        if self._watch_stop.wait(8):
            return
        while not self._watch_stop.is_set():
            prefs = load_settings()
            if prefs.get("watch_enabled") and prefs.get("watches") and not self.yt_busy:
                self._watch_once()
            minutes = int(load_settings().get("watch_minutes") or 15)
            if self._watch_stop.wait(minutes * 60):
                return

    def _watch_log(self, text: str) -> None:
        self.yt_log.insert("end", text if text.endswith("\n") else text + "\n")
        self.yt_log.see("end")

    def _watch_once(self) -> None:
        if self.yt_busy:
            return
        prefs = load_settings()
        watches = list(prefs.get("watches") or [])
        if not watches:
            self.root.after(0, lambda: self.yt_status.set("Слежка пустая."))
            return
        if sys.platform != "win32":
            self.root.after(0, lambda: self.yt_status.set("Слежка за YouTube работает на Windows."))
            return
        self.yt_busy = True
        self.root.after(0, lambda: self.yt_status.set("Проверяю подписки…"))
        try:
            ensure_media_tools(lambda text: self.root.after(0, lambda line=text: self._watch_log(line)))
            for entry in watches:
                self._watch_entry(entry)
        except Exception as error:
            self.root.after(0, lambda: self._watch_log(f"Слежка: {error}"))
        finally:
            self.yt_busy = False
            self.root.after(0, lambda: self.yt_status.set("Слежка проверена."))

    def _watch_entry(self, entry: dict) -> None:
        prefs = load_settings()
        title = entry.get("name") or entry["url"]
        self.root.after(0, lambda name=title: self._watch_log(f"Проверяю {name}"))
        if entry.get("mode") == "sort":
            self._watch_sort(entry, prefs)
            return
        if "list=LL" in entry["url"] and not str(prefs.get("cookies") or "").strip():
            self.root.after(0, lambda: self._watch_log("Понравившиеся закрыты. Нужен cookies.txt в настройках."))
        command, dest = watch_plan(entry, prefs)
        dest.mkdir(parents=True, exist_ok=True)
        self._run_capture(command)
        if entry.get("split", True):
            settle_full(dest, lambda text: self.root.after(0, lambda line=text: self._watch_log(line)))

    def _watch_sort(self, entry: dict, prefs: dict) -> None:
        catalog = str(prefs.get("catalog") or "").strip()
        if not catalog:
            self.root.after(0, lambda: self._watch_log("Для разбора по жанрам укажи каталог на первой вкладке."))
            return
        outdir = str(prefs.get("download_dir") or HERE / "Downloads")
        Path(outdir).mkdir(parents=True, exist_ok=True)
        before = {path.name for path in Path(outdir).iterdir() if path.is_dir()} if Path(outdir).is_dir() else set()
        kind = "2" if "list=" in entry["url"] else "1"
        fmt = prefs.get("youtube_format") or "mp3"
        command = downloader_command(entry["url"], kind, str(fmt), outdir, prefs, bool(entry.get("split", True)))
        self._run_capture(command, shell=True)
        fresh = [Path(outdir) / name for name in Path(outdir).iterdir() if name.is_dir() and name.name not in before and name.name != "_full"]
        for folder in fresh:
            self._sort_fresh(folder, Path(catalog), prefs)

    def _sort_fresh(self, folder: Path, catalog: Path, prefs: dict) -> None:
        try:
            item = describe_album(folder, folder.parent)
            verdict = sort_one(item, self.cache, use_net=True)
            if should_place(verdict, bool(prefs.get("place_unclear"))):
                verdict["placed"] = place(verdict, catalog, bool(prefs.get("move", True)))
            self.root.after(0, lambda text=f"{verdict.get('artist')} — {verdict.get('album')} → {verdict.get('main')} / {verdict.get('sub')}": self._watch_log(text))
        except Exception as error:
            self.root.after(0, lambda: self._watch_log(f"{folder.name}: {error}"))

    def _run_capture(self, command, shell: bool = False) -> None:
        process = subprocess.Popen(
            command,
            shell=shell,
            cwd=str(HERE),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
        )
        assert process.stdout is not None
        for raw in process.stdout:
            line = raw.decode("utf-8", "replace")
            self.root.after(0, lambda text=line: self._watch_log(text.rstrip("\n")))
        process.wait()

    def rebuild_playlist_tabs(self) -> None:
        from tkinter import ttk
        for child in list(self.tab_bar.winfo_children()):
            child.destroy()
        base_names = ("Сортировка", "Скачать", "Настройки")
        for key in list(self.pages):
            if key not in base_names:
                self.pages.pop(key).destroy()
        self._playlist_views = {}
        alive = []
        for button in self._buttons:
            try:
                if button.winfo_exists():
                    alive.append(button)
            except self.tk.TclError:
                pass
        self._buttons = alive
        for name in base_names:
            button = self._make_button(
                self.tab_bar, name, lambda n=name: self._open_page(n), accent=name == self.page_name,
            )
            button.page_name = name
            button.pack(side="left", padx=(0, 8))
        for item in load_settings()["watches"]:
            key = "pl:" + item["url"]
            frame = ttk.Frame(self.deck, padding=16)
            self.pages[key] = frame
            self._fill_playlist_page(frame, item)
            label = (item["name"] or "Плейлист")[:18]
            button = self._make_button(
                self.tab_bar, label, lambda n=key: self._open_page(n), accent=key == self.page_name,
            )
            button.page_name = key
            button.pack(side="left", padx=(0, 8))
        if self.page_name not in self.pages:
            self.page_name = "Скачать"
        for page in self.pages.values():
            page.place_forget()
        self.pages[self.page_name].place(x=0, y=0, relwidth=1, relheight=1)
        self._paint_buttons()

    def _fill_playlist_page(self, frame, item: dict) -> None:
        from tkinter import ttk
        title = item["name"] or "Плейлист"
        mode = "отдельная папка" if item.get("mode") == "folder" else "разбор по жанрам"
        heading = ttk.Label(frame, text=title, style="Title.TLabel")
        heading.pack(anchor="w")
        ttk.Label(frame, text=f"Плейлист · {mode}", style="Hint.TLabel").pack(anchor="w", pady=(0, 8))
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(0, 8))
        url = item["url"]
        self._make_button(buttons, "Обновить", lambda link=url: self.load_playlist(link), accent=True).pack(side="left")
        self._make_button(buttons, "Открыть на YouTube", lambda link=url: webbrowser.open(link)).pack(side="left", padx=(8, 0))
        status = self.tk.StringVar(value="Нажми «Обновить», чтобы увидеть видео.")
        ttk.Label(frame, textvariable=status).pack(anchor="w", pady=(0, 6))
        canvas = self.tk.Canvas(frame, highlightthickness=0, bd=0)
        bar = ttk.Scrollbar(frame, command=canvas.yview, style="Polka.Vertical.TScrollbar")
        inner = ttk.Frame(canvas)
        window = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=bar.set)
        canvas.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")

        def fit(event) -> None:
            canvas.itemconfigure(window, width=event.width)

        def stretch(_event=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        canvas.bind("<Configure>", fit)
        inner.bind("<Configure>", stretch)

        def wheel(event) -> None:
            step = int(-event.delta / 120) if event.delta else 0
            if not step:
                step = -1 if getattr(event, "num", 0) == 4 else 1
            canvas.yview_scroll(step, "units")

        canvas.bind("<Enter>", lambda _event: canvas.bind_all("<MouseWheel>", wheel))
        canvas.bind("<Leave>", lambda _event: canvas.unbind_all("<MouseWheel>"))
        self._playlist_views[url] = {"status": status, "inner": inner, "canvas": canvas, "photos": [], "title": heading}

    def load_playlist(self, url: str) -> None:
        threading.Thread(target=self._load_playlist, args=(url,), daemon=True).start()

    def _load_playlist(self, url: str) -> None:
        view = self._playlist_views.get(url)
        if view is None:
            return
        self.root.after(0, lambda: view["status"].set("Смотрю плейлист…"))
        try:
            if sys.platform == "win32":
                ensure_media_tools(lambda _text: None)
            title, _owner, rows = fetch_playlist(url, str(load_settings().get("cookies") or ""))
        except Exception as error:
            self.root.after(0, lambda: view["status"].set(f"Не открылся: {error}"))
            return
        self.root.after(0, lambda: self._render_playlist(url, title, rows))

    def _render_playlist(self, url: str, title: str, rows: list[dict]) -> None:
        from tkinter import ttk
        view = self._playlist_views.get(url)
        if view is None:
            return
        if title:
            try:
                view["title"].configure(text=title)
            except self.tk.TclError:
                pass
        done = read_archive_ids()
        got = sum(1 for row in rows if row["id"] in done)
        view["status"].set(f"{len(rows)} видео, уже скачано {got}")
        inner = view["inner"]
        for child in list(inner.winfo_children()):
            child.destroy()
        view["photos"] = []
        color = self.palette()
        for row in rows:
            line = ttk.Frame(inner)
            line.pack(fill="x", pady=4)
            shot = self.tk.Canvas(line, width=168, height=94, highlightthickness=0, bd=0, bg=color["paper"], cursor="hand2")
            shot.pack(side="left", padx=(0, 10))
            text = ttk.Frame(line)
            text.pack(side="left", fill="x", expand=True)
            ttk.Label(text, text=row["title"], font=(self.font_ui, 13), cursor="hand2").pack(anchor="w")
            mark = "уже скачано" if row["id"] in done else "ещё нет"
            extra = " · ".join(part for part in (row["channel"], row["duration"], mark) if part)
            ttk.Label(text, text=extra, style="Hint.TLabel", cursor="hand2").pack(anchor="w")
            link = row["url"]
            opener = lambda _event, target=link: webbrowser.open(target)
            line.bind("<Button-1>", opener)
            shot.bind("<Button-1>", opener)
            text.bind("<Button-1>", opener)
            for child in text.winfo_children():
                child.bind("<Button-1>", opener)
            if row["thumb"]:
                threading.Thread(
                    target=self._load_thumb, args=(url, row["id"], row["thumb"], shot), daemon=True,
                ).start()
        view["canvas"].update_idletasks()
        view["canvas"].configure(scrollregion=view["canvas"].bbox("all"))

    def _load_thumb(self, url: str, video_id: str, thumb: str, canvas) -> None:
        png = self._thumb_png(video_id, thumb)
        if png is None:
            return

        def show() -> None:
            view = self._playlist_views.get(url)
            if view is None:
                return
            try:
                if not canvas.winfo_exists():
                    return
                photo = self.tk.PhotoImage(file=str(png))
            except self.tk.TclError:
                return
            view["photos"].append(photo)
            canvas.delete("all")
            canvas.create_image(0, 0, image=photo, anchor="nw")

        self.root.after(0, show)

    def _thumb_png(self, video_id: str, thumb_url: str):
        safe = re.sub(r"[^\w-]", "", video_id)[:40] or "thumb"
        folder = HERE / "polka-thumbs"
        folder.mkdir(exist_ok=True)
        png = folder / f"{safe}.png"
        if png.is_file() and png.stat().st_size > 0:
            return png
        jpg = folder / f"{safe}.jpg"
        if not jpg.is_file() or jpg.stat().st_size == 0:
            try:
                request = urllib.request.Request(thumb_url, headers={"User-Agent": BROWSER_UA})
                with urllib.request.urlopen(request, context=CTX, timeout=20) as response:
                    jpg.write_bytes(response.read())
            except (OSError, urllib.error.URLError):
                return None
        ffmpeg = Path(tool_path("ffmpeg"))
        if not (ffmpeg.is_file() or shutil.which(str(ffmpeg))):
            return None
        subprocess.run(
            [str(ffmpeg), "-y", "-loglevel", "error", "-i", str(jpg), "-vf", "scale=168:94", str(png)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
        return png if png.is_file() and png.stat().st_size > 0 else None

    def pick_source(self) -> None:
        path = self.filedialog.askdirectory(title="Папка с альбомами")
        if path:
            self.source.set(path)

    def pick_catalog(self) -> None:
        path = self.filedialog.askdirectory(title="Куда складывать каталог")
        if path:
            self.catalog.set(path)

    def scan(self) -> None:
        self._run(False)

    def apply(self) -> None:
        if not self.results:
            self._run(True)
            return
        self._run(True)

    def _run(self, do_place: bool) -> None:
        self.remember_session()
        if self.busy:
            return
        source = self.source.get().strip()
        catalog = self.catalog.get().strip()
        if not source or not catalog:
            self.messagebox.showinfo("Полка", "Нужны обе папки: откуда брать альбомы и куда класть каталог.")
            return
        source_path, catalog_path = Path(source), Path(catalog)
        if not source_path.is_dir() or not catalog_path.is_dir():
            self.messagebox.showerror("Полка", "Одна из папок не открывается.")
            return
        if source_path.resolve() == catalog_path.resolve():
            self.messagebox.showerror("Полка", "Папка альбомов и каталог должны быть разными.")
            return
        self.busy = True
        self.status.set("Смотрю альбомы…")
        self.clear_log()
        threading.Thread(target=self._worker, args=(source_path, catalog_path, do_place), daemon=True).start()

    def _worker(self, source: Path, catalog: Path, do_place: bool) -> None:
        albums = find_albums(source)
        if not albums:
            self.root.after(0, lambda: self._finish("В папке нет альбомов с музыкой.", []))
            return
        results = []
        for index, folder in enumerate(albums, start=1):
            self.root.after(0, lambda i=index, n=len(albums), name=folder.name: self.status.set(f"{i} / {n}  {name}"))
            item = describe_album(folder, source)
            try:
                verdict = sort_one(item, self.cache, use_net=True)
            except Exception as error:
                verdict = {
                    "path": folder, "artist": item["artist"], "album": item["album"],
                    "main": "Other", "sub": "Other", "confidence": "low",
                    "reason": str(error), "log": [],
                }
            options = load_settings()
            if options.get("tag_files", True) or options.get("fetch_covers", True):
                genre_name = ""
                if verdict.get("sub") not in (None, "", "Other"):
                    genre_name = verdict["sub"]
                elif verdict.get("main") not in (None, "", "Other"):
                    genre_name = verdict["main"]
                try:
                    extra = enrich_album(
                        Path(verdict["path"]),
                        verdict.get("artist") or "",
                        verdict.get("album") or "",
                        genre_name,
                        write_tags=bool(options.get("tag_files", True)),
                        fetch_covers=bool(options.get("fetch_covers", True)),
                        year=str(verdict.get("year") or ""),
                    )
                except Exception as error:
                    extra = [f"теги: ошибка — {error}"]
                verdict["log"] = [*(verdict.get("log") or []), *extra]
            if do_place and should_place(verdict, self.keep_unclear.get()):
                try:
                    verdict["placed"] = place(verdict, catalog, self.move.get())
                except Exception as error:
                    verdict["placed"] = f"ошибка: {error}"
            else:
                verdict["placed"] = "план" if not do_place else "оставлен — жанр неясен"
            results.append(verdict)
            report = album_log(verdict)
            self.root.after(0, lambda text=report: self.append_log(text))
        try:
            save_cache(self.cache)
        except OSError:
            pass
        done = sum(1 for item in results if item.get("placed") == "ok")
        unclear = sum(1 for item in results if item.get("sub") in (None, "", "Other"))
        text = f"Готово. Альбомов: {len(results)}. Переложено: {done}. Неясных: {unclear}."
        self.root.after(0, lambda: self._finish(text, results))

    def _finish(self, text: str, results: list[dict]) -> None:
        self.busy = False
        self.results = results
        self.list.delete(0, "end")
        rows = []
        for item in results:
            mark = {"ok": "перенесён", "plan": "план"}.get(item.get("placed", ""), item.get("placed", ""))
            if item.get("placed") == "ok" and not self.move.get():
                mark = "скопирован"
            year = f" ({item['year']})" if item.get("year") else ""
            rows.append(f"{item['artist']} — {item['album']}{year}   →   {item['main']} / {item['sub']}   ({mark})")
        self._reveal(rows, 0)
        self.status.set(text)

    def _reveal(self, rows: list[str], index: int) -> None:
        if index >= len(rows):
            return
        self.list.insert("end", rows[index])
        self.list.see("end")
        self.root.after(42, lambda: self._reveal(rows, index + 1))

    def _ensure_mutagen(self) -> None:
        try:
            import mutagen  # noqa: F401
            return
        except Exception:
            pass

        def work() -> None:
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--quiet", "mutagen"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                return
            self.root.after(0, lambda: self.status.set("Библиотека mutagen установлена."))

        threading.Thread(target=work, daemon=True).start()

    def run(self) -> None:
        self.root.mainloop()


def verdict_public(verdict: dict) -> dict:
    return {
        "artist": verdict.get("artist") or "",
        "album": verdict.get("album") or "",
        "year": str(verdict.get("year") or ""),
        "main": verdict.get("main") or "",
        "sub": verdict.get("sub") or "",
        "placed": verdict.get("placed") or "",
        "confidence": verdict.get("confidence") or "",
        "reason": verdict.get("reason") or "",
    }


def sort_library(source: Path, catalog: Path, do_place: bool, on_status=None) -> dict:
    cache = load_cache()
    albums = find_albums(source)
    if not albums:
        return {"text": "В папке нет альбомов с музыкой.", "results": []}
    results = []
    for index, folder in enumerate(albums, start=1):
        if on_status:
            on_status(f"{index} / {len(albums)}  {folder.name}")
        item = describe_album(folder, source)
        try:
            verdict = sort_one(item, cache, use_net=True)
        except Exception as error:
            verdict = {
                "path": folder, "artist": item["artist"], "album": item["album"],
                "main": "Other", "sub": "Other", "confidence": "low",
                "reason": str(error), "log": [],
            }
        options = load_settings()
        if options.get("tag_files", True) or options.get("fetch_covers", True):
            genre_name = ""
            if verdict.get("sub") not in (None, "", "Other"):
                genre_name = verdict["sub"]
            elif verdict.get("main") not in (None, "", "Other"):
                genre_name = verdict["main"]
            try:
                extra = enrich_album(
                    Path(verdict["path"]),
                    verdict.get("artist") or "",
                    verdict.get("album") or "",
                    genre_name,
                    write_tags=bool(options.get("tag_files", True)),
                    fetch_covers=bool(options.get("fetch_covers", True)),
                    year=str(verdict.get("year") or ""),
                )
            except Exception as error:
                extra = [f"теги: ошибка — {error}"]
            verdict["log"] = [*(verdict.get("log") or []), *extra]
        if do_place and should_place(verdict, bool(options.get("place_unclear"))):
            try:
                verdict["placed"] = place(verdict, catalog, bool(options.get("move", True)))
            except Exception as error:
                verdict["placed"] = f"ошибка: {error}"
        else:
            verdict["placed"] = "план" if not do_place else "оставлен — жанр неясен"
        results.append(verdict_public(verdict))
    try:
        save_cache(cache)
    except OSError:
        pass
    done = sum(1 for item in results if item.get("placed") == "ok")
    unclear = sum(1 for item in results if item.get("sub") in (None, "", "Other"))
    return {
        "text": f"Готово. Альбомов: {len(results)}. Переложено: {done}. Неясных: {unclear}.",
        "results": results,
    }


IS_WINDOWS = sys.platform == "win32"


def tool_path(name: str) -> str:
    """Windows: рядом лежащий name.exe (как раньше). Иначе: локальный бинарник или системный из PATH."""
    if IS_WINDOWS:
        return str(HERE / f"{name}.exe")
    for local in (HERE / name, HERE / f"{name}.exe"):
        if local.is_file() and os.access(local, os.X_OK):
            return str(local)
    return shutil.which(name) or name


def ffmpeg_dir() -> str:
    if IS_WINDOWS:
        return str(HERE)
    system = shutil.which("ffmpeg")
    return str(Path(system).parent) if system else str(HERE)


def open_path(path) -> None:
    if IS_WINDOWS:
        os.startfile(path)
        return
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    subprocess.Popen([opener, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _tool_ready(path: Path, minimum: int) -> bool:
    try:
        return path.is_file() and path.stat().st_size >= minimum
    except OSError:
        return False


MEDIA_TOOLS_LOCK = threading.Lock()


def _remove_quietly(path: Path) -> None:
    for _attempt in range(5):
        try:
            path.unlink(missing_ok=True)
            return
        except OSError:
            time.sleep(0.3)


def _replace_retry(source: Path, dest: Path, tries: int = 10, delay: float = 0.5) -> Path:
    """Переименовать source -> dest; антивирус на Windows может ненадолго держать новый файл.
    Повторяет, потом пробует копию; если и это не вышло — возвращает source (им можно пользоваться)."""
    for attempt in range(tries):
        try:
            os.replace(source, dest)
            return dest
        except OSError:
            if attempt + 1 < tries:
                time.sleep(delay)
    try:
        shutil.copyfile(source, dest)
        return dest
    except OSError:
        return source


def _http_download(url: str, dest: Path, log) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    temporary = dest.with_name(dest.name + ".part")
    _remove_quietly(temporary)
    request = urllib.request.Request(url, headers={"User-Agent": "Polka/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        mark = 0
        with temporary.open("wb") as handle:
            while True:
                chunk = response.read(256 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                done += len(chunk)
                if total:
                    percent = done * 100 // total
                    if percent >= mark + 10:
                        mark = percent
                        log(f"{dest.name}: {percent}%\n")
                elif done - mark >= 8 * 1024 * 1024:
                    mark = done
                    log(f"{dest.name}: {done // (1024 * 1024)} МБ\n")
            handle.flush()
            os.fsync(handle.fileno())
    return _replace_retry(temporary, dest)


def ensure_media_tools(log) -> None:
    # два клика / два запроса сразу не должны качать один и тот же файл
    with MEDIA_TOOLS_LOCK:
        _ensure_media_tools(log)


def _ensure_media_tools(log) -> None:
    if not IS_WINDOWS:
        missing = [name for name in ("yt-dlp", "ffmpeg", "ffprobe") if not shutil.which(tool_path(name))]
        if missing:
            raise RuntimeError("Не найдено в системе: " + ", ".join(missing) + ". Установи через пакетный менеджер или pip.")
        return
    ytdlp = HERE / "yt-dlp.exe"
    ffmpeg = HERE / "ffmpeg.exe"
    ffprobe = HERE / "ffprobe.exe"
    if not _tool_ready(ytdlp, 1_000_000):
        log("Скачиваю yt-dlp…\n")
        got = _http_download(
            "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe",
            ytdlp,
            log,
        )
        if got != ytdlp:
            raise RuntimeError("Не удалось сохранить yt-dlp.exe: файл занят (антивирус?). Попробуй ещё раз через минуту.")
    if _tool_ready(ffmpeg, 1_000_000) and _tool_ready(ffprobe, 1_000_000):
        return
    log("Скачиваю ffmpeg, один раз, около 100 МБ…\n")
    archive = HERE / "_ffmpeg.zip"
    _remove_quietly(archive)
    _remove_quietly(archive.with_name(archive.name + ".part"))
    archive = _http_download("https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip", archive, log)
    import zipfile
    found: set[str] = set()
    with zipfile.ZipFile(archive) as bundle:
        targets = {"ffmpeg.exe": ffmpeg, "ffprobe.exe": ffprobe}
        for info in bundle.infolist():
            name = Path(info.filename).name.lower()
            folder = info.filename.replace("\\", "/").lower()
            if name in targets and "/bin/" in f"/{folder}":
                with bundle.open(info) as source, targets[name].open("wb") as handle:
                    shutil.copyfileobj(source, handle)
                found.add(name)
    _remove_quietly(archive)
    _remove_quietly(HERE / "_ffmpeg.zip.part")
    missing = [name for name in ("ffmpeg.exe", "ffprobe.exe") if name not in found]
    if missing:
        raise RuntimeError("в архиве ffmpeg нет " + ", ".join(missing))


def main() -> None:
    if "--selftest" in sys.argv:
        selftest()
        return
    if "--stamp" in sys.argv:
        index = sys.argv.index("--stamp")
        if index + 1 >= len(sys.argv):
            print("нужна папка")
            sys.exit(2)
        stamp_download_tree(Path(sys.argv[index + 1]))
        return
    try:
        App().run()
    except Exception:
        import traceback
        text = traceback.format_exc()
        try:
            (HERE / "polka-error.log").write_text(text, encoding="utf-8")
        except OSError:
            pass
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Polka", text[-1800:])
            root.destroy()
        except Exception:
            print(text)
        sys.exit(1)


if __name__ == "__main__":
    main()
