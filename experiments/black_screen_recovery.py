"""Evidence-driven BLACK SCREEN recovery policy; not a channel blacklist.

No Enigma2 API calls, actual tuner interaction, network I/O, GUI sleeps or disk
writes. The caller MUST pass real decoder/frame evidence tied to the current
zap generation. Calling with missing metrics is safe and cannot skip a channel.
Integrate first in a separate receiver test branch; do not ship automatically.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Decision:
    action: str  # "try_backup" | "next_channel"
    reason: str
    generation: int
    channel: str


class BlackScreenAutoSkip:
    """Recommend a single bounded action when a channel is actually failing.

    Decoder 'no_frames' means a receiver callback/metric PROVED no decoded
    frames, not just missing a video-size event or a short startup delay.
    A truly dark image is NOT necessarily a failure. Pixel-black recovery
    requires several fresh black frames AND independently confirmed no audio.
    Actions are advisory; caller navigates asynchronously and keeps locks.
    """
    def __init__(self, startup_grace=4.0, black_grace=7.0,
                 max_consecutive_skips=3, dark_threshold=0.995):
        if startup_grace < 1 or black_grace < 3 or max_consecutive_skips < 1:
            raise ValueError("unsafe recovery policy")
        self.startup_grace = float(startup_grace)
        self.black_grace = float(black_grace)
        self.max_consecutive_skips = int(max_consecutive_skips)
        self.dark_threshold = float(dark_threshold)
        self.reset_navigation()
        self._active = None

    def reset_navigation(self):
        """Call on an explicit human zap to reset automatic hop budget."""
        self._hops = 0

    def begin(self, generation, channel, now):
        """Begin new playback attempt. Does not blacklist or change mappings."""
        self._active = {
            "generation": int(generation), "channel": str(channel),
            "start": float(now), "last": float(now), "sent": False,
            "dark_since": None, "dark_samples": 0, "last_dark_at": None,
            "had_frame": False, "last_frame_count": 0, "last_frame_at": None,
        }

    def observe(self, generation, now, *, decoded_frames=None,
                decoder_status=None, black_ratio=None, audio_present=None,
                stream_eof=False, backup_available=False, auto_skip=True):
        """Return a proposed action once, or None.

        decoded_frames: monotonically increasing counter from the CURRENT
          decoder, or None if unobservable. Zero alone is insufficient.
        decoder_status: 'no_frames', 'stalled', 'playing', or None.
          'no_frames'/'stalled' must be backed by real receiver decoder status.
        black_ratio: actual pixel-black share 0..1 of a FRESH decoded frame
          (not an old screenshot or an on-screen overlay).
        audio_present: True/False only for independent reliable audio evidence.
          None means unknown. Never equate PID/track metadata with audible sound.
        """
        s = self._active
        if s is None or int(generation) != s["generation"] or s["sent"]:
            return None
        now = float(now)
        if now < s["last"]:
            return None
        s["last"] = now
        frames = decoded_frames if type(decoded_frames) is int and decoded_frames >= 0 else None
        fresh = frames is not None and frames > s["last_frame_count"]
        if fresh:
            s["had_frame"] = True
            s["last_frame_count"] = frames
            s["last_frame_at"] = now
        elapsed = now - s["start"]

        # Only fresh decoder frames can establish a dark image; a screenshot
        # captured while no decoder data exists is not reliable evidence.
        dark_frame = (fresh and
                      isinstance(black_ratio, (int, float)) and
                      self.dark_threshold <= black_ratio <= 1.0 and
                      audio_present is False)
        if dark_frame:
            if s["dark_since"] is None:
                s["dark_since"] = now
            if s["last_dark_at"] is None or now - s["last_dark_at"] >= 0.35:
                s["dark_samples"] += 1
                s["last_dark_at"] = now
        else:
            s["dark_since"] = None
            s["dark_samples"] = 0
            s["last_dark_at"] = None

        reason = None
        if stream_eof and elapsed >= 1.0:
            reason = "stream_eof"
        elif (elapsed >= self.startup_grace and frames == 0 and
              decoder_status == "no_frames"):
            reason = "decoder_no_frames"
        elif (decoder_status == "stalled" and s["had_frame"] and
              s["last_frame_at"] is not None and
              now - s["last_frame_at"] >= self.black_grace and
              audio_present is False):
            reason = "decoder_stalled"
        elif (s["dark_since"] is not None and s["dark_samples"] >= 3 and
              now - s["dark_since"] >= self.black_grace):
            reason = "confirmed_dark_and_silent"

        if reason is None:
            return None
        if backup_available:
            action = "try_backup"
        elif auto_skip and self._hops < self.max_consecutive_skips:
            self._hops += 1
            action = "next_channel"
        else:
            # No endless loop; consume this generation without a forced zap.
            s["sent"] = True
            return None
        s["sent"] = True
        return Decision(action, reason, s["generation"], s["channel"])

    def confirmed_playable(self, generation):
        """A successful real video reset ends consecutive auto-skip cycle."""
        if self._active is None or self._active["generation"] != int(generation):
            return False
        self._hops = 0
        return True
