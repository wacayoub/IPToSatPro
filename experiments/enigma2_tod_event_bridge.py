"""Opt-in Enigma2 navigation-event bridge for the experimental TOD policy.

No nav.playService, no network scan, no screenshot access, and no changes to
manual locks. Engine callbacks are ADVISORY only. This module is not installed
by the r69-beta package; hardware and video logo calibration are still needed.
"""
import time

from king_tod_router import tod_slot
from tod_dynamic_runtime import DynamicTodController


class Enigma2TodEventBridge:
    """Use real nav.event signals with generation/ref guards.

    context is a receiver-owned callback returning a dict containing:
      source_id, tod_channel, stream_id, event_id (verified from provider).
    Optional: manual_lock, timeshift, recording, backup_available.
    It must never infer the provider from a substring of a channel name.
    events supplies Enigma2 iPlayableService constants; injected in tests.
    """
    def __init__(self, nav, controller, context, on_proposal=None,
                 events=None, clock=None):
        if not isinstance(controller, DynamicTodController):
            raise TypeError("DynamicTodController required")
        if not callable(context):
            raise TypeError("context callback required")
        if events is None:
            from enigma import iPlayableService
            events = iPlayableService
        self.nav = nav
        self.controller = controller
        self.context = context
        self.on_proposal = on_proposal
        self.events = events
        self.clock = clock or time.monotonic
        self.generation = 0
        self._live = None
        self._attached = False

    def attach(self):
        if not self._attached:
            self.nav.event.append(self._event)
            self._attached = True

    def detach(self):
        if self._attached:
            try:
                self.nav.event.remove(self._event)
            except ValueError:
                pass
            self._attached = False
        self._live = None
        self.generation += 1

    def _ref(self):
        try:
            ref = self.nav.getCurrentlyPlayingServiceReference()
            return ref.toString() if ref is not None else ""
        except Exception:
            return ""

    def _ctx(self):
        try:
            ctx = self.context()
            return dict(ctx) if isinstance(ctx, dict) else {}
        except Exception:
            return {}

    def _verified_ctx(self):
        ctx = self._ctx()
        if ctx.get("source_id") != self.controller.king_source_id:
            return None
        if tod_slot(ctx.get("tod_channel")) is None:
            return None
        if not (ctx.get("stream_id") or ctx.get("event_id")):
            return None
        return ctx

    def _current(self):
        item = self._live
        if item is None or self._ref() != item["ref"]:
            return None
        ctx = self._verified_ctx()
        if ctx is None or (ctx.get("source_id"), tod_slot(ctx.get("tod_channel"))) != (
                item["source_id"], item["slot"]):
            return None
        return ctx

    def _invalidate(self, item):
        if item is not None:
            self.controller.stream_or_event_changed(
                source_id=item["source_id"], tod_channel=item["channel"])

    def _event(self, event):
        """Run on Enigma2 navigation event loop; never block or zap."""
        if event == self.events.evStart:
            self._invalidate(self._live)
            self.generation += 1
            self._live = None
            ctx = self._verified_ctx()
            ref = self._ref()
            if ctx is None or not ref:
                return
            self._live = dict(
                ref=ref, source_id=ctx["source_id"],
                channel=ctx["tod_channel"],
                slot=tod_slot(ctx["tod_channel"]),
                identity=(str(ctx.get("stream_id") or ""),
                          str(ctx.get("event_id") or "")),
                generation=self.generation)
            self.controller.selected_channel(
                generation=self.generation, service_key=ref,
                now=self.clock())
        elif event == self.events.evEnd:
            self._invalidate(self._live)
            self._live = None
            self.generation += 1
        elif event == self.events.evUpdatedEventInfo:
            self._check_transition()
        elif event == self.events.evEOF:
            ctx = self._current()
            if ctx is None or ctx.get("timeshift") or ctx.get("recording") or ctx.get("manual_lock"):
                return
            decision = self.controller.playback_evidence(
                generation=self.generation, now=self.clock(),
                stream_eof=True, backup_available=bool(ctx.get("backup_available")),
                auto_skip=bool(ctx.get("allow_auto_skip", False)))
            if decision is not None and callable(self.on_proposal):
                # Owner must reconfirm generation/ref and parental controls.
                self.on_proposal(decision)

    def _check_transition(self):
        item = self._live
        if item is None:
            return False
        ctx = self._current()
        if ctx is None:
            self._invalidate(item)
            self._live = None
            self.generation += 1
            return True
        new_id = (str(ctx.get("stream_id") or ""), str(ctx.get("event_id") or ""))
        if new_id != item["identity"]:
            self._invalidate(item)
            item["identity"] = new_id
            return True
        return False

    def screenshot_token(self):
        """Snapshot BEFORE a screenshot: reject images from a changed event/ref.

        Caller must capture the image in a worker, not on Enigma2's GUI thread.
        The same tuple is rechecked when classified results return to the GUI.
        """
        ctx = self._current()
        if ctx is None or self._live is None:
            return None
        if self._check_transition():
            return None
        return (self._live["ref"], self.generation, ctx["source_id"],
                tod_slot(ctx["tod_channel"]),
                str(ctx.get("stream_id") or ""),
                str(ctx.get("event_id") or ""))

    def classified_video_logo(self, *, number, confidence, capture_ref,
                              capture_generation, observed_at):
        """Consume independent video-only watermark evidence, never EPG text."""
        ctx = self._current()
        if ctx is None or self._live is None:
            return None
        if (capture_generation != self.generation or
                capture_ref != self._live["ref"]):
            return None
        if self._check_transition():
            return None
        return self.controller.verified_video_logo(
            source_id=ctx["source_id"], tod_channel=ctx["tod_channel"],
            logo=number, confidence=confidence,
            stream_id=ctx.get("stream_id", ""),
            event_id=ctx.get("event_id", ""),
            observed_at=observed_at, evidence_origin="decoded_video")
