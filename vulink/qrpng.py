# -*- coding: utf-8 -*-
"""Standalone QR PNG creator, no Pillow/qrencode/network.

QR version 4 L, byte mode, 78-byte maximum. Reed-Solomon error correction,
all eight QR masks scored. Designed for short private-LAN pairing URLs.
"""
import binascii
import struct
import zlib

SIZE = 33
DATA_BYTES = 80
ECC_BYTES = 20


def _gf_mul(a, b):
    out = 0
    for bit in range(7, -1, -1):
        out = (out << 1) ^ (0x11D if out & 0x80 else 0)
        if (b >> bit) & 1:
            out ^= a
    return out & 0xFF


def _rs_encode(data):
    poly = [1]
    root = 1
    for _ in range(ECC_BYTES):
        nxt = [0] * (len(poly) + 1)
        for j, coeff in enumerate(poly):
            nxt[j] ^= coeff
            nxt[j + 1] ^= _gf_mul(coeff, root)
        poly = nxt
        root = _gf_mul(root, 2)
    remainder = [0] * ECC_BYTES
    for value in data:
        factor = value ^ remainder[0]
        remainder = remainder[1:] + [0]
        for j in range(ECC_BYTES):
            remainder[j] ^= _gf_mul(poly[j + 1], factor)
    return remainder


def _encode_data(url):
    data = url.encode("utf-8")
    if not data or len(data) > 78:
        raise ValueError("QR URL must be 1..78 bytes")
    bits = [0, 1, 0, 0]  # byte mode 0100
    bits.extend((len(data) >> i) & 1 for i in range(7, -1, -1))
    for value in data:
        bits.extend((value >> i) & 1 for i in range(7, -1, -1))
    bits.extend([0] * min(4, DATA_BYTES * 8 - len(bits)))
    while len(bits) % 8:
        bits.append(0)
    codes = []
    for i in range(0, len(bits), 8):
        value = 0
        for bit in bits[i:i + 8]:
            value = (value << 1) | bit
        codes.append(value)
    pad = (0xEC, 0x11)
    while len(codes) < DATA_BYTES:
        codes.append(pad[len(codes) % 2])
    return codes + _rs_encode(codes)


def qr_matrix(url, mask=0):
    if not 0 <= mask <= 7:
        raise ValueError("QR mask out of range")
    codewords = _encode_data(url)
    m = [[False] * SIZE for _ in range(SIZE)]
    reserved = [[False] * SIZE for _ in range(SIZE)]

    def mark(x, y, dark):
        if 0 <= x < SIZE and 0 <= y < SIZE:
            m[y][x] = dark
            reserved[y][x] = True

    def finder(x0, y0):
        for dy in range(-1, 8):
            for dx in range(-1, 8):
                dist = max(abs(dx - 3), abs(dy - 3))
                mark(x0 + dx, y0 + dy, dist == 3 or dist <= 1)

    finder(0, 0)
    finder(SIZE - 7, 0)
    finder(0, SIZE - 7)

    for i in range(8, SIZE - 8):
        mark(6, i, i % 2 == 0)
        mark(i, 6, i % 2 == 0)

    for dy in range(-2, 3):
        for dx in range(-2, 3):
            mark(26 + dx, 26 + dy, max(abs(dx), abs(dy)) != 1)

    for i in range(9):
        if i != 6:
            mark(8, i, False)
            mark(i, 8, False)
    for i in range(8):
        mark(SIZE - 1 - i, 8, False)
    for i in range(7):
        mark(8, SIZE - 1 - i, False)
    mark(8, SIZE - 8, True)

    def mask_is_dark(x, y):
        product = x * y
        return (
            (x + y) % 2 == 0,
            y % 2 == 0,
            x % 3 == 0,
            (x + y) % 3 == 0,
            (x // 3 + y // 2) % 2 == 0,
            (product % 2 + product % 3) == 0,
            (product % 2 + product % 3) % 2 == 0,
            ((x + y) % 2 + product % 3) % 2 == 0,
        )[mask]

    bits = []
    for value in codewords:
        bits.extend((value >> i) & 1 for i in range(7, -1, -1))
    index = 0
    right = SIZE - 1
    upwards = True
    while right >= 1:
        if right == 6:
            right = 5
        for vert in range(SIZE):
            y = SIZE - 1 - vert if upwards else vert
            for x in (right, right - 1):
                if not reserved[y][x]:
                    value = bool(bits[index]) if index < len(bits) else False
                    index += 1
                    m[y][x] = value ^ mask_is_dark(x, y)
        upwards = not upwards
        right -= 2

    if index < len(bits):
        raise AssertionError("QR data area too small")

    fmt = (1 << 3) | mask  # error correction L / mask code
    remainder = fmt
    for _ in range(10):
        remainder = (remainder << 1) ^ (0x537 if remainder & 0x200 else 0)
    code = ((fmt << 10) | remainder) ^ 0x5412

    def format_bit(i):
        return ((code >> i) & 1) != 0

    for i in range(6):
        mark(8, i, format_bit(i))
    mark(8, 7, format_bit(6))
    mark(8, 8, format_bit(7))
    mark(7, 8, format_bit(8))
    for i in range(9, 15):
        mark(14 - i, 8, format_bit(i))
    for i in range(8):
        mark(SIZE - 1 - i, 8, format_bit(i))
    for i in range(8, 15):
        mark(8, SIZE - 15 + i, format_bit(i))
    mark(8, SIZE - 8, True)
    return m


def _penalty(matrix):
    score = 0
    for line in list(matrix) + list(zip(*matrix)):
        run = 1
        for i in range(1, SIZE):
            if line[i] == line[i - 1]:
                run += 1
            else:
                if run >= 5:
                    score += 3 + run - 5
                run = 1
        if run >= 5:
            score += 3 + run - 5
        pattern = [True, False, True, True, True, False, True]
        for i in range(SIZE - 6):
            if list(line[i:i + 7]) == pattern:
                if i >= 4 and all(not value for value in line[i - 4:i]):
                    score += 40
                if i + 11 <= SIZE and all(not value for value in line[i + 7:i + 11]):
                    score += 40
    for y in range(SIZE - 1):
        for x in range(SIZE - 1):
            if matrix[y][x] == matrix[y][x + 1] == matrix[y + 1][x] == matrix[y + 1][x + 1]:
                score += 3
    dark = sum(sum(1 for bit in line if bit) for line in matrix)
    score += (abs(dark * 20 - SIZE * SIZE * 10) // (SIZE * SIZE)) * 10
    return score


def qr_png(url, scale=6, quiet=4):
    matrix = min((qr_matrix(url, mask) for mask in range(8)), key=_penalty)
    n = (SIZE + 2 * quiet) * scale
    white = b"\xff\xff\xff"
    black = b"\x00\x00\x00"
    rows = []
    for y in range(SIZE + 2 * quiet):
        line = []
        for x in range(SIZE + 2 * quiet):
            dark = (quiet <= x < quiet + SIZE and quiet <= y < quiet + SIZE
                    and matrix[y - quiet][x - quiet])
            line.append((black if dark else white) * scale)
        for _ in range(scale):
            rows.append(b"\x00" + b"".join(line))

    def chunk(name, data):
        return (struct.pack("!I", len(data)) + name + data +
                struct.pack("!I", binascii.crc32(name + data) & 0xFFFFFFFF))

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack("!IIBBBBB", n, n, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
    png += chunk(b"IEND", b"")
    return png


def write_qr_png(url, filepath):
    with open(filepath, "wb") as out:
        out.write(qr_png(url))
    return True
