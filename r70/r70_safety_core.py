"""IPToSat Pro r70 unified safety kernel (candidate; not yet receiver validated).

All operations are bounded and stdlib-only. This module never starts threads,
uses network access, changes service/player mode, or performs GUI operations.
The Enigma2 adapter is intentionally non-invasive until hardware tests pass.
"""
import hashlib
import hmac
import json
import os
import shutil
import tempfile
import time
from collections import OrderedDict


MAX_HISTORY = 256
MAX_BYTES = 512 * 1024
STALE_AFTER = 7 * 86400
MAX_LOCKS = 4096


def _token(value):
    """Non-reversible ID. Never log IPTV credentials, URLs or user-supplied keys."""
    return hashlib.sha256(str(value or "").encode("utf-8", "replace")).hexdigest()[:24]


def _read(path, default):
    try:
        if os.stat(path).st_size > MAX_BYTES:
            return default
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else default
    except (OSError, ValueError, TypeError):
        return default


def _atomic_json(path, data):
    """Durable, bounded, crash-safe JSON write; never overwrite original on failure."""
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    if len(raw.encode("utf-8")) > MAX_BYTES:
        raise ValueError("Store exceeds cap")
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, mode=0o700, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".r70-", dir=parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temp, 0o600)
        os.replace(temp, path)
    finally:
        try:
            os.unlink(temp)
        except OSError:
            pass


class PlaybackGuard:
    """State machine: CONNECTED is never equivalent to VIDEO_DECODED."""
    def __init__(self, clock=None):
        self.clock = clock or time.monotonic
        self.generation = 0
        self.active = None

    def begin(self, stream_id, service_id):
        self.generation += 1
        now = self.clock()
        self.active = {
            "generation": self.generation,
            "stream": _token(stream_id),
            "service": _token(service_id),
            "start": now,
            "connected": False,
            "decoded": False,
            "stable": False,
            "first_frame": None,
            "last_frame": None,
            "frames": 0,
            "audio": "UNKNOWN",
            "dimensions": None,
            "failure": None,
            "recoveries": 0,
        }
        return self.generation

    def current(self, generation):
        return self.active if self.active and self.active["generation"] == generation else None

    def connected(self, generation):
        st = self.current(generation)
        if st:
            st["connected"] = True
        return st is not None

    def decoded_frame(self, generation, width, height):
        st = self.current(generation)
        if not st or width <= 0 or height <= 0:
            return False
        now = self.clock()
        if not st["decoded"]:
            st["first_frame"] = now
        st["decoded"] = True
        st["dimensions"] = [int(width), int(height)]
        st["last_frame"] = now
        st["frames"] += 1
        # A second decoder notification alone is not proof of uninterrupted
        # moving video. Keep STABLE until a later independent observation.
        return True

    def mark_stable(self, generation, observable=True):
        st = self.current(generation)
        if not st or not st["decoded"] or not observable:
            return False
        if self.clock() - st["first_frame"] < 1.0:
            return False
        st["stable"] = True
        return True

    def set_audio_observation(self, generation, available):
        st = self.current(generation)
        if st is None:
            return False
        st["audio"] = "TRACK_PRESENT" if available else "UNVERIFIED"
        # Track presence is NOT proof of audible sound.
        return True

    def mark_failure(self, generation, cause="unknown"):
        st = self.current(generation)
        if st is None:
            return False
        st["failure"] = str(cause)[:48]
        return True

    def no_frame_due(self, generation, wait_s=2.5):
        st = self.current(generation)
        if not st or st["decoded"]:
            return False
        return self.clock() - st["start"] >= wait_s

    def frozen_due(self, generation, wait_s=8.0):
        st = self.current(generation)
        if not st or not st["decoded"] or st["last_frame"] is None:
            return False
        # Only meaningful if genuine frame-update events are available;
        # never infer freeze from a static image or decoder-size notification.
        return False

    def snapshot(self):
        st = self.active
        if not st:
            return {}
        now = self.clock()
        return {
            "generation": st["generation"],
            "connected": st["connected"],
            "video_decoded": st["decoded"],
            "stable": st["stable"],
            "audio": st["audio"],
            "dimensions": st["dimensions"],
            "time_to_first_frame_ms": (
                round(1000 * (st["first_frame"] - st["start"]))
                if st["first_frame"] is not None else None
            ),
            "age_ms": round(1000 * (now - st["start"])),
        }


class CandidateHistory:
    """One sanitized, size-limited record per hashed stream fingerprint."""
    def __init__(self, path, clock=None):
        self.path = path
        self.clock = clock or time.time
        raw = _read(path, {})
        self.rows = OrderedDict()
        for key, row in list(raw.get("history", {}).items())[-MAX_HISTORY:]:
            if isinstance(key, str) and len(key) == 24 and isinstance(row, dict):
                self.rows[key] = row
        self.dirty = False

    def record(self, candidate_id, ok, mode="", elapsed_ms=None, source_id=""):
        key = _token(candidate_id)
        if key not in self.rows:
            self.rows[key] = {"ok": 0, "fail": 0}
        row = self.rows[key]
        row["ok" if ok else "fail"] = min(99999, int(row.get("ok" if ok else "fail", 0)) + 1)
        row["last"] = int(self.clock())
        row["source"] = _token(source_id)
        if mode in ("dvb", "5002", "4097"):
            if ok:
                row["mode"] = mode
        if elapsed_ms is not None and 0 <= elapsed_ms <= 60000:
            row["last_ms"] = int(elapsed_ms)
        self.rows.move_to_end(key)
        while len(self.rows) > MAX_HISTORY:
            self.rows.popitem(last=False)
        self.dirty = True
        return dict(row)

    def health(self, candidate_id):
        row = self.rows.get(_token(candidate_id))
        if not row or self.clock() - row.get("last", 0) > STALE_AFTER:
            return {"reliability": None, "mode": None}
        ok, bad = row.get("ok", 0), row.get("fail", 0)
        return {"reliability": round((ok + 1.0) / (ok + bad + 2.0), 3),
                "mode": row.get("mode")}

    def flush(self):
        if self.dirty:
            _atomic_json(self.path, {"format": 1, "history": dict(self.rows)})
            self.dirty = False

    def reset(self, candidate_id=None):
        if candidate_id is None:
            self.rows.clear()
        else:
            self.rows.pop(_token(candidate_id), None)
        self.dirty = True


class ManualLockGuard:
    """Opt-in mirror/snapshot for manual locks; never rewrites legacy overrides."""
    def __init__(self, path):
        self.path = path
        data = _read(path, {})
        self.locks = data.get("locks", {}) if isinstance(data.get("locks"), dict) else {}

    def keep(self, service_id, candidate_id):
        if len(self.locks) >= MAX_LOCKS and _token(service_id) not in self.locks:
            raise ValueError("Too many locks")
        self.locks[_token(service_id)] = _token(candidate_id)
        _atomic_json(self.path, {"format": 1, "locks": self.locks})

    def read(self, service_id):
        return self.locks.get(_token(service_id))

    def matches(self, service_id, candidate_id):
        return self.read(service_id) == _token(candidate_id)

    def snapshot_legacy(self, original_path, destination_path):
        """Backup existing mappings without changing the source of truth."""
        if not os.path.isfile(original_path) or os.path.islink(original_path):
            return False
        if os.stat(original_path).st_size > MAX_BYTES:
            return False
        with open(original_path, "rb") as f:
            raw = f.read()
        try:
            obj = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return False
        if not isinstance(obj, (dict, list)):
            return False
        parent = os.path.dirname(os.path.abspath(destination_path))
        os.makedirs(parent, mode=0o700, exist_ok=True)
        fd, temp = tempfile.mkstemp(prefix=".r70-backup-", dir=parent)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(raw)
                f.flush()
                os.fsync(f.fileno())
            os.chmod(temp, 0o600)
            os.replace(temp, destination_path)
        finally:
            try:
                os.unlink(temp)
            except OSError:
                pass
        return True


class RecoveryPolicy:
    """Advisory only: a watchdog must never forcibly restart Enigma2."""
    def __init__(self, clock=None):
        self.clock = clock or time.monotonic
        self.attempts = {}

    def allow(self, key, generation, max_attempts=2, cooldown_s=12.0):
        now = self.clock()
        stamp = (_token(key), int(generation))
        count, last = self.attempts.get(stamp, (0, -1e30))
        if count >= max_attempts or now - last < cooldown_s:
            return False
        self.attempts[stamp] = (count + 1, now)
        if len(self.attempts) > 128:
            self.attempts = {stamp: self.attempts[stamp]}
        return True

    @staticmethod
    def audio_recovery_needed(track_count, selected_track, known_silence=False):
        # No audible-silence telemetry => no speculative track switch.
        return bool(known_silence and track_count > 0 and selected_track < 0)


def validate_update(ipk_path, manifest, expected_prefix="1.0.46-r70"):
    """Safe Online Update prerequisite, not an update or installer."""
    if not isinstance(manifest, dict):
        raise ValueError("Manifest must be an object")
    version = str(manifest.get("version", ""))
    if not version.startswith(expected_prefix) or "/" in version or "\\" in version:
        raise ValueError("Unapproved version")
    expected_size = manifest.get("size")
    digest = str(manifest.get("sha256", ""))
    if not isinstance(expected_size, int) or not (10240 <= expected_size <= 10 * 1024 * 1024):
        raise ValueError("Invalid size")
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("Invalid digest")
    sha = hashlib.sha256()
    count = 0
    with open(ipk_path, "rb") as f:
        header = f.read(8)
        if header != b"!<arch>\\n":
            raise ValueError("Not an IPK archive")
        sha.update(header)
        count += len(header)
        while True:
            data = f.read(65536)
            if not data:
                break
            sha.update(data)
            count += len(data)
            if count > 10 * 1024 * 1024:
                raise ValueError("Package too large")
    if count != expected_size or not hmac.compare_digest(sha.hexdigest(), digest):
        raise ValueError("Integrity verification failed")
    return {"version": version, "size": count, "sha256": sha.hexdigest(), "safe_to_review": True}


FEATURES = (
    "Real Playback Verification", "Black Screen Detector",
    "Persistent Manual Lock", "Anti-Freeze Watchdog",
    "Source Health Monitor", "Audio Auto-Recovery",
    "Candidate History", "Safe Online Update",
)
