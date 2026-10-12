#!/usr/bin/env python3
"""Read real packaged R73 source on GitHub CI; only selected functional sections."""
import ast,importlib.util
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("r73",root/"scripts/build-r73-preview.py")
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)
import tempfile
with tempfile.TemporaryDirectory() as d:
    p=Path(d)/"r73.ipk";b.build(p)
    m=b.base.pack.members_from(b.base.pack.unpack_ar(p.read_bytes())["data.tar.gz"])
    sections={
        "plugin.py":[(2860,3087),(3140,3190),(6110,6135),(6470,6555),(6634,6749),(6870,6990),(7150,7310)],
        "core.py":[(1550,1668),(1750,1875),(1850,1932),(2060,2159),(2775,2863),(2862,3147),(3498,3615),(3818,3898)]
    }
    for name,spans in sections.items():
        lines=m[b.P+name].decode().splitlines()
        for start,end in spans:
            print("START",name,start,end)
            for j in range(start-1,min(end,len(lines))):
                print("%d %s"%(j+1,lines[j]))
            print("END",name,start,end)
