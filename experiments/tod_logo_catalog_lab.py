#!/usr/bin/env python3
"""TOD V6 read-only catalogue laboratory (NOT A RECEIVER MAPPER).

Audits THREE independent video-only BMPs for each HUMAN-labelled beIN number.
No image recognition claim is made from labels. Accepts either 480x270 or
960x540 captures, one actual resolution per audit. ROIs are defined in the
480x270 coordinate system and *scaled for diagnostics only* at 960x540.

This script NEVER captures video, changes channels, edits locks/settings,
reads provider credentials, uploads pictures, or installs plugins.
The missing 1-10 classes and all cross-number false matches must be resolved
BEFORE production deployment. Even a complete catalogue cannot enable mapping.
"""
import argparse
import hashlib
import json
import os
import struct

MAX_BYTES = 8000000
DIGIT = (449, 21, 454, 26)
BANNER = (404, 19, 456, 30)
NAMES = tuple("frame-%02d.bmp" % n for n in (1, 2, 3))
ALL_CLASSES = frozenset(range(1, 11))


def read_masks(path, digit_rect=DIGIT, banner_rect=BANNER):
    """Read two small pixel masks, without decoding entire BMP into objects."""
    with open(path, "rb") as f:
        raw = f.read(MAX_BYTES + 1)
    if not (54 <= len(raw) <= MAX_BYTES) or raw[:2] != b"BM":
        raise ValueError("missing, oversized or non-BMP screenshot")
    dib = struct.unpack_from("<I", raw, 14)[0]
    off = struct.unpack_from("<I", raw, 10)[0]
    if dib < 40 or len(raw) < 14 + dib or off < dib + 14:
        raise ValueError("invalid BMP header")
    w, signed_h, planes, bpp, compression = struct.unpack_from("<iiHHI", raw, 18)
    h = abs(signed_h)
    if (w, h) not in ((480, 270), (960, 540)) or planes != 1 or \
            bpp not in (24, 32) or compression != 0:
        raise ValueError("only 480x270 or 960x540 raw BMP supported")
    stride = ((w * (bpp // 8)) + 3) & ~3
    if off + stride * h > len(raw):
        raise ValueError("truncated BMP frame")
    step, scale = bpp // 8, w // 480

    def rectangle_mask(rect, mode):
        x0, y0, x1, y1 = rect
        if not (0 <= x0 < x1 <= 480 and 0 <= y0 < y1 <= 270):
            raise ValueError("ROI rectangle outside base 480x270 frame")
        mask = []
        for y in range(y0 * scale, y1 * scale):
            src_y = y if signed_h < 0 else h - 1 - y
            for x in range(x0 * scale, x1 * scale):
                p = off + src_y * stride + x * step
                b, g, r = raw[p:p + 3]
                if mode == "dark":
                    mask.append((r + g + b) / 3.0 < 155)
                else:
                    mask.append(min(r, g, b) >= 218 and
                                max(r, g, b) - min(r, g, b) <= 30)
        return tuple(mask)

    return {
        "size": (w, h),
        "sha": hashlib.sha256(raw).hexdigest(),
        "digit": rectangle_mask(digit_rect, "dark"),
        "banner": rectangle_mask(banner_rect, "white"),
    }


def dice(left, right):
    if len(left) != len(right) or min(sum(left), sum(right)) < 12:
        return 0.
    return 2. * sum(a and b for a, b in zip(left, right)) / float(sum(left) + sum(right))


def hamming(left, right):
    if len(left) != len(right):
        raise ValueError("cannot compare differently-sized logo masks")
    return sum(a != b for a, b in zip(left, right))


def evaluate_label(folder, digit_rect=DIGIT, banner_rect=BANNER):
    """Measure internal repeatability only; does not authenticate label."""
    images = [read_masks(os.path.join(folder, name), digit_rect, banner_rect)
              for name in NAMES]
    sizes = {item["size"] for item in images}
    if len(sizes) != 1:
        raise ValueError("mixed picture resolutions within label")
    independent = len({item["sha"] for item in images}) == 3
    masks = [item["digit"] for item in images]
    banner = [item["banner"] for item in images]
    flips = max(hamming(a, b) for a in masks for b in masks)
    scores = [round(dice(banner[0], b), 4) for b in banner]
    dark_counts = [sum(m) for m in masks]
    area = len(masks[0])
    # Strictly flags the sample as stable, NOT as an accurate broadcaster ID.
    stable = independent and flips == 0 and min(scores) >= .90 and \
        all(5 <= count <= area * .7 for count in dark_counts)
    return {
        "resolution": list(sizes.pop()),
        "capture_count": 3,
        "independent_full_frames": independent,
        "digit_dark_pixels": dark_counts,
        "digit_max_pixel_flips": flips,
        "banner_dice_from_first": scores,
        "internally_stable": bool(stable),
        "_majority_mask": tuple(sum(bits) >= 2 for bits in zip(*masks)),
    }


def audit(samples, digit_rect=DIGIT, banner_rect=BANNER):
    """Return read-only report: ALL possible results keep auto mapping off."""
    if not isinstance(samples, dict) or not samples:
        raise ValueError("at least one human-labelled reference directory needed")
    if any(type(n) is not int or n not in ALL_CLASSES for n in samples):
        raise ValueError("beIN labels must be integers 1-10")
    data = {
        "mode": "OFFLINE_CALIBRATION_AUDIT",
        "source_verified": False,
        "labels_verified_from_video": False,
        "mapping_enabled": False,
        "receiver_changes": False,
        "image_capture_attempted": False,
        "labels_seen": sorted(samples),
        "labels_missing": sorted(ALL_CLASSES - set(samples)),
        "complete_class_set": False,
        "class_separation_verified": False,
        "resolution": None,
        "labels": {},
        "potential_collisions": [],
        "reason": "human-labelled calibration evidence only; no automatic mapping",
    }
    masks = {}
    dimensions = set()
    for number, folder in sorted(samples.items()):
        try:
            if not os.path.isdir(folder):
                raise ValueError("reference directory is unavailable")
            observed = evaluate_label(folder, digit_rect, banner_rect)
            masks[number] = observed.pop("_majority_mask")
            dimensions.add(tuple(observed["resolution"]))
            data["labels"][str(number)] = observed
        except (OSError, ValueError) as exc:
            data["labels"][str(number)] = {"internally_stable": False,
                                          "error": str(exc)}
    if len(dimensions) == 1:
        data["resolution"] = list(dimensions.pop())
    else:
        data["reason"] = "incompatible or missing resolutions across labels"
        return data
    pixel_threshold = 3 if data["resolution"][0] == 480 else 10
    numbers = sorted(masks)
    for i, a in enumerate(numbers):
        for b in numbers[i + 1:]:
            distance = hamming(masks[a], masks[b])
            if distance < pixel_threshold:
                data["potential_collisions"].append(
                    {"labels": [a, b], "numeral_pixel_difference": distance})
    all_stable = all(x.get("internally_stable") for x in data["labels"].values())
    data["complete_class_set"] = len(masks) == 10 and all_stable
    data["class_separation_verified"] = (data["complete_class_set"] and
                                         not data["potential_collisions"])
    data["reason"] = (
        "complete-looking offline shapes still require labelled receiver "
        "validation and independent false-positive tests; auto mapping disabled"
        if data["complete_class_set"] else
        "only %d of 10 labels present/stable; auto mapping disabled"
        % sum(x.get("internally_stable", False) for x in data["labels"].values())
    )
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", action="append", required=True,
                        metavar="NUM=FOLDER", help="one labelled 3-frame folder")
    args = parser.parse_args(argv)
    samples = {}
    for pair in args.sample:
        number, separator, folder = pair.partition("=")
        if not separator or not number.isdigit() or int(number) not in ALL_CLASSES:
            parser.error("--sample must be beIN_number=folder, 1-10")
        if int(number) in samples:
            parser.error("duplicate beIN number")
        samples[int(number)] = folder
    print(json.dumps(audit(samples), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
