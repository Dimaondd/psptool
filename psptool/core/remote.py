"""Access to the UI from other devices (phone over Tailscale, the home
network): off by default; on, the server listens on every address and
asks other devices for a password. Requests from this computer never
need it."""
import hashlib
import hmac
import json
import os
import secrets
import shutil
import socket
import subprocess
from typing import Dict, List, Optional

PATH = os.path.join(os.path.expanduser("~"), ".config", "psptool", "remote.json")
COOKIE = "psptool_key"
TAILSCALE_APP = "/Applications/Tailscale.app/Contents/MacOS/Tailscale"
TAILSCALE_WIN = r"C:\Program Files\Tailscale\tailscale.exe"


def load() -> Dict:
    try:
        with open(PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save(cfg: Dict):
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    tmp = PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=1)
    os.chmod(tmp, 0o600)
    os.replace(tmp, PATH)


def _hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 200_000).hex()


def set_password(cfg: Dict, password: str):
    """A new password also signs every device out."""
    cfg["salt"] = secrets.token_hex(16)
    cfg["hash"] = _hash(password, cfg["salt"])
    cfg["tokens"] = []


def has_password(cfg: Dict) -> bool:
    return bool(cfg.get("hash"))


def login(cfg: Dict, password: str) -> Optional[str]:
    """A token for the cookie, or None."""
    if not has_password(cfg) or not hmac.compare_digest(_hash(password, cfg["salt"]), cfg["hash"]):
        return None
    tok = secrets.token_urlsafe(32)
    cfg["tokens"] = (cfg.get("tokens") or [])[-49:] + [tok]
    save(cfg)
    return tok


def allowed(cfg: Dict, token: str) -> bool:
    return bool(token) and any(hmac.compare_digest(token, t) for t in cfg.get("tokens") or [])


def is_local(addr: str) -> bool:
    """The address a request came from is this computer (IPv4, IPv6, or IPv4 mapped into IPv6)."""
    return addr in ("127.0.0.1", "::1", "::ffff:127.0.0.1")


def host(cfg: Dict) -> str:
    """Open: every address, IPv6 and IPv4 ("::", dual-stack: Tailscale's
    names resolve to both); closed: this computer only."""
    return "::" if cfg.get("on") and has_password(cfg) else "127.0.0.1"


def _tailscale_cli() -> Optional[str]:
    return shutil.which("tailscale") or next((p for p in (TAILSCALE_APP, TAILSCALE_WIN) if os.path.exists(p)), None)


def tailscale() -> Dict:
    """{"installed", "running", "ip", "name"} of this computer in the tailnet."""
    cli = _tailscale_cli()
    if not cli:
        return {"installed": False}
    try:
        out = subprocess.run([cli, "status", "--json"], capture_output=True, text=True, timeout=5).stdout
        st = json.loads(out or "{}")
    except (OSError, subprocess.SubprocessError, ValueError):
        return {"installed": True, "running": False}
    me = st.get("Self") or {}
    ips = [ip for ip in me.get("TailscaleIPs") or [] if "." in ip]
    return {"installed": True, "running": st.get("BackendState") == "Running",
            "ip": ips[0] if ips else "", "name": (me.get("DNSName") or "").rstrip(".")}


def lan_ip() -> str:
    """The address other devices in the home network reach this one by."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.168.0.1", 9))  # no packet is sent: only picks the route
        return s.getsockname()[0]
    except OSError:
        return ""
    finally:
        s.close()


def addresses(port: int) -> List[Dict]:
    out = []
    ts = tailscale()
    if ts.get("running"):
        if ts.get("name"):
            out.append({"kind": "tailscale", "url": "http://%s:%d/" % (ts["name"], port)})
        if ts.get("ip"):
            out.append({"kind": "tailscale", "url": "http://%s:%d/" % (ts["ip"], port)})
    ip = lan_ip()
    if ip and not ip.startswith("100."):
        out.append({"kind": "lan", "url": "http://%s:%d/" % (ip, port)})
    return out
