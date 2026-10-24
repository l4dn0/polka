"""Local engine for the Electron window. Listens only on this computer."""

from __future__ import annotations

import html
import json
import os
import urllib.parse
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import polka
import polka_auth

HOST = "127.0.0.1"
PORT = 47321
STATE = {
    "sort": {"busy": False, "status": "Выбери папки.", "text": "", "results": []},
    "download": {"busy": False, "status": "Ссылка на видео или плейлист.", "log": "", "progress": polka.progress_new(), "label": ""},
}
LOCK = threading.Lock()

if os.environ.get("POLKA_DEMO_JOB"):
    # только для скриншотов: показать полоску загрузки без реального скачивания
    STATE["download"].update(busy=True, status="Скачиваю…", label="test",
                             progress={**polka.progress_new(), "title": "Blank Banshee - Blank Banshee 0 [FULL ALBUM]",
                                       "item": 3, "total": 6, "percent": 47.0, "stage": "скачиваю", "skipped": 1, "failed": 1,
                                       "error": "недоступно в вашей стране (авторские права)",
                                       "items": [
                                           {"title": "OSCOB - kingdom of gods and demons", "state": "готово", "percent": 100,
                                            "path": "/tmp/demo/Music/Electronic/Dungeon Synth/OSCOB/kingdom of gods and demons", "note": ""},
                                           {"title": "Edelweiss - 205 (full album, 2019)", "state": "недоступно", "percent": 0, "path": "",
                                            "note": "недоступно в вашей стране (авторские права)"},
                                           {"title": "Blank Banshee - Blank Banshee 0 [FULL ALBUM]", "state": "скачиваю", "percent": 47, "path": "", "note": ""}]})


def body_json(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length") or 0)
    raw = handler.rfile.read(length) if length else b"{}"
    data = json.loads(raw.decode("utf-8") or "{}")
    return data if isinstance(data, dict) else {}


def quote(value: str) -> str:
    return '"' + value.replace('"', "") + '"'


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        return

    def send_json(self, payload: dict, code: int = 200) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def send_page(self, title: str, text: str, code: int = 200) -> None:
        raw = (
            "<!doctype html><meta charset='utf-8'><title>Полка</title>"
            "<body style='font:16px sans-serif;background:#f6f0e6;color:#2a2118;display:grid;place-items:center;height:90vh'>"
            f"<div style='text-align:center'><h2>{html.escape(title)}</h2><p>{html.escape(text)}</p></div>"
        ).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def auth_callback(self, path: str) -> None:
        query = dict(urllib.parse.parse_qsl(self.path.split("?", 1)[1] if "?" in self.path else ""))
        name = "lastfm" if "lastfm" in path else "discogs"
        try:
            if name == "lastfm":
                if not query.get("token"):
                    raise RuntimeError("Last.fm не вернул token.")
                entry = polka_auth.lastfm_finish(query["token"])
            else:
                if query.get("denied"):
                    raise RuntimeError("Доступ не разрешён.")
                if not query.get("oauth_token") or not query.get("oauth_verifier"):
                    raise RuntimeError("Discogs не вернул oauth_verifier.")
                entry = polka_auth.discogs_finish(query["oauth_token"], query["oauth_verifier"])
        except Exception as error:
            polka_auth.update_service(name, error=str(error))
            self.send_page("Не получилось подключить", str(error), 400)
            return
        self.send_page("Подключено", f"Вы вошли как {entry.get('user') or 'пользователь'}. Вкладку можно закрыть и вернуться в Полку.")

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in ("/auth/lastfm/callback", "/auth/discogs/callback"):
            self.auth_callback(path)
            return
        if path == "/api/auth":
            self.send_json(polka_auth.status())
            return
        if path == "/api/yt_search":
            query = dict(urllib.parse.parse_qsl(self.path.split("?", 1)[1] if "?" in self.path else "")).get("q", "")
            if not query.strip():
                self.send_json({"error": "Пустой запрос."}, 400)
                return
            try:
                if sys.platform == "win32":
                    polka.ensure_media_tools(lambda _text: None)
                rows = polka.youtube_search(query)
            except subprocess.TimeoutExpired:
                self.send_json({"error": "YouTube не ответил вовремя. Попробуй ещё раз."}, 504)
                return
            except FileNotFoundError:
                self.send_json({"error": "Не найден yt-dlp."}, 500)
                return
            except Exception as error:
                self.send_json({"error": f"Поиск не удался: {str(error)[-200:]}"}, 500)
                return
            done = polka.read_archive_ids()
            for row in rows:
                row["downloaded"] = row["id"] in done
            self.send_json({"query": query, "rows": rows})
            return
        if path == "/api/paths":
            prefs = polka.load_settings()
            self.send_json({"base": str(polka.downloaded_path(prefs).parent), "paths": polka.read_paths(prefs)})
            return
        if path == "/api/health":
            self.send_json({"ok": True, "version": polka.VERSION})
            return
        if path == "/api/prefs":
            self.send_json(polka.load_settings())
            return
        if path == "/api/sort":
            with LOCK:
                self.send_json(STATE["sort"])
            return
        if path == "/api/download":
            with LOCK:
                self.send_json(STATE["download"])
            return
        self.send_json({"error": "нет такого запроса"}, 404)

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        try:
            data = body_json(self)
        except json.JSONDecodeError:
            self.send_json({"error": "не json"}, 400)
            return
        if path == "/api/prefs":
            self.send_json(polka.save_settings(**data))
            return
        if path == "/api/sort":
            self.start_sort(data)
            return
        if path == "/api/download":
            self.start_download(data)
            return
        if path == "/api/playlist":
            self.playlist(data)
            return
        if path.startswith("/api/auth/"):
            self.auth_post(path, data)
            return
        if path == "/api/playlist_run":
            self.playlist_run(data)
            return
        if path == "/api/stream":
            self.stream(data)
            return
        self.send_json({"error": "нет такого запроса"}, 404)

    def start_sort(self, data: dict) -> None:
        source = Path(str(data.get("source") or ""))
        catalog = Path(str(data.get("catalog") or ""))
        if not source.is_dir() or not catalog.is_dir():
            self.send_json({"error": "Нужны две существующие папки."}, 400)
            return
        if source.resolve() == catalog.resolve():
            self.send_json({"error": "Папка альбомов и каталог должны быть разными."}, 400)
            return
        with LOCK:
            if STATE["sort"]["busy"]:
                self.send_json({"error": "Разбор уже идёт."}, 409)
                return
            STATE["sort"] = {"busy": True, "status": "Смотрю альбомы…", "text": "", "results": []}
        do_place = bool(data.get("place"))

        def run() -> None:
            try:
                result = polka.sort_library(
                    source, catalog, do_place,
                    on_status=lambda text: set_state("sort", status=text),
                )
                set_state("sort", busy=False, status=result["text"], text=result["text"], results=result["results"])
            except Exception as error:
                set_state("sort", busy=False, status=str(error), text=str(error), results=[])

        threading.Thread(target=run, daemon=True).start()
        self.send_json({"ok": True})

    def start_download(self, data: dict) -> None:
        urls = [str(item).strip() for item in (data.get("urls") or [data.get("url") or ""])]
        urls = [item for item in urls if item.startswith(("http://", "https://"))]
        if not urls:
            self.send_json({"error": "Нужна ссылка на YouTube."}, 400)
            return
        prefs = polka.load_settings()
        if not str(prefs.get("catalog") or "").strip():
            self.send_json({"error": polka.ROOT_MISSING, "code": "root"}, 400)
            return
        if sys.platform != "win32":
            self.send_json({"error": "Скачивание работает на Windows."}, 400)
            return
        fmt = polka.yt_format(data.get("format") or prefs.get("youtube_format"))
        kind = "2" if str(data.get("kind") or "1") in {"2", "playlist"} else "1"
        split = data.get("split")
        split = bool(prefs.get("youtube_split", True)) if split is None else split not in (False, 0, "0", "false")
        outdir = str(polka.link_dir(prefs))
        with LOCK:
            if STATE["download"]["busy"]:
                self.send_json({"error": "Скачивание уже идёт."}, 409)
                return
            STATE["download"] = {"busy": True, "status": "Проверяю программы…", "log": "", "progress": polka.progress_new(),
                                 "label": urls[0] if len(urls) == 1 else polka.ru_plural(len(urls), "ссылка", "ссылки", "ссылок"), "batch": [0, len(urls)]}

        def log(text: str) -> None:
            dl_log(text)

        def run() -> None:
            try:
                polka.ensure_media_tools(log)
                code = 0
                for number, url in enumerate(urls, 1):
                    set_state("download", status=f"Скачиваю… {number}/{len(urls)}" if len(urls) > 1 else "Скачиваю…", batch=[number, len(urls)])
                    command = polka.downloader_command(url, kind, fmt, outdir, prefs, split)
                    process = subprocess.Popen(
                        command, shell=True, cwd=str(polka.HERE),
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                    )
                    assert process.stdout is not None
                    started = time.time() - 2
                    for raw in process.stdout:
                        log(raw.decode("utf-8", "replace"))
                    code = process.wait() or code
                    for folder in Path(outdir).iterdir() if Path(outdir).is_dir() else []:
                        if folder.is_dir() and folder.stat().st_mtime >= started:
                            log(polka.placed_line(folder.name, folder))
                finish_download("Готово." if code == 0 else f"Ошибка, код {code}.", code == 0)
            except Exception as error:
                log(str(error))
                finish_download(str(error), False)

        threading.Thread(target=run, daemon=True).start()
        self.send_json({"ok": True})

    def playlist(self, data: dict) -> None:
        url = str(data.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            self.send_json({"error": "Нужна ссылка."}, 400)
            return
        try:
            if sys.platform == "win32":
                polka.ensure_media_tools(lambda _text: None)
            title, owner, rows = polka.fetch_playlist(url, str(polka.load_settings().get("cookies") or ""))
        except Exception as error:
            self.send_json({"error": str(error)}, 500)
            return
        done = polka.read_archive_ids()
        for row in rows:
            row["downloaded"] = row["id"] in done
        self.send_json({"title": title, "owner": owner, "rows": rows})

    def auth_post(self, path: str, data: dict) -> None:
        name = "discogs" if data.get("service") == "discogs" else "lastfm"
        try:
            if path == "/api/auth/keys":
                values = {"app_key": str(data.get("key") or "").strip() or None}
                secret = str(data.get("secret") or "").strip()
                if secret or not values["app_key"]:
                    values["app_secret"] = secret or None
                polka_auth.update_service(name, **values)
            elif path == "/api/auth/start":
                polka_auth.update_service(name, error=None)
                url = polka_auth.lastfm_start() if name == "lastfm" else polka_auth.discogs_start()
                self.send_json({"url": url, **polka_auth.status()})
                return
            elif path == "/api/auth/logout":
                polka_auth.logout(name)
            elif path == "/api/auth/discogs_token":
                polka_auth.discogs_personal(str(data.get("token") or ""))
            else:
                self.send_json({"error": "нет такого запроса"}, 404)
                return
        except Exception as error:
            self.send_json({"error": str(error)}, 400)
            return
        self.send_json(polka_auth.status())

    def playlist_run(self, data: dict) -> None:
        prefs = polka.load_settings()
        url = str(data.get("url") or "")
        entry = next((item for item in prefs.get("watches") or [] if item.get("url") == url), None)
        if not entry:
            self.send_json({"error": "Нет такого плейлиста."}, 400)
            return
        if not str(prefs.get("catalog") or "").strip():
            self.send_json({"error": polka.ROOT_MISSING, "code": "root"}, 400)
            return
        if sys.platform != "win32":
            self.send_json({"error": "Скачивание работает на Windows."}, 400)
            return
        with LOCK:
            if STATE["download"]["busy"]:
                self.send_json({"error": "Скачивание уже идёт."}, 409)
                return
            STATE["download"] = {"busy": True, "status": "Скачиваю новое из плейлиста…", "log": "", "progress": polka.progress_new(),
                                 "label": str(entry.get("name") or "Плейлист"), "batch": [0, 0]}

        def log(text: str) -> None:
            dl_log(text)

        def run() -> None:
            try:
                polka.ensure_media_tools(log)
                polka.run_playlist(entry, prefs, log)
                finish_download("Готово.", True)
            except Exception as error:
                log(str(error))
                finish_download(str(error), False)

        threading.Thread(target=run, daemon=True).start()
        self.send_json({"ok": True})

    def stream(self, data: dict) -> None:
        url = str(data.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            self.send_json({"error": "Нужна ссылка на видео."}, 400)
            return
        if sys.platform != "win32":
            self.send_json({"error": "Слушать можно в программе на Windows."}, 400)
            return
        try:
            polka.ensure_media_tools(lambda _text: None)
            link = polka.audio_stream(url)
        except Exception as error:
            self.send_json({"error": str(error)}, 500)
            return
        self.send_json({"url": link})


def dl_log(text: str) -> None:
    """Пишет вывод скачивания в лог (последние ~40 КБ) и обновляет разобранный ход."""
    with LOCK:
        job = STATE["download"]
        for line in text.replace("\r", "\n").splitlines():
            polka.progress_update(job.setdefault("progress", polka.progress_new()), line)
            if line.startswith(polka.PLACED_MARK) or (line.startswith("[download]") and "%" in line and " of " in line):
                continue  # строки процентов не копим в логе
            job["log"] += line + "\n"
        if len(job["log"]) > 40000:
            job["log"] = job["log"][-30000:]


def finish_download(status: str, ok: bool) -> None:
    with LOCK:
        job = STATE["download"]
        progress = job.setdefault("progress", polka.progress_new())
        progress["stage"] = "готово" if ok and not progress.get("error") else "ошибка"
        if ok and not progress.get("error"):
            progress["percent"] = 100.0
        job.update(busy=False, status=status)


def set_state(name: str, **updates) -> None:
    with LOCK:
        STATE[name].update(updates)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Полка слушает http://{HOST}:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
