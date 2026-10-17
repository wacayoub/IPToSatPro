"""Pure-Python routing policy for King IPTV TOD event feeds (no Enigma2 imports).

The image/logo classifier is *upstream*. Pass only logo evidence extracted from
on-screen video; the channel title or the EPG must NEVER stand in for evidence.
No network I/O, player restarts, or persistent mappings occur in this module.
"""
import re
import time
from collections import deque
from dataclasses import dataclass

SLOTS = frozenset(range(1, 15))
LOGOS = frozenset(range(1, 11))
_KING_NAMES = frozenset(("KING", "SOURCE KING", "KING IPTV", "IPTV KING"))
_TOD_RE = re.compile(r"\bTOD\s*(?:EVENT\s*)?(?:SPORTS?\s*)?0?(1[0-4]|[1-9])\b", re.I)
_BEIN_RE = re.compile(r"\bBEIN\s*(?:SPORTS?\s*)?0?(10|[1-9])\b", re.I)


def is_king_provider(value):
    return " ".join(str(value or "").upper().strip().split()) in _KING_NAMES


def tod_slot(value):
    matched = _TOD_RE.search(str(value or ""))
    return int(matched.group(1)) if matched else None


def bein_logo_number(value):
    if isinstance(value, int):
        return value if value in LOGOS else None
    matched = _BEIN_RE.search(str(value or ""))
    return int(matched.group(1)) if matched else None


def next_non_blacklisted(channels, current_index, direction, is_blacklisted):
    """Return the next playable (index, channel) or (None, None).

    Applies to manual selection and CH+/CH- when the caller supplies its
    channel-list order. It intentionally never calls Enigma2 navigation.
    """
    if direction not in (-1, 1):
        raise ValueError("direction must be +1 or -1")
    total = len(channels)
    if not total:
        return None, None
    for offset in range(1, total + 1):
        index = (current_index + direction * offset) % total
        channel = channels[index]
        if not is_blacklisted(channel):
            return index, channel
    return None, None


@dataclass(frozen=True)
class Assignment:
    tod: int
    bein: int
    confidence: float
    timestamp: float
    stream_id: str = ""
    event_id: str = ""


class KingTodRouter:
    """Conservative transient assignments based only on repeated on-air logos.

    Feed independent observations around 0.5-1.0s apart. Reset immediately
    when the event or source-stream identity changes. Conflicting logo evidence
    invalidates a former match while the new event is being verified.
    """
    def __init__(self, min_samples=3, min_confidence=0.88,
                 min_spacing=0.35, observation_window=15.0, ttl=150.0):
        if min_samples < 2 or not (0 < min_confidence <= 1):
            raise ValueError("invalid verification policy")
        self.min_samples = min_samples
        self.min_confidence = min_confidence
        self.min_spacing = min_spacing
        self.observation_window = observation_window
        self.ttl = ttl
        self._observed = {}
        self._identities = {}
        self._assignments = {}

    def clear(self, tod=None):
        if tod is None:
            self._observed.clear()
            self._identities.clear()
            self._assignments.clear()
        else:
            self._observed.pop(tod, None)
            self._identities.pop(tod, None)
            self._assignments.pop(tod, None)

    def observe(self, provider, tod_name, on_screen_logo, confidence,
                stream_id="", event_id="", now=None):
        """Return new Assignment after consensus; otherwise None.

        on_screen_logo MUST come from a VIDEO LOGO detector, not IPTV name.
        stream_id and event_id identify discontinuities when available.
        """
        if not is_king_provider(provider):
            return None
        slot = tod_slot(tod_name)
        if slot is None:
            return None
        now = time.monotonic() if now is None else float(now)
        stream_id, event_id = str(stream_id or ""), str(event_id or "")
        identity = (stream_id, event_id)
        previous_identity = self._identities.get(slot)
        # New event/URL invalidates a former match EVEN when the watermark
        # is not yet visible on the first frame of the new broadcast.
        if previous_identity is not None and identity != previous_identity:
            self.clear(slot)
        self._identities[slot] = identity
        logo = bein_logo_number(on_screen_logo)
        if logo is None:
            return None
        if not isinstance(confidence, (float, int)) or not (self.min_confidence <= confidence <= 1):
            return None
        existing = self._assignments.get(slot)
        if existing is not None and existing.bein != logo:
            self._assignments.pop(slot, None)
        history = self._observed.setdefault(slot, deque())
        while history and now - history[0][0] > self.observation_window:
            history.popleft()
        # Reject duplicate callbacks from the same decoder frame.
        if history and now - history[-1][0] < self.min_spacing:
            return None
        history.append((now, logo, float(confidence)))
        # Do not treat a previous logo in this window as new-event evidence.
        run = []
        for sample in reversed(history):
            if sample[1] != logo:
                break
            run.append(sample)
        if len(run) < self.min_samples:
            return None
        score = sum(sample[2] for sample in run) / len(run)
        verified = Assignment(slot, logo, round(score, 4), now,
                              stream_id, event_id)
        self._assignments[slot] = verified
        return verified

    def by_bein(self, provider, number, now=None):
        """Find verified TOD slots carrying beIN number, best first."""
        if not is_king_provider(provider):
            return []
        logo = bein_logo_number(number)
        if logo is None:
            return []
        now = time.monotonic() if now is None else float(now)
        result = []
        for slot, assignment in list(self._assignments.items()):
            if now - assignment.timestamp > self.ttl:
                self._assignments.pop(slot, None)
                continue
            if assignment.bein == logo:
                result.append(assignment)
        return sorted(result, key=lambda item: (-item.confidence, -item.timestamp, item.tod))

    def by_tod(self, provider, tod_name, now=None):
        """Return verified assignment for a TOD slot, never a permanent mapping."""
        slot = tod_slot(tod_name)
        if not is_king_provider(provider) or slot is None:
            return None
        now = time.monotonic() if now is None else float(now)
        a = self._assignments.get(slot)
        if a is not None and now - a.timestamp <= self.ttl:
            return a
        self._assignments.pop(slot, None)
        return None
