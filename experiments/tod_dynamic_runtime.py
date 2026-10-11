"""Receiver-facing policy adapter for dynamic King/TOD -> beIN mapping.

No direct navigation, network, filesystem, GUI, OCR or image capture.
An Enigma2 integration MUST provide an independent decoded-video logo
recognizer; a channel name, EPG title or IPTV playlist is not logo evidence.
"""
from king_tod_router import KingTodRouter, tod_slot, bein_logo_number
from black_screen_recovery import BlackScreenAutoSkip


class DynamicTodController:
    def __init__(self, king_source_id, mapping_ttl=60.0):
        # Exact ID from receiver source configuration; never fuzzy 'King'.
        if not str(king_source_id or "").strip():
            raise ValueError("exact King provider ID required")
        self.king_source_id = str(king_source_id).strip()
        self.routes = KingTodRouter(ttl=mapping_ttl)
        self.screen = BlackScreenAutoSkip()

    def verified_video_logo(self, *, source_id, tod_channel, logo, confidence,
                            stream_id, event_id, observed_at,
                            evidence_origin=""):
        """Return a transient assignment after repeated video-logo consensus.

        Caller must pass independently classified CURRENT VIDEO frames.
        No text names/EPG/XMLTV title can be used as evidence_origin.
        """
        if (source_id != self.king_source_id or
                evidence_origin != "decoded_video" or
                tod_slot(tod_channel) is None or
                bein_logo_number(logo) is None):
            return None
        if not (stream_id or event_id):
            # No identity -> cannot distinguish an event/URL discontinuity.
            return None
        return self.routes.observe("King", tod_channel, logo, confidence,
                                   stream_id=str(stream_id or ""),
                                   event_id=str(event_id or ""),
                                   now=observed_at)

    def stream_or_event_changed(self, *, source_id, tod_channel):
        """Invalidate previous map BEFORE inspecting the new event's logo."""
        if source_id != self.king_source_id:
            return False
        slot = tod_slot(tod_channel)
        if slot is None:
            return False
        self.routes.clear(slot)
        return True

    def resolve_bein(self, *, source_id, bein_channel, now,
                     explicit_manual_lock=False):
        """Return verified temporary TOD assignments; do not persist/lock."""
        if source_id != self.king_source_id or explicit_manual_lock:
            return []
        return self.routes.by_bein("King", bein_channel, now=now)

    def selected_channel(self, *, generation, service_key, now,
                         explicit_human_zap=False):
        if explicit_human_zap:
            self.screen.reset_navigation()
        self.screen.begin(generation, service_key, now)

    def playback_evidence(self, *, generation, now, **evidence):
        """Optional no-picture fallback proposal, never executes a zap."""
        return self.screen.observe(generation, now, **evidence)

    def confirmed_playable(self, *, generation):
        return self.screen.confirmed_playable(generation)
