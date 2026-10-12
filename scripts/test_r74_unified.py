#!/usr/bin/env python3
"""R74 native bouquet/satellite tests against the REAL generated IPK."""
import ast,importlib.util,sys,tempfile,types,unittest
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("build74",ROOT/"scripts/build-r74-unified.py")
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)

class R74Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        pkg=Path(cls.tmp.name)/"r74.ipk"
        cls.meta=builder.build(pkg)
        cls.files=builder.b.b.base.pack.members_from(
            builder.b.b.base.pack.unpack_ar(pkg.read_bytes())["data.tar.gz"])
        cls.src=cls.files[builder.PLUGIN].decode()
        cls.tree=ast.parse(cls.src)
        cls.preview=next(n for n in cls.tree.body if isinstance(n,ast.ClassDef) and n.name=="SatIPTVBridgePreview")
        cls.methods={n.name:n for n in cls.preview.body if isinstance(n,ast.FunctionDef)}

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def isolate(self,name,ctx):
        node=next(n for n in self.tree.body if isinstance(n,ast.FunctionDef) and n.name==name) if name.startswith("_r74_active_bouquet") else self.methods[name]
        gl=dict(ctx)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),
                     "r74-isolate","exec"),gl)
        return gl[name]

    def test_theme_all_widgets_exist_and_have_no_overlap(self):
        self.assertTrue(builder._validate_skin(self.files[builder.THEME].decode()))
        self.assertEqual(self.meta["theme_widgets"],20)

    def test_bouquet_root_captured_from_infobar(self):
        root=SimpleNamespace(toString=lambda:'1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "favorites.tv" ORDER BY bouquet')
        sl=SimpleNamespace(getRoot=lambda:root)
        screens=types.ModuleType("Screens")
        ibmod=types.ModuleType("Screens.InfoBar")
        ibmod.InfoBar=SimpleNamespace(instance=SimpleNamespace(servicelist=sl))
        old_screens=sys.modules.get("Screens");old_ib=sys.modules.get("Screens.InfoBar")
        sys.modules["Screens"]=screens;sys.modules["Screens.InfoBar"]=ibmod
        try:
            fn=self.isolate("_r74_active_bouquet_root",{})
            self.assertIs(fn()[0],root)
            sl.getRoot=lambda:SimpleNamespace(toString=lambda:'FROM SATELLITES ORDER BY satellitePosition')
            self.assertIsNone(fn()[0])
        finally:
            if old_screens is None:sys.modules.pop("Screens",None)
            else:sys.modules["Screens"]=old_screens
            if old_ib is None:sys.modules.pop("Screens.InfoBar",None)
            else:sys.modules["Screens.InfoBar"]=old_ib

    def test_native_bouquet_preserves_order_and_includes_fta_dvb(self):
        root=SimpleNamespace(toString=lambda:'FROM BOUQUET "myfav.tv"')
        left=SimpleNamespace(getBouquetList=lambda:[("Mes Favoris",root)])
        raw=["1:0:19:111:1:1:0:0:0:0:","1:0:1:222:1:1:0:0:0:0:",
             "4097:0:1:BAD:","1:0:19:111:1:1:0:0:0:0:"]
        names=["Nickelodeon HD","France 2 HD","IPTV","Dupe"]
        listing=SimpleNamespace(getContent=lambda kind,tw:[(x,y) for x,y in zip(raw,names)])
        service=SimpleNamespace(list=lambda r:listing)
        enigma=types.ModuleType("enigma")
        enigma.eServiceCenter=SimpleNamespace(getInstance=lambda:service)
        old=sys.modules.get("enigma")
        sys.modules["enigma"]=enigma
        try:
            key={}
            fn=self.isolate("_r74_active_bouquet_rows",key)
            fn.__globals__.update({
                "_r74_active_bouquet_root":lambda:(root,left),
                "eServiceReference":lambda r:SimpleNamespace(toString=lambda:r),
                "_is_tv_dvb_service":lambda ref,raw:raw.startswith("1:"),
                "ServiceReference":lambda ref:SimpleNamespace(getServiceName=lambda:"Fallback"),
                "clean_display_name":lambda value:value,
                "_sat_orbital_position":lambda raw:192,
                "_startup_log":lambda *a:None
            })
            rows,title=fn(None)
            self.assertEqual(title,"Mes Favoris")
            self.assertEqual([r["name"] for r in rows],names[:2])
            self.assertEqual(len(rows),2)
            self.assertTrue(all(r["crypted"] is None for r in rows))
        finally:
            if old is None:sys.modules.pop("enigma",None)
            else:sys.modules["enigma"]=old

    def test_native_bouquet_switch_mode_number7(self):
        events=[]
        class Fake:
            _r74_roster_mode="BOUQUET"
            sat_rows=[{"name":"A"}]
            def _ensure_full_sat_rows(self):return True
            def _set_focus(self,x):events.append("focus:"+x)
            def _sat_selection_changed(self):events.append("reload")
            def __getitem__(self,name):
                return SimpleNamespace(setText=lambda s:events.append(name))
        fn=self.isolate("_r74_switch_roster",{"_startup_log":lambda *a:events.append("log")})
        f=Fake();fn(f)
        self.assertEqual(f._r74_roster_mode,"SATELLITE")
        fn(f)
        self.assertEqual(f._r74_roster_mode,"BOUQUET")
        self.assertIn("reload",events)

    def test_bouquet_loading_fast_does_not_scan_all_lamedb(self):
        calls=[]
        class L:
            def moveToIndex(self,idx):calls.append(("move",idx))
        class Fake:
            session=None
            _sat_rows_loaded=False;_r74_roster_mode="BOUQUET";_r74_bouquet_name=""
            sat_ref_string="1:0:1:TWO";input_sat_ref="1:0:1:TWO"
            _suppress_sat_change=False
            def _render_sat_list(self,keep_index=False):calls.append(("render",len(self.sat_rows)))
            def __getitem__(self,k):
                return L() if k=="sat_list" else SimpleNamespace(setText=lambda x:None)
        n=self.methods["_ensure_full_sat_rows"]
        gl={"time":SimpleNamespace(monotonic=lambda:100),
            "_r74_active_bouquet_rows":lambda s:(
                [{"ref":"1:0:1:ONE","name":"One","crypted":False},
                 {"ref":"1:0:1:TWO","name":"Two","crypted":None}], "Favorites"),
            "_dvb_service_key":lambda r:r,
            "_startup_log":lambda *a:None,
            "_preview_sat_service_rows":lambda *a: (_ for _ in ()).throw(AssertionError("expensive scan invoked"))}
        fn=self.isolate("_ensure_full_sat_rows",gl)
        f=Fake()
        self.assertTrue(fn(f))
        self.assertEqual([x["name"] for x in f.sat_rows],["One","Two"])
        self.assertEqual(f.sat_index,1)
        self.assertTrue(f._sat_rows_loaded)
        self.assertEqual(f._r74_bouquet_name,"Favorites")
        self.assertIn(("move",1),calls)

    def test_action_is_wired_and_new_skin_is_used(self):
        self.assertIn('"7": self._r74_switch_roster',self.src)
        self.assertIn('"8": self._r74_cycle_server',self.src)
        self.assertIn('"9": self._r74_toggle_safe',self.src)
        self.assertIn('"3": self._r74_cycle_metadata',self.src)
        self.assertIn("from .preview_theme_r74 import PREVIEW_R74_FHD",self.src)
        self.assertIn("R74_BOUQUET_ROSTER",self.src)
        self.assertIn("AUTO_PLAY_START",self.src)

    def test_bounded_scoring_and_preview_source_still_present(self):
        core=self.files[builder.CORE].decode()
        self.assertIn("budget=48",core)
        self.assertIn("for i in range(48)",core)
        self.assertIn("fast_preview_mega_matches",core)


    def test_safe_fr_candidate_wins_over_foreign_higher_fuzzy_score(self):
        node=next(n for n in self.tree.body if isinstance(n,ast.FunctionDef) and n.name=="_r736_choose_best_safe")
        env={
            "cfg":SimpleNamespace(match_threshold=SimpleNamespace(value=82)),
            "channel_fingerprint":lambda ch:ch["id"],
            "match_decision":lambda score,detail,threshold:"SAFE",
            "quality_fit_key":lambda *args:(1,0,0,0,0),
            "MONITOR":None,
        }
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),
                     "rank-r74","exec"),env)
        vip=({"id":"vip","name":"VIP NICKELODEON HD","market":"EN","language":"EN"},148,{"name":100})
        strong=({"id":"fr","name":"FR NICKELODEON HD","market":"FR","language":"FR"},142,{"name":100})
        selected=env["_r736_choose_best_safe"]("sat","Nickelodeon HD",{
            "market_preferences":["FR"],"language_priorities":["FR"]},[vip,strong])
        self.assertEqual(selected[0]["id"],"fr")

    def test_server_safe_and_language_filters_keep_full_cache(self):
        base=[
            {"id":"a","server_role":"PRIMARY","market":"EN","language":"EN","quality":"HD"},
            {"id":"b","server_role":"BACKUP2","market":"FR","language":"FR","quality":"FHD"},
            {"id":"c","server_role":"BACKUP2","market":"AR","language":"AR","quality":"UHD"},
        ]
        events=[]
        class Fake:
            def __init__(self):
                self._r74_role_filter="BACKUP2"
                self._r74_meta_filter="FR"
                self._r74_safe_only=True
                self._r732_auto_rows=base
                self._r732_auto_page=3
                self.focus="right"
            def _candidate_decision(self,ch):
                return "REVIEW" if ch["id"]=="c" else "SAFE"
            def _r74_filters_active(self):return True
            def _render_source_list(self,keep_index=False):events.append("redraw")
            def _set_focus(self,which):events.append("focus")
            def __getitem__(self,key):return SimpleNamespace(setText=lambda x:None)
        f=Fake()
        fn=self.isolate("_r74_apply_filters",{"_startup_log":lambda *a:None})
        fn(f)
        self.assertEqual([x["id"] for x in f.channels],["b"])
        self.assertEqual(len(f._r732_auto_rows),3)
        self.assertEqual(f._r732_auto_page,0)
        self.assertEqual([x["id"] for x in f._r74_filtered_rows],["b"])
        self.assertIn("redraw",events)

    def test_player_and_monitor_unmodified(self):
        self.assertTrue(self.meta["monitor_unchanged"])
        self.assertFalse(self.meta["production_published"])
        self.assertFalse(self.meta["receiver_tested"])

if __name__=="__main__":unittest.main()
