#!/usr/bin/env python3
"""V8: offline, CROSS-SESSION validation of TOD broadcaster numeral masks.

Exactly two *separately captured* sessions (reference and holdout) of three
independent BMP frames each, per HUMAN-verified beIN Sports 1..10. Never use
playlist names/EPG as ground truth. Repeating three frames within a single
event is NOT a real cross-event benchmark. Different events must be manually
confirmed: BMP digests alone do not establish event identity.

This module only READS pre-existing local BMP files. No nav, screenshot, tuner,
network, credentials, mapping, plugin settings, or automatic routing. Always
keeps deployment_ready=False, even for excellent shape-only statistics.
"""
import argparse
import json
import os

from tod_logo_catalog_lab import ALL_CLASSES, NAMES, read_masks, dice, hamming
from tod_holdout_study_v7 import DIGIT, BANNER, validated_roi, parse_roi, \
    MAX_MISMATCH, MIN_MARGIN


def _validate_session(folder, digit_roi, banner_roi):
    if not isinstance(folder, str) or not os.path.isdir(folder):
        raise ValueError("missing private frame folder")
    images = [read_masks(os.path.join(folder, n), digit_roi, banner_roi)
              for n in NAMES]
    if len({item["sha"] for item in images}) != 3:
        raise ValueError("duplicate full frames in same session")
    sizes = {item["size"] for item in images}
    if len(sizes) != 1:
        raise ValueError("mixed resolution in same session")
    digits = [item["digit"] for item in images]
    banners = [item["banner"] for item in images]
    flips = max(hamming(a, b) for a in digits for b in digits)
    similarity = min(dice(banners[0], b) for b in banners)
    # Training and held-out clusters MUST be internally stable. One pixel
    # flicker is not enough to assert a different number or auto-match.
    if flips != 0 or similarity < .88 or sum(digits[0]) < 5:
        raise ValueError("unstable numeral or broadcaster banner")
    return images


def validate_two_sessions(reference, holdout, *,
                          corner="right", digit_roi=None, banner_roi=None):
    """Pure diagnostic: cross-session confusion matrix, never deployment."""
    if corner not in ("left", "right"):
        raise ValueError("invalid upper corner")
    if corner == "left" and (digit_roi is None or banner_roi is None):
        raise ValueError("left corner requires TWO manually verified ROIs")
    digit_roi = validated_roi(digit_roi or DIGIT, corner)
    banner_roi = validated_roi(banner_roi or BANNER, corner)
    if not (banner_roi[0] <= digit_roi[0] and
            banner_roi[1] <= digit_roi[1] and
            digit_roi[2] <= banner_roi[2] and
            digit_roi[3] <= banner_roi[3]):
        raise ValueError("numeral must fit inside the banner ROI")
    if not isinstance(reference, dict) or not isinstance(holdout, dict):
        raise ValueError("reference and holdout dictionaries required")
    if any(type(k) is not int or k not in ALL_CLASSES
           for k in list(reference) + list(holdout)):
        raise ValueError("only human-labelled 1-10 beIN logos accepted")
    report = {
        "mode": "TOD_V8_CROSS_SESSION_SHADOW_ONLY",
        "mapping_enabled": False,
        "deployment_ready": False,
        "receiver_validated": False,
        "human_event_identity_not_machine_verified": True,
        "receiver_modified": False,
        "capture_attempted": False,
        "source_id_read": False,
        "labels_used": sorted(set(reference) & set(holdout)),
        "missing_reference_labels": sorted(ALL_CLASSES - set(reference)),
        "missing_holdout_labels": sorted(ALL_CLASSES - set(holdout)),
        "corner": corner,
        "resolution": None,
        "status": "UNKNOWN",
        "confusion": {},
        "totals": {
            "actual_labels": 0, "heldout_frames": 0,
            "correct_shapes": 0, "wrong_shapes": 0, "abstained": 0,
        },
        "issues": [],
        "note": "Shapes only; no on-air identity accuracy can be claimed",
    }
    if set(reference) != ALL_CLASSES or set(holdout) != ALL_CLASSES:
        report["status"] = "MISSING_REAL_CLASSES"
        return report
    if digit_roi[2] - digit_roi[0] < 10:
        report["status"] = "TWO_DIGIT_BEIN10_NEEDS_WIDER_VERIFIED_ROI"
        return report
    train, test, all_hashes = {}, {}, set()
    dimensions = set()
    for label in sorted(ALL_CLASSES):
        try:
            a = _validate_session(reference[label], digit_roi, banner_roi)
            b = _validate_session(holdout[label], digit_roi, banner_roi)
            hashes = [item["sha"] for item in a + b]
            if any(h in all_hashes for h in hashes) or len(set(hashes)) != 6:
                raise ValueError("reused full frame across sessions or labels")
            all_hashes.update(hashes)
            train[label], test[label] = a, b
            dimensions.update(item["size"] for item in a + b)
        except (OSError, ValueError) as error:
            report["issues"].append("label %d: %s" % (label, error))
    if len(train) != 10:
        report["status"] = "REFERENCE_OR_HOLDOUT_INVALID"
        return report
    if len(dimensions) != 1:
        report["issues"].append("480/960 or other resolution mixed")
        report["status"] = "MIXED_RESOLUTIONS"
        return report
    width, height = dimensions.pop()
    report["resolution"] = [width, height]
    templates = {label: samples[0]["digit"] for label, samples in train.items()}
    collisions = []
    for n in sorted(templates):
        for m in sorted(templates):
            if m <= n:
                continue
            d = hamming(templates[n], templates[m])
            if d < MAX_MISMATCH[width] + MIN_MARGIN[width]:
                collisions.append({"labels": [n, m], "pixels_different": d})
    report["collisions"] = collisions
    if collisions:
        report["status"] = "TRAINING_LOGOS_TOO_SIMILAR"
        return report
    for actual, samples in sorted(test.items()):
        report["confusion"][str(actual)] = {
            "correct_shape": 0, "wrong_shape": 0, "abstain": 0,
            "predicted": [],
        }
        report["totals"]["actual_labels"] += 1
        for frame in samples:
            report["totals"]["heldout_frames"] += 1
            ordered = sorted((hamming(frame["digit"], shape), label)
                             for label, shape in templates.items())
            best, second = ordered[0], ordered[1]
            banner = max(dice(frame["banner"], t["banner"]) for t in train[best[1]])
            allowed = (
                best[0] <= MAX_MISMATCH[width] and
                second[0] - best[0] >= MIN_MARGIN[width] and
                banner >= .88
            )
            chosen = best[1] if allowed else None
            row = report["confusion"][str(actual)]
            row["predicted"].append(chosen)
            if chosen is None:
                row["abstain"] += 1
                report["totals"]["abstained"] += 1
            elif chosen == actual:
                row["correct_shape"] += 1
                report["totals"]["correct_shapes"] += 1
            else:
                row["wrong_shape"] += 1
                report["totals"]["wrong_shapes"] += 1
    # No stats may unlock receiver, no matter how excellent.
    report["status"] = "OFFLINE_SHAPES_EVALUATED_NOT_RECEIVER_VALIDATED"
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", action="append", required=True,
                        help="NUM=existing reference folder")
    parser.add_argument("--holdout", action="append", required=True,
                        help="NUM=existing separate-event holdout folder")
    parser.add_argument("--corner", choices=("left", "right"), default="right")
    parser.add_argument("--digit-roi", type=parse_roi)
    parser.add_argument("--banner-roi", type=parse_roi)
    args = parser.parse_args(argv)

    def parse_pairs(inputs):
        pairs = {}
        for item in inputs:
            number, equals, path = item.partition("=")
            if not equals or not number.isdigit() or int(number) not in ALL_CLASSES or not path:
                parser.error("expected NUM=FOLDER for beIN Sports 1..10")
            if int(number) in pairs:
                parser.error("duplicate number")
            pairs[int(number)] = path
        return pairs

    result = validate_two_sessions(parse_pairs(args.reference),
                                   parse_pairs(args.holdout),
                                   corner=args.corner,
                                   digit_roi=args.digit_roi,
                                   banner_roi=args.banner_roi)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
