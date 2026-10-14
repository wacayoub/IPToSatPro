# -*- coding: utf-8 -*-
"""VuLink v0.1: short-lived, LAN-only, read-only Enigma2 diagnostic pairing.

No cloud upload, remote execution, IPTV URLs, credentials, raw logs, or shell.
Everything is disabled when the Enigma2 screen closes.
"""
import datetime
import html
import ipaddress
import json
import os
import platform
import re
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

VERSION = "0.1.0"
TTL_SECONDS = 600
PLUGIN_ROOT = Path("/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge")
LOG_FILE = Path("/etc/enigma2/SatIPTVBridge/bridge.log")
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_EVENT_ALLOWLIST = frozenset((
    "PREVIEW_RANK_BG", "MATCH_BG_START", "MATCH_BG_DONE", "NO_MATCH",
    "IPTV_OK", "IPTV_FAIL", "MATCH_NEGATIVE_CACHE", "IPTV_BLACK",
    "PREVIEW_INSTANT_SEED", "PREVIEW_FAST_READY", "PLAYER_ERROR",
))
_METRIC_KEYS = frozenset(("elapsed", "latency", "candidate_count", "scored", "index", "scoring"))


def detect_lan_ipv4():
    """Detect LAN interface without sending any UDP packets."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("1.1.1.1", 80))
        ip = sock.getsockname()[0]
    except OSError:
        ip = ""
    finally:
        sock.close()
    if not ip:
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except OSError:
            pass
    try:
        addr = ipaddress.IPv4Address(ip)
        if addr.is_private and not addr.is_loopback and not addr.is_link_local:
            return ip
    except (ipaddress.AddressValueError, TypeError):
        pass
    raise OSError("Aucune adresse LAN privee detectee. Verifiez le reseau du Vu+.")


def _read_text(path, limit=256):
    try:
        return Path(path).read_bytes()[:limit].decode("utf-8", "replace").strip()
    except (OSError, ValueError):
        return ""


def _plugin_version():
    content = _read_text(PLUGIN_ROOT / "plugin.py", 300000)
    match = re.search(r"""(?m)^\s*PLUGIN_VERSION\s*=\s*['"]([^'"]+)['"]""", content)
    return match.group(1)[:90] if match else "unknown"


def _safe_event_metrics():
    """Parse numerical aggregates ONLY. Never include source or channel names."""
    counts = Counter()
    values = {"elapsed_ms": [], "latency_ms": [], "scored_count": []}
    try:
        with LOG_FILE.open("rb") as stream:
            stream.seek(0, os.SEEK_END)
            size = stream.tell()
            stream.seek(max(0, size - 262144))
            raw = stream.read(262144).decode("utf-8", "replace")
    except OSError:
        return {"available": False, "events": {}, "metrics": {}}
    for line in raw.splitlines()[-1200:]:
        found = re.search(r"\|\s*([A-Z][A-Z0-9_]{2,35})\s*\|", line)
        if not found or found.group(1) not in _EVENT_ALLOWLIST:
            continue
        name = found.group(1)
        counts[name] += 1
        for key, val in re.findall(r"\b(elapsed|latency|scored)=(\d{1,8})(?:ms)?\b", line):
            metric = "scored_count" if key == "scored" else key + "_ms"
            if len(values[metric]) < 1200:
                values[metric].append(int(val))
    aggregates = {}
    for key, data in values.items():
        if data:
            ordered = sorted(data)
            aggregates[key] = {"samples": len(ordered),
                               "median": ordered[len(ordered) // 2],
                               "p95": ordered[min(len(ordered) - 1, (95 * len(ordered) + 99) // 100 - 1)],
                               "max": ordered[-1]}
    return {"available": True, "events": dict(sorted(counts.items())), "metrics": aggregates}


def collect_report():
    """Strictly scoped, privacy-limited static report; does not mutate anything."""
    model = _read_text("/proc/stb/info/model", 80) or _read_text("/proc/stb/info/boxtype", 80)
    uptime = _read_text("/proc/uptime", 64).split(" ")[0]
    memory_line = next((x for x in _read_text("/proc/meminfo", 4096).splitlines()
                        if x.startswith("MemAvailable:")), "")
    def module_info(name):
        path = PLUGIN_ROOT / name
        try:
            st = path.stat()
            return {"present": True, "bytes": st.st_size}
        except OSError:
            return {"present": False}
    return {
        "schema": "vulink-diagnostic-v1",
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "receiver": {
            "model": model[:50] or "unknown",
            "python": platform.python_version(),
            "kernel": platform.release()[:100],
            "uptime_seconds": int(float(uptime)) if re.fullmatch(r"\d+(?:\.\d+)?", uptime) else None,
            "mem_available_kb": int(re.search(r"\d+", memory_line).group())
                if re.search(r"\d+", memory_line) else None,
        },
        "iptosatpro": {
            "installed": PLUGIN_ROOT.is_dir(),
            "version": _plugin_version(),
            "files": {name: module_info(name) for name in
                      ("plugin.py", "core.py", "player.py", "updater.py",
                       "preview_theme_r74.py", "home_themes_r767.py")}
        },
        "diagnostics": _safe_event_metrics(),
        "privacy": "No IPTV URLs, log lines, credentials, device IDs, public IP, mapping values or MAC addresses collected.",
    }


class PairingServer:
    """Ephemeral HTTP server reachable only through the receiver's private LAN IP."""

    def __init__(self, ip=None, lifetime=TTL_SECONDS):
        self.ip = ip if ip is not None else detect_lan_ipv4()
        if not ipaddress.IPv4Address(self.ip).is_private or ipaddress.IPv4Address(self.ip).is_loopback:
            raise ValueError("VuLink refuses a public/loopback listener")
        self.code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(12))
        self.deadline = time.monotonic() + max(30, min(int(lifetime), TTL_SECONDS))
        self._attempts = {}
        self._lock = threading.Lock()
        self.server = None
        self.thread = None

    def _allowed(self, code, remote):
        if time.monotonic() >= self.deadline:
            return False
        if not isinstance(code, str):
            return False
        # Failed attempts are limited by client IP, including on private LAN.
        with self._lock:
            start, n = self._attempts.get(remote, (time.monotonic(), 0))
            if time.monotonic() - start > 60:
                start, n = time.monotonic(), 0
            if n >= 8:
                return False
            ok = secrets.compare_digest(code.replace("-", "").upper(), self.code)
            if not ok:
                self._attempts[remote] = (start, n + 1)
        return ok

    def start(self):
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"

            def log_message(self, *_args):
                return  # no bearer-code URLs in persistent logs

            def _send(self, status, body, mimetype="text/html; charset=utf-8", attachment=None):
                content = body.encode("utf-8") if isinstance(body, str) else body
                self.send_response(status)
                self.send_header("Content-Type", mimetype)
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "no-store, max-age=0")
                self.send_header("Pragma", "no-cache")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Frame-Options", "DENY")
                self.send_header("Content-Security-Policy",
                                 "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'")
                if attachment:
                    self.send_header("Content-Disposition", 'attachment; filename="' + attachment + '"')
                self.end_headers()
                try:
                    self.wfile.write(content)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def _page(self, title, inner):
                return ('<!doctype html><html lang="fr"><meta charset="utf-8">'
                        '<meta name="viewport" content="width=device-width, initial-scale=1">'
                        '<title>' + html.escape(title) + '</title>'
                        '<style>body{font:17px sans-serif;background:#101923;color:#f3f6f9;'
                        'max-width:650px;margin:6vh auto;padding:22px}'
                        'a,button{display:inline-block;background:#188b78;color:white;'
                        'border:0;border-radius:8px;padding:14px;margin:8px 3px;text-decoration:none}'
                        'input{font-size:20px;padding:14px;max-width:94%;border-radius:8px}'
                        'p{line-height:1.55}</style><main><h2>' + html.escape(title) +
                        '</h2>' + inner + '</main></html>')

            def do_GET(self):
                if len(self.path) > 256:
                    return self._send(414, "Invalid path", "text/plain; charset=utf-8")
                parts = urlsplit(self.path)
                if time.monotonic() >= owner.deadline:
                    return self._send(410, self._page("Session expiree", "<p>Fermez et rouvrez VuLink sur la TV.</p>"))
                if parts.path == "/":
                    provided = parse_qs(parts.query).get("code", [""])[0]
                    if provided:
                        if owner._allowed(provided, self.client_address[0]):
                            self.send_response(302)
                            self.send_header("Location", "/p/" + owner.code)
                            self.send_header("Cache-Control", "no-store")
                            self.end_headers()
                            return
                        return self._send(403, self._page("Code incorrect", "<p>Reessayez sur la TV.</p>"))
                    return self._send(200, self._page(
                        "VuLink - Appairage local",
                        '<p>Le telephone et le Vu+ doivent etre sur le meme Wi-Fi/LAN.</p>'
                        '<form action="/" method="get"><input name="code" maxlength="16"'
                        ' autocomplete="off" placeholder="Code affiche sur la TV" required>'
                        '<button type="submit">Connecter</button></form>'))
                if parts.path.startswith("/p/"):
                    code = parts.path[3:]
                    if not owner._allowed(code, self.client_address[0]):
                        return self._send(403, "Acces refuse", "text/plain; charset=utf-8")
                    link = "/report/" + owner.code + ".json"
                    return self._send(200, self._page(
                        "VuLink - Diagnostic",
                        '<p>Connexion locale active pour quelques minutes.</p>'
                        '<p>Le rapport contient uniquement les versions, '
                        'comptages et temps de diagnostic, jamais les identifiants IPTV.</p>'
                        '<a href="' + link + '">Telecharger le rapport JSON</a>'
                        '<p>Ensuite ajoutez ce fichier dans votre conversation ChatGPT.</p>'
                        '<a href="https://chatgpt.com/">Ouvrir ChatGPT</a>'))
                if parts.path.startswith("/report/") and parts.path.endswith(".json"):
                    code = parts.path[len("/report/"):-len(".json")]
                    if not owner._allowed(code, self.client_address[0]):
                        return self._send(403, "Acces refuse", "text/plain; charset=utf-8")
                    payload = json.dumps(collect_report(), ensure_ascii=False, indent=2)
                    return self._send(200, payload, "application/json; charset=utf-8",
                                      "vulink-diagnostic.json")
                self._send(404, "Not found", "text/plain; charset=utf-8")

        class LocalHTTP(ThreadingHTTPServer):
            daemon_threads = True
            allow_reuse_address = False

        self.server = LocalHTTP((self.ip, 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       name="VuLinkLocalPair", daemon=True)
        self.thread.start()
        return self.url

    @property
    def url(self):
        if not self.server:
            return ""
        return "http://%s:%d/p/%s" % (self.ip, self.server.server_port, self.code)

    @property
    def base_url(self):
        if not self.server:
            return ""
        return "http://%s:%d/" % (self.ip, self.server.server_port)

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        self.thread = None


def create_qr_image(url, filepath):
    """Generate QR locally if a compatible renderer is available; never phone home."""
    # QR is optional: the displayed local URL + one-time code always works.
    try:
        import qrcode
        qr = qrcode.QRCode(border=3, box_size=6)
        qr.add_data(url)
        qr.make(fit=True)
        qr.make_image(fill_color="black", back_color="white").save(filepath)
        return True
    except (ImportError, OSError, ValueError, AttributeError):
        pass
    if shutil.which("qrencode"):
        try:
            subprocess.run(["qrencode", "-o", str(filepath), "-s", "6", "-m", "3", url],
                           check=True, timeout=4, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
            return Path(filepath).is_file()
        except (OSError, subprocess.SubprocessError):
            pass
    return False
