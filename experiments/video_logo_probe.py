"""Experimental video-only watermark matcher for Vu+/Enigma2 TOD streams.

Input MUST be an actual decoded-video screenshot (grab -v, not the OSD).
Requires manually verified cropped BMP samples of real beIN on-air watermarks.
No templates are bundled or downloaded, so this cannot auto-map by itself.
Pure Python/stdlib; no Pillow/OCR or expensive per-channel scanning required.
Capturing must happen OFF the Enigma2 GUI event thread.
"""
import hashlib
import os
import shutil
import struct
import subprocess
import tempfile


def load_bmp(data, max_bytes=8000000):
    """Return (width, height, rgb_rows) for uncompressed 24/32-bit BMP.

    Small captures only; bounds-check metadata before allocation.
    """
    if not isinstance(data, bytes) or not (54 <= len(data) <= max_bytes):
        raise ValueError("invalid BMP payload")
    if data[:2] != b"BM":
        raise ValueError("not a BMP capture")
    offset = struct.unpack_from("<I", data, 10)[0]
    dib = struct.unpack_from("<I", data, 14)[0]
    if dib < 40 or len(data) < 14 + dib:
        raise ValueError("unsupported BMP header")
    width, height, planes, bpp, compression = struct.unpack_from("<iiHHI", data, 18)
    if planes != 1 or compression != 0 or bpp not in (24, 32):
        raise ValueError("unsupported BMP format")
    if width <= 0 or abs(height) <= 0 or width > 1920 or abs(height) > 1080:
        raise ValueError("BMP dimensions outside safe bounds")
    step = bpp // 8
    stride = (width * step + 3) & ~3
    h = abs(height)
    if offset < 14 + dib or offset + stride * h > len(data):
        raise ValueError("truncated BMP pixels")
    rows = []
    for y in range(h):
        src_y = y if height < 0 else h - 1 - y
        pos = offset + src_y * stride
        row = []
        for x in range(width):
            p = pos + x * step
            row.append((data[p + 2], data[p + 1], data[p]))
        rows.append(row)
    return width, h, rows


def white_mask(rows, threshold=218, max_chroma=30):
    """Extract white/light neutral watermark strokes only; never text OCR."""
    return tuple(
        (min(rgb) >= threshold and max(rgb) - min(rgb) <= max_chroma)
        for row in rows for rgb in row
    )


def crop_rows(frame, roi):
    """Crop fractional (x, y, width, height) ROI, all in (0..1)."""
    w, h, rows = frame
    x, y, cw, ch = roi
    if not (0 <= x < 1 and 0 <= y < 1 and cw > 0 and ch > 0
            and x + cw <= 1.00001 and y + ch <= 1.00001):
        raise ValueError("invalid logo ROI")
    x0, y0 = int(x * w), int(y * h)
    x1, y1 = min(w, int((x + cw) * w)), min(h, int((y + ch) * h))
    if x1 - x0 < 8 or y1 - y0 < 8:
        raise ValueError("logo ROI too small")
    return [row[x0:x1] for row in rows[y0:y1]]


def _dice(a, b):
    if len(a) != len(b):
        return 0.0
    left, right = sum(a), sum(b)
    if left < 12 or right < 12:
        return 0.0
    common = sum(x and y for x, y in zip(a, b))
    return 2.0 * common / float(left + right)


class VideoLogoMatcher:
    """Only evaluate manually verified beIN templates, never guessed logos.

    templates: {6: {"roi": (x,y,w,h), "bmp": cropped_bmp_bytes}, ...}
    Reference BMP contains ONLY the watermark ROI at capture resolution.
    Fails closed if confidence or separation from second place is low.
    """
    def __init__(self, templates, confidence_floor=.93, margin=.07):
        if not (.85 <= confidence_floor <= 1.0) or margin < .03:
            raise ValueError("unsafe matching thresholds")
        self.confidence_floor = confidence_floor
        self.margin = margin
        self.references = {}
        for num, item in templates.items():
            if type(num) is not int or not 1 <= num <= 10:
                raise ValueError("only beIN Sports 1-10 supported")
            if not isinstance(item, dict) or "roi" not in item or "bmp" not in item:
                raise ValueError("verified cropped BMP template required")
            ref = load_bmp(item["bmp"])
            mask = white_mask(ref[2])
            if sum(mask) < 12 or sum(mask) > .65 * len(mask):
                raise ValueError("ambiguous reference watermark mask")
            self.references[num] = (tuple(item["roi"]), ref[0], ref[1], mask)

    def classify(self, actual_video_bmp):
        """Return dict with number/confidence/digest or None.

        Digest identifies full capture for caller to discard repeated old frames.
        A screenshot cannot prove whether the decoder produced a NEW frame.
        """
        if not self.references:
            return None
        frame = load_bmp(actual_video_bmp)
        ranked = []
        for num, (roi, w, h, reference) in self.references.items():
            cut = crop_rows(frame, roi)
            if len(cut) != h or len(cut[0]) != w:
                continue
            score = _dice(white_mask(cut), reference)
            ranked.append((score, num))
        if not ranked:
            return None
        ranked.sort(reverse=True)
        score, number = ranked[0]
        second = ranked[1][0] if len(ranked) > 1 else 0
        if score < self.confidence_floor or score - second < self.margin:
            return None
        return dict(number=number, confidence=round(score, 4),
                    capture_digest=hashlib.sha256(actual_video_bmp).hexdigest())


def grab_video_bmp(grab_binary=None, width=480, timeout=2.5):
    """Video-only capture using Enigma2 grab; never call on the GUI thread.

    Returns BMP bytes or None on unsupported boxes / failure / timeout.
    Does not confuse capture failure with a black screen. NEVER zaps.
    """
    grab_binary = grab_binary or shutil.which("grab")
    if not grab_binary or not os.path.isfile(grab_binary):
        return None
    if type(width) is not int or not 240 <= width <= 960:
        raise ValueError("unsafe capture width")
    fd, path = tempfile.mkstemp(prefix="tod-video-", suffix=".bmp")
    os.close(fd)
    try:
        result = subprocess.run(
            [grab_binary, "-v", "-r", str(width), path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=timeout, check=False)
        if result.returncode != 0:
            return None
        with open(path, "rb") as stream:
            payload = stream.read(8000001)
        if len(payload) > 8000000:
            return None
        load_bmp(payload)
        return payload
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
