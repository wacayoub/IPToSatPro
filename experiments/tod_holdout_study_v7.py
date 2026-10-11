#!/usr/bin/env python3
"""V7 TOD offline multi-class HOLDOUT study; NEVER an auto-mapper.

Each explicit numeric label is asserted by a human, NOT detected from IPTV
names, EPG, or filenames. Use only already captured decoded-video BMPs.
Default right-side numeral ROI is field-calibrated only for real beIN 7
(480x270); it is too narrow for beIN 10. Left-side ROI needs independent,
human-verified coordinates. Every outcome is advisory; no navigation, no
network, no screenshot, no plugin write, no mapping.
"""
import argparse
import json
import os

from tod_logo_catalog_lab import ALL_CLASSES, BANNER, DIGIT, NAMES, hamming, read_masks

MAX_MISMATCH = {480: 1, 960: 4}
MIN_MARGIN = {480: 4, 960: 12}


def validated_roi(rect, corner):
    if not (isinstance(rect, (tuple, list)) and len(rect) == 4 and
            all(type(x) is int for x in rect)):
        raise ValueError("ROI must be 4 integer 480-base coordinates")
    x0, y0, x1, y1 = rect
    if not (0 <= x0 < x1 <= 480 and 0 <= y0 < y1 <= 80):
        raise ValueError("logo ROI must stay in top 80 rows")
    if (corner == "right" and x0 < 240 or
            corner == "left" and x1 > 240):
        raise ValueError("ROI must be in selected top corner")
    return tuple(rect)


def study(samples, *, corner="right", digit_roi=None, banner_roi=None):
    if not isinstance(samples, dict) or not samples or any(
            type(n) is not int or n not in ALL_CLASSES for n in samples):
        raise ValueError("number-labelled sample directories required (1-10)")
    if corner not in ("left", "right"):
        raise ValueError("only explicitly selected left/right corner supported")
    if corner == "left" and (digit_roi is None or banner_roi is None):
        raise ValueError("left corner requires independently verified TWO ROIs")
    digit_roi = validated_roi(digit_roi or DIGIT, corner)
    banner_roi = validated_roi(banner_roi or BANNER, corner)
    if not (banner_roi[0] <= digit_roi[0] and
            banner_roi[1] <= digit_roi[1] and
            digit_roi[2] <= banner_roi[2] and
            digit_roi[3] <= banner_roi[3]):
        raise ValueError("digit ROI must be within broadcaster banner ROI")
    result = {
        "mode": "OFFLINE_SHADOW_HOLDOUT_V7",
        "mapping_enabled": False,
        "navigation_enabled": False,
        "receiver_changed": False,
        "capture_attempted": False,
        "labels_authenticated": False,
        "receiver_validated": False,
        "deployment_ready": False,
        "corner": corner,
        "roi_suitable_for_two_digit_10": digit_roi[2] - digit_roi[0] >= 10,
        "present": sorted(samples),
        "missing": sorted(ALL_CLASSES - set(samples)),
        "resolution": None,
        "class_coverage_complete": False,
        "intra_class_stable": False,
        "min_interclass_pixel_distance": None,
        "shape_collision_pairs": [],
        "leave_one_out": {
            "status": "NOT_EVALUATED", "tested": 0, "shape_match": 0,
            "rejected": 0, "mislabelled_as_other": 0,
        },
        "issues": [],
        "note": "A matching SHAPE is not proof of a broadcaster identity",
    }
    frames = {}
    dimensions = set()
    hashes = {}
    for number, folder in sorted(samples.items()):
        try:
            if not os.path.isdir(folder):
                raise ValueError("sample folder unavailable")
            samples_three = [
                read_masks(os.path.join(folder, name), digit_roi, banner_roi)
                for name in NAMES
            ]
            if len({f["size"] for f in samples_three}) != 1:
                raise ValueError("mixed resolutions in class")
            if len({f["sha"] for f in samples_three}) != 3:
                raise ValueError("same class has duplicate complete frames")
            for image in samples_three:
                if image["sha"] in hashes:
                    raise ValueError("a full frame is repeated across two labels")
                hashes[image["sha"]] = number
            dimensions.add(samples_three[0]["size"])
            frames[number] = samples_three
        except (OSError, ValueError) as error:
            result["issues"].append("class %d: %s" % (number, error))
    if len(frames) != len(samples):
        return result
    if len(dimensions) != 1:
        result["issues"].append("mixed resolutions across labelled classes")
        return result
    resolution = dimensions.pop()
    result["resolution"] = list(resolution)
    width = resolution[0]

    def stable_3(three):
        masks = [img["digit"] for img in three]
        banners = [img["banner"] for img in three]
        if max(hamming(a, b) for a in masks for b in masks) != 0:
            return False
        # Weak/empty white watermark is not adequate evidence.
        from tod_logo_catalog_lab import dice
        if min(dice(banners[0], b) for b in banners) < .90:
            return False
        area, count = len(masks[0]), sum(masks[0])
        return 5 <= count <= area * .70

    classes_stable = {n: stable_3(three) for n, three in frames.items()}
    result["intra_class_stable"] = all(classes_stable.values())
    for number, good in sorted(classes_stable.items()):
        if not good:
            result["issues"].append(
                "class %d numeral/banner unstable; cannot train reference" % number)
    if not result["intra_class_stable"]:
        return result

    templates = {number: three[0]["digit"] for number, three in frames.items()}
    pairs = []
    for a in sorted(templates):
        for b in sorted(templates):
            if a >= b:
                continue
            d = hamming(templates[a], templates[b])
            pairs.append(d)
            if d < MIN_MARGIN[width] + MAX_MISMATCH[width]:
                result["shape_collision_pairs"].append({
                    "labels": [a, b],
                    "pixel_difference": d,
                })
    result["min_interclass_pixel_distance"] = min(pairs) if pairs else None
    result["class_coverage_complete"] = set(samples) == ALL_CLASSES
    if not result["class_coverage_complete"]:
        result["leave_one_out"]["status"] = "MISSING_CLASSES_NO_CLASSIFICATION"
        return result
    if result["shape_collision_pairs"]:
        result["leave_one_out"]["status"] = "INSUFFICIENT_INTERCLASS_MARGIN"
        return result

    # Offline sanity study: train on two same-event frames; hold out third.
    # This is NOT an independent future-event validation.
    stats = result["leave_one_out"]
    stats["status"] = "SHAPES_ONLY_NOT_IDENTITY_VALIDATION"
    for number, three in sorted(frames.items()):
        for heldout in range(3):
            train = [three[i]["digit"] for i in range(3) if i != heldout]
            stats["tested"] += 1
            if train[0] != train[1]:
                stats["rejected"] += 1
                continue
            distances = sorted(
                (hamming(train[0], three[heldout]["digit"]), number)
                if label == number else
                (hamming(template, three[heldout]["digit"]), label)
                for label, template in templates.items()
            )
            best, next_best = distances[0], distances[1]
            if (best[0] <= MAX_MISMATCH[width] and
                    next_best[0] - best[0] >= MIN_MARGIN[width]):
                if best[1] == number:
                    stats["shape_match"] += 1
                else:
                    stats["mislabelled_as_other"] += 1
            else:
                stats["rejected"] += 1
    return result


def parse_roi(raw):
    parts = raw.split(",")
    if len(parts) != 4 or any(not part.strip().isdigit() for part in parts):
        raise argparse.ArgumentTypeError("ROI must be x0,y0,x1,y1 integers")
    return tuple(int(x) for x in parts)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sample", action="append", required=True, metavar="N=FOLDER")
    ap.add_argument("--corner", choices=("left", "right"), default="right")
    ap.add_argument("--digit-roi", type=parse_roi)
    ap.add_argument("--banner-roi", type=parse_roi)
    args = ap.parse_args(argv)
    samples = {}
    for v in args.sample:
        num, eq, folder = v.partition("=")
        if not eq or not num.isdigit() or int(num) not in ALL_CLASSES:
            ap.error("sample must be N=FOLDER with 1<=N<=10")
        if int(num) in samples:
            ap.error("duplicate class label")
        samples[int(num)] = folder
    print(json.dumps(study(samples, corner=args.corner,
                           digit_roi=args.digit_roi,
                           banner_roi=args.banner_roi), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
