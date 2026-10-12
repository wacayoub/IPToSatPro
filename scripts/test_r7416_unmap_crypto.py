"""R7416 regression: actual R74 package plus R7411-15 staged patches.

No receiver required. Validate intentional per-SAT unmapped marker, old mapping
backup, manual remap eligibility, bulk AutoScan protection, FTA/crypt icons,
bouquet access filter, BLUE confirmation, and byte-identical code rollback.
"""
import ast
import importlib.util
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]


def load(name,filename):
    spec=importlib.util.spec_from_file_location(name,ROOT/"scripts"/filename)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod


builder=load("build7416", "build-r74-unified.py")
p11=load("p11_7416", "r7411_preview_persist_priority_hotfix.py")
p12=load("p12_7416", "r7412_preview_fast_shortlist_hotfix.py")
p13=load("p13_7416", "r7413_preview_inline_hotfix.py")
p14=load("p14_7416", "r7414_fast_candidates_manual_lock.py")
p15=load("p15_7416", "r7415_firstpaint_green_any_focus.py")
p16=load("p16_7416", "r7416_unmap_fta_crypt_icons.py")


class R7416Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        filename=Path(cls.tmp.name)/"r74.ipk"
        cls.info=builder.build(filename)
        pack=builder.b.b.base.pack
        files=pack.members_from(pack.unpack_ar(filename.read_bytes())["data.tar.gz"])
        cls.original=files[builder.PLUGIN].decode()
        cls.s11=p11.patch_plugin(cls.original)[0]
        cls.s12=p12.patch(cls.s11)[0]
        cls.s13=p13.patch(cls.s12)[0]
        cls.s14=p14.patch(cls.s13)[0]
        cls.s15=p15.patch(cls.s14)[0]
        cls.s16,cls.stage=p16.patch(cls.s15)
        tree=ast.parse(cls.s16)
        cls.top={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
        cls.cls=next(n for n in tree.body if isinstance(n,ast.ClassDef)
                     and n.name=="SatIPTVBridgePreview")
        cls.methods={n.name:n for n in cls.cls.body if isinstance(n,ast.FunctionDef)}
        cls.pkgfiles=files

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    @classmethod
    def isolate(cls,name,env,scope="top"):
        n=(cls.top if scope=="top" else cls.methods)[name]
        tree=ast.fix_missing_locations(ast.Module(body=[n],type_ignores=[]))
        local=dict(env)
        exec(compile(tree,"r7416-real-plugin.py","exec"),local)
        return local[name]

    def test_installs_on_real_r74_chain(self):
        self.assertEqual(self.stage,"ready")
        self.assertEqual(p16.patch(self.s16)[1],"already-installed")
        self.assertIn(p15.TAG,self.s16)
        self.assertIn('candidate_budget = 192 if self._r71_worker_deep else 24',self.s16)
        self.assertIn("_r7413_keep_preview_visible()",self.s16)
        self.assertNotIn("R7416_UNMAP_CRYPT_ACCESS",self.s15)

    def test_crypto_icon_uses_static_three_state(self):
        fn=self.isolate("_r7416_crypt_icon",{})
        self.assertEqual(fn(True),"🔒")
        self.assertEqual(fn(False),"🔓")
        self.assertEqual(fn(None),"?")
        self.assertEqual(fn(0),"?")  # never use truthiness for unknown

    def test_bouquet_uses_lamedb_cached_caids_not_live_decoder(self):
        src=ast.get_source_segment(self.s16,self.top["_r74_active_bouquet_rows"])
        self.assertIn('crypt_states=_lamedb_access_states()',src)
        self.assertIn('crypto=crypt_states.get(ca_key)',src)
        self.assertNotIn('playService(',src)
        self.assertIn('"crypted":crypto',src)

    def test_unmap_only_one_service_preserves_other_keys_and_backups(self):
        with tempfile.TemporaryDirectory() as td:
            directory=Path(td)
            paths={n:directory/(n+".json") for n in ("overrides","aliases","learned")}
            for n,p in paths.items():
                contents={"SAT_A":{"channel_id":"old","name":"WRONG",
                                   "locked":True} if n=="overrides" else {"sat_name":"test"},
                          "SAT_B":{"channel_id":"keep","name":"OK"}}
                p.write_text(json.dumps(contents),encoding="utf-8")
            messages=[]
            env={"sat_service_key":lambda ref:ref,
                 "OVERRIDE_PATH":str(paths["overrides"]),
                 "ALIAS_PATH":str(paths["aliases"]),
                 "LEARNED_MAP_PATH":str(paths["learned"]),
                 "_ensure_base_dir":lambda:None,
                 "clean_display_name":lambda x:x,
                 "MONITOR":None,"os":os,"time":time}
            fn=self.isolate("_r7416_unmap_mapping",env)
            changed,backup=fn("SAT_A","Wrong SAT")
            self.assertTrue(changed)
            self.assertTrue(Path(backup).is_dir())
            self.assertTrue((Path(backup)/"overrides.json").is_file())
            new={n:json.loads(p.read_text()) for n,p in paths.items()}
            self.assertTrue(new["overrides"]["SAT_A"]["user_unmapped"])
            self.assertFalse(new["overrides"]["SAT_A"]["locked"])
            self.assertNotIn("channel_id",new["overrides"]["SAT_A"])
            self.assertEqual(new["overrides"]["SAT_B"]["channel_id"],"keep")
            for kind in ("aliases","learned"):
                self.assertNotIn("SAT_A",new[kind])
                self.assertIn("SAT_B",new[kind])
            self.assertEqual(fn("SAT_A","Wrong SAT"),(False,""))
            self.assertEqual(json.loads((Path(backup)/"overrides.json").read_text())["SAT_A"]["channel_id"],"old")

    def test_automatic_preview_refuses_user_unmapped(self):
        fn=self.isolate("_r736_auto_map_single_sat",{
            "sat_service_key":lambda value:value,
            "_load_overrides":lambda:{"SAT_A":{"user_unmapped":True,"locked":False}},
        })
        self.assertEqual(fn("SAT_A","Channel",{},[({},120,{})])[0],"USER_UNMAPPED")

    def test_bulk_auto_scan_cannot_replace_unmapped(self):
        with tempfile.TemporaryDirectory() as temp:
            f=Path(temp)/"overrides.json"
            old={"SAT_A":{"user_unmapped":True,"locked":False},
                 "SAT_B":{"auto_best_lock":True,"channel_id":"previous"},
                 "SAT_C":{"channel_id":"manual","locked":True}}
            f.write_text(json.dumps(old))
            mock={
                "OVERRIDE_PATH":str(f),"json":json,"os":os,
                "MONITOR":None,
                "_ensure_base_dir":lambda:None,
                "_load_overrides":lambda:json.loads(f.read_text())
            }
            commit=self.isolate("_commit_auto_scan_overrides",mock)
            added,removed=commit({"SAT_A":{"channel_id":"incorrect"},
                                  "SAT_B":{"channel_id":"new"},
                                  "SAT_C":{"channel_id":"wrong"}},
                                 {"SAT_A","SAT_B","SAT_C"})
            data=json.loads(f.read_text())
            self.assertTrue(data["SAT_A"]["user_unmapped"])
            self.assertEqual(data["SAT_B"]["channel_id"],"new")
            self.assertEqual(data["SAT_C"]["channel_id"],"manual")
            self.assertEqual((added,removed),(1,1))

    def test_access_filter_cycles_and_preserves_order(self):
        status=[]
        original=[
            {"ref":"a","crypted":True},
            {"ref":"b","crypted":False},
            {"ref":"c","crypted":None},
            {"ref":"d","crypted":True},
            {"ref":"e","crypted":False},
        ]
        class Fake:
            def __init__(self):
                self.sat_rows=list(original)
                self.sat_index=0
                self._r7416_all_sat_rows=None
                self._r7416_access_filter="ALL"
                self._suppress_sat_change=False
            def _selected_sat_row(self):
                if not self.sat_rows:return None
                return self.sat_rows[min(self.sat_index,len(self.sat_rows)-1)]
            def _render_sat_list(self,**kw):pass
            def _set_focus(self,name):pass
            def _sat_selection_changed(self):pass
            def __getitem__(self,name):
                return SimpleNamespace(setText=lambda x:status.append(x))
        f=Fake()
        cycle=self.isolate("_r7416_access_cycle",{},scope="preview")
        cycle(f)
        self.assertEqual([r["ref"] for r in f.sat_rows],["a","d"])
        cycle(f)
        self.assertEqual([r["ref"] for r in f.sat_rows],["b","e"])
        cycle(f)
        self.assertEqual([r["ref"] for r in f.sat_rows],["a","b","c","d","e"])
        self.assertEqual(f._r7416_access_filter,"ALL")
        self.assertTrue(any("1 unknown" in v for v in status))

    def test_blue_sat_requests_confirmation_not_immediate_delete(self):
        events=[]
        class Fake:
            focus="left"
            _manual_overrides={"SAT_A":{"channel_id":"old","name":"OLD IPTV"}}
            def _selected_sat_row(self):return {"ref":"SAT_A","name":"SAT A"}
            def _focus_right(self):events.append("FOCUS_RIGHT")
            def _r7416_confirm_unmap(self, accepted=False):pass
            def __getitem__(self,key):
                return SimpleNamespace(setText=lambda value:events.append(value))
            session=SimpleNamespace(openWithCallback=lambda cb,*args,**kw:events.append(("confirm",cb,args,kw)))
        env={"sat_service_key":lambda ref:ref,
             "MessageBox":SimpleNamespace(TYPE_YESNO=0),
             "clean_display_name":lambda s:s}
        request=self.isolate("_r7416_request_unmap",env,scope="preview")
        f=Fake()
        request(f)
        self.assertEqual(f._r7416_pending_unmap[0],"SAT_A")
        self.assertEqual(len([v for v in events if isinstance(v,tuple) and v[0]=="confirm"]),1)
        self.assertEqual(events[0][0],"confirm")
        self.assertNotIn("FOCUS_RIGHT",events)

    def test_key_blue_right_keeps_candidate_info(self):
        src=ast.get_source_segment(self.s16,self.methods["_blue_action"])
        self.assertIn('if self.focus != "right":',src)
        self.assertIn('self._r7416_request_unmap()',src)
        self.assertIn("Candidate: ",src)
        self.assertIn("MessageBox.TYPE_INFO",src)

    def test_user_unmap_status_and_manual_green_preserved(self):
        self.assertIn("MANUAL LOCK",self.s16)
        sat=ast.get_source_segment(self.s16,self.methods["_sat_status"])
        self.assertIn('return "UNMAPPED", "REVIEW"',sat)
        mapping=ast.get_source_segment(self.s16,self.methods["_mapping_text"])
        self.assertIn('USER UNMAPPED • manual GREEN to correct',mapping)
        save=ast.get_source_segment(self.s16,self.top["_save_override"])
        self.assertIn('data[key] = rec',save)  # replaces unmapped marker on GREEN
        self.assertIn("PREVIEW_MANUAL_UNVERIFIED",self.s16)

    def test_installer_check_apply_rollback(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"plugin.py"
            p.write_text(self.s15)
            self.assertEqual(p16.main(["--check","--target",str(p)]),0)
            self.assertEqual(p.read_text(),self.s15)
            self.assertEqual(p16.main(["--apply","--target",str(p)]),0)
            self.assertEqual(p.read_text(),self.s16)
            self.assertEqual(p16.main(["--rollback","--target",str(p)]),0)
            self.assertEqual(p.read_text(),self.s15)

if __name__=="__main__":
    unittest.main()
