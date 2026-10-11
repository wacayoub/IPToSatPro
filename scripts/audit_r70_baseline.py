#!/usr/bin/env python3
"""Offline source audit of released IPToSatPro r69 for final r70.

Reads only PUBLIC versioned package bytes; prints source structure and selected
methods; does not access a receiver, credentials, URLs, channel lists or network.
"""
import ast
import base64
import hashlib
import io
import json
import re
import sys
import tarfile
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/"
EXPECTED_SHA = "123e1118a7471075ad18dee3014b7367fa9a2cf02f8cdd52ad1e5e65034035ed"


def load_release():
    data = base64.b64decode((ROOT / "payload/r69-beta.b64").read_bytes())
    assert hashlib.sha256(data).hexdigest() == EXPECTED_SHA, "r69 baseline changed"
    assert len(data) == 276666, "r69 byte size changed"
    with tempfile.TemporaryDirectory() as temp:
        pkg = Path(temp) / "baseline.ipk"
        pkg.write_bytes(data)
        b = subprocess.check_output(["ar", "p", str(pkg), "data.tar.gz"])
    with tarfile.open(fileobj=io.BytesIO(b), mode="r:gz") as tar:
        return {m.name.lstrip("./"): tar.extractfile(m).read()
                for m in tar.getmembers()
                if m.isfile() and m.name.lstrip("./").startswith(PREFIX)
                and m.name.endswith(".py")}


def functions(source, file):
    tree = ast.parse(source, filename=file)
    found = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            found.append((node.name, node))
        elif isinstance(node, ast.ClassDef):
            for method in node.body:
                if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    found.append((node.name + "." + method.name, method))
    return found


def main():
    files = load_release()
    print("AUDIT_RELEASE=1.0.46-r69-beta, EXPECTED_SHA=" + EXPECTED_SHA)
    print("PYTHON_MODULES=" + ",".join(sorted(
        path.removeprefix(PREFIX) for path in files)))
    selector = re.compile(
        r"(?i)match|candidate|score|source|provider|lock|manual|audio|"
        r"zapp|play|preview|iptv|timeout|freeze|video|service")
    for name, raw in sorted(files.items()):
        short = name.removeprefix(PREFIX)
        code = raw.decode("utf-8")
        fns = functions(code, short)
        matching = [n for n, _ in fns if selector.search(n)]
        print("MODULE", short, "LINES", len(code.splitlines()),
              "MATCHING_METHODS", " ".join(matching[:100]))
    if len(sys.argv) > 1:
        needle = sys.argv[1].lower()
        limit = 12
        for name, raw in sorted(files.items()):
            short = name.removeprefix(PREFIX)
            text = raw.decode("utf-8")
            lines = text.splitlines()
            for fn_name, node in functions(text, short):
                if needle in fn_name.lower() and limit:
                    limit -= 1
                    source = "\n".join(lines[node.lineno - 1:node.end_lineno])
                    print("\nFUNCTION", short, fn_name, "LEN", len(source),
                          "\n", source[:9500])
    print("AUDIT_FINISHED")


if __name__ == "__main__":
    main()
