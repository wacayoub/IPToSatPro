# -*- coding: utf-8 -*-
"""VuLink Pro V2 (LAN): authenticated diagnostic & on-TV-approved local actions.

Never accepts a command, pathname, IPTV URL or script from the browser.
Does not provide SSH/FTP/cloud access to ChatGPT.
"""
import datetime
import html
import json
import os
import re
import secrets
import shutil
import stat
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .bridge import PairingServer, collect_report

V2_VERSION = "2.0.0-beta1"
BACKUP_ROOT = Path("/home/root/vulink-pro-backups")
CONF_ROOT = Path("/etc/enigma2/SatIPTVBridge")
PLUGIN_ROOT = Path("/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge")
MAX_BACKUP_BYTES = 24 * 1024 * 1024
MAX_FILES = 300
ACTIONS = {
    "audit_python": "Audit syntaxe du plugin (lecture seule)",
    "backup_iptosat": "Sauvegarde locale protegee du plugin et des reglages",
}
SCREEN_APPROVAL_SECONDS = 90


def _utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _safe_bool_file(path):
    try:
        return path.is_file() and not path.is_symlink()
    except OSError:
        return False



def _preview_stage_statistics():
    """Aggregate ONLY integers from PREVIEW_RANK_BG lines, never raw log content."""
    try:
        log = CONF_ROOT / "bridge.log"
        with log.open("rb") as stream:
            stream.seek(0, os.SEEK_END)
            stream.seek(max(0, stream.tell() - 512 * 1024))
            raw = stream.read(512 * 1024).decode("utf-8", "replace")
    except OSError:
        return {"available": False}
    stages = {"elapsed_ms": [], "index_ms": [], "scoring_ms": [], "candidates": [], "scored": []}
    errors = 0
    for line in raw.splitlines()[-2200:]:
        if not re.search(r"\|\s*PREVIEW_RANK_BG\s*\|", line):
            continue
        if re.search(r"\berror=(?!\s*(?:$|\|))\S+", line):
            errors += 1
        for source, target in (("elapsed", "elapsed_ms"), ("index", "index_ms"),
                               ("scoring", "scoring_ms"), ("candidate_count", "candidates"),
                               ("scored", "scored")):
            found = re.search(r"\b" + source + r"=(\d{1,8})(?:ms)?\b", line)
            if found:
                stages[target].append(int(found.group(1)))
    aggregates = {}
    for key, values in stages.items():
        if values:
            ordered = sorted(values)
            aggregates[key] = {"samples": len(ordered),
                               "median": ordered[len(ordered) // 2],
                               "p95": ordered[max(0, (len(ordered) * 95 + 99) // 100 - 1)],
                               "max": ordered[-1]}
    return {"available": True, "stage_metrics": aggregates,
            "error_count": errors}

def extended_report():
    """Add safe numeric platform facts; no file content, channels or credentials."""
    report = collect_report()
    report["schema"] = "vulink-pro-v2-diagnostic"
    report["preview_performance"] = _preview_stage_statistics()
    report["vulink"] = {
        "version": V2_VERSION,
        "remote_ssh_access": False,
        "lan_only": True,
        "tv_approval_for_actions": True,
        "cloud_connection": False,
    }
    try:
        loads = Path("/proc/loadavg").read_text().split()[:3]
        report["receiver"]["load_average"] = [round(float(v), 2) for v in loads]
    except (OSError, ValueError):
        report["receiver"]["load_average"] = None
    try:
        stats = os.statvfs("/home/root")
        report["receiver"]["free_storage_mb"] = (stats.f_bavail * stats.f_frsize) // (1024 * 1024)
    except OSError:
        report["receiver"]["free_storage_mb"] = None
    return report


def audit_python():
    """Read-only Python AST compilation; error summaries cannot disclose source."""
    results = {}
    for name in ("plugin.py", "core.py", "updater.py",
                 "preview_theme_r74.py", "home_themes_r767.py"):
        file = PLUGIN_ROOT / name
        if not _safe_bool_file(file):
            results[name] = "missing"
            continue
        try:
            if file.stat().st_size > 1024 * 1024:
                results[name] = "oversize"
                continue
            compile(file.read_bytes(), name, "exec")
            results[name] = "valid"
        except (OSError, SyntaxError, ValueError, MemoryError) as exc:
            results[name] = "error:" + type(exc).__name__
    return {"audit": "plugin_python_syntax", "modules": results, "finished_utc": _utc_now()}


def backup_iptosat():
    """Backup only regular non-symlink files into a root-private timestamp folder.

    No backup files can be downloaded via VuLink, and no arbitrary path supplied.
    No shell commands or network operations are involved.
    """
    BACKUP_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(BACKUP_ROOT, 0o700)
    destination = BACKUP_ROOT / (_utc_now().replace(":", "").replace("+", "_").replace(".", "-")
                                 + "-" + secrets.token_hex(3))
    destination.mkdir(mode=0o700)
    count = 0
    total = 0
    skipped = 0
    try:
        for label, origin in (("plugin", PLUGIN_ROOT), ("settings", CONF_ROOT)):
            if not origin.is_dir() or origin.is_symlink():
                continue
            stack = [(origin, destination / label, 0)]
            while stack:
                source, outdir, depth = stack.pop()
                outdir.mkdir(mode=0o700, parents=True, exist_ok=True)
                for child in source.iterdir():
                    if child.is_symlink():
                        skipped += 1
                        continue
                    try:
                        meta = child.lstat()
                    except OSError:
                        skipped += 1
                        continue
                    if stat.S_ISDIR(meta.st_mode):
                        if depth < 5:
                            stack.append((child, outdir / child.name, depth + 1))
                        else:
                            skipped += 1
                    elif stat.S_ISREG(meta.st_mode):
                        if count >= MAX_FILES or total + meta.st_size > MAX_BACKUP_BYTES:
                            raise ValueError("backup_size_limit")
                        # Open with O_NOFOLLOW where available; never follow new symlinks.
                        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                        fd = os.open(str(child), flags)
                        try:
                            with os.fdopen(fd, "rb") as handle:
                                data = handle.read(meta.st_size + 1)
                        except Exception:
                            raise
                        if len(data) != meta.st_size:
                            raise ValueError("concurrent_file_change")
                        dest = outdir / child.name
                        with dest.open("xb") as output:
                            output.write(data)
                        os.chmod(dest, 0o600)
                        total += len(data)
                        count += 1
                    else:
                        skipped += 1
        if count == 0:
            raise ValueError("no_backup_files")
        return {"backup": "created", "files": count,
                "bytes": total, "skipped": skipped,
                "stored_locally_only": True, "finished_utc": _utc_now()}
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise


def perform_action(action):
    if action == "audit_python":
        return audit_python()
    if action == "backup_iptosat":
        return backup_iptosat()
    raise ValueError("unsupported_action")


def _page(title, inner, refresh=False):
    refresh_meta = '<meta http-equiv="refresh" content="8">' if refresh else ""
    return ('<!doctype html><html lang="fr"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            + refresh_meta + '<title>' + html.escape(title) + '</title>'
            '<style>body{font:16px system-ui, sans-serif;background:#111A25;'
            'color:#F0F6FA;max-width:660px;margin:4vh auto;padding:18px}'
            'h2{font-size:24px}p{line-height:1.55}'
            'button,a{font:inherit;display:inline-block;background:#167e71;'
            'color:#fff;border:0;border-radius:10px;padding:13px;'
            'margin:7px 4px;text-decoration:none}input{font-size:19px;'
            'padding:12px;width:90%;border-radius:8px}'
            'section{padding:14px;background:#1c2b38;border-radius:12px;'
            'margin:13px 0}small{color:#b9cfdb}</style>'
            '<h2>' + html.escape(title) + '</h2>' + inner + '</html>')


class ProPairingServer(PairingServer):
    """The QR is a bearer bootstrap; after pairing only IP-bound sessions work."""

    def __init__(self, ip=None, lifetime=600):
        super().__init__(ip=ip, lifetime=lifetime)
        self._sessions = {}
        self._queue = {}
        self._last_result = None
        self._busy = False
        self._closed = False

    def _make_session(self, ip, code):
        if not self._allowed(code, ip):
            return None
        with self._lock:
            token = secrets.token_urlsafe(32)
            csrf = secrets.token_urlsafe(24)
            # One paired mobile at a time; pairing a new device revokes the old.
            self._sessions = {token: {"ip": ip, "csrf": csrf}}
        return token

    def _auth(self, client_ip, cookie_header):
        if time.monotonic() >= self.deadline or self._closed:
            return None
        jar = SimpleCookie()
        try:
            jar.load(cookie_header or "")
            token = jar["vulink_v2"].value if "vulink_v2" in jar else ""
        except (KeyError, ValueError):
            return None
        with self._lock:
            session = self._sessions.get(token)
            return dict(session) if session and session["ip"] == client_ip else None

    def request(self, action):
        if action not in ACTIONS:
            return None
        now = time.monotonic()
        with self._lock:
            if self._closed or self._busy or any(row["status"] == "pending" for row in self._queue.values()):
                return None
            request_id = secrets.token_hex(8)
            self._queue[request_id] = {
                "action": action,
                "title": ACTIONS[action],
                "created": now, "expires": min(self.deadline, now + SCREEN_APPROVAL_SECONDS),
                "status": "pending",
            }
            return request_id

    def pending(self):
        now = time.monotonic()
        with self._lock:
            for row in self._queue.values():
                if row["status"] == "pending" and (now >= row["expires"] or self._closed):
                    row["status"] = "expired"
            return next(((key, dict(row)) for key, row in self._queue.items()
                         if row["status"] == "pending"), None)

    def decide(self, request_id, approved):
        """Call only from the Vu+ physical remote green/yellow key handler."""
        with self._lock:
            row = self._queue.get(request_id)
            if not row or row["status"] != "pending" or self._closed:
                return False
            if time.monotonic() >= row["expires"] or time.monotonic() >= self.deadline:
                row["status"] = "expired"
                return False
            row["status"] = "running" if approved else "denied"
            if approved:
                self._busy = True
            action = row["action"]
        if approved:
            def run():
                try:
                    outcome = perform_action(action)
                    state = "completed"
                except Exception as exc:
                    outcome = {"error": type(exc).__name__}
                    state = "failed"
                with self._lock:
                    row["status"] = state
                    self._busy = False
                    self._last_result = {"action": action, "status": state, "outcome": outcome}
            threading.Thread(target=run, name="VuLinkProApprovedAction", daemon=True).start()
        return True

    def public_state(self):
        waiting = self.pending()
        with self._lock:
            latest = self._last_result
            busy = self._busy
        return {"version": V2_VERSION,
                "expires_in_seconds": max(0, int(self.deadline - time.monotonic())),
                "pending_tv_approval": waiting[1]["title"] if waiting else None,
                "busy": busy, "last_action": latest}

    def start(self):
        owner = self
        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"
            def log_message(self, *_):
                pass

            def send_data(self, status, body, mime="text/html; charset=utf-8", cookie=None, file=None, redirect=None):
                body = body.encode("utf-8") if isinstance(body, str) else body
                self.send_response(status)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Pragma", "no-cache")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Frame-Options", "DENY")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("Content-Security-Policy",
                                 "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'")
                if cookie:
                    self.send_header("Set-Cookie", "vulink_v2=" + cookie +
                                     "; HttpOnly; SameSite=Strict; Path=/")
                if file:
                    self.send_header("Content-Disposition", 'attachment; filename="' + file + '"')
                if redirect:
                    self.send_header("Location", redirect)
                self.end_headers()
                try:
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def auth(self):
                return owner._auth(self.client_address[0], self.headers.get("Cookie"))

            def do_GET(self):
                if len(self.path) > 256:
                    return self.send_data(414, "bad request", "text/plain")
                if time.monotonic() >= owner.deadline or owner._closed:
                    return self.send_data(410, _page("Session fermee", "<p>Rouvre VuLink sur la TV.</p>"))
                path = urlsplit(self.path).path
                if path.startswith("/p/"):
                    token = owner._make_session(self.client_address[0], path[3:])
                    if not token:
                        return self.send_data(403, _page("Code invalide", "<p>Acces refuse</p>"))
                    return self.send_data(303, b"", cookie=token, redirect="/app")
                if path == "/":
                    return self.send_data(200, _page("VuLink Pro V2",
                        '<p>Appairage prive sur ton reseau local. Code affiche sur la TV.</p>'
                        '<form action="/pair" method="post">'
                        '<input name="code" autocomplete="off" maxlength="20" required>'
                        '<button type="submit">Connecter</button></form>'))
                auth = self.auth()
                if not auth:
                    return self.send_data(401, _page("Connexion requise",
                                             '<p>Scanne le QR affiche sur le Vu+.</p>'))
                if path == "/api/report":
                    return self.send_data(200, json.dumps(extended_report(),
                                          ensure_ascii=False, indent=2),
                                          "application/json; charset=utf-8",
                                          file="vulink-pro-diagnostic.json")
                if path == "/api/state":
                    return self.send_data(200, json.dumps(owner.public_state()),
                                          "application/json; charset=utf-8")
                if path == "/app":
                    state = owner.public_state()
                    last = state["last_action"]
                    status = html.escape(json.dumps(last, ensure_ascii=False)[:700]) if last else "Aucune action"
                    pending = html.escape(state["pending_tv_approval"] or "Aucune")
                    token = html.escape(auth["csrf"], quote=True)
                    options = "".join(
                        '<form action="/action" method="post">'
                        '<input type="hidden" name="csrf" value="' + token + '">'
                        '<input type="hidden" name="action" value="' + html.escape(key) + '">'
                        '<button type="submit">' + html.escape(label) + '</button></form>'
                        for key, label in ACTIONS.items())
                    content = ('<section><p>Session active, expire dans %ds.</p>'
                               '<a href="/api/report">Telecharger diagnostic JSON</a></section>'
                               '<section><b>Actions locales</b><p>Une confirmation VERTE sur la '
                               'telecommande du Vu+ est obligatoire.</p>' + options + '</section>'
                               '<section><p>En attente sur TV : ' + pending + '</p>'
                               '<p>Dernier resultat : ' + status + '</p>'
                               '<small>Cette page s actualise toutes les 8 secondes.</small></section>'
                               '<p>Ajoute le rapport JSON dans notre conversation ChatGPT. '
                               'Pas de SSH/cloud direct depuis ChatGPT.</p>') % state["expires_in_seconds"]
                    return self.send_data(200, _page("VuLink Pro V2", content, refresh=True))
                return self.send_data(404, "not found", "text/plain")

            def do_POST(self):
                if len(self.path) > 256:
                    return self.send_data(414, "bad request", "text/plain")
                if time.monotonic() >= owner.deadline or owner._closed:
                    return self.send_data(410, "expired", "text/plain")
                if self.path not in ("/pair", "/action"):
                    return self.send_data(404, "not found", "text/plain")
                try:
                    size = int(self.headers.get("Content-Length", "-1"))
                except ValueError:
                    size = -1
                if size < 1 or size > 1024:
                    return self.send_data(413, "bad size", "text/plain")
                # Prevent cross-site submission if Origin is supplied (CSRF still mandatory).
                origin = self.headers.get("Origin")
                expected = "http://%s:%s" % (owner.ip, owner.server.server_port)
                if origin and origin != expected:
                    return self.send_data(403, "bad origin", "text/plain")
                data = parse_qs(self.rfile.read(size).decode("ascii", "replace"))
                if self.path == "/pair":
                    code = data.get("code", [""])[0][:40]
                    token = owner._make_session(self.client_address[0], code)
                    if not token:
                        return self.send_data(403, "pair denied", "text/plain")
                    return self.send_data(303, b"", cookie=token, redirect="/app")
                auth = self.auth()
                if not auth or not secrets.compare_digest(data.get("csrf", [""])[0], auth["csrf"]):
                    return self.send_data(403, "forbidden", "text/plain")
                action = data.get("action", [""])[0]
                request_id = owner.request(action)
                if not request_id:
                    return self.send_data(409, _page("Action refusee",
                        '<p>Action inconnue ou une demande est deja en cours.</p>'
                        '<a href="/app">Retour</a>'))
                return self.send_data(303, b"", redirect="/app")

        class LocalHTTP(ThreadingHTTPServer):
            daemon_threads = True
            allow_reuse_address = False

        self.server = LocalHTTP((self.ip, 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       name="VuLinkProLocalHTTP", daemon=True)
        self.thread.start()
        return self.url

    def stop(self):
        with self._lock:
            self._closed = True
            self._sessions.clear()
            for row in self._queue.values():
                if row["status"] == "pending":
                    row["status"] = "expired"
        super().stop()
