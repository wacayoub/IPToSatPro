"""TOD V8 regression: cross-event-like synthetic frames, NEVER receiver tests."""
import os
import tempfile
import unittest

from test_tod_logo_catalog_lab import synthetic_bmp
from test_tod_holdout_study_v7 import mask_for
from tod_cross_session_v8 import validate_two_sessions

# Wider ROI contains the entire fictional test numeral; field calibration
# for true beIN Sports 10 is not established by this synthetic coordinate.
WIDE = (446, 21, 456, 26)


class V8OfflineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.refs, self.tests = {}, {}

    def _folder(self, label, role, shape_label=None, width=480, duplicate=False):
        dirname = os.path.join(self.temp.name, "%s-%d" % (role, label))
        os.makedirs(dirname)
        for i in range(1, 4):
            seed = 10 + label * 4 + i if role == "ref" else 80 + label * 4 + i
            if duplicate:
                seed = 10 + label * 4 + i
            data = synthetic_bmp(
                width, mask_for(shape_label or label), seed=seed)
            with open(os.path.join(dirname, "frame-%02d.bmp" % i), "wb") as f:
                f.write(data)
        return dirname

    def _full(self, *, wrong_shape=None, unknown_shape=None,
              duplicate=None, mixed=None):
        for label in range(1, 11):
            self.refs[label] = self._folder(label, "ref")
            shape = label
            if wrong_shape == label:
                shape = 8 if label == 7 else 7
            if unknown_shape == label:
                shape = None
            self.tests[label] = self._folder(
                label, "test", shape_label=shape,
                duplicate=(duplicate == label),
                width=960 if mixed == label else 480)
        if unknown_shape:
            # Use all-on numeral pixels (almost solid 5x5), > threshold
            root = self.tests[unknown_shape]
            solid = tuple((i % 5, i // 5) for i in range(25))
            for i in range(1, 4):
                seed = 80 + unknown_shape * 4 + i
                with open(os.path.join(root, "frame-%02d.bmp" % i), "wb") as f:
                    f.write(synthetic_bmp(480, solid, seed))
        return self.refs, self.tests

    def test_partial_catalog_refuses_any_broadcast_claim(self):
        refs = {7: self._folder(7, "ref")}
        held = {7: self._folder(7, "test")}
        output = validate_two_sessions(refs, held)
        self.assertEqual(output["status"], "MISSING_REAL_CLASSES")
        self.assertEqual(output["totals"]["heldout_frames"], 0)
        self.assertEqual(len(output["missing_reference_labels"]), 9)
        self.assertFalse(output["mapping_enabled"])
        self.assertFalse(output["deployment_ready"])

    def test_full_catalog_too_narrow_for_two_digit_bein10(self):
        refs, held = self._full()
        output = validate_two_sessions(refs, held)
        self.assertEqual(output["status"],
                         "TWO_DIGIT_BEIN10_NEEDS_WIDER_VERIFIED_ROI")
        self.assertFalse(output["receiver_validated"])

    def test_full_catalog_independent_synthetic_sessions(self):
        refs, held = self._full()
        output = validate_two_sessions(refs, held, digit_roi=WIDE)
        self.assertEqual(output["status"],
                         "OFFLINE_SHAPES_EVALUATED_NOT_RECEIVER_VALIDATED")
        self.assertEqual(output["totals"], {
            "actual_labels": 10, "heldout_frames": 30,
            "correct_shapes": 30, "wrong_shapes": 0, "abstained": 0
        })
        self.assertEqual(output["confusion"]["7"]["predicted"], [7, 7, 7])
        for key in ("mapping_enabled", "deployment_ready", "receiver_validated",
                    "receiver_modified", "capture_attempted", "source_id_read"):
            self.assertFalse(output[key])

    def test_wrong_human_label_detected_as_confusion_not_silent_match(self):
        refs, held = self._full(wrong_shape=7)
        result = validate_two_sessions(refs, held, digit_roi=WIDE)
        self.assertEqual(result["status"],
                         "OFFLINE_SHAPES_EVALUATED_NOT_RECEIVER_VALIDATED")
        self.assertEqual(result["confusion"]["7"]["predicted"], [8, 8, 8])
        self.assertEqual(result["totals"]["wrong_shapes"], 3)
        self.assertFalse(result["mapping_enabled"])

    def test_unseen_numeral_abstains_without_guess(self):
        refs, held = self._full(unknown_shape=7)
        result = validate_two_sessions(refs, held, digit_roi=WIDE)
        self.assertEqual(result["confusion"]["7"]["predicted"], [None]*3)
        self.assertEqual(result["totals"]["abstained"], 3)
        self.assertFalse(result["mapping_enabled"])

    def test_repeated_across_sessions_never_means_independence(self):
        refs, held = self._full()
        # Reuse EXACT same full bitmaps, not only matching watermark shape.
        for i in range(1, 4):
            name = "frame-%02d.bmp" % i
            content = open(os.path.join(refs[7], name), "rb").read()
            with open(os.path.join(held[7], name), "wb") as f:
                f.write(content)
        data = validate_two_sessions(refs, held, digit_roi=WIDE)
        self.assertEqual(data["status"], "REFERENCE_OR_HOLDOUT_INVALID")
        self.assertIn("reused full frame", " ".join(data["issues"]))
        self.assertEqual(data["totals"]["heldout_frames"], 0)

    def test_mixed_480_and_960_never_scored(self):
        refs, held = self._full(mixed=7)
        output = validate_two_sessions(refs, held, digit_roi=WIDE)
        self.assertEqual(output["status"], "MIXED_RESOLUTIONS")
        self.assertFalse(output["mapping_enabled"])

    def test_left_requires_two_independent_rois(self):
        with self.assertRaises(ValueError):
            validate_two_sessions({}, {}, corner="left")
        with self.assertRaises(ValueError):
            validate_two_sessions({}, {}, corner="left",
                                  digit_roi=(449, 21, 454, 26),
                                  banner_roi=(404, 19, 456, 30))
        with self.assertRaises(ValueError):
            validate_two_sessions({}, {}, corner="middle")

    def test_class_label_validation_and_missing_frames(self):
        with self.assertRaises(ValueError):
            validate_two_sessions({11: "/tmp"}, {})
        with self.assertRaises(ValueError):
            validate_two_sessions({"7": "/tmp"}, {})
        refs, held = self._full()
        os.unlink(os.path.join(held[4], "frame-02.bmp"))
        verdict = validate_two_sessions(refs, held, digit_roi=WIDE)
        self.assertEqual(verdict["status"], "REFERENCE_OR_HOLDOUT_INVALID")
        self.assertFalse(verdict["receiver_modified"])


if __name__ == "__main__":
    unittest.main()
