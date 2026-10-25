"""Local web UI: `psptool ui [WORKDIR]` -> http://127.0.0.1:8765

Plain stdlib HTTP server with a JSON API; the page is static files in
ui/static. Long jobs (unpack, pack...) run in a thread, one at a time,
and the page polls /api/job for the log.
"""
import json
import os
import re
import socket
import threading
import time
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional
from urllib.parse import parse_qs, urlparse

from ..core import ffmpeg, hdtex, llm, ocr, picker, playtest, plugin, remote, textfit
from ..core.iso import IsoImage
from ..core.project import Project
from ..core.sfo import parse_sfo

# jobs that look at Job.stop now and then
STOPPABLE = ("hd", "hdarchive", "movies")

# save dialog lines (UTF-8, system font): SFO title fields are 128 bytes
UTF8_MAX_BYTES = 120
STATIC = os.path.join(os.path.dirname(__file__), "static")
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8", ".png": "image/png", ".svg": "image/svg+xml"}
RECENT = os.path.join(os.path.expanduser("~"), ".config", "psptool", "recent.json")


class Job:
    def __init__(self):
        self.lock = threading.Lock()
        self.name = ""
        self.running = False
        self.log = []
        self.error = ""
        self.progress = None  # [done, total] when the job knows it
        self.stop = False     # asked to stop (jobs that check it)
        self.stoppable = False
        self.log_dir = None   # finished jobs leave their log there
        self.log_file = ""

    def start(self, name, fn):
        with self.lock:
            if self.running:
                raise RuntimeError("busy: " + self.name)
            self.name, self.running, self.log, self.error, self.progress = name, True, [], "", None
            self.stop, self.stoppable = False, name in STOPPABLE
            self.log_file = ""

        def run():
            try:
                fn(self.say)
            except Exception as e:  # shown in the UI
                self.error = "%s: %s" % (type(e).__name__, e)
                self.log.append(traceback.format_exc())
            finally:
                self._save_log()
                self.running = False
        threading.Thread(target=run, daemon=True).start()

    def _save_log(self):
        """logs/<job>.log in the project: the whole log, error last."""
        if not self.log_dir:
            return
        try:
            os.makedirs(self.log_dir, exist_ok=True)
            path = os.path.join(self.log_dir, self.name + ".log")
            with open(path, "w", encoding="utf-8") as f:
                f.write("# %s %s\n" % (self.name, time.strftime("%Y-%m-%d %H:%M:%S")))
                f.write("".join(str(l).rstrip("\n") + "\n" for l in self.log))
                if self.error:
                    f.write("ERROR: %s\n" % self.error)
            self.log_file = path
        except OSError:
            pass

    def say(self, line):
        self.log.append(str(line))

    def state(self, since=0):
        return {"name": self.name, "running": self.running, "error": self.error,
                "log": self.log[since:], "next": len(self.log), "progress": self.progress,
                "stoppable": self.stoppable, "stopping": self.stop,
                "log_file": "" if self.running else self.log_file}


class App:
    def __init__(self, workdir: Optional[str]):
        self.game = None
        self.job = Job()
        self.edit_lock = threading.Lock()
        if workdir:
            self.open(workdir)

    # --- project ---------------------------------------------------------

    def open(self, workdir: str):
        p = Project(workdir)
        if not p.meta:
            raise ValueError("%s is not a project" % workdir)
        self.game = plugin.get_plugin(p.meta["plugin"])(p)
        self._src_count = None
        self.job.log_dir = p.path("logs")
        self._remember(p.root)

    def _remember(self, root):
        try:
            with open(RECENT, encoding="utf-8") as f:
                items = json.load(f)
        except (OSError, ValueError):
            items = []
        items = [root] + [x for x in items if x != root]
        os.makedirs(os.path.dirname(RECENT), exist_ok=True)
        with open(RECENT, "w", encoding="utf-8") as f:
            json.dump(items[:10], f)

    def recent(self):
        try:
            with open(RECENT, encoding="utf-8") as f:
                return [x for x in json.load(f) if os.path.exists(os.path.join(x, "project.json"))]
        except (OSError, ValueError):
            return []

    def project_info(self):
        if not self.game:
            return {"open": False, "recent": self.recent()}
        g = self.game
        return {"open": True, "root": g.project.root, "meta": g.project.meta,
                "plugin": {"id": g.id, "name": g.name, "features": list(g.features)},
                "unpacked": os.path.isdir(g.project.path("files")),
                "texts": bool(g.text_entries()) if "texts" in g.features else False,
                # the reference was imported (and the image is still there)
                "ref": bool(g.project.meta.get("ref_iso")) and os.path.isfile(g.project.meta.get("ref_iso")),
                "font": {"settings": g.font_settings(),
                         "cells": {"%04x" % c: ch for c, ch in g.font_cells().items()}}
                if "font" in g.features else None,
                "eboot": g.eboot_patched() if "eboot" in g.features else None,
                "movies": any(i >= 9000 for i in g.text_entries()) if "movies" in g.features else None,
                "recent": self.recent()}

    def init(self, iso_path: str, workdir: str):
        with IsoImage(iso_path) as iso:
            try:
                sfo = parse_sfo(iso.read("/PSP_GAME/PARAM.SFO"))
            except KeyError:
                sfo = {}
            cls = plugin.detect(iso, sfo)
            if cls is None:
                raise ValueError("no plugin for %s (%s)" % (sfo.get("DISC_ID"), sfo.get("TITLE")))
            Project.create(workdir, iso_path, cls.id, {"disc_id": sfo.get("DISC_ID"), "title": sfo.get("TITLE")})
        self.open(workdir)

    # --- texts -----------------------------------------------------------

    def text_summary(self):
        g = self.game
        out = []
        for i in g.text_entries():
            rows = g.load_texts(i)
            out.append({"entry": i, "name": g.entry_name(i) if hasattr(g, "entry_name") else None,
                        "total": len(rows), "done": sum(1 for r in rows if r.get("dst")),
                        "checked": sum(1 for r in rows if r.get("dst") and r.get("checked")),
                        "preview": next((r["src"] for r in rows if r["src"].strip()), "")[:40]})
        return out

    def check(self, text: str, utf8: bool = False) -> str:
        if utf8:
            n = len(text.encode("utf-8"))
            return "длиннее %d байт UTF-8" % UTF8_MAX_BYTES if n > UTF8_MAX_BYTES else ""
        try:
            self.game.target_charmap().encode(text)
            return ""
        except ValueError as e:
            return str(e)

    def save_texts(self, entry: int, changes: dict):
        with self.edit_lock:
            rows = self.game.load_texts(entry)
            for r in rows:
                if r["id"] in changes:
                    if r.get("dst") != changes[r["id"]]:
                        r.pop("checked", None)  # changed text needs a new look
                    r["dst"] = changes[r["id"]]
                    r.pop("mt", None)  # a person touched it
            self.game.save_texts(entry, rows)
        return {k: self.check(v) for k, v in changes.items() if v}

    @staticmethod
    def row_ok(r: dict, flt: dict) -> bool:
        """The UI's line filters (app.js rowOk): tr empty|done, src mt|manual, chk yes|no."""
        dst = bool(r.get("dst"))
        tr, src, chk = flt.get("tr"), flt.get("src"), flt.get("chk")
        return ((not tr or (not dst if tr == "empty" else dst))
                and (not src or (dst and bool(r.get("mt")) == (src == "mt")))
                and (not chk or (dst and bool(r.get("checked")) == (chk == "yes"))))

    def search(self, q: str, field: str, flt: dict, limit=500):
        g = self.game
        rx = re.compile(re.escape(q), re.I) if q else None
        hits = []
        for i in g.text_entries():
            for r in g.load_texts(i):
                if not self.row_ok(r, flt):
                    continue
                hay = r.get(field, "") if field != "any" else r["src"] + "\n" + r.get("ref", "") + "\n" + r.get("dst", "")
                if rx is None or rx.search(hay):
                    hits.append(dict(r, entry=i))
                    if len(hits) >= limit:
                        return hits
        return hits

    def set_checked(self, entry: int, ids, value: bool) -> int:
        """Mark lines as checked (only translated ones). ids=None: whole file."""
        n = 0
        with self.edit_lock:
            rows = self.game.load_texts(entry)
            for r in rows:
                if (ids is None or r["id"] in ids) and r.get("dst"):
                    if value:
                        r["checked"] = True
                    else:
                        r.pop("checked", None)
                    n += 1
            self.game.save_texts(entry, rows)
        return n

    def with_dups(self, rows):
        """Add `dups`: how many times the same source line is in the game."""
        if getattr(self, "_src_count", None) is None:
            from collections import Counter
            c = Counter()
            for i in self.game.text_entries():
                c.update(r["src"] for r in self.game.load_texts(i))
            self._src_count = c
        for r in rows:
            r["dups"] = self._src_count.get(r["src"], 1)
        self._add_limits(rows, range(len(rows)))
        return rows

    def propagate(self, src: str, dst: str):
        """Same source line elsewhere -> same translation, filled or not."""
        g = self.game
        n = 0
        with self.edit_lock:
            for i in g.text_entries():
                rows = g.load_texts(i)
                hit = False
                for r in rows:
                    if r["src"] == src and r.get("dst") != dst:
                        r["dst"] = dst
                        r.pop("mt", None)
                        r.pop("checked", None)
                        hit = True
                        n += 1
                if hit:
                    g.save_texts(i, rows)
        return n


    # --- LLM ---------------------------------------------------------------

    def glossary(self) -> str:
        try:
            with open(self.game.project.path("glossary.txt"), encoding="utf-8") as f:
                return f.read()
        except OSError:
            return ""

    def set_glossary(self, text: str):
        with open(self.game.project.path("glossary.txt"), "w", encoding="utf-8") as f:
            f.write(text)

    def _examples(self) -> llm.Examples:
        """Lines marked checked: the model follows them like a glossary."""
        g = self.game
        pairs, seen = [], set()
        for i in g.text_entries():
            for r in g.load_texts(i):
                if r.get("dst") and r.get("checked") and r["src"] not in seen:
                    seen.add(r["src"])
                    pairs.append((r["src"], r["dst"]))
        return llm.Examples(pairs)

    def llm_translate(self, log, entry=None, limit=0):
        """Untranslated strings -> LLM. Same source already translated
        somewhere -> reused for free. Results are marked mt (machine)."""
        g = self.game
        settings = llm.load_settings()
        encode = g.target_charmap().encode
        glossary = self.glossary()
        entries = [entry] if entry is not None else g.text_entries()
        examples = self._examples()
        if examples.pool:
            log("проверенных строк как образец: %d" % len(examples.pool))
        memory = {}
        for i in g.text_entries():
            for r in g.load_texts(i):
                if r.get("dst") and (r.get("checked") or r["src"] not in memory):
                    memory[r["src"]] = r["dst"]
        letters = re.compile(r"[^\s0-9{}.,!?・…ー\-]")  # some real text left after tags

        def wanted(r):
            return not r.get("dst") and letters.search(TAG_RX.sub("", r["src"]))
        planned = sum(1 for i in entries for r in g.load_texts(i) if wanted(r))
        if limit:
            planned = min(planned, limit)
        self.job.progress = [0, planned]
        total = 0
        for i in entries:
            with self.edit_lock:
                rows = g.load_texts(i)
            todo = []
            for k, r in enumerate(rows):
                if not wanted(r):
                    continue
                if r["src"] in memory:
                    r["dst"], r["mt"] = memory[r["src"]], True
                    self.job.progress[0] += 1
                    continue
                todo.append(k)
            if limit:
                todo = todo[:max(0, limit - total)]
            self._add_limits(rows, todo)
            step = int(settings.get("batch") or 30)
            for b in range(0, len(todo), step):
                part = todo[b:b + step]
                log("%04d: строки %d-%d из %d" % (i, b + 1, b + len(part), len(todo)))
                got = llm.translate([rows[k] for k in part], settings, encode, glossary,
                                    measure=getattr(g, "line_widths", None), log=log, examples=examples)
                for n, text in got.items():
                    rows[part[n]]["dst"], rows[part[n]]["mt"] = text, True
                    memory.setdefault(rows[part[n]]["src"], text)
                total += len(got)
                # lines that failed count as handled too: the bar should reach the end
                self.job.progress[0] = min(planned, self.job.progress[0] + len(part))
                self._merge_save(i, rows)
            self._merge_save(i, rows)
            if limit and total >= limit:
                break
        log("готово: переведено %d строк" % total)

    # --- HD textures: marks (to redo with another model) ---------------

    def hd_marks(self) -> set:
        try:
            with open(self.game.project.path("hd_marks.json")) as f:
                return set(json.load(f))
        except (OSError, ValueError):
            return set()

    def set_hd_marks(self, names, value: bool):
        m = self.hd_marks()
        m = m | set(names) if value else m - set(names)
        with open(self.game.project.path("hd_marks.json"), "w") as f:
            json.dump(sorted(m), f)

    # --- text on textures ----------------------------------------------

    def _layout_path(self, tid: str) -> str:
        return self.game.project.path("textures", "auto", os.path.basename(tid) + ".json")

    def tex_layout(self, tid: str) -> Optional[dict]:
        try:
            with open(self._layout_path(tid), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def _save_layout(self, tid: str, layout: dict):
        p = self._layout_path(tid)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(layout, f, ensure_ascii=False, indent=1)

    def _tex_image(self, tid: str, which: str):
        from PIL import Image
        import io
        return Image.open(io.BytesIO(self.game.texture_png(tid, which))).convert("RGBA")

    def tex_auto(self, tid: str, note: str = "", font: str = "pt-sans-bold") -> dict:
        """Find the Japanese text, guess its look, translate (LLM)."""
        jp = self._tex_image(tid, "jp")
        ref = []
        if self.game.project.meta.get("ref_iso"):
            try:
                ref = textfit.detect(self._tex_image(tid, "ref"), "en-US")
            except Exception:
                ref = []
        boxes = []
        for b in textfit.detect(jp, "ja-JP"):
            en = " ".join(e["text"] for e in ref if textfit.overlap(b, e) > 0.3)
            box = {k: b[k] for k in ("x", "y", "w", "h")}
            box.update(textfit.guess_style(jp, b), src=b["text"], ref=en, dst="",
                       on=textfit.has_japanese(b["text"]), size=None)
            boxes.append(box)
        layout = {"font": font, "note": note, "boxes": boxes}
        err = self._tex_translate(layout)
        self._save_layout(tid, layout)
        return dict(layout, error=err)

    def _tex_translate(self, layout: dict, only=None) -> str:
        todo = [k for k, b in enumerate(layout["boxes"]) if b.get("on") and (only is None or k in only)]
        if not todo:
            return ""
        rows = []
        for k in todo:
            b = layout["boxes"][k]
            # about how many letters fit: the box at its own height
            rows.append({"src": b["src"], "ref": b.get("ref", ""), "note": layout.get("note", ""), "ttf": True,
                         "max_chars": max(2, int(b["w"] / max(4, b["h"] * 0.55)))})
        try:
            got = llm.translate(rows, llm.load_settings(), lambda s: None, self.glossary(),
                                log=lambda *_: None, examples=self._examples())
        except llm.LLMError as e:
            return str(e)
        for n, text in got.items():
            layout["boxes"][todo[n]]["dst"] = text
        return "" if len(got) == len(todo) else "не все надписи переведены"

    def tex_render(self, tid: str, layout: dict, save: bool = False) -> bytes:
        img = textfit.render(self._tex_image(tid, "jp"), layout)
        import io
        buf = io.BytesIO()
        img.save(buf, "PNG")
        png = buf.getvalue()
        self._save_layout(tid, layout)
        if save:
            self.game.set_texture(tid, png)
        return png

    def llm_one(self, entry: int, rid: str) -> dict:
        """Translate one line now (no job): returns {dst} or {error}."""
        g = self.game
        rows = g.load_texts(entry)
        k = next(n for n, r in enumerate(rows) if r["id"] == rid)
        self._add_limits(rows, [k])
        notes = []
        examples = self._examples()
        try:
            got = llm.translate([rows[k]], llm.load_settings(), g.target_charmap().encode, self.glossary(),
                                measure=getattr(g, "line_widths", None), log=notes.append,
                                examples=examples)
        except llm.LLMError as e:
            return {"error": str(e)}
        if 0 not in got:
            return {"error": "; ".join(n.strip() for n in notes) or "не вышло"}
        with self.edit_lock:
            cur = g.load_texts(entry)
            for r in cur:
                if r["id"] == rid:
                    r["dst"], r["mt"] = got[0], True
                    r.pop("checked", None)
            g.save_texts(entry, cur)
        return {"dst": got[0], "examples": examples.pick([rows[k]])}

    def _add_limits(self, rows, todo):
        """Line width limit per string: the widest original line of its
        table (strings of one table share a window)."""
        g = self.game
        if not hasattr(g, "line_widths"):
            return
        table_max = {}
        own = {}
        for k, r in enumerate(rows):
            if r.get("utf8") or r.get("sub"):
                continue
            try:
                w = max(g.line_widths(r["src"], new=False))
            except ValueError:
                continue
            own[k] = w
            t = (r.get("entry"), r["id"].rsplit(":", 1)[0])
            table_max[t] = max(table_max.get(t, 0), w)
        avg = max(1, sum(g.line_widths("абвгдежзиклмнопрстуфхцчшэюя")) // 27)
        for k in todo:
            if rows[k].get("sub"):  # drawn with a TTF and wrapped: two lines of about 50
                rows[k]["max_chars"] = 100
                continue
            if rows[k].get("utf8"):
                # save dialog fields: title 128 bytes, keep a margin
                rows[k]["max_bytes"] = UTF8_MAX_BYTES
                continue
            lim = max(own.get(k, 0), table_max.get((rows[k].get("entry"), rows[k]["id"].rsplit(":", 1)[0]), 0))
            if lim:
                rows[k]["limit_px"] = lim
                rows[k]["max_chars"] = lim // avg

    def _merge_save(self, i, rows):
        """Save LLM results without clobbering edits made in the UI meanwhile."""
        with self.edit_lock:
            cur = self.game.load_texts(i)
            mine = {r["id"]: r for r in rows if r.get("mt")}
            for r in cur:
                m = mine.get(r["id"])
                if m and not r.get("dst"):
                    r["dst"], r["mt"] = m["dst"], True
                    r.pop("checked", None)
            for r in cur:
                r.pop("limit_px", None)
                r.pop("max_chars", None)
            self.game.save_texts(i, cur)


TAG_RX = re.compile(r"\[[#0-9a-fA-F]+\]")


class Handler(BaseHTTPRequestHandler):
    app: App = None

    def log_message(self, fmt, *args):
        # requests from other devices go to the terminal: who reached the server
        if not remote.is_local(self.client_address[0]):
            print("%s %s" % (self.client_address[0], fmt % args), flush=True)

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        self._route("GET")

    def do_POST(self):
        self._route("POST")

    def do_PUT(self):
        self._route("PUT")

    def do_DELETE(self):
        self._route("DELETE")

    def _raw(self) -> bytes:
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n)

    def _local(self) -> bool:
        return remote.is_local(self.client_address[0])

    def _token(self) -> str:
        for part in (self.headers.get("Cookie") or "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == remote.COOKIE:
                return v
        return ""

    def _login(self):
        tok = remote.login(remote.load(), (self._body().get("password") or ""))
        if not tok:
            time.sleep(1)  # slows down guessing
            return self._send(403, {"error": "Неверный пароль"})
        body = b'{"ok": true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Set-Cookie", "%s=%s; Max-Age=31536000; Path=/; HttpOnly; SameSite=Strict" % (remote.COOKIE, tok))
        self.end_headers()
        self.wfile.write(body)

    def _route(self, method):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        # other devices: the password first (login page and its style are open)
        if not self._local() and not remote.allowed(remote.load(), self._token()):
            if u.path == "/api/login" and method == "POST":
                return self._login()
            if u.path in ("/login.html", "/app.css", "/i18n.js", "/favicon.svg", "/favicon-32.png", "/apple-touch-icon.png") \
                    or re.fullmatch(r"/i18n/[\w-]+\.js", u.path):
                return self._static(u.path)
            if u.path.startswith("/api/"):
                return self._send(401, {"error": "login"})
            self.send_response(302)
            self.send_header("Location", "/login.html")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        try:
            if u.path in ("/api/pick", "/api/shutdown", "/api/remote", "/api/ocr", "/api/emulator") and method != "GET" and not self._local():
                raise PermissionError("только на этом компьютере")
            if not u.path.startswith("/api/"):
                return self._static(u.path)
            res = self._api(method, u.path[5:], q)
            if isinstance(res, tuple):
                return self._send(200, res[1], res[0])
            self._send(200, res)
        except KeyError as e:
            self._send(404, {"error": "not found: %s" % e})
        except Exception as e:
            self._send(400, {"error": "%s: %s" % (type(e).__name__, e)})

    def _static(self, path):
        name = "index.html" if path in ("/", "") else path.lstrip("/")
        full = os.path.normpath(os.path.join(STATIC, name))
        if not full.startswith(STATIC) or not os.path.isfile(full):
            return self._send(404, b"not found", "text/plain")
        with open(full, "rb") as f:
            self._send(200, f.read(), TYPES.get(os.path.splitext(full)[1], "application/octet-stream"))

    def _api(self, method, path, q):
        app = self.app
        g = app.game
        if path == "project":
            return dict(app.project_info(), client_remote=not self._local())
        if path == "ocr":
            if method == "PUT":
                b = self._body()
                st = ocr.load_settings()
                if b.get("engine") in ocr.ENGINES:
                    st["engine"] = b["engine"]
                if "tesseract" in b:
                    st["tesseract"] = b["tesseract"] or ""
                ocr.save_settings(st)
            return ocr.status()
        if path == "remote":
            if method == "PUT":
                b = self._body()
                cfg = remote.load()
                if b.get("password"):
                    if len(b["password"]) < 6:
                        raise ValueError("пароль: не короче 6 символов")
                    remote.set_password(cfg, b["password"])
                if "on" in b:
                    if b["on"] and not remote.has_password(cfg):
                        raise ValueError("сначала задайте пароль")
                    cfg["on"] = bool(b["on"])
                remote.save(cfg)
                if remote.host(cfg) != self.server.server_address[0]:
                    _rebind(self.server)  # after this answer: listen on the new address
            cfg = remote.load()
            port = self.server.server_address[1]
            return {"on": bool(cfg.get("on")), "has_password": remote.has_password(cfg),
                    "listening": self.server.server_address[0], "tailscale": remote.tailscale(),
                    "addresses": remote.addresses(port) if remote.host(cfg) != "127.0.0.1" else []}
        if path == "pick" and method == "POST":
            b = self._body()
            return {"path": picker.pick(b.get("kind", "open"), b.get("prompt", ""), b.get("start", ""), b.get("name", ""))}
        if path == "job/stop" and method == "POST":
            app.job.stop = True
            return app.job.state()
        if path == "job":
            return app.job.state(int(q.get("since", 0)))
        if path == "ping":
            return {"app": "psptool"}
        if method == "POST" and path == "shutdown":
            # a newer `psptool ui` takes over the port
            threading.Timer(0.2, self.server.shutdown).start()
            return {"ok": True}
        if method == "POST" and path == "open":
            app.open(self._body()["workdir"])
            return app.project_info()
        if method == "POST" and path == "init":
            b = self._body()
            app.init(b["iso"], b["workdir"])
            return app.project_info()
        if path == "llm/settings":
            if method == "PUT":
                cur = llm.load_settings()
                for k, v in self._body().items():
                    if isinstance(v, dict):
                        v = {a: b for a, b in v.items() if not (a == "api_key" and b.startswith("…"))}
                        v.pop("has_key", None)
                        cur.setdefault(k, {}).update(v)
                    else:
                        cur[k] = v
                llm.save_settings(cur)
            return llm.public_settings(llm.load_settings())
        if method == "POST" and path == "llm/test":
            try:
                out = llm.ask(llm.load_settings(), "Answer with one word.", 'Return JSON {"items": [{"n": 0, "text": "ok"}]}')
                return {"ok": True, "reply": out[:200]}
            except llm.LLMError as e:
                return {"ok": False, "reply": str(e)}
        # app settings: none of these need a project
        if path == "emulator":
            if method == "PUT":
                cfg = playtest.load()
                cfg["emulator"] = self._body().get("emulator", "")
                playtest.save(cfg)
            return {"emulator": playtest.find_emulator()}
        if path == "components":
            return {"tools": hdtex.tools(), "ffmpeg": ffmpeg.find() or "", "tesseract": ocr.tesseract_bin() or "",
                    "vision": ocr.vision_available()}
        if method == "POST" and path == "run/hdtool":
            tool = self._body()["tool"]

            def fetch(log):
                app.job.progress = [0, 0]
                hdtex.install(tool, log=log, progress=app.job.progress)
            app.job.start("hdtool", fetch)
            return app.job.state()

        if g is None:
            raise ValueError("no project open")

        if method == "POST" and path.startswith("run/"):
            return self._run(path[4:], self._body())

        if path == "texts":
            return app.text_summary()
        m = re.fullmatch(r"texts/(\d+)/checked", path)
        if m and method == "PUT":
            b = self._body()
            return {"count": app.set_checked(int(m.group(1)), b.get("ids"), bool(b.get("value", True)))}
        m = re.fullmatch(r"texts/(\d+)", path)
        if m:
            if method == "PUT":
                return {"errors": app.save_texts(int(m.group(1)), self._body())}
            return app.with_dups(g.load_texts(int(m.group(1))))
        if path == "search":
            return app.with_dups(app.search(q.get("q", ""), q.get("in", "any"), {k: q.get(k, "") for k in ("tr", "src", "chk")}))
        if method == "POST" and path == "propagate":
            b = self._body()
            return {"count": app.propagate(b["src"], b["dst"])}
        if method == "POST" and path == "llm/row":
            b = self._body()
            return app.llm_one(int(b["entry"]), b["id"])
        if method == "POST" and path == "check":
            b = self._body()
            return {"error": app.check(b["text"], bool(b.get("utf8")))}

        if path == "playtest":
            meta = g.project.meta
            if method == "PUT":
                b = self._body()
                if "emulator" in b:
                    cfg = playtest.load()
                    cfg["emulator"] = b["emulator"]
                    playtest.save(cfg)
                for k in ("state", "probe_slots"):
                    if k in b:
                        meta[k] = b[k]
                g.project.save_meta()
            sts = playtest.states(meta.get("disc_id") or "")
            return {"emulator": playtest.find_emulator(), "states": sts, "state": meta.get("state", ""),
                    "probe_slots": g.probe_slots() if hasattr(g, "probe_slots") else []}
        if path == "state.jpg":
            p = q.get("path", "")
            if p not in [x["path"] for x in playtest.states(g.project.meta.get("disc_id") or "")]:
                raise KeyError(p)
            with open(p[:-5] + ".jpg", "rb") as f:
                return ("image/jpeg", f.read())

        if path == "glossary":
            if method == "PUT":
                app.set_glossary(self._body().get("text", ""))
            return {"text": app.glossary()}

        if path == "textures":
            rows = g.texture_index()
            indexed = bool(rows)
            if q.get("q"):
                rows = [r for r in rows if r["id"].startswith(q["q"].zfill(4)) or q["q"] in r["id"]]
            # what each "Показать" choice would show (the filter menu's counts)
            show = {"ref": lambda r: r["ref"] or r["edited"], "edited": lambda r: r["edited"],
                    "todo": lambda r: r["ref"] and not r["edited"], "all": lambda r: True}
            counts = {k: sum(1 for r in rows if fn(r)) for k, fn in show.items()}
            rows = [r for r in rows if show.get(q.get("filter", "ref"), show["ref"])(r)]
            if q.get("sort") == "size":
                rows.sort(key=lambda r: (r["w"] * r["h"], r["id"]))
            if q.get("dir") == "desc":
                rows.reverse()
            off = int(q.get("offset", 0))
            return {"total": len(rows), "items": rows[off:off + int(q.get("limit", 300))],
                    "indexed": indexed, "counts": counts}
        m = re.fullmatch(r"texture/([0-9a-zA-Z_\-]+)\.png", path)
        if m:
            return ("image/png", g.texture_png(m.group(1), q.get("which", "jp"), int(q.get("scale", 1))))
        m = re.fullmatch(r"texture/([0-9a-zA-Z_\-]+)/auto", path)
        if m:
            if method == "POST":
                b = self._body()
                if b.get("retranslate"):  # keep boxes, translate the ones asked again
                    layout = b["layout"]
                    err = app._tex_translate(layout, set(b.get("only") or []) or None)
                    app._save_layout(m.group(1), layout)
                    return dict(layout, error=err)
                return app.tex_auto(m.group(1), b.get("note", ""), b.get("font") or "pt-sans-bold")
            return {"layout": app.tex_layout(m.group(1)), "fonts": textfit.fonts()}
        m = re.fullmatch(r"texture/([0-9a-zA-Z_\-]+)/render\.png", path)
        if m and method == "POST":
            b = self._body()
            return ("image/png", app.tex_render(m.group(1), b["layout"], bool(b.get("save"))))
        m = re.fullmatch(r"texture/([0-9a-zA-Z_\-]+)", path)
        if m and method == "PUT":
            g.set_texture(m.group(1), self._raw())
            return {"ok": True}
        if m and method == "DELETE":
            g.set_texture(m.group(1), None)
            return {"ok": True}

        if path == "charmap":
            if method == "PUT":
                g.set_chars({int(k): v for k, v in self._body().items()})
                return {"ok": True}
            return g.charmap_rows()
        if path.startswith("hd"):
            hdtex.set_archive_dir(g.project.meta.get("disc_id") or "", g.project.path("hd_src"))
        if path == "hd":
            disc = g.project.meta.get("disc_id") or ""
            if method == "PUT":
                hdtex.set_saving(disc, bool(self._body().get("saving")))
            st = hdtex.status(disc)
            st["samples"] = hdtex.samples(disc)
            st["models"] = hdtex.models()
            st["hd"] = g.project.meta.get("hd", {"scale": 3, "model": hdtex.DEFAULT_MODEL})
            return st
        if path == "movies":
            if method == "PUT":
                g.set_movie_enhance(self._body())
            return g.movie_status()
        if path == "movies/frame.png":
            return ("image/png", g.movie_frame(int(q["n"]), int(q.get("frame", 0)),
                                               q.get("mode") or g.movie_enhance_settings()["mode"], q.get("which", "enh")))
        if path == "hd/pick":  # what an upscale run with these choices would take
            sz = [x for x in q.get("sizes", "").split(",") if x]
            md = [x for x in q.get("models", "").split(",") if x]
            r = hdtex.pick(g.project.meta.get("disc_id") or "", sz, md, q.get("redo") == "1")
            return {"count": len(r["names"]), "sizes": r["sizes"], "models": r["models"]}
        if path == "hd/gallery":
            marks = app.hd_marks()
            return hdtex.gallery(g.project.meta.get("disc_id") or "", int(q.get("offset", 0)),
                                 int(q.get("limit", 60)), q.get("q", ""), q.get("size", ""),
                                 marks if q.get("marked") == "1" else None, q.get("model", ""), marks,
                                 sort=q.get("sort", "size"), desc=q.get("dir", "desc") == "desc")
        if path == "hd/marks":
            b = self._body() if method != "GET" else {}
            if method == "PUT":  # these names
                app.set_hd_marks(b.get("names") or [], bool(b.get("value", True)))
            elif method == "POST":  # everything the gallery filter shows
                f = b.get("filter") or {}
                marks = app.hd_marks()
                res = hdtex.gallery(g.project.meta.get("disc_id") or "", 0, 0, f.get("q", ""), f.get("size", ""),
                                    marks if f.get("marked") else None, f.get("model", ""), marks, want_all=True)
                app.set_hd_marks(res["all"], bool(b.get("value", True)))
            return {"count": len(app.hd_marks())}
        if path == "hd/thumb":
            return ("image/png", hdtex.thumb(g.project.meta.get("disc_id") or "", os.path.basename(q["name"]),
                                             q.get("which", "hd"), g.project.path("hd_thumbs")))
        if path == "hd/img":
            name = os.path.basename(q["name"])
            d = hdtex.tex_dir(g.project.meta.get("disc_id") or "")
            disc = g.project.meta.get("disc_id") or ""
            with open(hdtex.original(disc, name) if q.get("which") == "orig" else os.path.join(d, name), "rb") as f:
                return ("image/png", f.read())
        if path == "subframe.png":
            return ("image/png", g.movie_preview(int(q["entry"]), q["id"], q.get("text", "")))
        if path == "render.png":
            return ("image/png", g.render_png(q.get("text", "")))
        m = re.fullmatch(r"glyph/([0-9a-fA-F]+)\.png", path)
        if m:
            return ("image/png", g.glyph_png(int(m.group(1), 16), new=q.get("new") == "1"))
        raise KeyError(path)

    def _run(self, what, b):
        app, g = self.app, self.app.game
        if what == "unpack":
            def fn(log):
                with IsoImage(g.project.iso_path) as iso:
                    g.unpack(iso, log=log)
        elif what == "texts":
            def fn(log):
                with IsoImage(g.project.iso_path) as iso:
                    g.extract_texts(iso, log=log)
                app._src_count = None
        elif what == "ref":
            def fn(log):
                g.import_ref(b["iso"], log=log)
        elif what == "subs":
            def fn(log):
                g.import_movie_lines(log=log)
        elif what == "llm":
            def fn(log):
                app.llm_translate(log, entry=b.get("entry"), limit=int(b.get("limit") or 0))
        elif what == "textures":
            def fn(log):
                g.build_texture_index(log=log)
        elif what == "eboot":
            def fn(log):
                g.import_eboot(b["path"], log=log)
        elif what == "font":
            def fn(log):
                st = g.font_settings()
                st.update({k: v for k, v in b.items() if k in ("ttf", "index", "px", "chars", "redraw_ascii", "tracking")})
                g.build_font(st, log=log)
        elif what == "playtest":
            def fn(log):
                out = g.project.path("test.iso")
                kw = {"probe": b["probe"]} if b.get("probe") is not None else {}
                g.pack(out, log=lambda m: None if m.startswith(("cfc ", "copy ")) else log(m), **kw)
                playtest.launch(out, g.project.meta.get("state", ""), log=log)
        elif what == "pack":
            def fn(log):
                g.pack(b["out"], log=log)
        elif what == "hd":
            hdtex.set_archive_dir(g.project.meta.get("disc_id") or "", g.project.path("hd_src"))
            model = b.get("model") or hdtex.DEFAULT_MODEL
            g.project.meta["hd"] = {"scale": int(b.get("scale") or 3), "model": model}
            g.project.save_meta()

            def fn(log):
                app.job.progress = [0, 0]
                names = sorted(app.hd_marks()) if b.get("marked") else b.get("names")
                if names is None and (b.get("sizes") or b.get("models")):  # from the run dialog
                    names = hdtex.pick(g.project.meta["disc_id"], b.get("sizes") or [], b.get("models") or [],
                                       bool(b.get("redo")))["names"]
                try:
                    hdtex.upscale(g.project.meta["disc_id"], int(b.get("scale") or 3), model,
                                  redo=bool(b.get("redo")), log=log, progress=app.job.progress,
                                  stop=lambda: app.job.stop, names=names)
                except hdtex.Stopped:
                    pass
        elif what == "hdtool":
            def fn(log):
                app.job.progress = [0, 0]
                hdtex.install(b["tool"], log=log, progress=app.job.progress)
        elif what == "hdarchive":
            model = b.get("model") or hdtex.DEFAULT_MODEL
            scale = int(b.get("scale") or 3)
            g.project.meta["hd"] = {"scale": scale, "model": model}
            g.project.save_meta()
            disc = g.project.meta["disc_id"]
            hdtex.set_archive_dir(disc, g.project.path("hd_src"))

            def fn(log):
                app.job.progress = [0, 0]
                stop = lambda: app.job.stop
                g.hd_archive(g.project.path("hd_src"), log=log, progress=app.job.progress, stop=stop)
                if stop():
                    return
                try:
                    hdtex.upscale(disc, scale, model, log=log, progress=app.job.progress, stop=stop)
                except hdtex.Stopped:
                    pass
        elif what == "movies":
            mode = b.get("mode") or g.movie_enhance_settings()["mode"]

            def fn(log):
                app.job.progress = [0, 0]
                g.enhance_movies(mode, log=log, progress=app.job.progress, stop=lambda: app.job.stop)
        elif what == "hdzip":
            hdtex.set_archive_dir(g.project.meta.get("disc_id") or "", g.project.path("hd_src"))

            def fn(log):
                out = g.project.path("%s_hd_textures.zip" % g.project.meta["disc_id"])
                n = hdtex.make_zip(g.project.meta["disc_id"], out)
                log("%d textures -> %s" % (n, out))
        else:
            raise KeyError(what)
        app.job.start(what, fn)
        return app.job.state()


def _stop_old(url: str) -> bool:
    """Ask a running psptool UI on this port to quit. True if it agreed."""
    import urllib.request
    try:
        with urllib.request.urlopen(url + "api/ping", timeout=2) as r:
            if json.loads(r.read()).get("app") != "psptool":
                return False
    except Exception:
        return False
    req = urllib.request.Request(url + "api/shutdown", data=b"{}", method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=2).read()
    except Exception:
        pass  # it may go away before answering
    print("stopped the running psptool ui, starting a new one")
    return True


class DualStackServer(ThreadingHTTPServer):
    """IPv6 socket that also takes IPv4 (mapped addresses)."""
    address_family = socket.AF_INET6

    def server_bind(self):
        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        super().server_bind()


def make_server(host: str, port: int) -> ThreadingHTTPServer:
    return (DualStackServer if ":" in host else ThreadingHTTPServer)((host, port), Handler)


_REBIND = []


def _rebind(srv):
    """Stop serving and start again on the address remote.json asks for."""
    _REBIND.append(True)
    threading.Timer(0.3, srv.shutdown).start()


def serve(workdir: Optional[str] = None, port: int = 8765, open_browser: bool = True,
          ready: Optional[threading.Event] = None):
    """ready: set once the server answers (the desktop app waits for it)."""
    url = "http://127.0.0.1:%d/" % port
    srv = None
    for attempt in range(20):
        try:
            srv = make_server(remote.host(remote.load()), port)
            break
        except OSError:
            if attempt == 0 and not _stop_old(url):
                print("port %d is busy (not psptool?), try --port 8766" % port)
                return
            time.sleep(0.25)
    if srv is None:
        print("port %d is still busy" % port)
        return
    Handler.app = App(workdir)
    print("psptool ui: " + url)
    if ready:
        ready.set()
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    while True:
        if srv.server_address[0] != "127.0.0.1":
            print("open to other devices (password)")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            break
        srv.server_close()
        if not _REBIND:
            break
        _REBIND.clear()
        for _ in range(40):  # the old socket may take a moment to let go
            try:
                srv = make_server(remote.host(remote.load()), port)
                break
            except OSError:
                time.sleep(0.25)
        else:
            print("could not listen again on port %d" % port)
            break
