#!/usr/bin/env python3
"""R80.0 Index Focus -> Preview optimization SOURCE PARITY audit (READ ONLY).

Never installs/patches plugin files or reads settings, mappings, services,
log contents, tokens or IPTV credentials. This is NOT a runtime AV benchmark.
"""
import ast
import difflib
import functools
import hashlib
import json
import re
import sys
import tarfile
import textwrap
from pathlib import Path

PLUGIN_DIR = Path("/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge")
BACKUP = Path("/tmp/IPToSatPro_R80_0_Index_Focus_CORE_ONLY.tar.gz")
PATCH = Path("/tmp/r80_preview_hotpath_patch.py")
EXPECTED_VERSION = "1.0.46-r80.0-rc1-index-focus"
EXPECTED_HASH = "795b3bb206ec9ca4a285db7a85f497af1037248837d5a299442cea10e608ee1b"
TARGETS = {"match_score_details", "Catalog.fast_rank_matches_all_servers"}

def sha(data):
    return hashlib.sha256(data).hexdigest()

def function_map(tree):
    result = {}
    seen = {}
    def add(label, node):
        seen[label] = seen.get(label, 0) + 1
        key = "%s#%d" % (label, seen[label])
        result[key] = ast.dump(node, include_attributes=False)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            add(node.name, node)
        elif isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    add(node.name + "." + child.name, child)
    return result

def non_function_map(tree):
    result = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if isinstance(node, ast.ClassDef):
            original = ast.ClassDef(
                name=node.name,
                bases=node.bases,
                keywords=node.keywords,
                body=[n for n in node.body if not isinstance(n,(ast.FunctionDef, ast.AsyncFunctionDef))],
                decorator_list=node.decorator_list)
            result.append(ast.dump(original, include_attributes=False))
        else:
            result.append(ast.dump(node, include_attributes=False))
    return result

def fixture_key_snippet(source, patched):
    tree = ast.parse(source)
    catalog = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Catalog")
    fn = next(node for node in catalog.body if isinstance(node, ast.FunctionDef) and node.name == "fast_rank_matches_all_servers")
    lines = source.splitlines()
    body = "\n".join(lines[fn.lineno - 1:fn.end_lineno])
    entry = "        def _r80_original_key(item):" if patched else "        def key(item):"
    terminator = "        rows.sort(key=key, reverse=True)"
    a = body.index(entry)
    b = body.index(terminator, a) + len(terminator)
    return textwrap.dedent(body[a:b])

def check_behavior(before, after):
    channels = []
    for i in range(57):
        channels.append({
            "name": "DEMO %d" % (i % 19),
            "server_role": ("PRIMARY", "BACKUP1", "BACKUP2")[i % 3],
            "score": float(70 + i % 27),
            "details": {
                "name": float(10 + i % 23), "equivalence": float(i % 3),
                "variant": float(i % 5), "provider_identity": bool(i % 4)
            },
            "market": i % 3, "language": i % 5,
            "quality": i % 4, "server_priority": (i % 3) + 1
        })
    def trial(source, patched):
        calls = {"context":0, "quality":0}
        def bands(ch, details, context):
            calls["context"] += 1
            return (int(ch.get("market",0)),int(ch.get("language",0)),0)
        def qfit(ch, sat, context):
            calls["quality"] += 1
            return int(ch.get("quality",0))
        class CatalogFixture:
            _context_rank_bands = staticmethod(bands)
        rows = [(ch,float(ch["score"]),dict(ch["details"])) for ch in channels]
        env = {
            "self":CatalogFixture(), "sat_name":"DEMO SPORTS",
            "context":{"confidence":"HIGH","match_threshold":82.0},
            "rows":rows,
            "match_decision":lambda score,det,threshold:"SAFE" if score>=threshold else "REVIEW",
            "quality_fit_key":qfit,
            "_stream_penalty":lambda ch:0,
        }
        exec(compile(fixture_key_snippet(source, patched), "isolated_ranking_key_fixture.py", "exec"),env)
        env["out"] = rows[:7]
        exec("out.sort(key=key, reverse=True)", env)
        return [(x[0]["name"],x[0]["server_role"]) for x in rows], [(x[0]["name"],x[0]["server_role"]) for x in env["out"]], calls
    original = trial(before,False)
    modified = trial(after,True)
    if original[:2] != modified[:2]:
        raise RuntimeError("RANK_CANDIDATE_ORDER_CHANGED")
    if modified[2]["context"] > original[2]["context"]:
        raise RuntimeError("RANK_EXTRA_COMPUTATION")
    tree = ast.parse(after)
    ratio_fn = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name == "_r80_preview_ratio")
    node = ast.Module(body=[ratio_fn], type_ignores=[])
    ast.fix_missing_locations(node)
    namespace = {"SequenceMatcher":difflib.SequenceMatcher,"_r80_lru_cache":functools.lru_cache}
    exec(compile(node,"isolated_r80_ratio_fixture.py","exec"),namespace)
    cached = namespace["_r80_preview_ratio"]
    probes = (
      ("bein sports 1","bein sports 1"),("tve la 1","la 1"),
      ("osn cinema","osn cinema hd"),("tlc at","tlc austria"),
      ("filmbox one","one filmbox"),("fr disney channel","de disney channel"),
      ("nat geo abu dhabi","natgeo ad"),("ushuaia tv","ushuaia hd"))
    for _ in range(30):
        for left,right in probes:
            if cached(left,right) != difflib.SequenceMatcher(None,left,right).ratio():
                raise RuntimeError("PREVIEW_RATIO_DIFF")
    return {
        "sort_identity_and_order_parity":True,
        "preview_ratio_parity":True,
        "cached_ratio_hits":cached.cache_info().hits,
        "old_sort_context_calls":original[2]["context"],
        "new_sort_context_calls":modified[2]["context"],
        "synthetic_rows":len(channels),
    }

def main():
    report = {
        "audit":"IPToSatPro R80.0 installed engine -> R80.1 hot-path rebase in memory",
        "installed_code_modified":False,
        "settings_or_mappings_read":False,
        "install_authorized":False,
        "final_release_authorized":False,
    }
    try:
        plug = (PLUGIN_DIR/"plugin.py").read_bytes()
        match = re.search(rb'''(?m)^\s*PLUGIN_VERSION\s*=\s*["']([^"'\r\n]+)["']''',plug)
        version = match.group(1).decode("ascii","replace") if match else "UNKNOWN"
        data = (PLUGIN_DIR/"core.py").read_bytes()
        if version != EXPECTED_VERSION or sha(data) != EXPECTED_HASH:
            raise RuntimeError("INSTALLED_R800_VERSION_OR_CORE_CHANGED")
        with tarfile.open(BACKUP,"r:gz") as archive:
            if {x.name for x in archive.getmembers()} != {"core.py","manifest.json"}:
                raise RuntimeError("CORE_ONLY_EXPORT_STRUCTURE_MISMATCH")
            if archive.extractfile("core.py").read() != data:
                raise RuntimeError("CORE_EXPORT_NOT_IDENTICAL")
        report["original_core_verified"] = True
        before = data.decode("utf-8")
        patch_ns = {"__name__":"r80_preview_hotpath_patch"}
        exec(compile(PATCH.read_bytes(), str(PATCH),"exec"),patch_ns)
        if patch_ns.get("TAG") != "R80_PREVIEW_PURE_HOTPATH_V1":
            raise RuntimeError("UNEXPECTED_PATCH")
        after = patch_ns["patch_core"](before)
        if patch_ns["patch_core"](after) != after:
            raise RuntimeError("PATCH_NOT_IDEMPOTENT")
        base_tree, new_tree = ast.parse(before), ast.parse(after)
        old, new = function_map(base_tree), function_map(new_tree)
        changed = sorted(k for k in old.keys() & new.keys() if old[k] != new[k])
        added = sorted(new.keys() - old.keys())
        removed = sorted(old.keys() - new.keys())
        report["ast_delta"] = {"modified":changed,"added":added,"removed":removed}
        if {x.rsplit("#",1)[0] for x in changed} != TARGETS:
            raise RuntimeError("UNEXPECTED_FUNCTION_MODIFICATION")
        if added != ["_r80_preview_ratio#1"] or removed:
            raise RuntimeError("UNEXPECTED_FUNCTION_ADDED_OR_REMOVED")
        top_old = non_function_map(base_tree)
        top_new = non_function_map(new_tree)
        alias = ast.dump(ast.parse("from functools import lru_cache as _r80_lru_cache").body[0],include_attributes=False)
        if top_new.count(alias) != 1:
            raise RuntimeError("MISSING_RATIO_CACHE_IMPORT")
        top_new.remove(alias)
        if top_old != top_new:
            raise RuntimeError("UNEXPECTED_NON_FUNCTION_AST_CHANGE")
        report["source_guards"] = {
            "changed_only_expected_methods":True,
            "all_other_functions_unchanged":True,
            "non_function_ast_identical_except_cache_import":True,
            "idempotent":True,
        }
        report["synthetic_behavior"] = check_behavior(before,after)
        report["patched_core_sha256_in_memory_only"] = sha(after.encode("utf-8"))
        report["result"] = "STATIC_AND_SYNTHETIC_PARITY_PASS__NOT_HARDWARE_VALIDATED"
    except Exception as exc:
        report["result"] = "REBASE_BLOCKED"
        report["reason"] = type(exc).__name__ + ": " + str(exc)[:160]
    print(json.dumps(report,sort_keys=True,indent=2))
    return 0 if report["result"].startswith("STATIC_AND") else 2

if __name__ == "__main__":
    sys.exit(main())
