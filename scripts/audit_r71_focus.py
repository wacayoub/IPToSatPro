#!/usr/bin/env python3
"""Read-only R71 source audit of pinned R69/R70 identical runtime.
No IPTV requests, Enigma2 interaction, mappings or credentials.
"""
import ast
from audit_r70_baseline import load_release, PREFIX

FUNCTIONS = {
    "core.py": {"match_score_details", "match_decision",
                "_effective_sat_provider_family", "_iptv_provider_family",
                "_sat_provider_family", "_provider_market", "_audio_market"},
    "monitor.py": {"_on_start", "_play_match", "_verify_iptv",
                   "_handle_iptv_failure", "_prewarm_locked_stream",
                   "_fallback_with_native_pat_guard"},
}
CLASS_FUNCTIONS = {
    "core.py": {"Catalog._preview_nomination_pool", "Catalog.fast_preview_top_matches",
                "Catalog.rank_matches"},
    "monitor.py": {"SatFallbackMonitor._on_start", "SatFallbackMonitor._play_match",
                   "SatFallbackMonitor._verify_iptv", "SatFallbackMonitor._handle_iptv_failure"},
}

def main():
    files = load_release()
    for module, wanted in FUNCTIONS.items():
        raw = files[PREFIX + module].decode("utf-8")
        lines = raw.splitlines()
        tree = ast.parse(raw)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in wanted:
                print("\n=== R71 INSPECT", module, node.name, node.lineno, node.end_lineno)
                print("\n".join(lines[node.lineno-1:node.end_lineno])[:14000])
            if isinstance(node, ast.ClassDef):
                for child in node.body:
                    fullname = node.name + "." + getattr(child, "name", "")
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and fullname in CLASS_FUNCTIONS[module]:
                        print("\n=== R71 INSPECT", module, fullname, child.lineno, child.end_lineno)
                        print("\n".join(lines[child.lineno-1:child.end_lineno])[:12000])
    print("R71_READ_ONLY_AUDIT_OK")

if __name__ == "__main__":
    main()
