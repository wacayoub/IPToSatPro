"""Final integration boundary for TOD suggestions; ZERO navigation or writes.

Pure-Python ENIGMA2-FREE adapter. Receives verified, ephemeral assignments
from DynamicTodController/KingTodRouter and only proposes a temporary label.
It cannot switch player, modify saved mappings/locks or access IPTV sources.
A proposal is NEVER an instruction to navigate: caller must still satisfy
independent receiver release gates after genuine hardware acceptance.

The advisory refuses a stale event even if an older assignment is still in
router memory. No trust is placed in textual IPTV channel names for deciding
the broadcaster number; target_bein originates from a decoded-video recognizer
already guarded upstream.
"""
from dataclasses import dataclass
from king_tod_router import LOGOS, tod_slot


@dataclass(frozen=True)
class ShadowRecommendation:
    decision: str
    reason: str
    tod: int = 0
    bein: int = 0
    confidence: float = 0.0


class TodShadowIntegration:
    """Read-only adapter to a receiver-owned event context.

    A service context must be captured on the Enigma2 GUI thread. Controller
    itself does no device operations and is injected by the receiver owner.
    """

    BLOCK_FLAGS = (
        "manual_lock", "timeshift", "recording", "parental_blocked",
        "unverified_king_source", "user_disabled", "zap_in_progress",
    )

    def __init__(self, controller, min_confidence=0.93):
        if not (.93 <= min_confidence <= 1.0):
            raise ValueError("confidence must be at least 0.93")
        if not getattr(controller, "king_source_id", None):
            raise ValueError("exact King source ID required")
        self.controller = controller
        self.minimum = min_confidence

    def propose(self, context, target_bein, now):
        """Propose only. Returns immutable reasoned verdict; NEVER maps/zaps."""
        def reject(reason):
            return ShadowRecommendation("BLOCK", reason)
        if not isinstance(context, dict):
            return reject("missing-current-context")
        if context.get("source_id") != self.controller.king_source_id:
            return reject("not-exact-king-provider")
        try:
            slot = tod_slot(context.get("tod_channel"))
        except Exception:
            slot = None
        if slot is None:
            return reject("not-king-tod-1-14")
        if type(target_bein) is not int or target_bein not in LOGOS:
            return reject("invalid-bein-number")
        if any(context.get(f) for f in self.BLOCK_FLAGS):
            return reject("protected-player-state")
        if (context.get("stream_id") in (None, "") or
                context.get("event_id") in (None, "")):
            return reject("unidentified-stream-or-event")
        if type(now) not in (float, int) or now < 0:
            return reject("invalid-time")
        a = self.controller.routes.by_tod(
            "King", context["tod_channel"], now=now)
        if a is None:
            return reject("no-fresh-verified-logo")
        if a.tod != slot or a.bein != target_bein:
            return reject("wrong-tod-or-bein")
        if (a.stream_id != str(context["stream_id"]) or
                a.event_id != str(context["event_id"])):
            return reject("event-or-stream-changed")
        if (a.timestamp > now or now - a.timestamp >
                self.controller.routes.ttl or
                not self.minimum <= a.confidence <= 1.0):
            return reject("stale-or-low-confidence")
        return ShadowRecommendation(
            "SHADOW_SUGGEST_ONLY", "current-decoded-logo-consensus",
            a.tod, a.bein, a.confidence)
