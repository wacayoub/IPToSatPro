#!/usr/bin/env python3
"""One-shot, read-only diagnostic: screenshots of the CURRENTLY PLAYING TV picture.

For Vu+ Zero 4K / Enigma2. DOES NOT install anything, zap, unlock channels, open
web services, read passwords, modify bouquets/mappings, or upload recordings.
Only creates private temporary image files in /tmp, for local inspection.

Usage after selecting a King TOD 1-14 channel on the receiver:
  python3 /tmp/tod-capture.py
Then inspect or share ONLY the images from the printed /tmp directory.
Do not send IPTV URLs, source credentials, service-reference strings or logs.
A screenshot cannot independently prove which King source/event is playing.
"""
import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import tempfile
import time

MAX_BYTES = 8000000
CORNER_ROIS = {
    "left": (0.02, 0.02, 0.32, 0.24),
    "right": (0.66, 0.02, 0.32, 0.24),
}


def bmp_decode(raw):
    """Strict 24/32bpp uncompressed Windows BMP. Return (w, h, rows)."""
    if not isinstance(raw, bytes) or not (54 <= len(raw) <= MAX_BYTES):
        raise ValueError("missing/oversized BMP")
    if raw[:2] != b"BM":
        raise ValueError("not a BMP; grab tool may be configured for PNG")
    header_size = struct.unpack_from("<I", raw, 14)[0]
    if header_size < 40 or len(raw) < 14 + header_size:
        raise ValueError("unsupported BMP header")
    offset = struct.unpack_from("<I", raw, 10)[0]
    w, signed_h, planes, bits, compression = struct.unpack_from("<iiHHI", raw, 18)
    h = abs(signed_h)
    if not (planes == 1 and bits in (24, 32) and compression == 0 and
            8 <= w <= 1920 and 8 <= h <= 1080):
        raise ValueError("unsupported BMP geometry/encoding")
    stride = ((w * bits // 8) + 3) & ~3
    if offset < 14 + header_size or offset + stride * h > len(raw):
        raise ValueError("truncated BMP payload")
    rows = []
    for y in range(h):
        src_y = y if signed_h < 0 else h - 1 - y
        pos = offset + src_y * stride
        row = []
        for x in range(w):
            k = pos + (bits // 8) * x
            row.append((raw[k + 2], raw[k + 1], raw[k]))
        rows.append(row)
    return w, h, rows


def bmp_encode(rows):
    if not rows or not rows[0] or any(len(row) != len(rows[0]) for row in rows):
        raise ValueError("invalid image rows")
    w, h = len(rows[0]), len(rows)
    stride = (w * 3 + 3) & ~3
    payload = bytearray()
    for row in reversed(rows):
        for r, g, b in row:
            payload.extend((b, g, r))
        payload.extend(b"\0" * (stride - 3 * w))
    return (b"BM" + struct.pack("<IHHI", 54 + len(payload), 0, 0, 54) +
            struct.pack("<IiiHHIIiiII", 40, w, h, 1, 24, 0,
                        len(payload), 0, 0, 0, 0) + payload)


def extract_corner(frame, roi):
    w, h, rows = frame
    x, y, width, height = roi
    x0, y0 = int(x * w), int(y * h)
    x1, y1 = int((x + width) * w), int((y + height) * h)
    if x1 - x0 < 8 or y1 - y0 < 8:
        raise ValueError("capture too small to crop")
    return bmp_encode([row[x0:x1] for row in rows[y0:y1]])


def collect(grab_path=None, parent="/tmp", count=3, spacing=0.85,
            run_command=None, sleep_fn=None):
    """Capture 3 distinct frames on selected service; never changes service.

    Injectable capture runner/sleeper are used for synthetic offline tests.
    A failed grab is reported as a capture failure, NOT a black screen.
    """
    if count != 3 or spacing < .5 or spacing > 3:
        raise ValueError("safe collector supports only 3 spaced captures")
    real_parent = os.path.realpath(parent)
    if real_parent != "/tmp" and not real_parent.startswith("/tmp/"):
        raise ValueError("temporary output must stay under /tmp")
    if not os.path.isdir(real_parent):
        raise ValueError("missing /tmp output directory")
    grab_path = grab_path or shutil.which("grab")
    if not grab_path or not os.path.isfile(grab_path):
        raise RuntimeError("Enigma2 'grab' unavailable (no capture attempted)")
    runner = run_command or subprocess.run
    sleep = sleep_fn or time.sleep
    folder = tempfile.mkdtemp(prefix="tod-king-diagnostic-", dir=real_parent)
    os.chmod(folder, 0o700)
    report = {
        "purpose": "capture only current tuned TV picture; verify King TOD manually",
        "source_verified": False,
        "capture_count": count,
        "captured": 0,
        "distinct_images": 0,
        "image_identity": "full-screen digest, NOT decoder-frame counter",
        "samples": [],
        "limitations": [
            "No beIN logo templates available; no automatic number recognition",
            "No receiver navigation, tuning, streaming or IPTV provider verification",
            "Image capture failure does not establish an on-air black screen",
        ],
    }
    digests = set()
    try:
        for i in range(count):
            if i:
                sleep(spacing)
            name = "frame-%02d.bmp" % (i + 1)
            destination = os.path.join(folder, name)
            try:
                result = runner(
                    [grab_path, "-v", "-r", "480", destination],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=3.0, check=False)
                if result.returncode != 0:
                    raise ValueError("grab failed (nonzero exit)")
                with open(destination, "rb") as handle:
                    raw = handle.read(MAX_BYTES + 1)
                frame = bmp_decode(raw)
                digest = hashlib.sha256(raw).hexdigest()
                sample = {
                    "index": i + 1,
                    "frame": name,
                    "width": frame[0],
                    "height": frame[1],
                    "digest": digest,
                    "unique": digest not in digests,
                    "corners": {},
                }
                digests.add(digest)
                report["captured"] += 1
                for corner, roi in CORNER_ROIS.items():
                    corner_name = "frame-%02d-%s.bmp" % (i + 1, corner)
                    corner_path = os.path.join(folder, corner_name)
                    with open(corner_path, "wb") as out:
                        out.write(extract_corner(frame, roi))
                    sample["corners"][corner] = corner_name
                report["samples"].append(sample)
                os.chmod(destination, 0o600)
                for corner_name in sample["corners"].values():
                    os.chmod(os.path.join(folder, corner_name), 0o600)
            except (OSError, ValueError, subprocess.TimeoutExpired):
                # Remove an incomplete or unsupported format; no automatic skip.
                try:
                    os.unlink(destination)
                except OSError:
                    pass
                report["samples"].append({
                    "index": i + 1,
                    "status": "capture unsupported/failed (NOT screen black)",
                })
        report["distinct_images"] = len(digests)
        if len(digests) < 3:
            report["warning"] = "Fewer than 3 distinct screenshots; recognition must remain disabled"
        path = os.path.join(folder, "report.json")
        with open(path, "w", encoding="utf-8") as out:
            json.dump(report, out, indent=2, ensure_ascii=False)
        os.chmod(path, 0o600)
        return folder, report
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grab", default=None, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    print("Make sure CURRENT channel is King TOD 1-14; diagnostic does NOT zap.")
    try:
        folder, report = collect(grab_path=args.grab)
    except (RuntimeError, ValueError, OSError) as exc:
        print("CAPTURE UNSUPPORTED:", exc)
        return 1
    print("DIAGNOSTIC:", folder)
    print("FRAMES:", report["captured"], "DISTINCT:", report["distinct_images"])
    print("CHECK:", folder + "/report.json")
    print("No plugin setting/mapping changed; no images were uploaded.")
    return 0 if report["captured"] == 3 else 2


if __name__ == "__main__":
    raise SystemExit(main())
