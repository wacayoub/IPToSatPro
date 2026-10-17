#!/usr/bin/env python3
"""Opt-in R80 UNMAP RC1 *online update channel*, no package installation.

Enable with --enable (requires root and GUI restart after success).
Restore the stable feed with --stable (also requires GUI restart).
Refuses unrecognized receiver builds. Makes a private pre-change backup.
Never reads or displays IPTV credentials; never changes mapping files.
"""
import argparse
import hashlib
import json
import os
import re
import stat
import sys
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

BASE=Path("/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge")
CONF=Path("/etc/enigma2/SatIPTVBridge")
SETTINGS=Path("/etc/enigma2/settings")
UPDATER=BASE/"updater.py"
PLUGIN=BASE/"plugin.py"
CORE=BASE/"core.py"
BACKUPS=Path("/home/root/iptosatpro-r80-unmap-backups")
STABLE_URL="https://raw.githubusercontent.com/wacayoub/IPToSatPro/release/r80-indexfocus-final-20261017/staging/r80-final.update.json"
BETA_URL="https://raw.githubusercontent.com/wacayoub/IPToSatPro/fix/r80-unmap-stale-candidate-20261017/staging/r80-unmap-rc1.update.json"
PAYLOAD_URL="https://raw.githubusercontent.com/wacayoub/IPToSatPro/fix/r80-unmap-stale-candidate-20261017/payload/r80-unmap-rc1.b64"
STABLE_UPDATER_SHA="7bf4f16f4d339e8fec02e0f1a05763d0d913ab607fba2fb086ce6d1cc3e0e89c"
CORE_SHA="74cd89b8c6a41b4537fd758cedb3a07b2bc0f9a5c215063e4c45b99e5d92cd2a"
BETA_SHA="08bcba2ad5982de9d55589bb5f0afe2c727e6e7a74cc2e90411cf7be2ca8a3e2"
BETA_SIZE=462254
VERSION_STABLE="1.0.46-r80.2-final"
VERSION_BETA="1.0.46-r80.2.1-unmap-rc1"
FEED_PREFIX='MANIFEST_URL = "'
FEED_PATTERN=re.compile(rb'(?m)^MANIFEST_URL = "([^"\r\n]+)"$')


def hashbytes(blob):
    return hashlib.sha256(blob).hexdigest()


def require(ok, code):
    if not ok:
        raise RuntimeError(code)


def read_safe(path):
    require(path.is_file() and not path.is_symlink(), "EXPECTED_REGULAR_FILE_MISSING:"+path.name)
    return path.read_bytes()


def saved_version(data):
    hits=re.findall(rb'(?m)^PLUGIN_VERSION\s*=\s*"([^"\r\n]+)"',data)
    require(len(hits)==1,"UNKNOWN_INSTALLED_VERSION")
    return hits[0].decode()


def online_feed_check():
    req=Request(BETA_URL,headers={"User-Agent":"IPToSatPro-R80-UNMAP-beta-optin/1.0"})
    with urlopen(req,timeout=20) as response:
        require(response.geturl()==BETA_URL,"UNEXPECTED_GITHUB_REDIRECT")
        data=response.read(8193)
    require(len(data)<=8192,"BETA_MANIFEST_OVERSIZED")
    obj=json.loads(data)
    require(obj.get("version")==VERSION_BETA,"BETA_VERSION_MISMATCH")
    require(obj.get("sha256")==BETA_SHA and obj.get("size")==BETA_SIZE,
            "BETA_SHA_OR_SIZE_MISMATCH")
    require(obj.get("parts")==[PAYLOAD_URL],"BETA_PART_URL_MISMATCH")
    require(obj.get("beta") is True,"NOT_A_BETA_FEED")
    return obj


def archive_backup():
    require(not BACKUPS.is_symlink(),"BACKUP_ROOT_IS_SYMLINK")
    BACKUPS.mkdir(mode=0o700,parents=True,exist_ok=True)
    BACKUPS.chmod(0o700)
    folder=BACKUPS/("optin-"+datetime.now().strftime("%Y%m%dT%H%M%S")+"-"+str(os.getpid()))
    folder.mkdir(mode=0o700,exist_ok=False)
    output=folder/"before-online-beta.tar.gz"
    with tarfile.open(output,mode="w:gz") as tar:
        for path in (BASE,CONF,SETTINGS):
            if path.exists():
                tar.add(path,arcname=str(path).lstrip("/"),recursive=True)
    require(output.stat().st_size>1000,"BACKUP_TOO_SMALL")
    output.chmod(0o600)
    return output


def replace_updater(original, replacement):
    # Write in the same filesystem, atomically. Do not follow symlinks.
    s=UPDATER.stat()
    with tempfile.NamedTemporaryFile(mode="wb",prefix=".r80-unmap-optin-",
                                    dir=str(BASE),delete=False) as tmp:
        target=Path(tmp.name)
        try:
            tmp.write(replacement)
            tmp.flush()
            os.fsync(tmp.fileno())
        except Exception:
            target.unlink(missing_ok=True)
            raise
    try:
        os.chmod(target,stat.S_IMODE(s.st_mode))
        os.chown(target,s.st_uid,s.st_gid)
        require(hashbytes(read_safe(target))==hashbytes(replacement),"WRITE_HASH_MISMATCH")
        require(read_safe(UPDATER)==original,"CONCURRENT_UPDATER_CHANGE")
        os.replace(str(target),str(UPDATER))
        require(read_safe(UPDATER)==replacement,"POST_WRITE_DIFFERENCE")
    finally:
        target.unlink(missing_ok=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    g=ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--enable",action="store_true",help="Opt into isolated UNMAP RC1 beta Online Update")
    g.add_argument("--stable",action="store_true",help="Restore stable R80-only update feed (no downgrade)")
    args=ap.parse_args()
    report={"installed_package_changed":False,"opkg_executed":False,
            "mappings_changed":False,"enigma2_restarted":False}
    try:
        require(os.geteuid()==0,"ROOT_REQUIRED")
        updater=read_safe(UPDATER)
        plugin=read_safe(PLUGIN)
        core=read_safe(CORE)
        require(hashbytes(core)==CORE_SHA,"UNKNOWN_CORE_NOT_R80_FINAL")
        version=saved_version(plugin)
        require(version in (VERSION_STABLE,VERSION_BETA),"OTHER_PLUGIN_VERSION_BLOCKED")
        hits=FEED_PATTERN.findall(updater)
        require(len(hits)==1,"FEED_DECLARATION_NOT_UNIQUE")
        previous=hits[0].decode()
        require(previous in (STABLE_URL,BETA_URL),"UNRECOGNIZED_UPDATE_CHANNEL")
        target=BETA_URL if args.enable else STABLE_URL
        if args.enable:
            require(version==VERSION_STABLE or previous==BETA_URL,
                    "CANNOT_ENABLE_TEST_FEED_ON_UNKNOWN_BUILD")
            online_feed_check()
            if previous==STABLE_URL:
                require(hashbytes(updater)==STABLE_UPDATER_SHA,
                        "STABLE_UPDATER_BYTES_DIFFER_FROM_APPROVED")
        if previous==target:
            report.update({"result":"ONLINE_CHANNEL_ALREADY_SELECTED",
                           "version":version,"active_channel":"test-unmap" if args.enable else "stable"})
            print(json.dumps(report,indent=2))
            return 0
        old_line=(FEED_PREFIX+previous+'"').encode()
        new_line=(FEED_PREFIX+target+'"').encode()
        require(updater.count(old_line)==1,"EXPECTED_FEED_DECLARATION_MISMATCH")
        new_data=updater.replace(old_line,new_line,1)
        compile(new_data,str(UPDATER),"exec")
        backup=archive_backup()
        replace_updater(updater,new_data)
        report.update({
            "result":"UNMAP_TEST_ONLINE_CHANNEL_ENABLED" if args.enable else "STABLE_ONLINE_CHANNEL_RESTORED",
            "version":version,
            "backup_file":str(backup),
            "active_channel":"test-unmap" if args.enable else "stable",
            "gui_restart_required":True,
            "update_installed":False,
        })
        print(json.dumps(report,indent=2,sort_keys=True))
        return 0
    except Exception as exc:
        report.update({"result":"ONLINE_CHANNEL_CHANGE_BLOCKED",
                       "reason":type(exc).__name__+": "+str(exc)[:170]})
        print(json.dumps(report,indent=2,sort_keys=True))
        return 3


if __name__=="__main__":
    sys.exit(main())
