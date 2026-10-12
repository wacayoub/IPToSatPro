#!/usr/bin/env python3
"""R74.16: intentional UNMAP per SAT service + FTA/crypted roster icons/filter.

BLUE in LEFT SAT panel asks confirmation and marks one SAT service USER_UNMAPPED,
removing its old alias/learned association. BLUE in RIGHT IPTV panel keeps
candidate details. Preview + bulk AutoScan respect the user-unmapped marker;
GREEN manual lock replaces that marker using existing save logic.
Key 6 cycles ALL -> CRYPT -> FTA -> ALL within current native bouquet,
preserving native bouquet order. Key 7 still switches bouquet/satellite.
SAT labels add 🔒 / 🔓 / ? from cached static DVB CAIDs, not current
decoder status. Missing CAIDs may be unknown; this is NOT a live decryption test.

Use --check first. Only installed plugin.py changes; maps change only when the
user confirms a BLUE/UNMAP choice inside Enigma2. Backup and rollback supplied.
"""
import argparse
import os
import shutil
import stat
import tempfile
from pathlib import Path

TARGET=Path("/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/plugin.py")
BACKUP="plugin.py.r7416-unmap-crypt-original.bak"
TAG="R7416_UNMAP_CRYPT_ACCESS"

HELPERS='''# R7416_UNMAP_CRYPT_ACCESS
def _r7416_crypt_icon(crypted):
    if crypted is True:
        return "🔒"
    if crypted is False:
        return "🔓"
    return "?"


def _r7416_unmap_mapping(sat_ref, sat_name=""):
    """Remove one chosen SAT mapping and prevent background auto-relocking.

    A small user-unmapped marker replaces the old mapping.  This is NOT an
    active IPTV lock (no channel_id). Saved aliases and learned mappings for
    this same SAT key are also removed; all other keys are untouched.
    Snapshot the three original files before writing anything.
    """
    import json
    import shutil
    import tempfile
    key=sat_service_key(sat_ref)
    if not key:
        raise ValueError("Missing SAT service key")
    paths=(OVERRIDE_PATH, ALIAS_PATH, LEARNED_MAP_PATH)
    sources={}
    original={}
    for path in paths:
        try:
            with open(path,"rb") as handle:
                raw=handle.read()
            data=json.loads(raw.decode("utf-8"))
            if not isinstance(data,dict):
                raise ValueError("Expected JSON dictionary: "+path)
            sources[path]=data
            original[path]=raw
        except FileNotFoundError:
            sources[path]={}
            original[path]=None
    active=sources[OVERRIDE_PATH].get(key)
    if not isinstance(active,dict) or not active.get("channel_id"):
        return False,""

    _ensure_base_dir()
    directory=os.path.join(os.path.dirname(OVERRIDE_PATH),"unmap-backups")
    os.makedirs(directory,exist_ok=True)
    stamp=time.strftime("%Y%m%dT%H%M%S")
    backup=tempfile.mkdtemp(prefix=stamp+"-",dir=directory)
    os.chmod(backup,0o700)
    # Preserve previous files for user recovery; never log credentials/URLs.
    for path,raw in original.items():
        if raw is not None:
            dest=os.path.join(backup,os.path.basename(path))
            with open(dest,"wb") as f:
                f.write(raw)
            os.chmod(dest,0o600)
    sources[OVERRIDE_PATH][key]={
        "sat_ref":str(sat_ref),"sat_name":clean_display_name(sat_name or ""),
        "user_unmapped":True,"locked":False,
        "saved_at":time.strftime("%Y-%m-%d %H:%M:%S")
    }
    sources[ALIAS_PATH].pop(key,None)
    sources[LEARNED_MAP_PATH].pop(key,None)

    def _write(path,raw):
        fd,tmp=tempfile.mkstemp(prefix=".unmap-",suffix=".tmp",
                                dir=os.path.dirname(path))
        try:
            with os.fdopen(fd,"wb") as f:
                f.write(raw)
                f.flush()
                os.fsync(f.fileno())
            os.chmod(tmp,0o600)
            os.replace(tmp,path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    changed=[]
    try:
        for path in paths:
            data=sources[path]
            # Do not create absent alias/learned files just to delete a key.
            if path!=OVERRIDE_PATH and original[path] is None:
                continue
            packed=json.dumps(data,ensure_ascii=False,indent=2).encode("utf-8")
            _write(path,packed)
            changed.append(path)
    except Exception:
        for path in reversed(changed):
            old=original[path]
            try:
                if old is None:
                    os.unlink(path)
                else:
                    _write(path,old)
            except Exception:
                pass
        raise

    if MONITOR is not None:
        for method in ("invalidate_overrides","invalidate_learned_mappings",
                       "invalidate_manual_aliases"):
            try:
                getattr(MONITOR,method)()
            except Exception:
                pass
        try:
            MONITOR._log("MANUAL_UNMAP","sat=%r user_unmapped=1"%(key,))
        except Exception:
            pass
    return True,backup


'''

CLASS_METHODS='''    def _r7416_request_unmap(self):
        """BLUE on SAT: ask before removing only this service association."""
        row=self._selected_sat_row() or {}
        raw=str(row.get("ref") or "")
        key=sat_service_key(raw)
        mapping=(self._manual_overrides or {}).get(key)
        if not isinstance(mapping,dict) or not mapping.get("channel_id"):
            self["detail"].setText("No locked association for this SAT service • BLUE opens IPTV details on right")
            self._focus_right()
            return
        self._r7416_pending_unmap=(key,raw,str(row.get("name") or "SAT channel"))
        message=("UNMAP only this SAT channel?\\n\\n"+
                 clean_display_name(row.get("name") or "SAT channel")+
                 "\\nPrevious IPTV: "+clean_display_name(mapping.get("name") or "?")+
                 "\\n\\nAuto Mapping will not relock until you manually choose GREEN.")
        try:
            self.session.openWithCallback(
                self._r7416_confirm_unmap,MessageBox,message,
                type=MessageBox.TYPE_YESNO,default=False)
        except Exception as error:
            self["detail"].setText("UNMAP confirmation unavailable: "+str(error)[:90])

    def _r7416_confirm_unmap(self,accepted=False):
        if not accepted:
            self._r7416_pending_unmap=None
            return
        requested=getattr(self,"_r7416_pending_unmap",None)
        self._r7416_pending_unmap=None
        if not requested:
            return
        key,raw,sat_name=requested
        row=self._selected_sat_row() or {}
        if sat_service_key(row.get("ref") or "")!=key:
            self["detail"].setText("SAT selection changed • UNMAP cancelled")
            return
        try:
            changed,backup=_r7416_unmap_mapping(raw,sat_name)
            if not changed:
                self["status"].setText("UNMAP • channel was already unlocked")
                return
            self._refresh_mapping_caches(force=True)
            # Old mapping-derived row flags cannot remain SAFE/MANUAL in view.
            for values in (self.channels,self._r732_auto_rows):
                for ch in values:
                    if isinstance(ch,dict):
                        ch.pop("_r735_verified_manual_lock",None)
                        ch.pop("_r735_old_auto_lock",None)
                        ch.pop("auto_best_lock",None)
            self._sat_list_dirty=True
            self._render_sat_list(keep_index=True)
            self._render_source_list(keep_index=True)
            self._update_header()
            self["status"].setText("UNMAPPED • SAT only • manual GREEN can remap • browser stays open")
            self["detail"].setText("Old mapping cleared. Backup stored under unmap-backups; select IPTV candidate and GREEN to correct")
            _startup_log("PREVIEW_UNMAP","sat=%r user_unmapped=1"%(key,))
        except Exception as error:
            self["status"].setText("UNMAP FAILED • no confirmed mapping change")
            self["detail"].setText(str(error)[:150])

    def _r7416_access_cycle(self):
        """Filter the native bouquet view in memory without changing bouquets."""
        if getattr(self,"_r7416_all_sat_rows",None) is None:
            self._r7416_all_sat_rows=list(self.sat_rows or [])
        allrows=self._r7416_all_sat_rows
        current=getattr(self,"_r7416_access_filter","ALL")
        nextmode={"ALL":"CRYPT","CRYPT":"FTA","FTA":"ALL"}.get(current,"ALL")
        wanted=True if nextmode=="CRYPT" else False if nextmode=="FTA" else None
        view=(list(allrows) if nextmode=="ALL" else
              [r for r in allrows if r.get("crypted") is wanted])
        previous=str((self._selected_sat_row() or {}).get("ref") or "")
        selected=next((i for i,r in enumerate(view)
                       if r.get("ref")==previous),0)
        self._suppress_sat_change=True
        try:
            self._r7416_access_filter=nextmode
            self.sat_rows=view
            self.sat_index=selected
            self._sat_list_rendered=None
            self._sat_list_source_id=None
            self._sat_list_dirty=True
            self._render_sat_list(keep_index=False)
        finally:
            self._suppress_sat_change=False
        self._set_focus("left")
        if view:
            self._sat_selection_changed()
        mode_label={"ALL":"ALL TV","CRYPT":"🔒 CRYPTED","FTA":"🔓 FTA"}[nextmode]
        unknown=sum(1 for r in allrows if r.get("crypted") is None)
        self["status"].setText("BOUQUET FILTER • %s • %d shown / %d total • %d unknown" %
                               (mode_label,len(view),len(allrows),unknown))

'''

def replace_once(source,before,after,label,expected=1):
    n=source.count(before)
    if n!=expected:
        raise ValueError("R7416 incompatible %s anchor count=%d"%(label,n))
    return source.replace(before,after,expected)


def replace_in_method(source,method,before,after,label):
    """Patch a verified class method or module-level function exactly once."""
    class_marker="    def "+method+"("
    top_marker="def "+method+"("
    begin=source.find(class_marker)
    is_top=False
    if begin<0:
        begin=source.find("\n"+top_marker)
        if begin>=0:begin+=1
        is_top=True
    if begin<0:
        raise ValueError("R7416 missing method "+method)
    if is_top:
        ends=[source.find(token,begin+len(top_marker)) for token in
              ("\ndef ","\nclass ")]
    else:
        ends=[source.find("\n    def ",begin+len(class_marker))]
    stops=[n for n in ends if n>=0]
    end=min(stops) if stops else len(source)
    part=source[begin:end]
    if part.count(before)!=1 and part.count("\n"+before)==1:
        before="\n"+before
        after="\n"+after
    if part.count(before)!=1:
        raise ValueError("R7416 %s in %s anchor count=%d" %
                         (label,method,part.count(before)))
    return source[:begin]+part.replace(before,after,1)+source[end:]

def patch(source):
    if TAG in source:
        return source,"already-installed"
    for tag in ("R7411_STAY_PREVIEW_PROVIDER_LANGUAGE_RESOLUTION",
                "R7412_FAST_PREVIEW_SHORTLIST",
                "R7413_PREVIEW_INLINE_NO_HIDE",
                "R7414_PREVIEW_FAST_SEED_MANUAL_LOCK",
                "R7415_FIRSTPAINT_GREEN_ANY_FOCUS"):
        if tag not in source:
            raise ValueError("Missing installed prerequisite "+tag)

    source=replace_once(source,'def _r74_active_bouquet_root():',
                        HELPERS+'def _r74_active_bouquet_root():',
                        "extra helpers")
    source=replace_once(source,'    def _blue_action(self):',
                        CLASS_METHODS+'    def _blue_action(self):',
                        "GUI methods")

    source=replace_in_method(source,"_blue_action",
            '''        if self.focus != "right":
            self._focus_right()
            return''',
            '''        if self.focus != "right":
            self._r7416_request_unmap()
            return''',"unmap dispatch")
    source=replace_in_method(source,"_r736_auto_map_single_sat",
            '''    existing=_load_overrides().get(key)
    if isinstance(existing,dict) and existing.get("channel_id")''',
            '''    existing=_load_overrides().get(key)
    if isinstance(existing,dict) and existing.get("user_unmapped"):
        return "USER_UNMAPPED",None
    if isinstance(existing,dict) and existing.get("channel_id")''',
            "auto map hold")
    source=replace_in_method(source,"_commit_auto_scan_overrides",
            '''        old = data.get(key)
        if isinstance(old, dict) and old.get("channel_id")''',
            '''        old = data.get(key)
        if isinstance(old, dict) and old.get("user_unmapped"):
            continue
        if isinstance(old, dict) and old.get("channel_id")''',
            "bulk automap hold")

    source=replace_in_method(source,"_r74_active_bouquet_rows",
            '''        result=[]
        seen=set()
        for entry in items:''',
            '''        result=[]
        seen=set()
        # Cached lamedb access states, read once, not per-row native calls.
        try: crypt_states=_lamedb_access_states()
        except Exception: crypt_states={}
        for entry in items:''',
            "bouquet CAID map")
    source=replace_in_method(source,"_r74_active_bouquet_rows",
            '''                result.append({"ref":raw,"name":clean_display_name(label) or "SAT TV",
                               "crypted":None,"orbital_position":_sat_orbital_position(raw)})''',
            '''                ca_key=_dvb_service_key(raw)
                crypto=crypt_states.get(ca_key) if ca_key in crypt_states else None
                result.append({"ref":raw,"name":clean_display_name(label) or "SAT TV",
                               "crypted":crypto,"orbital_position":_sat_orbital_position(raw)})''',
            "bouquet access classification")

    source=replace_once(source,
            '''        self._r74_bouquet_name = "Bouquet actuel"
        self.input_sat_ref''',
            '''        self._r74_bouquet_name = "Bouquet actuel"
        self._r7416_access_filter = "ALL"
        self._r7416_all_sat_rows = None
        self._r7416_pending_unmap = None
        self.input_sat_ref''',
            "screen new state")

    source=replace_in_method(source,"_r74_switch_roster",
            '''        previous=self._r74_roster_mode''',
            '''        self._r7416_all_sat_rows=None
        self._r7416_access_filter="ALL"
        previous=self._r74_roster_mode''',
            "reset access filter")
    source=replace_in_method(source,"_r731_toggle_fta",
            '''        if self._r74_roster_mode == "BOUQUET":
            self._r74_roster_mode = "SATELLITE"''',
            '''        if self._r74_roster_mode == "BOUQUET":
            self._r7416_access_cycle()
            return
        if self._r74_roster_mode == "BOUQUET":
            self._r74_roster_mode = "SATELLITE"''',
            "bouquet filter key 6")
    source=replace_in_method(source,"_sat_status",
            '''        if isinstance(manual, dict) and manual.get("channel_id"):
            return "LOCKED", "LOCKED"''',
            '''        if isinstance(manual, dict) and manual.get("user_unmapped"):
            return "UNMAPPED", "REVIEW"
        if isinstance(manual, dict) and manual.get("channel_id"):
            return "LOCKED", "LOCKED"''',
            "unmapped status")
    source=replace_in_method(source,"_mapping_text",
            '''        if isinstance(manual, dict) and manual.get("channel_id"):
            role''',
            '''        if isinstance(manual, dict) and manual.get("user_unmapped"):
            return "USER UNMAPPED • manual GREEN to correct"
        if isinstance(manual, dict) and manual.get("channel_id"):
            role''',
            "unmapped mapping label")
    source=replace_in_method(source,"_render_sat_list",
            '''        text = "[%s] %s" % (label, clean_display_name(row.get("name") or "SAT channel"))''',
            '''        text = "%s [%s] %s" % (_r7416_crypt_icon(row.get("crypted")),label,
                                      clean_display_name(row.get("name") or "SAT channel"))''',
            "partial SAT refresh")
    source=replace_in_method(source,"_render_sat_list",
            '''            text = "[%s] %s" % (label, clean_display_name(row.get("name") or "SAT channel"))''',
            '''            text = "%s [%s] %s" % (_r7416_crypt_icon(row.get("crypted")),label,
                                          clean_display_name(row.get("name") or "SAT channel"))''',
            "full SAT refresh")
    source=replace_in_method(source,"_render_sat_list",
            '''            rows = [sat_list.row("[NO CRYPTED TV] No confirmed encrypted TV service", "NO_SOURCE")]''',
            '''            rows = [sat_list.row("[NO TV] No channels for current access filter", "NO_SOURCE")]''',
            "empty filter placeholder")
    source=replace_once(source,
            '''        self["key_blue"] = Label("CANDIDATE INFO")''',
            '''        self["key_blue"] = Label("UNMAP SAT / INFO")''',
            "blue caption")
    source=replace_once(source,
            '''        self["key_menu"] = Label("7 BOUQUET / SAT")''',
            '''        self["key_menu"] = Label("6 FTA/CRYPT • 7 BOUQUET/SAT")''',
            "access filter caption")

    compile(source,"plugin.py","exec")
    return source,"ready"


def atomic_write(path,data,mode):
    fd,tmp=tempfile.mkstemp(prefix=".r7416-",suffix=".tmp",dir=str(path.parent))
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.chmod(tmp,stat.S_IMODE(mode))
        os.replace(tmp,str(path))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main(args=None):
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group()
    group.add_argument("--check",action="store_true")
    group.add_argument("--apply",action="store_true")
    group.add_argument("--rollback",action="store_true")
    parser.add_argument("--target",type=Path,default=TARGET,help=argparse.SUPPRESS)
    a=parser.parse_args(args)
    path=a.target
    bak=path.with_name(BACKUP)
    if not path.is_file():
        parser.error("plugin.py not found")
    old=path.read_bytes()
    mode=path.stat().st_mode
    try:src=old.decode("utf-8")
    except UnicodeError:parser.error("plugin.py is not UTF-8")
    if a.rollback:
        if TAG not in src or not bak.is_file():
            parser.error("R7416 not installed or backup missing")
        saved=bak.read_bytes()
        compile(saved,"plugin.py","exec")
        atomic_write(path,saved,mode)
        print("ROLLBACK_OK: R7415 plugin restored; restart Enigma2 GUI")
        print("NOTE: UNMAP choices already confirmed by user remain in mapping files")
        return 0
    try:changed,status=patch(src)
    except (ValueError,SyntaxError) as err:parser.error(str(err))
    if not a.apply:
        print("CHECK_OK:",status)
        print("BLUE on SAT -> confirm UNMAP this service; BLUE on IPTV -> details")
        print("6 bouquet access filter: ALL/CRYPT/FTA; SAT rows: 🔒 🔓 ?")
        print("Auto Preview and bulk AutoScan cannot relock user-unmapped SAT")
        print("Player/relay/TOD AAC and all other mappings unchanged")
        return 0
    if status=="already-installed":
        print("ALREADY_INSTALLED")
        return 0
    if bak.exists():
        parser.error("Rollback backup exists; refusing overwrite")
    shutil.copy2(str(path),str(bak))
    try:atomic_write(path,changed.encode("utf-8"),mode)
    except Exception:
        atomic_write(path,old,mode)
        raise
    print("PATCH_OK: backup at "+str(bak))
    print("Restart Enigma2 GUI to activate")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
