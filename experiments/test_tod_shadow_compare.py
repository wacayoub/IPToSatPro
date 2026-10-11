"""Synthetic SHADOW-mode regression tests. No real stream access or navigation."""
import os
import tempfile
import unittest

from receiver_tod_capture import bmp_encode
from tod_shadow_compare import compare_sessions, read_rgb_bmp, read_session


DARK_7 = ((1, 0), (2, 0), (3, 0), (3, 1), (2, 2), (2, 3), (2, 4))


def frame(seed=0, number_mask=DARK_7, move_banner=False):
    base = (83 + (seed % 2), 91, 113)
    rows = [[base for x in range(480)] for y in range(270)]
    for y in range(20, 26):
        for x in range(412, 430):
            rows[y][x] = (246, 247, 245)  # stable fake broadcaster banner
    for y in range(21, 26):
        for x in range(449, 454):
            rows[y][x] = (239, 237, 235)
    for x, y in number_mask:
        rows[21 + y][449 + x] = (58, 52, 79)
    if move_banner:
        rows[22][412] = (83, 91, 113)
    rows[150 + (seed % 2)][110 + seed] = (seed + 1, 27, 28)
    return bmp_encode(rows)


class ShadowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ref = os.path.join(self.tmp.name, "ref")
        self.cur = os.path.join(self.tmp.name, "current")
        os.mkdir(self.ref)
        os.mkdir(self.cur)

    def write_three(self, path, mask=DARK_7, seedbase=0, changes=False):
        for i in range(1, 4):
            with open(os.path.join(path, "frame-%02d.bmp" % i), "wb") as out:
                out.write(frame(seed=i+seedbase, number_mask=mask,
                                move_banner=bool(changes and i == 2)))

    def test_three_frames_consistent_with_manual_seven_reference(self):
        self.write_three(self.ref, seedbase=0)
        self.write_three(self.cur, seedbase=10)
        result = compare_sessions(self.ref, self.cur, slot=3, reference_logo=7)
        self.assertEqual(result["classification"], "CONSISTENT_WITH_REFERENCE")
        self.assertEqual(result["tod_slot_user_label"], 3)
        self.assertEqual(result["reference_bein_logo_user_label"], 7)
        self.assertFalse(result["mapping_enabled"])
        self.assertFalse(result["reference_verified_from_frames"])
        self.assertFalse(result["receiver_changes"])
        self.assertEqual(len(result["scores"]), 3)

    def test_altered_number_stays_unknown_even_with_identical_banner(self):
        other = DARK_7[:-1] + ((1, 4),)
        self.write_three(self.ref, seedbase=0)
        self.write_three(self.cur, mask=other, seedbase=10)
        result = compare_sessions(self.ref, self.cur)
        self.assertEqual(result["classification"], "UNKNOWN")
        self.assertFalse(result["mapping_enabled"])
        self.assertEqual(len(result["scores"]), 3)
        self.assertFalse(result["scores"][0]["numeral_mask_same"])

    def test_reused_images_not_a_new_event(self):
        self.write_three(self.ref)
        self.write_three(self.cur)
        result = compare_sessions(self.ref, self.cur)
        self.assertEqual(result["classification"], "UNKNOWN")
        self.assertIn("reuse", result["reason"])

    def test_unstable_reference_never_accepted(self):
        self.write_three(self.ref)
        self.write_three(self.cur, seedbase=10)
        f = os.path.join(self.ref, "frame-03.bmp")
        with open(f, "wb") as out:
            out.write(frame(seed=3, number_mask=DARK_7[:-1]))
        result = compare_sessions(self.ref, self.cur)
        self.assertEqual(result["classification"], "UNKNOWN")
        self.assertIn("numeral not independently stable", result["reason"])
        self.assertGreater(result["reference_health"]["digit_max_pairwise_flips"], 0)
        self.assertTrue(result["current_health"]["numeral_mask_stable"])
        self.assertIn("next_step", result)
        self.assertFalse(result["mapping_enabled"])

    def test_health_report_does_not_change_pass_fail_policy(self):
        self.write_three(self.ref, seedbase=0)
        self.write_three(self.cur, seedbase=20)
        verdict = compare_sessions(self.ref, self.cur)
        for label in ("reference_health", "current_health"):
            health = verdict[label]
            self.assertEqual(len(health["digit_dark_pixels"]), 3)
            self.assertEqual(health["digit_max_pairwise_flips"], 0)
            self.assertEqual(health["digit_flipped_pixels_from_first"], [0, 0, 0])
            self.assertTrue(health["numeral_mask_stable"])
            self.assertEqual(len(health["banner_similarity_from_first"]), 3)
        self.assertEqual(verdict["classification"], "CONSISTENT_WITH_REFERENCE")
        self.assertFalse(verdict["mapping_enabled"])

    def test_only_480_bmp_supported_and_no_partial_results(self):
        self.write_three(self.ref)
        self.write_three(self.cur, seedbase=10)
        with open(os.path.join(self.cur, "frame-02.bmp"), "wb") as out:
            out.write(b"\x89PNG\r\nBAD")
        result = compare_sessions(self.ref, self.cur)
        self.assertEqual(result["classification"], "UNKNOWN")
        self.assertIn("BMP", result["reason"])
        self.assertEqual(result["scores"], [])

    def test_missing_frame_returns_unknown_no_exception(self):
        self.write_three(self.ref)
        self.assertEqual(compare_sessions(self.ref, self.cur)["classification"], "UNKNOWN")

    def test_bad_user_metadata_rejected(self):
        with self.assertRaises(ValueError):
            compare_sessions(self.ref, self.cur, slot=15)
        with self.assertRaises(ValueError):
            compare_sessions(self.ref, self.cur, reference_logo=11)

    def test_matching_is_not_an_assignment(self):
        self.write_three(self.ref)
        self.write_three(self.cur, seedbase=10)
        result = compare_sessions(self.ref, self.cur)
        self.assertNotIn("assignment", result)
        self.assertNotIn("write_mapping", result)
        self.assertEqual(result["classification"], "CONSISTENT_WITH_REFERENCE")


if __name__ == "__main__":
    unittest.main()
