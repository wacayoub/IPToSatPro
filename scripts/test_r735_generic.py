#!/usr/bin/env python3
"""R73.5 full packaged generic match regression; no receiver needed."""
import ast,base64,importlib.util,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("build735",ROOT/"scripts/build-r73-preview.py")
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)

class GenericMatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.ipk=Path(cls.tmp.name)/"r735.ipk";cls.meta=b.build(cls.ipk)
        cls.package=b.base.pack.members_from(b.base.pack.unpack_ar(cls.ipk.read_bytes())["data.tar.gz"])
        cls.baseline=b.base.pack.members_from(b.base.pack.unpack_ar(base64.b64decode(b.B64.read_bytes()))["data.tar.gz"])
        cls.psrc=cls.package[b.PLUGIN].decode()
        core=Path(cls.tmp.name)/"core.py";core.write_bytes(cls.package[b.CORE])
        sp=importlib.util.spec_from_file_location("core735",core)
        cls.core=importlib.util.module_from_spec(sp);sp.loader.exec_module(cls.core)
        cls.tree=ast.parse(cls.psrc)
        cls.preview=next(x for x in cls.tree.body if isinstance(x,ast.ClassDef) and x.name=="SatIPTVBridgePreview")
        cls.autoscan=next(x for x in cls.tree.body if isinstance(x,ast.ClassDef) and x.name=="SatIPTVBridgeAutoScan")
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def channel(self,name,role="BACKUP2",idx=1,**extra):
        return dict({"name":name,"url":"http://192.0.2.%d/%d"%(2 if role=="BACKUP2" else 3,idx),
          "server_role":role,"server_priority":0,"market":"","language":"",
          "group":""},**extra)

    def score(self,sat,cand,preview=True,ctx=None):
        score,details=self.core.match_score_details(sat,cand,["EN","FR"],ctx or {},
                                                    "best",preview=preview)
        return score,details,self.core.match_decision(score,details,82)

    def method(self,cls,name,env):
        method=next(x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name==name)
        mod=ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[]))
        ns=dict(env);exec(compile(mod,"method_isolate","exec"),ns)
        return ns[name]

    def test_vsport_live_is_not_vsport(self):
        for sat,candidate in [
            ("V Sport 1 HD","V SPORT LIVE 1"),
            ("V Sport LIVE 1 HD","V Sport 1 FHD"),
            ("CANAL+ Sport 1 HD","CANAL+ Sport LIVE 1 HD"),
            ("Sky Sport 1 HD","Sky Sport Live 1"),
        ]:
            s,d,decision=self.score(sat,self.channel(candidate),preview=True)
            self.assertEqual(decision,"REVIEW",(sat,candidate,s,d))
            self.assertIn("LIVE",d.get("review_reason",""))
            _s,_d,autodecision=self.score(sat,self.channel(candidate),preview=False)
            self.assertEqual(autodecision,"REJECT",(sat,candidate,_s,_d))
        self.assertTrue(self.core._r735_numbered_live_subservice("V SPORT LIVE 1"))
        self.assertFalse(self.core._r735_numbered_live_subservice("Live : V Sport 1"))
        self.assertFalse(self.core._r735_numbered_live_subservice("V Sport 1 HD"))
        self.assertFalse(self.core._r735_numbered_live_subservice("V Sport 1 Live broadcast"))

    def test_exact_real_channels_still_safe(self):
        cases=[
            ("V Sport 1 HD","V SPORT 1"),
            ("V Sport LIVE 1 HD","V Sport LIVE 1 FHD"),
            ("beIN Sports 6 HD","beIN Sports 6 FHD"),
            ("Ushuaia TV HD","Ushuaia TV FHD"),
            ("Nat Geo Wild HD","Nat Geo Wild HD"),
            ("Rai 1 HD","RAI 1 HD"),
        ]
        for sat,iptv in cases:
            score,details,decision=self.score(sat,self.channel(iptv))
            self.assertNotIn("numbered LIVE",details.get("review_reason",""),(sat,iptv,score))
            self.assertNotIn("numbered LIVE",details.get("reject_reason",""),(sat,iptv,score))

    def test_wrong_real_channel_number_cannot_be_safe(self):
        for sat,bad in [("beIN Sports 6 HD","beIN Sports 8 FHD"),
                        ("V Sport 1 HD","V SPORT 2"),
                        ("Sky Cinema 1","Sky Cinema 2"),
                        ("OSN Cinema 4","OSN Cinema 5"),
                        ("Rai 1","Rai 2")]:
            sc,d,decision=self.score(sat,self.channel(bad))
            self.assertEqual(decision,"REJECT",(sat,bad,sc,d))

    def test_correct_candidate_is_ranked_ahead_of_old_auto(self):
        method=self.method(self.preview,"_sort_candidates_with_cached_evidence",{})
        core=self.core
        class Fake:
            sat_name="V Sport 1 HD"
            def _candidate_decision(self,ch):
                return {"correct":"SAFE","old":"REVIEW","wrong":"REJECT"}[ch["id"]]
            def _health_record(self,ch):
                return {"width":3840,"height":2160} if ch["id"]=="old" else {}
        f=Fake()
        arr=[
           {"id":"old","name":"V SPORT LIVE 1 FHD","_r735_old_auto_lock":True,"_preview_score":118.0,
            "_preview_details":{"name":97,"variant":-42,"review_reason":"numbered LIVE service variant"}},
           {"id":"wrong","name":"V SPORT 8 HD","_preview_score":130,"_preview_details":{"name":100,"reject_reason":"number"}},
           {"id":"correct","name":"V Sport 1","_preview_score":95,"_preview_details":{"name":95}},
        ]
        chosen=method(f,arr)
        self.assertEqual(chosen[0]["id"],"correct",[x["id"] for x in chosen])
        self.assertEqual(chosen[-1]["id"],"wrong")

    def test_manual_lock_is_never_demoted(self):
        method=self.method(self.preview,"_sort_candidates_with_cached_evidence",{})
        class Fake:
            sat_name="V Sport 1 HD"
            def _candidate_decision(self,ch):return "MANUAL" if ch["id"]=="manual" else "SAFE"
            def _health_record(self,ch):return {}
        rows=[
            {"id":"correct","name":"V Sport 1","_preview_score":130,"_preview_details":{"name":100}},
            {"id":"manual","name":"V Sport 1 FHD","_r735_verified_manual_lock":True},
        ]
        self.assertEqual(method(Fake(),rows)[0]["id"],"manual")

    def test_old_auto_is_not_user_manual_decision(self):
        core=self.core
        env=dict(channel_fingerprint=lambda ch:ch["id"],
                 sat_service_key=lambda x:x,
                 cfg=SimpleNamespace(match_threshold=SimpleNamespace(value=82)),
                 match_decision=core.match_decision)
        dec=self.method(self.preview,"_candidate_decision",env)
        class Fake:
            def __init__(self,manual):
                self._manual_overrides={"sat":manual}
                self._user_rejected_ids=set()
            def _sat_key(self):return "sat"
        ch={"id":"old","_preview_score":40.0,"_preview_details":{"review_reason":"old AUTO"}}
        self.assertEqual(dec(Fake({"channel_id":"old","auto_best_lock":True}),ch),"REVIEW")
        self.assertEqual(dec(Fake({"channel_id":"old","auto_best_lock":False}),ch),"MANUAL")

    def test_auto_scan_does_not_lock_review_or_reject(self):
        env=dict(channel_fingerprint=lambda ch:ch["id"], sat_service_key=lambda x:x,
                 match_decision=self.core.match_decision,quality_fit_key=lambda *args:(1,2),
                 cfg=SimpleNamespace(match_threshold=SimpleNamespace(value=82)),
                 MONITOR=None)
        pick=self.method(self.autoscan,"_pick_safe",env)
        class Fake:
            user_rejections={}
        ctx={}
        rows=[
           ({"id":"r1","name":"V Sport Live 1","server_priority":0},125.0,
            {"name":100,"review_reason":"LIVE subservice mismatch"}),
           ({"id":"r2","name":"V Sport 8","server_priority":0},130.0,
            {"name":100,"reject_reason":"wrong number"}),
        ]
        ch,score,details,review=pick(Fake(),"sat","V Sport 1 HD",ctx,rows)
        self.assertIsNone(ch)
        self.assertTrue(review)
        rows.append(({"id":"safe","name":"V Sport 1","server_priority":1},92.0,{"name":100}))
        chosen,score,details,review=pick(Fake(),"sat","V Sport 1 HD",ctx,rows)
        self.assertEqual(chosen["id"],"safe")
        self.assertEqual(details.get("auto_lock_original_decision"),"SAFE")

    def test_runtime_protected_and_counter_updated(self):
        for name,blob in self.baseline.items():
            if name not in (b.PLUGIN,b.CORE,b.UPDATER):
                self.assertEqual(self.package[name],blob,name)
        self.assertTrue(self.meta["player_unchanged"])
        self.assertFalse(self.meta["production_published"])
        self.assertFalse(self.meta["receiver_tested"])
        self.assertIn("self._set_focus(self.focus)",self.psrc)
        self.assertIn("turbo_192_first_paint_delayed_sat_roster_late_video_poll" if False else
                      "r735_generic_SAFE_first_and_numbered_LIVE_variant_guard",
                      self.meta["candidate_search"])

if __name__=="__main__":
    unittest.main()
