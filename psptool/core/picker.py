"""Native file dialogs for the web UI. A browser never tells the page the
full path of a chosen file, so the (local) server opens the dialog itself:
the desktop app's window, else AppleScript on macOS, tkinter elsewhere. Returns "" when cancelled."""
import os
import subprocess
import sys


def _as_str(s: str) -> str:
    return '"%s"' % s.replace("\\", "\\\\").replace('"', '\\"')


# the desktop app's own dialogs (psptool/app.py): fn(kind, prompt, start, name)
BACKEND = None


def pick(kind: str = "open", prompt: str = "", start: str = "", name: str = "") -> str:
    """kind: open (a file), folder, save (a new file name)."""
    start = os.path.expanduser(start or "")
    if start and not os.path.isdir(start):
        start = os.path.dirname(start)
    if BACKEND:
        return _app_binary(BACKEND(kind, prompt, start, name) or "")
    if sys.platform == "darwin":
        return _mac(kind, prompt, start, name)
    return _tk(kind, prompt, start, name)


def _mac(kind, prompt, start, name) -> str:
    opts = ""
    if prompt:
        opts += " with prompt " + _as_str(prompt)
    if start and os.path.isdir(start):
        opts += " default location (POSIX file %s)" % _as_str(start)
    if kind == "folder":
        cmd = "choose folder" + opts
    elif kind == "save":
        cmd = "choose file name" + opts + (" default name " + _as_str(name) if name else "")
    else:
        cmd = "choose file" + opts
    # System Events brings the dialog to the front, over the browser
    script = ['tell application "System Events"', "activate", "set f to " + cmd, "end tell", "POSIX path of f"]
    args = ["osascript"]
    for line in script:
        args += ["-e", line]
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:  # cancelled (-128) or no permission
        if "-128" in r.stderr or "canceled" in r.stderr.lower():
            return ""
        raise RuntimeError(r.stderr.strip() or "file dialog failed")
    return _app_binary(r.stdout.strip())


def _app_binary(p: str) -> str:
    """An .app bundle picked as a file -> its executable."""
    if p.rstrip("/").endswith(".app"):
        d = os.path.join(p, "Contents", "MacOS")
        names = sorted(os.listdir(d)) if os.path.isdir(d) else []
        base = os.path.basename(p.rstrip("/"))[:-4]
        if base in names:
            return os.path.join(d, base)
        if names:
            return os.path.join(d, names[0])
    return p


def _tk(kind, prompt, start, name) -> str:
    import tkinter
    from tkinter import filedialog
    root = tkinter.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        if kind == "folder":
            p = filedialog.askdirectory(title=prompt, initialdir=start or None)
        elif kind == "save":
            p = filedialog.asksaveasfilename(title=prompt, initialdir=start or None, initialfile=name)
        else:
            p = filedialog.askopenfilename(title=prompt, initialdir=start or None)
    finally:
        root.destroy()
    return p or ""
