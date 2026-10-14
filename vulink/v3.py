# -*- coding: utf-8 -*-
"""VuLink V3: outbound-only GitHub Issues relay for ChatGPT's GitHub connector.

NO incoming ports, SSH daemon, FTP or raw shell. Only allowlisted operations.
The actual GitHub repository MUST be private and a separate dedicated repo.
"""
import datetime as dt
import json
import os
from pathlib import Path
import re
import secrets
import stat
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from .v2 import extended_report, audit_python, backup_iptosat

VERSION = "3.0.0-rc1"
PROTOCOL = "vulink-v3.1"
PREFIX_REQUEST = "VULINK_V3_REQUEST\n"
PREFIX_RESULT = "VULINK_V3_RESULT\n"
CONFIG_PATH = Path("/etc/enigma2/VuLink/v3-relay.json")
REMOTE_READ = ("get_diagnostic", "preview_performance", "audit_python")
TV_APPROVAL = ("backup_iptosat",)
ALLOWED = REMOTE_READ + TV_APPROVAL
MAX_AGE_SECONDS = 600
PENDING_TTL_SECONDS = 180
POLL_SECONDS = 25
MAX_COMMENT_BODY = 2048
REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,39}/[A-Za-z0-9_.-]{1,100}$")
ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
DEVICE_PATTERN = re.compile(r"^[0-9a-f]{16}$")
MAX_REPLY_LEN = 9000


def _iso_now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _from_iso(raw):
    if not isinstance(raw, str) or len(raw) > 40:
        raise ValueError("invalid date")
    when = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if when.tzinfo is None:
        raise ValueError("timezone required")
    return when.astimezone(dt.timezone.utc)


def read_config(path=CONFIG_PATH):
    p = Path(path)
    metadata = p.lstat()
    if not stat.S_ISREG(metadata.st_mode) or (metadata.st_mode & 0o077):
        raise PermissionError("VuLink config must be a regular, root-private 0600 file")
    cfg = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(cfg, dict):
        raise ValueError("invalid relay configuration")
    if not REPO_PATTERN.fullmatch(str(cfg.get("repo", ""))):
        raise ValueError("invalid repository")
    if not DEVICE_PATTERN.fullmatch(str(cfg.get("device_id", ""))):
        raise ValueError("invalid device identity")
    if not re.fullmatch(r"[A-Za-z0-9-]{1,39}", str(cfg.get("owner", ""))):
        raise ValueError("invalid GitHub owner")
    token = cfg.get("token")
    if not isinstance(token, str) or len(token) < 30 or "\n" in token:
        raise ValueError("GitHub token missing")
    return cfg


def save_config(cfg, path=CONFIG_PATH):
    p = Path(path)
    p.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(p.parent, 0o700)
    tmp = p.parent / (".v3-" + secrets.token_hex(8))
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(cfg, out, sort_keys=True)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(str(tmp), str(p))
        os.chmod(p, 0o600)
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass


class GithubAPI:
    """Strict endpoints; token never sent to a URL supplied by a task."""
    def __init__(self, repo, token, opener=None):
        if not REPO_PATTERN.fullmatch(repo):
            raise ValueError("invalid GitHub repo")
        self.repo = repo
        self.token = token
        self.opener = opener or urllib.request.build_opener(
            urllib.request.ProxyHandler({}))
        self.root = "https://api.github.com/repos/" + repo

    def call(self, method, relative, data=None, params=None):
        if method not in ("GET", "POST"):
            raise ValueError("unsupported method")
        if relative != "" and (not relative.startswith("/") or not re.fullmatch(r"/[A-Za-z0-9/_-]*", relative)):
            raise ValueError("unsupported GitHub endpoint")
        # Only a known repo metadata endpoint or this repo's Issues API.
        if relative not in ("", "/issues") and not re.fullmatch(
                r"/issues/[0-9]+(?:/comments)?", relative):
            raise ValueError("GitHub endpoint forbidden")
        suffix = relative
        if params:
            suffix += "?" + urllib.parse.urlencode(params)
        url = self.root + suffix
        payload = json.dumps(data).encode("utf-8") if data is not None else None
        req = urllib.request.Request(
            url, data=payload, method=method,
            headers={
                "Authorization": "Bearer " + self.token,
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "VuLink-V3-Private-Relay",
                "Content-Type": "application/json",
            })
        with self.opener.open(req, timeout=12) as response:
            body = response.read(262145)
            if len(body) > 262144:
                raise ValueError("GitHub response too large")
            return json.loads(body.decode("utf-8"))

    def assert_private_repo(self):
        info = self.call("GET", "")
        if info.get("private") is not True or info.get("archived") is True:
            raise PermissionError("VuLink V3 requires a non-archived PRIVATE repository")
        if info.get("full_name", "").lower() != self.repo.lower():
            raise PermissionError("GitHub repo mismatch")
        if info.get("has_issues") is False:
            raise PermissionError("GitHub Issues must be enabled")

    def register(self, device_id, existing_issue=0):
        if existing_issue:
            issue = self.call("GET", "/issues/%d" % int(existing_issue))
            if issue.get("state") == "open" and issue.get("title") == (
                    "[VuLink V3] Device " + device_id):
                return int(existing_issue)
        title = "[VuLink V3] Device " + device_id
        body = (
            "PRIVATE DEVICE RELAY. Do not post credentials or stream URLs.\n\n"
            "The agent accepts only messages formatted as:\n\n"
            "VULINK_V3_REQUEST followed by JSON with protocol, device_id, "
            "request_id, created_at, operation.\n\n"
            "Read-only: get_diagnostic, preview_performance, audit_python.\n"
            "Approval on TV required: backup_iptosat.\n"
            "Version: " + VERSION)
        result = self.call("POST", "/issues", {"title": title, "body": body})
        return int(result["number"])

    def comments(self, issue, since=None):
        """Fetch bounded pages, oldest first. Cursor is advanced only after reply."""
        rows = []
        for page in range(1, 6):
            params = {"per_page": 100, "page": page}
            if since:
                params["since"] = since
            entries = self.call("GET", "/issues/%d/comments" % int(issue), params=params)
            if not isinstance(entries, list):
                raise ValueError("invalid GitHub comments payload")
            rows.extend(entries)
            if len(entries) < 100:
                break
        return rows

    def reply(self, issue, response):
        payload = json.dumps(response, separators=(",", ":"), ensure_ascii=True)
        if len(payload) > MAX_REPLY_LEN:
            raise ValueError("VuLink result exceeds redacted output budget")
        return self.call("POST", "/issues/%d/comments" % int(issue),
                         {"body": PREFIX_RESULT + payload})


def decode_request(comment, device_id, owner, now=None):
    if not isinstance(comment, dict):
        return None
    actor = comment.get("user") or {}
    if str(actor.get("login", "")).casefold() != owner.casefold():
        return None
    if actor.get("type") not in (None, "User"):
        return None
    body = comment.get("body")
    if not isinstance(body, str) or not body.startswith(PREFIX_REQUEST) or len(body) > MAX_COMMENT_BODY:
        return None
    try:
        data = json.loads(body[len(PREFIX_REQUEST):])
        if not isinstance(data, dict):
            return None
        if set(data) != {"protocol", "device_id", "request_id", "created_at", "operation"}:
            return None
        if data["protocol"] != PROTOCOL or data["device_id"] != device_id:
            return None
        if not ID_PATTERN.fullmatch(str(data["request_id"])):
            return None
        if data["operation"] not in ALLOWED:
            return None
        when = _from_iso(data["created_at"])
        now = now or dt.datetime.now(dt.timezone.utc)
        delta = (now - when).total_seconds()
        if delta < -60 or delta > MAX_AGE_SECONDS:
            return None
        return data
    except (TypeError, ValueError, KeyError, OverflowError):
        return None


def run_readonly(op):
    if op == "get_diagnostic":
        return extended_report()
    if op == "preview_performance":
        return extended_report().get("preview_performance", {"available": False})
    if op == "audit_python":
        return audit_python()
    raise ValueError("unknown readonly action")


class RelayAgent:
    """Enigma2 daemon thread: outbound HTTPS poll, never blocks GUI."""
    def __init__(self, path=CONFIG_PATH, api_factory=GithubAPI):
        self.path = Path(path)
        self.api_factory = api_factory
        self._lock = threading.Lock()
        self._thread = None
        self._stop = threading.Event()
        self.pending_action = None
        self.last_status = "inactive"
        self.last_op = None
        self.last_result = None
        self.private_repo = ""
        self.device_id = ""
        self.issue_no = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return True
        try:
            cfg = read_config(self.path)
            self.device_id = cfg["device_id"]
            self.private_repo = cfg["repo"]
        except (OSError, ValueError, PermissionError):
            self.last_status = "not_configured"
            return False
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="VuLinkV3Relay", daemon=True)
        self._thread.start()
        return True

    def stop(self):
        self._stop.set()
        with self._lock:
            if self.pending_action:
                self.pending_action["status"] = "cancelled"
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self.last_status = "stopped"

    def summary(self):
        with self._lock:
            item = dict(self.pending_action) if self.pending_action else None
        return {
            "version": VERSION,
            "connected": self.last_status == "connected",
            "status": self.last_status,
            "device_id": self.device_id,
            "private_repo": self.private_repo,
            "issue_no": self.issue_no,
            "last_op": self.last_op,
            "last_result": self.last_result,
            "waiting_for_tv": item["operation"] if item and item["status"] == "pending" else None
        }

    def tv_decide(self, approve):
        """Must only be called by the physical remote key of VuLink's GUI."""
        with self._lock:
            task = self.pending_action
            if not task or task["status"] != "pending":
                return False
            if time.monotonic() > task["expires"]:
                task["status"] = "expired"
                return False
            task["status"] = "approved" if approve else "denied"
            return True

    def _respond(self, api, cfg, request, state, result):
        response = {
            "protocol": PROTOCOL, "device_id": cfg["device_id"],
            "request_id": request["request_id"], "operation": request["operation"],
            "status": state, "completed_at": _iso_now(),
            "result": result
        }
        api.reply(cfg["issue_no"], response)
        self.last_op = request["operation"]
        self.last_result = state

    def _process(self, api, cfg, req):
        if req["operation"] in REMOTE_READ:
            try:
                result = run_readonly(req["operation"])
                state = "completed"
            except Exception as exc:
                result = {"error_type": type(exc).__name__}
                state = "failed"
            self._respond(api, cfg, req, state, result)
            return
        # Other operations are NEVER auto-executed.
        with self._lock:
            is_busy = self.pending_action is not None
            if not is_busy:
                self.pending_action = {"operation": req["operation"],
                                       "expires": time.monotonic() + PENDING_TTL_SECONDS,
                                       "status": "pending", "request": req}
        if is_busy:
            self._respond(api, cfg, req, "rejected", {"reason": "device_busy"})
            return
        self._respond(api, cfg, req, "awaiting_tv_approval",
                      {"reason": "approve_on_receiver_green_or_deny_yellow"})

    def _complete_approved(self, api, cfg):
        with self._lock:
            task = self.pending_action
            if not task:
                return
            state = task["status"]
            if state == "pending" and time.monotonic() > task["expires"]:
                state = "expired"
                task["status"] = "expired"
            if state == "pending":
                return
            task["status"] = "running"
        if state == "approved":
            try:
                result = backup_iptosat()
                outcome = "completed"
            except Exception as exc:
                result = {"error_type": type(exc).__name__}
                outcome = "failed"
        else:
            result = {"reason": "tv_denied_or_expired"}
            outcome = "denied"
        try:
            self._respond(api, cfg, task["request"], outcome, result)
        finally:
            with self._lock:
                self.pending_action = None

    def _loop(self):
        try:
            cfg = read_config(self.path)
            api = self.api_factory(cfg["repo"], cfg["token"])
            api.assert_private_repo()
            issue = api.register(cfg["device_id"], cfg.get("issue_no", 0))
            self.issue_no = issue
            if cfg.get("issue_no") != issue:
                cfg["issue_no"] = issue
                # Discard prior comments when new device session is registered.
                cfg["last_comment_id"] = 0
                cfg["last_comment_time"] = _iso_now()
                save_config(cfg, self.path)
            self.last_status = "connected"
            while not self._stop.is_set():
                self._complete_approved(api, cfg)
                latest = int(cfg.get("last_comment_id") or 0)
                since = cfg.get("last_comment_time")
                comments = api.comments(issue, since=since)
                for comment in comments:
                    if self._stop.is_set():
                        break
                    comment_id = int(comment.get("id") or 0)
                    if comment_id <= latest:
                        continue
                    req = decode_request(comment, cfg["device_id"], cfg["owner"])
                    if req:
                        self._process(api, cfg, req)
                    latest = comment_id
                    cfg["last_comment_id"] = latest
                    cfg["last_comment_time"] = comment.get("created_at", cfg.get("last_comment_time", _iso_now()))
                    save_config(cfg, self.path)
                self.last_status = "connected"
                self._stop.wait(POLL_SECONDS)
        except (OSError, ValueError, KeyError, TypeError, PermissionError,
                urllib.error.URLError, urllib.error.HTTPError) as exc:
            self.last_status = "offline_" + type(exc).__name__
        except Exception:
            self.last_status = "offline_InternalError"
