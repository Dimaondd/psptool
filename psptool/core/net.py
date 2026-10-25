"""HTTPS for the app's own requests (updates, upscaler downloads, LLM).

A frozen app's Python looks for CA certificates where the build machine kept
them, so on another Mac it finds none and every HTTPS request fails. The
context trusts the system's certificates and certifi's (bundled with the app),
and the macOS system file when neither is there.
"""
import os
import ssl
import urllib.request

_CTX = None


def context() -> ssl.SSLContext:
    global _CTX
    if _CTX is None:
        ctx = ssl.create_default_context()
        try:
            import certifi
            ctx.load_verify_locations(certifi.where())
        except (ImportError, OSError):
            if os.path.exists("/etc/ssl/cert.pem"):
                ctx.load_verify_locations("/etc/ssl/cert.pem")
        _CTX = ctx
    return _CTX


def urlopen(req, timeout=60):
    return urllib.request.urlopen(req, timeout=timeout, context=context())
