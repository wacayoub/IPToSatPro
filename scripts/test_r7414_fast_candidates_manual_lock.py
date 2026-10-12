"""R7414 regression against exact generated R74 and prior staged hotfixes."""
import ast
import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/"scripts"/path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

builder=load("build_r7414_real","build-r74-unified.py")
fix11=load("fix_r7411_real","r7411_preview_persist_priority_hotfix.py")
fix12=load("fix_r7412_real","r7412_preview_fast_shortlist_hotfix.py")
fix13=load("fix_r7413_real","r7413_preview_inline_hotfix.py")
fix14=load("fix_r7414_real","r7414_fast_candidates_manual_lock.py")


class PreviewFastManualTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        ipk=Path(cls.tmp.name)/"r74.ipk";builder.build(ipk)
        pack=builder.b.b.base.pack
        members=pack.members_from(pack.unpack_ar(ipk.read_bytes())["data.tar.gz"])
        cls.original=members[builder.PLUGIN].decode()
        cls.s11=fix11.patch_plugin(cls.original)[0]
        cls.s12=fix12.patch(cls.s11)[0]
        cls.s13=fix13.patch(cls.s12)[0]
        cls.patched,cls.status=fix14.patch(cls.s13)
        cls.tree=ast.parse(cls.patched)
        cls.preview=next(n for n in cls.tree.body if isinstance(n,ast.ClassDef) and n.name=="SatIPTVBridgePreview")
        cls.methods={n.name:n for n in cls.preview.body if isinstance(n,ast.FunctionDef)}
        cls.helper=next(n for n in cls.tree.body if isinstance(n,ast.FunctionDef) and n.name=="_r7414_fast_exact_seed")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def isolate(self,node,namespace,package=None):
        values=dict(namespace)
        if package:
            values["__package__"]=package
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),
                     "isolated-R7414.py","exec"),values)
        return values[node.name]

    def test_real_r74_patch_chain_and_idempotence(self):
        self.assertEqual(self.status,"ready")
        self.assertEqual(fix14.patch(self.patched)[1],"already-installed")
        self.assertIn(fix13.TAG,self.patched)
        self.assertIn(fix12.TAG,self.patched)
        self.assertIn(fix11.TAG,self.patched)
        self.assertIn("candidate_budget = 192 if self._r71_worker_deep else 24",self.patched)

    def test_first_paint_uses_only_existing_exact_index(self):
        prefix="mockpack7414"
        orig_pkg=sys.modules.get(prefix)
        orig_core=sys.modules.get(prefix+".core")
        sys.modules[prefix]=types.ModuleType(prefix)
        core=types.ModuleType(prefix+".core")
        core.normalize_name=lambda name:(name or "").strip().lower()
        sys.modules[prefix+".core"]=core
        try:
            seed=self.isolate(self.helper,{},package=prefix)
            data=[dict(id=str(i),name="beIN SPORTS 2",server_role=("PRIMARY","BACKUP1","BACKUP2")[i%3],url="http://example.invalid/%d"%i) for i in range(70)]
            c=SimpleNamespace(_exact={"bein sports 2":data})
            found=seed("beIN SPORTS 2",c)
            self.assertEqual(len(found),12)
            self.assertEqual(set(ch["server_role"] for ch in found),{"PRIMARY","BACKUP1","BACKUP2"})
            self.assertTrue(all(ch["_manual_candidate"] and ch["_r7414_seed"] for ch in found))
            self.assertTrue(all(ch["_preview_score"]==0 for ch in found))
            self.assertEqual(len(data),70)
        finally:
            if orig_pkg is None:sys.modules.pop(prefix,None)
            else:sys.modules[prefix]=orig_pkg
            if orig_core is None:sys.modules.pop(prefix+".core",None)
            else:sys.modules[prefix+".core"]=orig_core

    def test_index_missing_returns_instant_empty_no_catalog_walk(self):
        # No _exact available -> fast empty, never call a full fuzzy matcher.
        self.assertIn('groups = getattr(catalog, "_exact", None) or {}',
                      ast.get_source_segment(self.patched,self.helper))
        self.assertNotIn("fast_preview_mega_matches(",ast.get_source_segment(self.patched,self.helper))

    def test_sat_selection_paints_seed_then_schedules_full_worker(self):
        events=[]
        ch=dict(id="c",name="same",url="http://example.invalid/iptv",_manual_candidate=True)
        class Timer:
            def stop(self):events.append("STOP")
        class Fake:
            _suppress_sat_change=False
            sat_rows=[{"ref":"sref","name":"SAT TEST"}]
            _candidate_cache={}
            sat_ref_string=""
            _r731_search_ref=""
            candidate_expand_timer=Timer()
            sat_change_timer=Timer()
            def _sat_index_now(self):return 0
            def _selected_sat_row(self):return self.sat_rows[0]
            def _load_selected_sat_candidates(self):events.append("LOAD_FIRST")
            def __getitem__(self,k):return SimpleNamespace(setText=lambda txt:events.append(("STATUS",txt)))
        env={"sat_service_key":lambda ref:ref,
             "_preview_candidate_cache_get":lambda ref:None,
             "_r7414_fast_exact_seed":lambda name,cat:[dict(ch)],
             "MONITOR":SimpleNamespace(catalog=SimpleNamespace()),
             "clean_display_name":lambda name:name,
             "_startup_log":lambda *args:events.append("LOG"),
             "PREVIEW_LAST_SAT_REF":""}
        func=self.isolate(self.methods["_sat_selection_changed"],env)
        f=Fake();func(f)
        self.assertEqual(len(f._candidate_cache["sref"][2]),1)
        self.assertFalse(f._candidate_cache["sref"][3])
        self.assertIn("LOAD_FIRST",events)

    def test_green_saves_without_ok_does_not_claim_verified(self):
        saved=[]
        notices={}
        row=dict(id="a",name="BEIN SPORTS 2 HD",url="http://example.invalid/a",
                 _preview_score=0,_preview_details={"review_reason":"instant"})
        class Fake:
            focus="right";sat_ref_string="sref";sat_name="BEIN SPORTS 2";active_fp=""
            active_sat_ref="";current_result="UNKNOWN";preview_ok=False
            _preview_results={};_preview_audio={};context={}
            def _selected_channel(self):return dict(row)
            def _sat_key(self):return "sref"
            def _candidate_decision(self,ch):return "REVIEW"
            def _refresh_mapping_caches(self,force=False):saved.append("refresh")
            def _render_sat_list(self,keep_index=True):pass
            def _render_source_list(self,keep_index=True):pass
            def _update_header(self):pass
            def _update_verify_strip(self):pass
            def __getitem__(self,k):return SimpleNamespace(setText=lambda x:notices.__setitem__(k,x))
        globs={"channel_fingerprint":lambda x:x["id"],
               "_remove_user_rejection":lambda *a:None,
               "_save_override":lambda *a,**kw:saved.append(kw),
               "_startup_log":lambda *a:None}
        lock=self.isolate(self.methods["_lock"],globs)
        view=Fake();lock(view)
        self.assertTrue(any(isinstance(x,dict) and x.get("forced") for x in saved))
        self.assertEqual(view.current_result,"MANUAL LOCKED")
        self.assertFalse(view.preview_ok)
        self.assertNotIn(("sref","a"),view._preview_results)
        self.assertIn("NOT VIDEO/AUDIO VERIFIED",notices["status"])

    def test_manual_lock_saves_even_if_review(self):
        body=ast.get_source_segment(self.patched,self.methods["_lock"])
        self.assertIn("unverified_manual or before",body)
        self.assertIn('PREVIEW_MANUAL_UNVERIFIED',body)
        self.assertIn('if not unverified_manual and audio_state == "MISMATCH"',body)
        self.assertNotIn('Preview required • OK → PLAYING',body)

    def test_player_and_audio_unchanged(self):
        self.assertIn("_r7413_keep_preview_visible()",self.patched)
        self.assertIn("PREVIEW_STAY_OPEN",self.patched)
        self.assertIn("def _r736_auto_map_single_sat(",self.patched)

    def test_backup_apply_rollback(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"plugin.py";path.write_text(self.s13)
            self.assertEqual(fix14.main(["--check","--target",str(path)]),0)
            self.assertEqual(path.read_text(),self.s13)
            self.assertEqual(fix14.main(["--apply","--target",str(path)]),0)
            self.assertEqual(path.read_text(),self.patched)
            self.assertEqual(fix14.main(["--rollback","--target",str(path)]),0)
            self.assertEqual(path.read_text(),self.s13)


if __name__=="__main__":
    unittest.main()
