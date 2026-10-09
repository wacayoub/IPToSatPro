#!/usr/bin/env python3
"""Minimal portable 'ar' fallback used for offline test IPK build only.

Supports exactly: ar p <archive> <member>, ar r <archive> <files...>
No input files are executed. Only used in /tmp staging if system ar unavailable.
"""
import os
import sys
import time


MAGIC = b"!<arch>\n"


def extract(path, wanted):
    with open(path, "rb") as src:
        if src.read(8) != MAGIC:
            raise ValueError("Bad ar archive")
        while True:
            header = src.read(60)
            if not header:
                break
            if len(header) != 60 or header[58:] != b"`\n":
                raise ValueError("Bad ar header")
            name = header[:16].decode("ascii").strip().rstrip("/")
            size = int(header[48:58].decode("ascii").strip())
            if size < 0 or size > 16 * 1024 * 1024:
                raise ValueError("Invalid ar member")
            data = src.read(size)
            if len(data) != size:
                raise ValueError("Truncated ar member")
            if size % 2:
                src.read(1)
            if name == wanted:
                sys.stdout.buffer.write(data)
                return
    raise ValueError("ar member absent: " + wanted)


def pack(path, members):
    with open(path, "wb") as dst:
        dst.write(MAGIC)
        for member in members:
            name = os.path.basename(member)
            if len(name.encode("ascii")) > 15:
                raise ValueError("Long member name not supported")
            with open(member, "rb") as src:
                data = src.read()
            mode = "100644"
            header = (
                ("%s/" % name).ljust(16)
                + str(int(time.time())).ljust(12)
                + "0".ljust(6)
                + "0".ljust(6)
                + mode.ljust(8)
                + str(len(data)).ljust(10)
                + "`\n"
            ).encode("ascii")
            if len(header) != 60:
                raise ValueError("Invalid generated header")
            dst.write(header)
            dst.write(data)
            if len(data) % 2:
                dst.write(b"\n")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "p":
        extract(sys.argv[2], sys.argv[3])
    elif len(sys.argv) >= 4 and sys.argv[1] == "r":
        pack(sys.argv[2], sys.argv[3:])
    else:
        sys.stderr.write("Usage: ar p archive member | ar r archive member...\n")
        sys.exit(2)
