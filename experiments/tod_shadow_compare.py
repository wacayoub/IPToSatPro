#!/usr/bin/env python3
"""Offline TOD SHADOW comparator: never routes, zaps, writes a mapping or installs.

A reference session MUST be human-labelled from the actual on-air logo.
Given 3 BMPs from that session and 3 BMPs from a subsequent session, say only
whether the new logo looks CONSISTENT WITH the reference image.

A match is NOT a verified beIN identification: at 480px the broadcaster number
is only ~5x5 pixels; this tool cannot distinguish all beIN 1-10 variants.
A 7-only reference MUST NEVER become an automatic TOD -> beIN assignment.
This compares two EXPLICIT local directories; never scans other TV channels.
"""
import argparse
import hashlib
import json
import os
import struct

BANNER = (404, 19, 456, 30)    # 480x270 observed beIN logo, upper-right only
DIGIT = (449, 21, 454, 26)     # inner numeral, 5x5px; NOT sufficient for routing
FRAMES = tuple("frame-%02d.bmp" % i for i in (1, 2, 3))
MAX_BMP = 8000000


def read_rgb_bmp(filename):
    with open(filename, "rb") as f:
        data = f.read(MAX_BMP + 1)
    if not 54 <= len(data) <= MAX_BMP or data[:2] != b"BM":
        raise ValueError("not a supported small BMP")
    dib = struct.unpack_from("<I", data, 14)[0]
    off = struct.unpack_from("<I", data, 10)[0]
    if dib < 40 or off < dib + 14 or len(data) < dib + 14:
        raise ValueError("unsupported BMP header")
    width, height, planes, bpp, compress = struct.unpack_from("<iiHHI", data, 18)
    if (width != 480 or abs(height) != 270 or planes != 1 or
            bpp not in (24, 32) or compress != 0):
        raise ValueError("shadow reference requires exactly 480x270 BMP")
    stride = ((width * (bpp // 8)) + 3) & ~3
    if off + stride * abs(height) > len(data):
        raise ValueError("truncated BMP")
    step = bpp // 8

    def pixels(rect):
        x0, y0, x1, y1 = rect
        for y in range(y0, y1):
            src = y if height < 0 else 269 - y
            for x in range(x0, x1):
                p = off + src * stride + x * step
                yield (data[p + 2], data[p + 1], data[p])
    whites = tuple(min(rgb) >= 218 and max(rgb) - min(rgb) <= 30
                   for rgb in pixels(BANNER))
    digit = tuple(sum(rgb) / 3.0 < 155 for rgb in pixels(DIGIT))
    return dict(whites=whites, digit=digit,
                hash=hashlib.sha256(data).hexdigest(),
                white_count=sum(whites), digit_count=sum(digit))


def dice(a, b):
    if len(a) != len(b):
        return 0.0
    count_a, count_b = sum(a), sum(b)
    if min(count_a, count_b) < 12:
        return 0.0
    return 2.0 * sum(x and y for x, y in zip(a, b)) / float(count_a + count_b)


def read_session(folder):
    """Read ONLY three fixed names; never expose paths or stream identifiers."""
    if not os.path.isdir(folder):
        raise ValueError("session directory not accessible")
    images = []
    for name in FRAMES:
        f = os.path.join(folder, name)
        if not os.path.isfile(f):
            raise ValueError("missing expected screenshot " + name)
        images.append(read_rgb_bmp(f))
    if len(set(i["hash"] for i in images)) != 3:
        raise ValueError("3 independent full-frame captures required")
    return images


def compare_sessions(reference, sample, *, slot=3, reference_logo=7):
    """Return an offline conservative RESULT; never a routing Assignment."""
    if type(slot) is not int or not 1 <= slot <= 14:
        raise ValueError("TOD slot must be 1-14")
    if type(reference_logo) is not int or not 1 <= reference_logo <= 10:
        raise ValueError("human-labelled beIN number must be 1-10")
    outcome = {
        "mode": "SHADOW_ONLY",
        "tod_slot_user_label": slot,
        "reference_bein_logo_user_label": reference_logo,
        "mapping_enabled": False,
        "receiver_changes": False,
        "reference_verified_from_frames": False,
        "classification": "UNKNOWN",
        "reason": "insufficient or incompatible image evidence",
        "scores": [],
    }
    try:
        references = read_session(reference)
        samples = read_session(sample)
    except (OSError, ValueError) as exc:
        outcome["reason"] = str(exc)
        return outcome

    if set(item["hash"] for item in references) & set(item["hash"] for item in samples):
        outcome["reason"] = "reference and current reuse identical full screenshots"
        return outcome

    # Reject poorly marked/ambiguous references rather than learning a wrong
    # number from the label alone. 5x5 at 480px remains a fragile signal.
    ref_digit = references[0]["digit"]
    if not (5 <= sum(ref_digit) <= 17 and
            all(other["digit"] == ref_digit for other in references)):
        outcome["reason"] = "reference numeral not independently stable"
        return outcome
    if any(dice(references[0]["whites"], r["whites"]) < .88
           for r in references[1:]):
        outcome["reason"] = "reference broadcaster banner not stable"
        return outcome
    good = True
    for snap in samples:
        banner_score = dice(references[0]["whites"], snap["whites"])
        digit_equal = snap["digit"] == ref_digit
        outcome["scores"].append({
            "banner_dice": round(banner_score, 4),
            "numeral_mask_same": digit_equal,
            "banner_pixels": snap["white_count"],
            "numeral_dark_pixels": snap["digit_count"],
        })
        if banner_score < .88 or not digit_equal:
            good = False
    if good:
        outcome["classification"] = "CONSISTENT_WITH_REFERENCE"
        outcome["reason"] = (
            "3 frames have matching tiny numeral masks and stable broadcaster "
            "banner; this is NOT a cross-number beIN identification")
    else:
        outcome["reason"] = (
            "logo/image changed or uncertain; no conclusion about new beIN number")
    return outcome


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reference", required=True, help="folder with 3 labelled captures")
    p.add_argument("--current", required=True, help="folder with 3 new captures")
    p.add_argument("--slot", type=int, default=3)
    p.add_argument("--reference-logo", type=int, default=7)
    args = p.parse_args(argv)
    # No filesystem mutation; JSON contains no IPTV URLs, IDs or credentials.
    result = compare_sessions(
        args.reference, args.current,
        slot=args.slot, reference_logo=args.reference_logo)
    print(json.dumps(result, indent=2))
    return 0 if result["classification"] == "CONSISTENT_WITH_REFERENCE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
