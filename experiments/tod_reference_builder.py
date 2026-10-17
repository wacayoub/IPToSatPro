"""Offline calibration of real on-air beIN upper-corner screenshot references.

This tool NEVER invents which beIN logo is shown. A human must identify the
logo 1-10 and inspect the actual video-only source screenshot and tight ROI.
No screenshots are included in the repository. Captures and templates are
local files only. This module does not access or control Enigma2.

Examples:
 python3 experiments/tod_reference_builder.py \
     --screenshot /tmp/king-tod-frame.bmp --logo 6 --corner right \
     --roi .91 .035 .075 .08 --out-dir /tmp/tod-calibration --verified
"""
import argparse
import json
import os
import struct

from video_logo_probe import crop_rows, load_bmp, white_mask


def encode_bmp(rows):
    if not rows or not rows[0]:
        raise ValueError("empty BMP crop")
    h, w = len(rows), len(rows[0])
    if w < 8 or h < 8 or w > 1920 or h > 1080 or any(len(r) != w for r in rows):
        raise ValueError("invalid crop dimensions")
    stride = (w * 3 + 3) & ~3
    payload = bytearray()
    for row in reversed(rows):
        for r, g, b in row:
            payload.extend((b, g, r))
        payload.extend(b"\0" * (stride - w * 3))
    return (b"BM" + struct.pack("<IHHI", 54+len(payload), 0, 0, 54) +
            struct.pack("<IiiHHIIiiII", 40, w, h, 1, 24, 0,
                        len(payload), 0, 0, 0, 0) + bytes(payload))


def reference_crop(screenshot, roi, corner, number):
    """Crop a manually identified real broadcaster watermark.

    Sanity checks prevent accepting wide whole-corner regions as a logo.
    This CANNOT prove the label is correct or that King is the broadcaster.
    """
    if type(number) is not int or not 1 <= number <= 10:
        raise ValueError("only beIN Sports 1-10 supported")
    if corner not in ("left", "right"):
        raise ValueError("corner must be left/right")
    if len(roi) != 4:
        raise ValueError("expected fractional x,y,width,height ROI")
    x, y, w, h = [float(v) for v in roi]
    if not (0 <= y < .3 and h > 0 and y+h <= .35 and
            0 < w <= .35 and 0 < h <= .28 and
            (x >= .5 if corner == "right" else x+w <= .5)):
        raise ValueError("watermark must fit the chosen upper screen corner")
    full = load_bmp(screenshot)
    cropped = crop_rows(full, (x, y, w, h))
    mask = white_mask(cropped)
    if sum(mask) < 12 or sum(mask) > .65*len(mask):
        raise ValueError("ROI lacks a sufficiently distinctive white watermark")
    return encode_bmp(cropped)


def create_reference(screenshot_path, number, corner, roi, out_dir, verified=False):
    """Write BMP and manifest only after explicit manual verification."""
    if not verified:
        raise ValueError("visually verify REAL King/beIN source before saving")
    with open(screenshot_path, "rb") as stream:
        screenshot = stream.read(8000001)
    if len(screenshot) > 8000000:
        raise ValueError("screenshot too large")
    bmp = reference_crop(screenshot, roi, corner, number)
    os.makedirs(out_dir, exist_ok=True)
    basename = "bein-sports-%d-%s.bmp" % (number, corner)
    name = os.path.join(out_dir, basename)
    manifest_path = os.path.join(out_dir, "manifest.json")
    entries = []
    if os.path.isfile(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as stream:
            document = json.load(stream)
        if document.get("schema") != 1:
            raise ValueError("unsupported calibration manifest")
        entries = document.get("references", [])
        if not isinstance(entries, list):
            raise ValueError("invalid calibration reference entries")
    entries = [entry for entry in entries if not (
        entry.get("logo") == number and entry.get("corner") == corner)]
    entries.append(dict(logo=number, corner=corner, roi=list(map(float, roi)),
                        file=basename, human_verified=True))
    with open(name, "wb") as stream:
        stream.write(bmp)
    with open(manifest_path, "w", encoding="utf-8") as stream:
        json.dump({"schema": 1, "references": entries},
                  stream, indent=2, sort_keys=True)
    return name, manifest_path


def load_verified_templates(manifest_path):
    """Strictly read a human-verified local calibration manifest."""
    base = os.path.dirname(os.path.realpath(manifest_path))
    with open(manifest_path, "r", encoding="utf-8") as stream:
        document = json.load(stream)
    if document.get("schema") != 1 or not isinstance(document.get("references"), list):
        raise ValueError("invalid manifest schema")
    templates = {}
    for entry in document["references"]:
        if entry.get("human_verified") is not True:
            raise ValueError("unverified logo reference")
        number, corner, roi = entry["logo"], entry["corner"], entry["roi"]
        if type(number) is not int or number not in range(1, 11):
            raise ValueError("invalid beIN Sports number")
        basename = entry["file"]
        if not isinstance(basename, str) or os.path.basename(basename) != basename:
            raise ValueError("reference path must be a local file")
        filename = os.path.realpath(os.path.join(base, basename))
        if os.path.dirname(filename) != base:
            raise ValueError("reference path escaped calibration directory")
        with open(filename, "rb") as stream:
            bmp = stream.read(8000001)
        load_bmp(bmp)
        if len(bmp) > 8000000:
            raise ValueError("reference too large")
        templates.setdefault(number, {"placements": []})["placements"].append(
            dict(roi=tuple(roi), bmp=bmp, corner=corner))
    return templates


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshot", required=True)
    parser.add_argument("--logo", type=int, required=True)
    parser.add_argument("--corner", choices=("left", "right"), required=True)
    parser.add_argument("--roi", nargs=4, type=float, required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--verified", action="store_true",
                        help="Confirm reference really shows this numbered beIN logo")
    args = parser.parse_args(argv)
    print("Local template:", create_reference(
        args.screenshot, args.logo, args.corner,
        args.roi, args.out_dir, args.verified)[0])


if __name__ == "__main__":
    main()
