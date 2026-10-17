"""V7 strict SHADOW holdout tests: synthetic frames, NO receiver writes."""
import os
import tempfile
import unittest

from test_tod_logo_catalog_lab import synthetic_bmp
from tod_holdout_study_v7 import study, parse_roi

# Ten deliberately distinct 5x5 binary SHAPES, not actual beIN logos.
BITS = [
    [1, 2, 3, 5, 7, 10, 12, 20, 21, 24],
    [2, 4, 5, 7, 8, 21, 22],
    [0, 3, 4, 7, 14, 19, 20, 23],
    [1, 3, 4, 13, 15, 21, 24],
    [2, 9, 12, 15, 16, 17, 19, 20],
    [3, 5, 6, 9, 13, 18, 19, 20, 21],
    [2, 3, 6, 9, 14, 19, 22, 23],
    [1, 4, 10, 17, 19, 20, 21, 22, 24],
    [1, 3, 4, 10, 13, 17, 18, 19, 23, 24],
    [1, 7, 8, 9, 11, 14, 15, 16, 18, 24],
]


def mask_for(number):
    return tuple((p % 5, p // 5) for p in BITS[number - 1])


def mirror_bmp(raw):
    """Mirror synthetic BMP test picture horizontally; NOT receiver capture."""
    buf = bytearray(raw)
    step = 3
    width, height = 480, 270
    for y in range(height):
        start = 54 + y * width * step
        end = start + width * step
        row = raw[start:end]
        buf[start:end] = b"".join(row[i:i+3] for i in range(
            (width-1)*3, -1, -3))
    return bytes(buf)


class OfflineHoldoutV7Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def make_class(self, number, *, mask=None, width=480, mirrored=False,
                   variant_at=None):
        folder = os.path.join(self.tmp.name, str(number))
        os.mkdir(folder)
        for i in range(1, 4):
            chosen = mask if mask is not None else mask_for(number)
            if i == variant_at:
                chosen = tuple(p for p in chosen if p != chosen[-1])
            image = synthetic_bmp(width, chosen, number*3+i)
            if mirrored:
                image = mirror_bmp(image)
            with open(os.path.join(folder, "frame-%02d.bmp" % i), "wb") as out:
                out.write(image)
        return folder

    def full_set(self, *, collision=False):
        data = {}
        for n in range(1, 11):
            m = mask_for(1) if collision and n == 10 else mask_for(n)
            data[n] = self.make_class(n, mask=m)
        return data

    def test_one_real_style_logo_never_attempts_classification(self):
        report = study({7: self.make_class(7)})
        self.assertEqual(report["present"], [7])
        self.assertEqual(len(report["missing"]), 9)
        self.assertFalse(report["class_coverage_complete"])
        self.assertEqual(report["leave_one_out"]["status"],
                         "MISSING_CLASSES_NO_CLASSIFICATION")
        self.assertFalse(report["mapping_enabled"])
        self.assertFalse(report["navigation_enabled"])
        self.assertFalse(report["deployment_ready"])
        self.assertFalse(report["receiver_validated"])
        self.assertFalse(report["labels_authenticated"])

    def test_ten_classes_reject_narrow_roi_for_channel_10(self):
        result = study(self.full_set())
        self.assertTrue(result["class_coverage_complete"])
        self.assertFalse(result["roi_suitable_for_two_digit_10"])
        self.assertEqual(result["leave_one_out"]["status"],
                         "DIGIT_ROI_TOO_NARROW_FOR_BEIN10")
        self.assertFalse(result["mapping_enabled"])

    def test_ten_synthetic_shapes_held_out_but_never_release_ready(self):
        samples = self.full_set()
        result = study(samples, digit_roi=(446, 21, 456, 26))
        self.assertTrue(result["class_coverage_complete"])
        self.assertTrue(result["intra_class_stable"])
        self.assertTrue(result["roi_suitable_for_two_digit_10"])
        self.assertEqual(result["shape_collision_pairs"], [])
        stats = result["leave_one_out"]
        self.assertEqual(stats["tested"], 30)
        self.assertEqual(stats["shape_match"], 30)
        self.assertEqual(stats["rejected"], 0)
        self.assertEqual(stats["mislabelled_as_other"], 0)
        self.assertEqual(stats["status"], "SHAPES_ONLY_NOT_IDENTITY_VALIDATION")
        self.assertFalse(result["mapping_enabled"])
        self.assertFalse(result["labels_authenticated"])
        self.assertFalse(result["receiver_validated"])
        self.assertFalse(result["deployment_ready"])

    def test_ten_labels_cannot_hide_identical_numeral_masks(self):
        result = study(self.full_set(collision=True),
                       digit_roi=(446, 21, 456, 26))
        self.assertTrue(result["class_coverage_complete"])
        self.assertTrue(result["shape_collision_pairs"])
        self.assertIn({"labels": [1, 10], "pixel_difference": 0},
                      result["shape_collision_pairs"])
        self.assertEqual(result["leave_one_out"]["status"],
                         "INSUFFICIENT_INTERCLASS_MARGIN")
        self.assertFalse(result["mapping_enabled"])

    def test_one_flicker_prevents_holdout_training(self):
        folders = self.full_set()
        # Same class label, slight in-event numeral inconsistency.
        path = folders[8]
        bmp = synthetic_bmp(480, mask_for(8)[:-1], 8*3+2)
        with open(os.path.join(path, "frame-02.bmp"), "wb") as out:
            out.write(bmp)
        result = study(folders, digit_roi=(446, 21, 456, 26))
        self.assertFalse(result["intra_class_stable"])
        self.assertEqual(result["leave_one_out"]["tested"], 0)
        self.assertFalse(result["deployment_ready"])

    def test_no_left_guessed_position_without_independent_roi(self):
        samples = {7: self.make_class(7, mirrored=True)}
        with self.assertRaises(ValueError):
            study(samples, corner="left")
        result = study(samples, corner="left",
                       digit_roi=(26, 21, 31, 26),
                       banner_roi=(24, 19, 76, 30))
        self.assertTrue(result["intra_class_stable"])
        self.assertEqual(result["corner"], "left")
        self.assertFalse(result["deployment_ready"])
        self.assertEqual(result["leave_one_out"]["status"],
                         "MISSING_CLASSES_NO_CLASSIFICATION")

    def test_wrong_corner_and_invalid_roi_fail(self):
        s = {7: self.make_class(7)}
        with self.assertRaises(ValueError):
            study(s, corner="left",
                  digit_roi=(449, 21, 454, 26),
                  banner_roi=(404, 19, 456, 30))
        with self.assertRaises(ValueError):
            study(s, corner="right",
                  digit_roi=(444, 22, 456, 31))
        with self.assertRaises(ValueError):
            study(s, corner="right", digit_roi=(449, 0, 470, 82))
        with self.assertRaises(ValueError):
            study(s, corner="middle")

    def test_same_full_frame_used_for_two_labels_rejected(self):
        s = {6: self.make_class(6), 7: self.make_class(7)}
        original = open(os.path.join(s[6], "frame-01.bmp"), "rb").read()
        with open(os.path.join(s[7], "frame-01.bmp"), "wb") as out:
            out.write(original)
        data = study(s)
        self.assertTrue(any("repeated across two labels" in x
                            for x in data["issues"]))
        self.assertFalse(data["mapping_enabled"])

    def test_mixed_resolutions_refuse(self):
        s = {6: self.make_class(6), 7: self.make_class(7, width=960)}
        report = study(s)
        self.assertTrue(any("mixed resolutions" in x for x in report["issues"]))
        self.assertIsNone(report["resolution"])
        self.assertFalse(report["deployment_ready"])

    def test_corrupt_image_fails_no_autorouting(self):
        s = {7: self.make_class(7)}
        with open(os.path.join(s[7], "frame-02.bmp"), "wb") as f:
            f.write(b"broken")
        d = study(s)
        self.assertEqual(d["leave_one_out"]["tested"], 0)
        self.assertTrue(d["issues"])
        self.assertFalse(d["mapping_enabled"])

    def test_roi_parser_and_invalid_class_metadata(self):
        self.assertEqual(parse_roi("449,21,454,26"), (449, 21, 454, 26))
        with self.assertRaises(Exception):
            parse_roi("449;21;454;26")
        with self.assertRaises(ValueError):
            study({11: self.tmp.name})
        with self.assertRaises(ValueError):
            study({"7": self.tmp.name})
        with self.assertRaises(ValueError):
            study({})


if __name__ == "__main__":
    unittest.main()
