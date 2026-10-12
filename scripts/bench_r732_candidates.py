#!/usr/bin/env python3
"""Synthetic 24k IPTV rows, speed profile of production R73.1 index-only Preview."""
import importlib.util,time,tempfile,statistics,random
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("r731b",root/"scripts/build-r73-preview.py")
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)
with tempfile.TemporaryDirectory() as tmp:
    pkg=Path(tmp)/"original.ipk";b.build(pkg)
    core=Path(tmp)/"core.py"
    data=b.base.pack.members_from(b.base.pack.unpack_ar(pkg.read_bytes())["data.tar.gz"])
    core.write_bytes(data[b.CORE])
    sp=importlib.util.spec_from_file_location("core_r731",core)
    lib=importlib.util.module_from_spec(sp);sp.loader.exec_module(lib)
    names=["CANAL+ GOLF HD","USHUAIA TV FHD","NAT GEO HD","BEIN SPORTS %d FHD","OSN CINEMA %d HD","DUBAI SPORTS %d HD","TVE LA %d FHD","AL JAZEERA %d HD"]
    ch=[]
    for i in range(24000):
        label=names[i%len(names)]
        name=(label%(i%16+1)) if "%d" in label else label
        if i%5==0:name=name+" FR"
        if i%7==0:name="IT: "+name
        if i%11==0:name="PL: "+name
        ch.append({"name":name,"url":"http://192.0.2.1/%d"%i,
            "server_role":("PRIMARY","BACKUP1","BACKUP2")[i%3],
            "server_label":"Synthetic","group":"TEST","language":"FR" if i%3 else "EN",
            "server_priority":i%3})
    t=time.perf_counter();catalog=lib.Catalog(ch);print("PROFILE init_24k %.1f ms"%((time.perf_counter()-t)*1000))
    for target in ["CANAL+ GOLF HD","BEIN SPORTS 6 FHD","OSN CINEMA 3 HD","USHUAIA TV FHD"]:
        ctx={"confidence":"HIGH","market":"FR","language_priorities":["FR"],
              "market_preferences":["FR"],"match_threshold":60.0,"provider_family":""}
        t=time.perf_counter()
        pool=catalog._preview_nomination_pool(target,context=ctx,per_server=48,cap=312)
        print("PROFILE",target,"nomination_count",len(pool),"ms",round(1000*(time.perf_counter()-t),1))
        for size in (16,48,96):
            t=time.perf_counter()
            for item in pool[:size]:
                enr=lib._enrich_channel(item)
                lib.match_score_details(target,enr,["FR"],ctx,"best",preview=True)
            print("PROFILE",target,"score",min(len(pool),size),"ms",round((time.perf_counter()-t)*1000,1))
        t=time.perf_counter();rows=catalog.fast_rank_matches_all_servers(target,["FR"],context=ctx,per_server=42,topn=144)
        old_ms=(time.perf_counter()-t)*1000
        print("PROFILE",target,"full_rank",len(rows),"ms",round(old_ms,1))
        t=time.perf_counter()
        mega=catalog.fast_preview_mega_matches(target,["FR"],context=ctx,per_server=64,topn=192)
        new_ms=(time.perf_counter()-t)*1000
        print("PROFILE",target,"MEGA_192",len(mega),"ms",round(new_ms,1),
              "speedup_vs_previous",round(old_ms/max(new_ms,0.001),2))
