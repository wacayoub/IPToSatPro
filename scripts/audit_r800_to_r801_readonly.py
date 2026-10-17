#!/usr/bin/env python3
"""IPToSatPro R80.0 -> R80.1 compatibility audit; NO installation.

Reads only installed plugin code plus the previous core-only archive.
Compares with an exact hash-pinned public candidate and tests the Preview
hot-path source patch in memory, never on the running plugin.
Never reads IPTV settings, mappings, URLs, logs or credentials.
"""
import ast
import base64
import hashlib
import io
import json
import re
import sys
import tarfile
import urllib.request
from pathlib import Path

PLUGIN = Path("/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge")
ARCHIVE = Path("/tmp/IPToSatPro_R80_0_Index_Focus_CORE_ONLY.tar.gz")
PATCH = Path("/tmp/r80_preview_hotpath_patch.py")
VERSION = "1.0.46-r80.0-rc1-index-focus"
CORE_SHA = "795b3bb206ec9ca4a285db7a85f497af1037248837d5a299442cea10e608ee1b"
CANDIDATE_SHA = "210fe7de203353b71f02829f4f2b31acc582dfc663ce7bc8971425e0ecd2f173"
CANDIDATE_URL = ("https://raw.githubusercontent.com/wacayoub/IPToSatPro/"
    "9949bc9a90f3f19ce6f3749bf03a095d776e1d8d/payload/r801-preview-hotpath.b64")
PFX = "usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/"

def sha(data):
    return hashlib.sha256(data).hexdigest()

def stop(why):
    raise ValueError(why)

def functions(src):
    tree = ast.parse(src)
    out = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            out[node.name] = ast.dump(node, include_attributes=False)
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, ast.FunctionDef):
                    out[node.name + "." + child.name] = ast.dump(child, include_attributes=False)
    return out

def validate_current():
    raw = (PLUGIN / "plugin.py").read_bytes()
    match = re.search(rb'''(?m)^\s*PLUGIN_VERSION\s*=\s*["']([^"'\r\n]+)["']''', raw)
    actual = match.group(1).decode("ascii", "replace") if match else "UNKNOWN"
    data = (PLUGIN / "core.py").read_bytes()
    if actual != VERSION:
        stop("UNEXPECTED_VERSION_" + actual)
    if sha(data) != CORE_SHA:
        stop("INSTALLED_CORE_MISMATCH")
    with tarfile.open(ARCHIVE, "r:gz") as tar:
        names = {f.name for f in tar.getmembers()}
        if names != {"core.py", "manifest.json"}:
            stop("ARCHIVE_FILE_SET_MISMATCH")
        exported = tar.extractfile("core.py").read()
        manifest = json.loads(tar.extractfile("manifest.json").read())
        if exported != data or manifest.get("core_sha256") != CORE_SHA:
            stop("ARCHIVE_AND_INSTALLED_CODE_DIFFER")
    return data

def patch_probe(core):
    if not PATCH.is_file():
        stop("PATCH_SOURCE_NOT_DOWNLOADED")
    namespace = {"__name__": "r80_preview_hotpath_patch_probe"}
    exec(compile(PATCH.read_bytes(), str(PATCH), "exec"), namespace)
    if namespace.get("TAG") != "R80_PREVIEW_PURE_HOTPATH_V1":
        stop("PATCH_SOURCE_NOT_RECOGNIZED")
    before = core.decode("utf-8")
    after = namespace["patch_core"](before)
    previous, updated = functions(before), functions(after)
    modified = sorted(k for k in previous.keys() & updated.keys() if previous[k] != updated[k])
    added = sorted(updated.keys() - previous.keys())
    deleted = sorted(previous.keys() - updated.keys())
    if modified != ["Catalog.fast_rank_matches_all_servers", "match_score_details"]:
        stop("UNEXPECTED_PATCH_METHOD_CHANGES")
    if added != ["_r80_preview_ratio"] or deleted:
        stop("UNEXPECTED_PATCH_FUNCTION_SET")
    if namespace["patch_core"](after) != after:
        stop("PATCH_NOT_IDEMPOTENT")
    return {
        "result": "PATCH_ANCHORS_AND_AST_PASS_ONLY",
        "in_memory_core_sha256": sha(after.encode("utf-8")),
        "modified_functions": modified, "added_functions": added,
        "other_functions_unchanged_ast": True,
        "installed_code_modified": False
    }

def ipk_files(raw):
    if not raw.startswith(b"!<arch>\n"):
        stop("INVALID_IPK_HEADER")
    blocks, pos = {}, 8
    while pos + 60 <= len(raw):
        header = raw[pos:pos + 60]
        if header[58:60] != bytes([96, 10]):
            stop("INVALID_AR_ENTRY")
        n = header[:16].decode("ascii", "replace").strip().rstrip("/")
        size = int(header[48:58].strip())
        pos += 60
        if size < 0 or pos + size > len(raw):
            stop("INVALID_AR_SIZE")
        blocks[n] = raw[pos:pos + size]
        pos += size + size % 2
    if pos != len(raw) or "data.tar.gz" not in blocks:
        stop("IPK_DATA_NOT_FOUND")
    entries = {}
    with tarfile.open(fileobj=io.BytesIO(blocks["data.tar.gz"]), mode="r:gz") as tar:
        for entry in tar.getmembers():
            if not entry.isfile():
                continue
            path = entry.name
            while path.startswith("./"):
                path = path[2:]
            path = path.lstrip("/")
            if path.startswith(PFX) and entry.size < 4_000_000:
                relative = path[len(PFX):]
                if relative and ".." not in Path(relative).parts:
                    entries[relative] = tar.extractfile(entry).read()
    if not {"core.py", "plugin.py"}.issubset(entries):
        stop("CANDIDATE_CODE_NOT_FOUND")
    return entries

def compare_candidate():
    with urllib.request.urlopen(CANDIDATE_URL, timeout=25) as response:
        b64 = response.read(800_000)
    if len(b64) >= 800_000:
        stop("CANDIDATE_DOWNLOAD_TOO_LARGE")
    data = base64.b64decode(b64)
    if len(data) != 461044 or sha(data) != CANDIDATE_SHA:
        stop("CANDIDATE_SHA256_MISMATCH")
    candidate = ipk_files(data)
    identical, different, missing = 0, [], []
    for name, payload in sorted(candidate.items()):
        local = PLUGIN / name
        if not local.is_file():
            missing.append(name)
        elif sha(local.read_bytes()) != sha(payload):
            different.append(name)
        else:
            identical += 1
    return {"verified_sha256": CANDIDATE_SHA,
            "candidate_asset_count": len(candidate), "identical_assets": identical,
            "different_assets": different[:70], "missing_assets": missing[:70],
            "verdict": "BASELINE_DIFFERENCES_REQUIRE_REBASE_NO_INSTALL"}

def main():
    out = {"audit": "IPToSatPro R80 installed-code compatibility",
           "installed_version_expected": VERSION,
           "receiver_modified": False, "mapping_files_read": False,
           "install_authorized": False}
    try:
        core = validate_current()
        out["installed_core_verified"] = True
        out["core_bytes"] = len(core)
        try:
            out["preview_patch"] = patch_probe(core)
        except Exception as e:
            out["preview_patch"] = {"result": "BLOCKED", "reason": str(e)[:180]}
        try:
            out["r801_package_comparison"] = compare_candidate()
        except Exception as e:
            out["r801_package_comparison"] = {"result": "UNAVAILABLE",
                                               "reason": type(e).__name__ + ": " + str(e)[:80]}
        out["verdict"] = "READ_ONLY_INSPECTION_COMPLETE_FINAL_NOT_AUTHORIZED"
    except Exception as e:
        out["verdict"] = "BLOCKED"
        out["reason"] = type(e).__name__ + ": " + str(e)[:160]
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0 if out["verdict"].startswith("READ_ONLY") else 2

if __name__ == "__main__":
    sys.exit(main())
