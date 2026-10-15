#!/usr/bin/env python3
"""Inspect R76.11 Preview unmap/manual-unverified semantics in genuine beta IPK.

Offline only. No receiver access, no mappings changes, no IPTV credentials.
"""
import ast
import importlib.util
import tempfile
from pathlib import Path

root=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location("b7611",root/"scripts/build-r7611-preview-cold.py")
b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
with tempfile.TemporaryDirectory() as tmp:
    ipk=Path(tmp)/"r7611.ipk"
    b.build(ipk)
    data=b.pack.members_from(b.pack.unpack_ar(ipk.read_bytes())["data.tar.gz"])
    src=data[b.PLUGIN].decode("utf8")
    lines=src.splitlines()
    for token in ("PREVIEW_UNMAP","PREVIEW_MANUAL_UNV","PREVIEW_RANK_BG",
                  "def _blue_action","def _rescan_selected_sat"):
        matches=[i for i,s in enumerate(lines) if token in s]
        print("UNMAP_TOKEN",token,"COUNT",len(matches))
        for i in matches[:12]:
            print("UNMAP_CONTEXT",token,"LINE",i+1)
            for j in range(max(0,i-10),min(len(lines),i+12)):
                print("UNMAP_SRC",j+1,lines[j][:200])

    for start,end in ((8400,8520),(8965,9030)):
        print("UNMAP_FULL_REGION",start,end)
        for line_n in range(start-1,min(end,len(lines))):
            print("UNMAP_FULL_SRC",line_n+1,lines[line_n][:200])
