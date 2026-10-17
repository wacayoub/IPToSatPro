#!/usr/bin/env python3
"""Install ONLY SHA-pinned R80.2 FINAL Index Focus after private backup.

No connection to external servers, no publishing, no automatic GUI restart.
Explicit --install required; without the flag this only verifies readiness.
The final metadata-only package preserves the existing R80.1 engine and
checks pre/post mapping hashes. Never prints or uploads mappings or credentials.
"""
import argparse
import hashlib
import io
import json
import os
import re
import stat
import subprocess
import sys
import tarfile
from datetime import datetime
from pathlib import Path

BASE = Path("/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge")
CONF = Path("/etc/enigma2/SatIPTVBridge")
PACKAGE = Path("/tmp/iptosatpro-r80-final.ipk")
BACKUP_ROOT = Path("/home/root/iptosatpro-r76-backups")
EXPECTED_OLD = "1.0.46-r80.1-indexfocus-hotpath-rc1"
EXPECTED_NEW = "1.0.46-r80.2-final"
IPK_SHA = "5c7e48ba51e5ed1689c5930df72309c7c495cc702f5cff6b91142ddc2985606a"
IPK_BYTES = 461198
CORE_BEFORE = "74cd89b8c6a41b4537fd758cedb3a07b2bc0f9a5c215063e4c45b99e5d92cd2a"
CORE_AFTER = "74cd89b8c6a41b4537fd758cedb3a07b2bc0f9a5c215063e4c45b99e5d92cd2a"
PFX = "usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/"
EXTERNAL = {"etc/init.d/iptosat-tsbridge", "usr/bin/iptosat-tsbridge"}
SETTINGS = Path("/etc/enigma2/settings")
TRACKED = ("overrides.json","manual_aliases.json","resolved_mappings.json",
           "rejected_sources.json","player_overrides.json","import_spec.json",
           "r723_home_layout","r76_home_layout")

def require(test, msg):
    if not test:
        raise RuntimeError(msg)

def sha(blob):
    return hashlib.sha256(blob).hexdigest()

def file_hash(path):
    with path.open("rb") as stream:
        h=hashlib.sha256()
        while True:
            part=stream.read(1024*1024)
            if not part:
                return h.hexdigest()
            h.update(part)

def version(blob,name,expected):
    matches = re.findall(rb'(?m)^\s*' + name.encode() +
                         rb'\s*=\s*["\x27]([^"\x27\r\n]+)["\x27]',blob)
    require(matches == [expected.encode("utf-8")], "INSTALLED_VERSION_DIFFERS:"+name)

def tarfiles(blob):
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as ar:
        entries={}
        for member in ar.getmembers():
            require(member.isfile() or member.isdir(), "PACKAGE_LINK_OR_SPECIAL_ENTRY_BLOCKED")
            name=member.name
            while name.startswith("./"):
                name=name[2:]
            require(name and not name.startswith("/") and ".." not in Path(name).parts,
                    "UNSAFE_PACKAGE_PATH")
            if member.isfile():
                require(name not in entries, "DUPLICATE_PACKAGE_FILE")
                entries[name]=ar.extractfile(member).read()
        return entries

def unpack_package():
    require(not PACKAGE.is_symlink() and PACKAGE.is_file(), "STAGED_PACKAGE_ABSENT_OR_SYMLINK")
    require(PACKAGE.stat().st_size == IPK_BYTES and file_hash(PACKAGE)==IPK_SHA,
            "STAGED_PACKAGE_SHA_OR_SIZE_CHANGED")
    raw=PACKAGE.read_bytes()
    require(raw.startswith(b"!<arch>\n"),"NOT_AR_IPK")
    pieces={}
    at=8
    while at<len(raw):
        require(at+60<=len(raw),"TRUNCATED_IPK")
        h=raw[at:at+60]
        require(h[58:60]==b"\x60\n","INVALID_AR_HEADER")
        name=h[:16].decode("ascii").strip().rstrip("/")
        count=int(h[48:58].strip())
        require(count >= 0 and at+60+count<=len(raw) and name not in pieces,
                "INVALID_AR_MEMBER")
        pieces[name]=raw[at+60:at+60+count]
        at+=60+count+(count%2)
    require(set(pieces)=={"debian-binary","control.tar.gz","data.tar.gz"},
            "PACKAGE_ARCHIVE_MEMBERS_CHANGED")
    ct=tarfiles(pieces["control.tar.gz"])
    require("control" in ct and "postinst" in ct,"PACKAGE_CONTROL_MISSING")
    require(not (set(ct)&{"preinst","prerm","postrm"}),"DANGEROUS_NEW_MAINTAINER_SCRIPT")
    expected_post=("#!/bin/sh\n"
      "printf '%s\\n' 'IPToSatPro R80 FINAL installed; restart Enigma2 GUI manually via OpenATV.'\n"
      "exit 0\n").encode()
    require(ct["postinst"]==expected_post,"POSTINSTALL_HOOK_UNEXPECTED")
    control=ct["control"].decode("utf8")
    require("Maintainer: wacayoub\n" in control, "FINAL_MAINTAINER_INVALID")
    require("Description: IPToSat Pro R80 FINAL - Index Focus; hardware-tested core preserved" in control,
            "FINAL_DESCRIPTION_INVALID")
    require(re.search(r"(?m)^Version:\s*"+re.escape(EXPECTED_NEW)+r"\s*$",control),
            "PACKAGE_VERSION_MISMATCH")
    name_match=re.search(r"(?m)^Package:\s*([a-z0-9][a-z0-9+._-]*)\s*$",control)
    require(name_match,"INVALID_PACKAGE_NAME")
    files=tarfiles(pieces["data.tar.gz"])
    external=set(files)-{n for n in files if n.startswith(PFX)}
    require(external==EXTERNAL,"PACKAGE_EXTERNAL_FILE_SET_CHANGED")
    plugin_names={x[len(PFX):] for x in files if x.startswith(PFX)}
    require(len(plugin_names)==87,"EXPECTED_87_PLUGIN_FILES")
    for n in EXTERNAL:
        local=Path("/")/n
        require(local.is_file() and not local.is_symlink() and local.read_bytes()==files[n],
                "SERVICE_ASSET_NOT_IDENTICAL:"+n)
    require(sha(files[PFX+"core.py"])==CORE_AFTER,"PACKAGE_CORE_SHA_CHANGED")
    version(files[PFX+"plugin.py"],"PLUGIN_VERSION",EXPECTED_NEW)
    version(files[PFX+"updater.py"],"CURRENT_VERSION",EXPECTED_NEW)
    return name_match.group(1)

def existing_installer_scripts(pkgname):
    found=[]
    for base in (Path("/usr/lib/opkg/info"),Path("/var/lib/opkg/info"),
                 Path("/lib/opkg/info")):
        for suffix in (".prerm",".postrm"):
            p=base/(pkgname+suffix)
            if p.is_file():
                found.append(str(p))
    require(not found,"OLD_MAINTAINER_SCRIPTS_NEED_REVIEW")
    return True

def receiver_check():
    require(os.geteuid()==0,"ROOT_REQUIRED")
    require(BASE.is_dir() and CONF.exists(),"EXPECTED_PLUGIN_OR_CONFIG_NOT_PRESENT")
    version((BASE/"plugin.py").read_bytes(),"PLUGIN_VERSION",EXPECTED_OLD)
    version((BASE/"updater.py").read_bytes(),"CURRENT_VERSION",EXPECTED_OLD)
    require(file_hash(BASE/"core.py")==CORE_BEFORE,"INSTALLED_CORE_CHANGED")
    pkg=unpack_package()
    existing_installer_scripts(pkg)
    require(Path("/usr/bin/opkg").exists() or Path("/bin/opkg").exists() or
            Path("/usr/sbin/opkg").exists(),"OPKG_NOT_FOUND")
    return pkg

def map_hashes():
    names=[SETTINGS]+[CONF/n for n in TRACKED]
    results={}
    for path in names:
        if path.is_file() and not path.is_symlink():
            results[str(path)]=file_hash(path)
    return results

def tar_backup(target,paths):
    command=["tar","-czf",str(target),"-C","/"]+[
        str(path).lstrip("/") for path in paths if path.exists()]
    require(len(command)>5,"EMPTY_BACKUP_TARGET")
    subprocess.run(command,check=True,stdout=subprocess.DEVNULL)
    subprocess.run(["tar","-tzf",str(target)],check=True,stdout=subprocess.DEVNULL)
    require(target.stat().st_size>100,"BACKUP_EMPTY")
    target.chmod(0o600)

def backups():
    require(not BACKUP_ROOT.is_symlink(),"BACKUP_ROOT_SYMLINK_BLOCKED")
    BACKUP_ROOT.mkdir(mode=0o700,parents=True,exist_ok=True)
    name="r80-final-"+datetime.now().strftime("%Y%m%dT%H%M%S")+"-"+str(os.getpid())
    dest=BACKUP_ROOT/name
    dest.mkdir(mode=0o700,exist_ok=False)
    code=dest/"plugin-code-before-r80-final.tar.gz"
    tar_backup(code,[BASE]+[Path("/")/x for x in sorted(EXTERNAL)])
    config=[]
    if CONF.is_dir():
        config.append(CONF)
    if SETTINGS.is_file():
        config.append(SETTINGS)
    if config:
        tar_backup(dest/"private-config-before-r80-final.tar.gz",config)
    return dest,code

def restore_code(code):
    try:
        subprocess.run(["tar","-xzf",str(code),"-C","/"],check=True)
        return "CODE_RESTORED_FROM_PRIVATE_BACKUP__OPKG_STATE_NOT_VERIFIED"
    except Exception as exc:
        return "CODE_RESTORE_FAILED__MANUAL_RECOVERY_REQUIRED:"+type(exc).__name__

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--install",action="store_true",help="Explicit upgrade only after SHA and backup checks")
    args=ap.parse_args()
    os.umask(0o077)
    report={"audit":"R80 FINAL pinned guarded installation",
            "receiver_release_final":True,"mapping_values_exported":False}
    try:
        pkg=receiver_check()
        report.update({"verified_candidate_sha256":IPK_SHA,"package_name":pkg,
                       "installed_before":EXPECTED_OLD,
                       "package_version":EXPECTED_NEW,
                       "installed_code_modified":False})
        if not args.install:
            report["result"]="INSTALL_READINESS_PASS__NO_CHANGES"
            print(json.dumps(report,indent=2,sort_keys=True))
            return 0
        before=map_hashes()
        folder,code=backups()
        report["backup_path"]=str(folder)
        report["private_backup_verified"]=True
        report["tracked_config_files"]=len(before)
        print("BACKUP_VERIFIED: "+str(folder),flush=True)
        cmd=["opkg","install",str(PACKAGE)]
        rc=subprocess.run(cmd,check=False).returncode
        ok=(rc==0)
        if ok:
            try:
                version((BASE/"plugin.py").read_bytes(),"PLUGIN_VERSION",EXPECTED_NEW)
                version((BASE/"updater.py").read_bytes(),"CURRENT_VERSION",EXPECTED_NEW)
                require(file_hash(BASE/"core.py")==CORE_AFTER,"CORE_AFTER_INSTALL_CHANGED")
                require(map_hashes()==before,"USER_CONFIG_OR_MAPPINGS_CHANGED")
            except Exception as exc:
                ok=False
                report["post_install_error"]=type(exc).__name__+": "+str(exc)[:120]
        if not ok:
            report["result"]="INSTALL_FAILED_OR_POSTCHECK_MISMATCH"
            report["opkg_rc"]=rc
            report["code_recovery"]=restore_code(code)
            report["installed_code_modified"]="POSSIBLY_RESTORED__REQUIRES_CHECK"
            print(json.dumps(report,indent=2,sort_keys=True))
            return 5
        report["result"]="R80_FINAL_METADATA_INSTALLED__GUI_RESTART_CHECK_REQUIRED"
        report["installed_code_modified"]=True
        report["mapping_hashes_unchanged"]=True
        report["gui_restarted"]=False
        report["opkg_rc"]=rc
        print(json.dumps(report,indent=2,sort_keys=True))
        return 0
    except Exception as exc:
        report["result"]="INSTALL_GUARD_BLOCKED"
        report["reason"]=type(exc).__name__+": "+str(exc)[:170]
        print(json.dumps(report,indent=2,sort_keys=True))
        return 3

if __name__=="__main__":
    sys.exit(main())
