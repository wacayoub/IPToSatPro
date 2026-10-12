#!/usr/bin/env python3
"""R73.1 tests against exact built IPK, no receiver or remote streams."""
import ast,base64,importlib.util,tempfile,unittest,types
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("r731_build",ROOT/"scripts/build-r73-preview.py")
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)

class RecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.pkg=Path(cls.tmp.name)/"r731.ipk"
        cls.meta=b.build(cls.pkg)
        cls.new=b.base.pack.members_from(b.base.pack.unpack_ar(cls.pkg.read_bytes())["data.tar.gz"])
        cls.old=b.base.pack.members_from(b.base.pack.unpack_ar(base64.b64decode(b.B64.read_bytes()))["data.tar.gz"])
        cls.plugin=cls.new[b.PLUGIN].decode()
        cls.coretext=cls.new[b.CORE].decode()
        core=Path(cls.tmp.name)/"r731_core.py"
        core.write_text(cls.coretext,encoding="utf-8")
        cs=importlib.util.spec_from_file_location("r731_core",core)
        cls.core=importlib.util.module_from_spec(cs);cs.loader.exec_module(cls.core)
        tree=ast.parse(cls.plugin)
        cls.pclass=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=="SatIPTVBridgePreview")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_runtime_protected_files_unchanged(self):
        for name,payload in self.old.items():
            if name not in (b.PLUGIN,b.CORE,b.UPDATER):
                self.assertEqual(payload,self.new[name],name)
        self.assertFalse(self.meta["receiver_tested"])
        self.assertFalse(self.meta["production_published"])
        self.assertEqual(self.meta["candidate_search"],"indexed_full_catalogue")

    def test_search_control_and_sat_filter_wired(self):
        for expected in ('"5": self._r731_search_dialog','"6": self._r731_toggle_fta',
                         'self._r731_show_fta = False','_r731_page_search(step)',
                         'if candidate.get("crypted") is not False:',
                         'self._r731_search_timer.callback.append(self._r731_poll_search)',
                         'catalog.manual_search(query, topn=limit, context=ctx)'):
            self.assertIn(expected,self.plugin)
        for expected in ("_r731_search_dialog","_r731_start_search",
                         "_r731_poll_search","_r731_show_search_page",
                         "_r731_page_search","_r731_toggle_fta","_r731_cleanup"):
            self.assertEqual(sum(isinstance(x,ast.FunctionDef) and x.name==expected for x in self.pclass.body),1)
        self.assertNotIn('import requests',self.plugin.split("    def _r731_start_search",1)[1].split("    def _r731_poll_search",1)[0])

    def test_native_display_page_bounded(self):
        func=next(x for x in self.pclass.body if isinstance(x,ast.FunctionDef) and x.name=="_r731_show_search_page")
        mod=ast.Module(body=[func],type_ignores=[])
        ns={};exec(compile(ast.fix_missing_locations(mod),"preview_paging","exec"),ns)
        class FakeLabel:
            def __init__(self):self.text=""
            def setText(self,x):self.text=x
        class Fake:
            def __init__(self):
                self._r731_search_active=True
                self._r731_search_rows=[{"name":str(i)} for i in range(131)]
                self._r731_search_page=2
                self._r731_search_query="CINEMA"
                self.labels={"status":FakeLabel()}
            def __getitem__(self,key):return self.labels[key]
            def _render_source_list(self,keep_index=True):self.rendered=True
            def _set_focus(self,dest):self.focus=dest
        item=Fake();ns["_r731_show_search_page"](item)
        self.assertEqual(len(item.channels),35)
        self.assertEqual(item.channels[0]["name"],"96")
        self.assertEqual(item.focus,"right")
        self.assertIn("page 3/3",item.labels["status"].text)

    def test_literally_search_across_server_catalogue(self):
        channels=[{"name":"OSN CINEMA %02d FHD"%i,
                   "url":"http://127.0.0.1/%d"%i,
                   "group":"MENA","server_role":("PRIMARY" if i%3==0 else "BACKUP1" if i%3==1 else "BACKUP2"),
                   "server_label":"Test Provider"} for i in range(85)]
        cat=self.core.Catalog(channels)
        rows=cat.manual_search("cinema",topn=len(cat.channels),context={})
        self.assertGreaterEqual(len(rows),70)
        # Repeated provider and channel names are preserved as distinct IDs.
        self.assertTrue(any((x[0] if isinstance(x,(tuple,list)) else x).get("server_role")=="BACKUP2" for x in rows))

    def test_exact_country_hint_is_review_preview_only(self):
        sat="Ushuaia TV HD"
        ctx={"confidence":"HIGH","market_preferences":["FR"],
             "language_priorities":["FR"],"audio_language_set":[]}
        ch={"name":"Ushuaia TV HD","market":"PL","market_source":"name",
            "language":"FR","url":"http://127.0.0.1/stream","server_role":"BACKUP1"}
        score,detail=self.core.match_score_details(sat,ch,["FR"],ctx,preview=True)
        self.assertEqual(self.core.match_decision(score,detail,82.0),"REVIEW",(score,detail))
        score2,detail2=self.core.match_score_details(sat,ch,["FR"],ctx,preview=False)
        self.assertEqual(self.core.match_decision(score2,detail2,82.0),"REJECT",(score2,detail2))

    def test_hard_channel_numbers_still_rejected(self):
        ch={"name":"beIN Sports 8 HD","market":"FR","language":"FR",
            "url":"http://127.0.0.1/stream","server_role":"PRIMARY"}
        s,d=self.core.match_score_details("beIN Sports 6 HD",ch,["FR"],{},preview=True)
        self.assertEqual(self.core.match_decision(s,d,60.0),"REJECT")

    def test_decoder_dimensions_without_pts_do_not_auto_verify(self):
        import time
        method=next(x for x in self.pclass.body if isinstance(x,ast.FunctionDef) and x.name=="_poll")
        namespace={"time":time, "MONITOR":types.SimpleNamespace(_read_pts=lambda:None),
                   "_server_badge":lambda role,label:"TEST"}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])),
                     "r731_preview_poll","exec"),namespace)
        class Label:
            def __init__(self):self.value=""
            def setText(self,value):self.value=value
        class Clock:
            def __init__(self):self.calls=0
            def start(self,*args):self.calls+=1
        class Fake:
            def __init__(self):
                self.finished=False;self.preview_ok=False;self.current_result="OPENING"
                self.started_at=time.monotonic()-0.35
                self.attempt_started_at=time.monotonic()-0.35
                self.attempt_pre_dims=(0,0)
                self.attempt_pre_pts=None
                self.samples=0;self.last_dims=(0,0)
                self._r731_last_pts=None;self._r731_pts_steps=0
                self.modes=["4097"];self.mode_index=0
                self.timer=Clock()
                self.channel={"server_role":"PRIMARY","server_label":"TEST"}
                self.labels={"status":Label(),"detail":Label()}
            def __getitem__(self,key):return self.labels[key]
            def _dimensions(self):return (1920,1080)
            def _preview_player_active(self):return True
            def _preview_failover_deadline_ms(self,active=False):return 1100
        f=Fake()
        namespace["_poll"](f)
        namespace["_poll"](f)
        self.assertFalse(f.preview_ok)
        self.assertEqual(f.current_result,"OPENING")
        self.assertGreaterEqual(f.timer.calls,2)
        self.assertIn("if confirmed and self._r731_pts_steps < 2",self.plugin)
        self.assertIn("now = time.monotonic(); attempt_ms",self.plugin)

    def test_build_deterministic(self):
        again=Path(self.tmp.name)/"again.ipk"
        meta=b.build(again)
        self.assertEqual(self.pkg.read_bytes(),again.read_bytes())
        self.assertEqual(meta["sha256"],self.meta["sha256"])

if __name__=="__main__":
    unittest.main()
