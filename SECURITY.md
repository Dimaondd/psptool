# Security

## Reporting a problem

Please report vulnerabilities privately through GitHub: the repository's
**Security → Report a vulnerability** form. Do not open a public issue.

## How PSPtool protects you

PSPtool runs a small web server on your computer; the app window and your
browser talk to it.

- **Only this computer, by default.** The server listens on `127.0.0.1`.
  Requests from this computer need no password.
- **Web pages cannot drive it.** A request that comes from another site
  (its `Origin`) or names another host (`Host`, DNS rebinding) is refused,
  so a page you visit cannot start jobs, change settings or read your
  project through the local server.
- **Other devices need a password** (Settings → Access from other devices,
  off by default; at least 8 characters, stored as a PBKDF2 hash). After 8
  wrong tries an address waits 10 minutes. Settings that change what runs on
  this computer (the emulator, OCR, the file dialog, remote access itself)
  can only be changed on this computer.
- **Prefer Tailscale for the phone.** Its connection is encrypted. On a
  plain Wi-Fi network the password and pages travel unencrypted (HTTP).
- **Keys stay local.** API keys live in `~/.config/psptool/` (mode 0600)
  and are never sent back to the interface in full.
- **Downloads are checked.** The AI upscalers are fetched from their own
  GitHub releases and installed only if their SHA-256 matches the one
  pinned in `psptool/core/hdtex.py`.
- **Release builds** use pinned GitHub Actions (by commit) and pinned
  Python packages.

The release apps are not signed by Apple or Microsoft; your system will warn
about an unknown developer on first start.
