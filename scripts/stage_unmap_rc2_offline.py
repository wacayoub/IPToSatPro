#!/usr/bin/env python3
"""Rebuild EXACT R80.2.2 UNMAP RC2 beta from frozen on-branch RC1 payload.

Offline, deterministic and fail closed. No opkg, receiver, secret, runtime
settings or stable update feed touched.
"""
import base64
import copy
import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'payload/r80-unmap-rc1.b64'
DEST=ROOT/'payload/r80-unmap-rc2.b64'
META=ROOT/'staging/r80-unmap-rc2.update.json'
SUM=ROOT/'staging/r80-unmap-rc2.sha256'
BEFORE_SHA="08bcba2ad5982de9d55589bb5f0afe2c727e6e7a74cc2e90411cf7be2ca8a3e2"
MONITOR_RC1_SHA="df5ec38edcf10944bcafcb3bdbf7f63a6ec12e7ce873b51c5de4e4bf5ed4aa23"
MONITOR_RC2_SHA="2d80674e70683c23abe78d362addd6a9b5841217f85703c8366ad3d7f942ab80"
RC2_SHA="61acad0521f98ad8ea12c1d42e53d36d595ccd479874ee706a9ff52e69e9af4b"
CORE_SHA="74cd89b8c6a41b4537fd758cedb3a07b2bc0f9a5c215063e4c45b99e5d92cd2a"
OLD="1.0.46-r80.2.1-unmap-rc1"
NEW="1.0.46-r80.2.2-unmap-rc2"
BRANCH="fix/r80-unmap-stale-candidate-20261017"
PFX="usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/"
OLD_URL="https://raw.githubusercontent.com/wacayoub/IPToSatPro/"+BRANCH+"/staging/r80-unmap-rc1.update.json"
NEW_URL="https://raw.githubusercontent.com/wacayoub/IPToSatPro/"+BRANCH+"/staging/r80-unmap-rc2.update.json"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def once(src, old, new):
    if src.count(old) != 1:
        raise ValueError("ANCHOR_NOT_UNIQUE: "+old[:90]+" count="+str(src.count(old)))
    return src.replace(old,new,1)


def ar_unpack(raw):
    assert raw[:8]==b"!<arch>\n"
    result=[]
    pos=8
    while pos<len(raw):
        h=raw[pos:pos+60]
        assert len(h)==60 and h[58:60]==b"\x60\n"
        name=h[:16].decode("ascii").strip().rstrip("/")
        size=int(h[48:58])
        content=raw[pos+60:pos+60+size]
        assert len(content)==size
        result.append((name,h,content))
        pos+=60+size+size%2
    assert pos==len(raw)
    assert {x[0] for x in result}=={"debian-binary","control.tar.gz","data.tar.gz"}
    return result


def ar_pack(members):
    out=bytearray(b"!<arch>\n")
    for name,h,body in members:
        out+=h[:48]+str(len(body)).encode().ljust(10)+b"\x60\n"
        out+=body
        if len(body)%2: out+=b"\n"
    return bytes(out)


def tar_unpack(blob):
    with tarfile.open(fileobj=io.BytesIO(blob),mode="r:gz") as tf:
        members=tf.getmembers()
        assert all(m.isfile() or m.isdir() for m in members)
        files={m.name.removeprefix("./"):tf.extractfile(m).read()
               for m in members if m.isfile()}
    assert len(files)==sum(m.isfile() for m in members)
    return members,files


def tar_pack(members,files):
    out=io.BytesIO()
    with gzip.GzipFile(fileobj=out,mode="wb",mtime=0,filename="") as z:
        with tarfile.open(fileobj=z,mode="w",format=tarfile.GNU_FORMAT) as tf:
            for m in members:
                key=m.name.removeprefix("./")
                w=copy.copy(m)
                if m.isfile():
                    assert key in files
                    body=files[key]
                    w.size=len(body)
                    tf.addfile(w,io.BytesIO(body))
                else:tf.addfile(w)
    return out.getvalue()


def monitor_patch(s):
    s=once(s,'    effective_quality_info,\n','    effective_quality_info,\n    quality_info,\n')
    s=once(s,'    def _direct_candidate_plan(self, channel, source="LEARNED"):', '''    def _r802_strict_manual_pin(self, channel):
        """A user-corrected GREEN lock pins the chosen stream, not its HD alias.

        The persisted override controls this; old generic manual mappings keep
        their established backup behavior. No extra files or global cache writes.
        """
        if not channel:
            return False
        try:
            rec = self._load_overrides().get(sat_service_key(self.current_sat_ref_string))
            return bool(isinstance(rec, dict) and rec.get("forced_correct")
                        and str(rec.get("channel_id") or "") == channel_fingerprint(channel))
        except Exception:
            return False

    def _direct_candidate_plan(self, channel, source="LEARNED"):''')
    s=once(s,'''        direct_fp = channel_fingerprint(channel)
        try:
            replicas = list(self.catalog._exact.get(target_norm, [])) if target_norm else []''','''        direct_fp = channel_fingerprint(channel)
        exact_user_pin = bool(source == "MANUAL_LOCK" and self._r802_strict_manual_pin(channel))
        # Use the *labelled* variant for a manual correction, never a stale
        # receiver-observed quality inherited from a different stream. Missing
        # quality labels permit the exact fingerprint only (fail-closed).
        pin_variant = quality_info(target_name)[1] if exact_user_pin else 0
        try:
            replicas = list(self.catalog._exact.get(target_norm, [])) if target_norm else []''')
    s=once(s,'''        for ch in replicas:
            fp = channel_fingerprint(ch)
            if not fp or fp in seen or fp in rejected:
                continue
            seen.add(fp)
            if self._health_blocked(ch):
                if fp == direct_fp:
                    blocked_direct = ch
                continue
            qlabel, qrank, _qsource = effective_quality_info(ch)''','''        for ch in replicas:
            fp = channel_fingerprint(ch)
            if not fp or fp in seen or fp in rejected:
                continue
            seen.add(fp)
            if exact_user_pin and fp != direct_fp:
                # A corrected FHD lock must not silently become HD/SD, even
                # when their names share the same normalized IPTV identity.
                candidate_variant = quality_info(str(ch.get("name") or ""))[1]
                if pin_variant == 300 or candidate_variant != pin_variant:
                    continue
            # Previous health failure may predate the user's new GREEN choice.
            # Give the exact newly corrected pin one fresh attempt each SAT zap;
            # failures *within* this zap still prevent an immediate retry loop.
            if exact_user_pin and fp == direct_fp and fp not in self.failed_candidate_ids:
                blocked = False
            else:
                blocked = self._health_blocked(ch)
            if blocked:
                if fp == direct_fp:
                    blocked_direct = ch
                continue
            qlabel, qrank, _qsource = effective_quality_info(ch)''')
    s=once(s,'''        if source == "MANUAL_LOCK":
            # r66-beta: retain saved manual primary unchanged.''','''        if source == "MANUAL_LOCK" and exact_user_pin:
            # A new explicit correction outranks the old health/fast-cache
            # shortcut. Same-variant BACKUP1/BACKUP2 remain after the pin only.
            rows.sort(key=lambda row: (0 if channel_fingerprint(row[0]) == direct_fp else 1,
                                       int(row[4]), int(row[5])))
            self._log("MANUAL_EXACT_PIN", "sat=%r chosen=%r replicas=%d" % (
                self.current_sat_name, target_name, len(rows)))
        elif source == "MANUAL_LOCK":
            # r66-beta: retain saved manual primary unchanged.''')
    s=once(s,'''                    if last_bad > last_ok and 0 <= time.time() - last_bad < 900:
                        # Only use a replica with confirmed health; never send two''','''                    if (last_bad > last_ok and 0 <= time.time() - last_bad < 900
                            and not self._r802_strict_manual_pin(direct)):
                        # Only use a replica with confirmed health; never send two''')
    compile(s,"monitor_rc2.py","exec")
    return s


def main():
    source=base64.b64decode(b"".join(SOURCE.read_bytes().split()),validate=True)
    assert len(source)==462254 and sha(source)==BEFORE_SHA
    members=ar_unpack(source)
    dc=next(x for x in members if x[0]=="data.tar.gz")
    cc=next(x for x in members if x[0]=="control.tar.gz")
    dm,data=tar_unpack(dc[2])
    cm,ctl=tar_unpack(cc[2])
    assert len(data)==89 and set(ctl)=={"control","postinst"}
    updated=dict(data)
    src_monitor=data[PFX+"monitor.py"]
    assert sha(src_monitor)==MONITOR_RC1_SHA
    patched=monitor_patch(src_monitor.decode("utf-8")).encode("utf-8")
    assert sha(patched)==MONITOR_RC2_SHA
    updated[PFX+"monitor.py"]=patched
    pv=once(data[PFX+"plugin.py"].decode("utf-8"),
            'PLUGIN_VERSION = "'+OLD+'"','PLUGIN_VERSION = "'+NEW+'"')
    updated[PFX+"plugin.py"]=pv.encode("utf-8")
    u=data[PFX+"updater.py"].decode("utf-8")
    u=once(u,'CURRENT_VERSION = "'+OLD+'"','CURRENT_VERSION = "'+NEW+'"')
    u=once(u,OLD_URL,NEW_URL)
    updated[PFX+"updater.py"]=u.encode("utf-8")
    assert sha(updated[PFX+"core.py"])==CORE_SHA
    diffs={n for n in data if data[n]!=updated[n]}
    assert diffs=={PFX+"monitor.py",PFX+"plugin.py",PFX+"updater.py"}
    for path,body in updated.items():
        if path.endswith(".py"):
            compile(body,path,"exec")
    ctrl=dict(ctl)
    c=ctrl["control"].decode("utf-8")
    c=once(c,"Version: "+OLD+"\n","Version: "+NEW+"\n")
    c=once(c,"Description: IPToSat Pro R80.2.1 UNMAP targeted hotfix RC1; manual beIN corrections",
           "Description: IPToSat Pro R80.2.2 UNMAP RC2; exact corrected FHD lock precedence")
    ctrl["control"]=c.encode("utf-8")
    ctrl["postinst"]=b"#!/bin/sh\nprintf '%s\\n' 'IPToSatPro UNMAP RC2 staged; restart Enigma2 GUI manually.'\nexit 0\n"
    outdata=tar_pack(dm,updated)
    outcontrol=tar_pack(cm,ctrl)
    result=ar_pack([(n,h,outcontrol if n=="control.tar.gz" else outdata if n=="data.tar.gz" else body)
                    for n,h,body in members])
    assert len(result)==463008 and sha(result)==RC2_SHA, (len(result),sha(result))
    verify=ar_unpack(result)
    assert tar_unpack(next(x[2] for x in verify if x[0]=="data.tar.gz"))[1]==updated
    assert tar_unpack(next(x[2] for x in verify if x[0]=="control.tar.gz"))[1]==ctrl
    assert not DEST.exists() and not META.exists(), "NEVER_OVERWRITE_EXISTING_RELEASE"
    payload=base64.b64encode(result)+b"\n"
    manifest={
      "version":NEW,
      "sha256":sha(result),"size":len(result),
      "parts":["https://raw.githubusercontent.com/wacayoub/IPToSatPro/"+BRANCH+"/payload/r80-unmap-rc2.b64"],
      "notes":"R80.2.2 UNMAP RC2 beta: preserve corrected FHD manual GREEN pin precedence over old known-good HD variant; same-variant backup only; previous user UNMAP fixes kept. Streaming codec and core unchanged. Single beIN SAT hardware confirmation required.",
      "beta":True,"production_published":False,"final_binary_receiver_tested":False,
      "installation_requires_explicit_flag":True,
      "source_version":OLD,"source_sha256":BEFORE_SHA}
    DEST.write_bytes(payload)
    META.write_text(json.dumps(manifest,indent=2)+"\n")
    SUM.write_text(sha(result)+"  iptosatpro-r80.2.2-unmap-rc2-NOT_INSTALLED.ipk\n")
    print(json.dumps({"version":NEW,"sha256":sha(result),"size":len(result),
                       "created_online":True,"production_published":False},indent=2))


if __name__=="__main__":
    main()
