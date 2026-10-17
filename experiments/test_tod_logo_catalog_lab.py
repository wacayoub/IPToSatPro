"""V6 offline laboratory tests. No tuner, settings, IPTV network or mapping."""
import os
import struct
import tempfile
import unittest

from tod_logo_catalog_lab import audit, read_masks, evaluate_label


MASK7 = ((1, 0), (2, 0), (3, 0), (3, 1), (2, 2), (2, 3), (2, 4))
MASK6 = ((1, 0), (2, 0), (3, 0), (3, 1), (2, 2), (2, 3), (1, 4))


def synthetic_bmp(width=480, mask=MASK7, seed=0, top_down=False, bpp=24):
    height = width * 9 // 16
    scale = width // 480
    depth = bpp // 8
    stride = ((width * depth) + 3) & ~3
    rows = [bytearray(b"\x49\x55\x61" * width if bpp == 24 else
                      b"\x49\x55\x61\xff" * width) for _ in range(height)]

    def pixel(x, y, red, green, blue):
        p = x * depth
        rows[y][p:p + depth] = (bytes((blue, green, red)) if bpp == 24 else
                                bytes((blue, green, red, 200)))

    for y in range(20 * scale, 26 * scale):
        for x in range(412 * scale, 430 * scale):
            pixel(x, y, 247, 246, 247)
    for y in range(21 * scale, 26 * scale):
        for x in range(449 * scale, 454 * scale):
            pixel(x, y, 239, 237, 235)
    for dx, dy in mask:
        for yy in range((21 + dy) * scale, (22 + dy) * scale):
            for xx in range((449 + dx) * scale, (450 + dx) * scale):
                pixel(xx, yy, 58, 52, 79)
    pixel(seed + 5, 180 * scale, 13, 20, 40)
    data = b"".join(rows if top_down else reversed(rows))
    return (b"BM" + struct.pack("<IHHI", 54 + len(data), 0, 0, 54) +
            struct.pack("<IiiHHIIiiII", 40, width,
                        -height if top_down else height,
                        1, bpp, 0, len(data), 0, 0, 0, 0) + data)


class LogoCatalogLabTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def folder(self, name, width=480, mask=MASK7, top_down=False, bpp=24,
               variant_at=None):
        root = os.path.join(self.tmp.name, name)
        os.mkdir(root)
        for i in range(1, 4):
            selected = mask if i != variant_at else MASK6
            with open(os.path.join(root, "frame-%02d.bmp" % i), "wb") as f:
                f.write(synthetic_bmp(width, selected, i,
                                      top_down=top_down, bpp=bpp))
        return root

    def test_realistic_label7_stability_but_no_mapping(self):
        folder = self.folder("seven")
        item = evaluate_label(folder)
        self.assertTrue(item["internally_stable"])
        self.assertEqual(item["digit_dark_pixels"], [7, 7, 7])
        self.assertEqual(item["digit_max_pixel_flips"], 0)
        self.assertEqual(item["hd_mixed_2x2_mask_blocks"], [None, None, None])
        data = audit({7: folder})
        self.assertEqual(data["resolution"], [480, 270])
        self.assertEqual(data["labels_seen"], [7])
        self.assertIn(10, data["labels_missing"])
        self.assertFalse(data["complete_class_set"])
        self.assertFalse(data["class_separation_verified"])
        self.assertFalse(data["mapping_enabled"])
        self.assertFalse(data["labels_verified_from_video"])
        self.assertFalse(data["receiver_changes"])
        self.assertFalse(data["image_capture_attempted"])

    def test_HD_960_32bit_top_down_bmp_supported_diagnostic_only(self):
        folder = self.folder("hd", 960, top_down=True, bpp=32)
        observed = evaluate_label(folder)
        self.assertEqual(observed["resolution"], [960, 540])
        self.assertEqual(observed["digit_dark_pixels"], [28, 28, 28])
        self.assertEqual(observed["digit_max_pixel_flips"], 0)
        self.assertEqual(observed["hd_mixed_2x2_mask_blocks"], [0, 0, 0])
        self.assertTrue(observed["internally_stable"])
        summary = audit({7: folder})
        self.assertEqual(summary["resolution"], [960, 540])
        self.assertFalse(summary["mapping_enabled"])

    def test_native_hd_like_subpixel_edges_reported_not_identified(self):
        folder = self.folder("native", 960)
        for i in range(1, 4):
            path = os.path.join(folder, "frame-%02d.bmp" % i)
            data = bytearray(open(path, "rb").read())
            # 960x540, bottom-up, 24bpp; alter one dark pixel of a
            # previously uniformly white 2x2 cell inside the digit ROI.
            w, h = 960, 540
            x, y = 449 * 2, 21 * 2
            offset = 54 + (h - 1 - y) * (w * 3) + x * 3
            data[offset:offset + 3] = b"\x10\x10\x10"
            with open(path, "wb") as out:
                out.write(data)
        item = evaluate_label(folder)
        self.assertEqual(item["resolution"], [960, 540])
        self.assertEqual(item["hd_mixed_2x2_mask_blocks"], [1, 1, 1])
        self.assertTrue(item["internally_stable"])
        self.assertFalse(audit({7: folder})["mapping_enabled"])

    def test_one_pixel_logo_change_refuses_stable_reference(self):
        folder = self.folder("flicker", variant_at=2)
        result = audit({7: folder})
        self.assertFalse(result["labels"]["7"]["internally_stable"])
        self.assertGreater(result["labels"]["7"]["digit_max_pixel_flips"], 0)
        self.assertFalse(result["mapping_enabled"])

    def test_collision_two_human_labels_same_logo_mask(self):
        seven = self.folder("seven")
        six = self.folder("six")
        result = audit({6: six, 7: seven})
        self.assertIn({"labels": [6, 7], "numeral_pixel_difference": 0},
                      result["potential_collisions"])
        self.assertFalse(result["class_separation_verified"])

    def test_mixed_480_and_960_fail_closed(self):
        low = self.folder("low")
        high = self.folder("high", 960)
        result = audit({6: low, 7: high})
        self.assertIsNone(result["resolution"])
        self.assertIn("incompatible", result["reason"])
        self.assertFalse(result["mapping_enabled"])

    def test_malformed_images_fail_as_label_errors(self):
        folder = self.folder("broken")
        with open(os.path.join(folder, "frame-02.bmp"), "wb") as f:
            f.write(b"invalid")
        result = audit({7: folder})
        self.assertIn("non-BMP", result["labels"]["7"]["error"])
        self.assertFalse(result["mapping_enabled"])
        self.assertIsNone(result["resolution"])

    def test_invalid_labels_rejected(self):
        with self.assertRaises(ValueError):
            audit({})
        with self.assertRaises(ValueError):
            audit({11: self.tmp.name})
        with self.assertRaises(ValueError):
            audit({"7": self.tmp.name})

    def test_duplicate_full_screens_dont_count_as_independent(self):
        folder = self.folder("duplicate")
        original = open(os.path.join(folder, "frame-01.bmp"), "rb").read()
        for i in (2, 3):
            with open(os.path.join(folder, "frame-%02d.bmp" % i), "wb") as f:
                f.write(original)
        result = audit({7: folder})
        self.assertFalse(result["labels"]["7"]["internally_stable"])
        self.assertFalse(result["labels"]["7"]["independent_full_frames"])
        self.assertFalse(result["mapping_enabled"])


if __name__ == "__main__":
    unittest.main()
