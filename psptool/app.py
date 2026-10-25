"""PSPtool as a desktop app: the web UI in its own window (pywebview),
the server in a thread. Closing the window quits."""
import os
import sys
import threading

PORT = int(os.environ.get("PSPTOOL_PORT", "8765"))


def _quiet_children():
    """Windows: a windowed app's ffmpeg / tesseract / upscaler calls would
    each flash a console window."""
    import subprocess
    if sys.platform != "win32":
        return
    base = subprocess.Popen

    class Popen(base):
        def __init__(self, *a, **k):
            k.setdefault("creationflags", subprocess.CREATE_NO_WINDOW)
            super().__init__(*a, **k)
    subprocess.Popen = Popen


def _dialog(window):
    import webview

    def pick(kind, prompt, start, name):
        if kind == "folder":
            r = window.create_file_dialog(webview.FileDialog.FOLDER, directory=start or "")
        elif kind == "save":
            r = window.create_file_dialog(webview.FileDialog.SAVE, directory=start or "", save_filename=name or "")
        else:
            r = window.create_file_dialog(webview.FileDialog.OPEN, directory=start or "")
        if not r:
            return ""
        return r if isinstance(r, str) else r[0]
    return pick


def selftest() -> int:
    """What a release build carries: printed, 1 if something is missing."""
    from .core import ffmpeg, fonts, native, net, ocr, updates, xxh
    from .plugins.racjin import lz
    import urllib.error
    try:  # certificates: a frozen Python may not find any (0.3.0 on macOS)
        with net.urlopen("https://api.github.com/", timeout=20):
            https = True
    except urllib.error.HTTPError:
        https = True   # an answer (a shared CI address is often rate limited): TLS worked
    except Exception as e:
        https = False
        print("https:", e)
    ok = True
    for name, good, info in [
        ("ffmpeg", bool(ffmpeg.find()), ffmpeg.find()),
        ("xxh (C)", bool(xxh._lib()), xxh.xxh64(b"psptool")),
        ("racjin lz (C)", bool(lz._load_c()), native.PREBUILT),
        ("font PT Sans Bold", fonts.exists(fonts.PTSANS, 7), fonts.resolve(fonts.PTSANS, 7)[0]),
        ("ocr", True, ocr.engine() or "none"),
        ("https", https, "api.github.com"),
        ("self-update", True, updates.installable() or "can replace itself"),
    ]:
        print("%-18s %s  %s" % (name, "ok" if good else "MISSING", info))
        ok = ok and good
    return 0 if ok else 1


def main():
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    _quiet_children()
    import webview
    from .core import picker
    from .ui import server

    workdir = sys.argv[1] if len(sys.argv) > 1 and os.path.isdir(sys.argv[1]) else None
    ready = threading.Event()
    threading.Thread(target=server.serve, kwargs={"workdir": workdir, "port": PORT, "open_browser": False,
                                                 "ready": ready}, daemon=True).start()
    if not ready.wait(15):
        sys.exit("psptool: the server did not start (port %d busy?)" % PORT)
    webview.settings["ALLOW_DOWNLOADS"] = True
    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
    window = webview.create_window("PSPtool", "http://127.0.0.1:%d/" % PORT, width=1400, height=900,
                                   min_size=(900, 600), background_color="#171719")
    picker.BACKEND = _dialog(window)
    webview.start()


if __name__ == "__main__":
    main()
