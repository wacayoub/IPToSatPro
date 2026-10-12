#!/usr/bin/env python3
"""R73.6 real IPK candidate → automatic SAT mapping integration tests."""
import ast, base64, importlib.util, tempfile, json, os, time, unittest
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("build736",ROOT/"scripts/build-r73-preview.py")
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)

class AutoMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.pkg=Path(cls.tmp.name)/"r736.ipk"
        cls.meta=b.build(cls.pkg)
        cls.members=b.base.pack.members_from(b.base.pack.unpack_ar(cls.pkg.read_bytes())["data.tar.gz"])
        cls.orig=b.base.pack.members_from(b.base.pack.unpack_ar(base64.b64decode(b.B64.read_bytes()))["data.tar.gz"])
        cls.src=cls.members[b.PLUGIN].decode()
        cls.tree=ast.parse(cls.src)
        cls.preview=next(n for n in cls.tree.body if isinstance(n,ast.ClassDef) and n.name=="SatIPTVBridgePreview")
        cls.scan=next(n for n in cls.tree.body if isinstance(n,ast.ClassDef) and "AutoScan" in n.name)
        corepath=Path(cls.tmp.name)/"core736.py";corepath.write_bytes(cls.members[b.CORE])
        sp=importlib.util.spec_from_file_location("core736",corepath)
        cls.core=importlib.util.module_from_spec(sp);sp.loader.exec_module(cls.core)
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def setUp(self):
        self.dir=tempfile.TemporaryDirectory()
        self.path=Path(self.dir.name)/"overrides.json"
        self.log=[]
        cfg=SimpleNamespace(match_threshold=SimpleNamespace(value=82),
           languages=SimpleNamespace(value="EN,FR"),
           quality_mode=SimpleNamespace(value="best"))
        namespace={
           "json":json,"os":os,"time":time,
           "MONITOR":None,"OVERRIDE_PATH":str(self.path),"cfg":cfg,
           "quality_fit_key":lambda *args:(2,1,0,0,0),
           "clean_display_name":lambda v:str(v or ""),
           "channel_fingerprint":lambda ch:ch.get("id") or ch.get("url",""),
           "sat_service_key":lambda ref:ref,
           "match_decision":self.core.match_decision,
           "_ensure_base_dir":lambda:None,
           "_load_user_rejections":lambda:{},
           "_load_overrides":lambda:json.loads(self.path.read_text()) if self.path.exists() else {},
        }
        names=["_r736_choose_best_safe","_r736_auto_map_single_sat",
               "_auto_scan_override_record","_commit_auto_scan_overrides"]
        funcs=[n for n in self.tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
        self.assertEqual(len(funcs),len(names))
        ns=dict(namespace)
        exec(compile(ast.fix_missing_locations(ast.Module(body=funcs,type_ignores=[])),
                     "plugin736_isolate","exec"),ns)
        self.ns=ns
    def tearDown(self):self.dir.cleanup()

    def row(self,name,score,details,idx="good",role="PRIMARY"):
        ch=dict(id=idx,name=name,url="http://192.0.2.1/"+idx,server_role=role,
                group="SPORTS",server_priority=0)
        return ch,float(score),dict(details)

    def test_green_auto_map_creates_persistent_mapping_without_green_button(self):
        safe=self.row("V Sport 1 FHD",107,{"name":100},idx="exact",role="BACKUP2")
        uncertain=self.row("V SPORT LIVE 1",139,{"name":100,"review_reason":"LIVE variant"},idx="live")
        state,ch=self.ns["_r736_auto_map_single_sat"]("sat1","V Sport 1 HD",{},[uncertain,safe])
        self.assertEqual(state,"AUTO_CREATED")
        self.assertEqual(ch["id"],"exact")
        data=json.loads(self.path.read_text())
        self.assertTrue(data["sat1"]["auto_best_lock"])
        self.assertTrue(data["sat1"]["locked"])
        self.assertEqual(data["sat1"]["channel_id"],"exact")
        self.assertEqual(data["sat1"]["auto_scan_decision"],"SAFE")

    def test_manual_correction_remains_immutable(self):
        manual={"channel_id":"user-corrected","auto_best_lock":False,"locked":True}
        self.path.write_text(json.dumps({"sat2":manual}))
        state,ch=self.ns["_r736_auto_map_single_sat"]("sat2","V Sport 1 HD",{},
                    [self.row("V Sport 1",120,{"name":100},idx="auto")])
        self.assertEqual(state,"MANUAL_PROTECTED")
        self.assertIsNone(ch)
        self.assertEqual(json.loads(self.path.read_text())["sat2"],manual)

    def test_stale_auto_mapping_replaced_by_better_green(self):
        self.path.write_text(json.dumps({"sat1":{"auto_best_lock":True,"channel_id":"old-bad","locked":True}}))
        state,ch=self.ns["_r736_auto_map_single_sat"]("sat1","V Sport 1 HD",{},
                    [self.row("V SPORT LIVE 1",125,{"name":100,"review_reason":"wrong variant"},idx="old-bad"),
                     self.row("V Sport 1",91,{"name":100},idx="new-good")])
        self.assertEqual(state,"AUTO_REPLACED")
        self.assertEqual(json.loads(self.path.read_text())["sat1"]["channel_id"],"new-good")

    def test_safe_mapping_on_cache_hit_is_idempotent(self):
        self.path.write_text(json.dumps({"sat1":{"auto_best_lock":True,"channel_id":"same","locked":True}}))
        prev=self.path.read_bytes()
        state,ch=self.ns["_r736_auto_map_single_sat"]("sat1","V Sport 1",{},
                    [self.row("V Sport 1",120,{"name":100},idx="same")])
        self.assertEqual(state,"ALREADY_AUTO")
        self.assertEqual(self.path.read_bytes(),prev)

    def test_wrong_number_or_known_language_mismatch_not_mapped(self):
        rows=[self.row("beIN Sports 8",147,{"name":100,"reject_reason":"wrong number"},idx="8"),
              self.row("FR beIN Sports 6",141,{"name":100,"review_reason":"language uncertain"},idx="fr")]
        state,ch=self.ns["_r736_auto_map_single_sat"]("sat3","beIN Sports 6",{},rows)
        self.assertEqual(state,"REVIEW_ONLY")
        self.assertIsNone(ch)
        self.assertFalse(self.path.exists())

    def test_explicit_user_rejected_green_is_skipped(self):
        self.ns["_load_user_rejections"]=lambda:{"sat4":{"items":{"rejected":{}}}}
        best=self.row("OSN Cinema 4",140,{"name":100},idx="rejected")
        backup=self.row("OSN Cinema 4",104,{"name":100},idx="allowed")
        state,ch=self.ns["_r736_auto_map_single_sat"]("sat4","OSN Cinema 4",{},[best,backup])
        self.assertEqual(state,"AUTO_CREATED")
        self.assertEqual(ch["id"],"allowed")

    def test_review_index_overflow_never_auto_locks(self):
        ch,score,det=self.row("CANAL Golf",130,{"name":100},idx="r")
        ch["_manual_candidate"]=True
        chosen=self.ns["_r736_choose_best_safe"]("sat","CANAL Golf",{},[(ch,score,det)])
        self.assertIsNone(chosen[0])
        self.assertTrue(chosen[3])

    def test_bulk_scan_uses_same_ranker_and_shared_selector(self):
        method=next(n for n in self.scan.body if isinstance(n,ast.FunctionDef) and n.name=="_scan_one")
        body=ast.get_source_segment(self.src,method)
        self.assertIn("catalog.fast_preview_mega_matches(",body)
        self.assertIn("self._pick_safe(raw, sat_name, ctx, ranked)",body)
        picker=next(n for n in self.scan.body if isinstance(n,ast.FunctionDef) and n.name=="_pick_safe")
        self.assertIn("_r736_choose_best_safe(",ast.get_source_segment(self.src,picker))

    def test_preview_auto_maps_fresh_and_cached_without_manual_action(self):
        for name in ("_poll_expanded_candidates","_load_selected_sat_candidates"):
            meth=next(n for n in self.preview.body if isinstance(n,ast.FunctionDef) and n.name==name)
            text=ast.get_source_segment(self.src,meth)
            self.assertIn("_r736_auto_map_single_sat(",text,name)
            self.assertIn("PREVIEW_AUTO_MAP",text,name)

    def test_package_protects_player_and_all_existing_data_files(self):
        for name,bytes_ in self.orig.items():
            if name not in (b.PLUGIN,b.CORE,b.UPDATER):
                self.assertEqual(self.members[name],bytes_,name)
        self.assertTrue(self.meta["player_unchanged"])
        self.assertFalse(self.meta["receiver_tested"])
        self.assertFalse(self.meta["production_published"])
        self.assertIn(self.meta["candidate_search"], ("r736_unified_preview_and_bulk_safe_automapping", "r737_8s_video_preview_then_auto_restore_with_r736_automap"))

if __name__=="__main__":unittest.main()
