"""Safe/offline regression tests; no real receiver, video or network involved."""
import unittest
from black_screen_recovery import BlackScreenAutoSkip
from tod_dynamic_runtime import DynamicTodController
from king_tod_router import KingTodRouter


class BlackScreenTests(unittest.TestCase):
    def test_missing_telemetry_never_skips(self):
        d = BlackScreenAutoSkip()
        d.begin(1, "beIN 1", 0)
        self.assertIsNone(d.observe(1, 30))
        self.assertIsNone(d.observe(1, 31, decoded_frames=0))
        self.assertIsNone(d.observe(1, 32, decoder_status="no_frames"))
        self.assertIsNone(d.observe(1, 33, black_ratio=1.0, audio_present=False))

    def test_no_video_backups_first_and_once(self):
        d = BlackScreenAutoSkip()
        d.begin(8, "beIN 2", 0)
        self.assertIsNone(d.observe(8, 2, decoded_frames=0, decoder_status="no_frames"))
        a = d.observe(8, 4.5, decoded_frames=0, decoder_status="no_frames",
                      backup_available=True)
        self.assertEqual((a.action, a.reason), ("try_backup", "decoder_no_frames"))
        self.assertIsNone(d.observe(8, 10, stream_eof=True, backup_available=True))

    def test_eof_temporary_next_channel_not_blacklist(self):
        d = BlackScreenAutoSkip(max_consecutive_skips=2)
        for i in range(2):
            d.begin(i, "failed-{}".format(i), i * 3)
            a = d.observe(i, i * 3 + 1.1, stream_eof=True)
            self.assertEqual(a.action, "next_channel")
        d.begin(2, "also failed", 6)
        self.assertIsNone(d.observe(2, 7.1, stream_eof=True))
        d.begin(3, "now working", 9)
        self.assertTrue(d.confirmed_playable(3))
        d.begin(4, "failed again", 12)
        self.assertEqual(d.observe(4, 13.1, stream_eof=True).action, "next_channel")

    def test_dark_scene_audio_protects(self):
        d = BlackScreenAutoSkip()
        d.begin(1, "movie", 0)
        for t, f in [(0, 1), (3, 2), (7, 3), (11, 4)]:
            self.assertIsNone(d.observe(1, t, decoded_frames=f,
                                        black_ratio=1.0, audio_present=True))

    def test_dark_without_audio_requires_fresh_frames(self):
        d = BlackScreenAutoSkip()
        d.begin(1, "black-and-silent", 0)
        self.assertIsNone(d.observe(1, 1, decoded_frames=1,
                                    black_ratio=1.0, audio_present=False))
        # Reused old screenshot/counter does not create a second proof.
        self.assertIsNone(d.observe(1, 5, decoded_frames=1,
                                    black_ratio=1.0, audio_present=False))
        self.assertIsNone(d.observe(1, 6, decoded_frames=2,
                                    black_ratio=1.0, audio_present=False))
        self.assertIsNone(d.observe(1, 10, decoded_frames=3,
                                    black_ratio=1.0, audio_present=False))
        self.assertEqual(d.observe(1, 14, decoded_frames=4,
                                   black_ratio=1.0, audio_present=False).reason,
                         "confirmed_dark_and_silent")

    def test_decoder_stall_and_stale_generation(self):
        d = BlackScreenAutoSkip()
        d.begin(5, "A", 0)
        d.observe(5, 1, decoded_frames=5)
        self.assertIsNone(d.observe(4, 99, stream_eof=True))
        self.assertIsNone(d.observe(5, 3, decoded_frames=5,
                                    decoder_status="stalled", audio_present=False))
        self.assertEqual(d.observe(5, 8.5, decoded_frames=5,
                                   decoder_status="stalled",
                                   audio_present=False).reason, "decoder_stalled")

    def test_human_navigation_resets_hop_budget(self):
        d = DynamicTodController("provider-ID-001")
        d.selected_channel(generation=1, service_key="A", now=0, explicit_human_zap=True)
        for i in range(3):
            d.selected_channel(generation=i+1, service_key=str(i), now=10*i)
            self.assertEqual(d.playback_evidence(generation=i+1, now=10*i+2,
                                                 stream_eof=True).action, "next_channel")
        d.selected_channel(generation=4, service_key="max", now=40)
        self.assertIsNone(d.playback_evidence(generation=4, now=42, stream_eof=True))
        d.selected_channel(generation=5, service_key="user choice", now=50,
                           explicit_human_zap=True)
        self.assertEqual(d.playback_evidence(generation=5, now=52,
                                              stream_eof=True).action, "next_channel")


class DynamicTodTests(unittest.TestCase):
    def test_king_only_and_live_video_required(self):
        s = DynamicTodController("ID-KING")
        for n in range(3):
            self.assertIsNone(s.verified_video_logo(
                source_id="another-source", tod_channel="TOD Sports 3", logo=6,
                confidence=.97, stream_id="u", event_id="ev", observed_at=n,
                evidence_origin="decoded_video"))
            self.assertIsNone(s.verified_video_logo(
                source_id="ID-KING", tod_channel="TOD Sports 3", logo=6,
                confidence=.97, stream_id="u", event_id="ev", observed_at=n,
                evidence_origin="playlist_title"))
        self.assertEqual(s.resolve_bein(source_id="ID-KING", bein_channel=6, now=4), [])

    def test_dynamic_king_3_to_bein6_and_switch8(self):
        s = DynamicTodController("ID-KING", mapping_ttl=60)
        for n in range(3):
            s.verified_video_logo(source_id="ID-KING", tod_channel="TOD SPORTS 3",
                logo="beIN Sports 6", confidence=.96, stream_id="s1", event_id="A",
                observed_at=n, evidence_origin="decoded_video")
        self.assertEqual(s.resolve_bein(source_id="ID-KING", bein_channel=6,
                                         now=4)[0].tod, 3)
        self.assertEqual(s.resolve_bein(source_id="ID-KING", bein_channel=6,
                                         now=4, explicit_manual_lock=True), [])
        self.assertFalse(s.resolve_bein(source_id="other", bein_channel=6, now=4))
        self.assertTrue(s.stream_or_event_changed(source_id="ID-KING",
                                                   tod_channel="TOD SPORTS 3"))
        self.assertFalse(s.resolve_bein(source_id="ID-KING", bein_channel=6, now=5))
        for n in range(3):
            s.verified_video_logo(source_id="ID-KING", tod_channel="TOD SPORTS 3",
                logo="beIN Sports 8", confidence=.96, stream_id="s1", event_id="B",
                observed_at=6+n, evidence_origin="decoded_video")
        self.assertEqual(s.resolve_bein(source_id="ID-KING", bein_channel=8,
                                         now=9)[0].tod, 3)
        self.assertFalse(s.resolve_bein(source_id="ID-KING", bein_channel=8, now=70))

    def test_unknown_watermark_new_event_invalidates(self):
        r = KingTodRouter()
        for n in range(3):
            r.observe("KING", "TOD Sports 3", 6, .95, stream_id="s",
                      event_id="A", now=n)
        self.assertTrue(r.by_bein("KING", 6, now=3))
        self.assertIsNone(r.observe("KING", "TOD Sports 3", None, .0,
                                    stream_id="s", event_id="B", now=4))
        self.assertFalse(r.by_bein("KING", 6, now=5))

    def test_no_identity_and_no_title_inference(self):
        s = DynamicTodController("ID-KING")
        for n in range(3):
            self.assertIsNone(s.verified_video_logo(
                source_id="ID-KING", tod_channel="TOD Sports 3", logo="beIN 6",
                confidence=.99, stream_id="", event_id="", observed_at=n,
                evidence_origin="decoded_video"))
        self.assertFalse(s.resolve_bein(source_id="ID-KING",
                                         bein_channel=6, now=4))


if __name__ == "__main__":
    unittest.main()
