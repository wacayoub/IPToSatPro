#!/usr/bin/env python3
"""R73.4 actual built preview UI, delayed decoder evidence, locked stream protection."""
import ast,base64,importlib.util,tempfile,time,types,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("r734_build",ROOT/"scripts/build-r73-preview.py")
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)

class PreviewFirstPaintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.ipk=Path(cls.tmp.name)/"r734.ipk"
        cls.meta=b.build(cls.ipk)
        cls.pack=b.base.pack.members_from(b.base.pack.unpack_ar(cls.ipk.read_bytes())["data.tar.gz"])
        cls.base=b.base.pack.members_from(b.base.pack.unpack_ar(base64.b64decode(b.B64.read_bytes()))["data.tar.gz"])
        cls.source=cls.pack[b.PLUGIN].decode()
        cls.tree=ast.parse(cls.source)
        cls.preview=next(x for x in cls.tree.body if isinstance(x,ast.ClassDef) and x.name=="SatIPTVBridgePreview")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_one_rank_then_roster_not_inverse(self):
        self.assertIn("try: self.sat_roster_timer.start(8500, True)",self.source)
        self.assertNotIn("try: self.sat_roster_timer.start(750, True)",self.source)
        poll=next(x for x in self.preview.body if isinstance(x,ast.FunctionDef) and x.name=="_poll_expanded_candidates")
        body=ast.get_source_segment(self.source,poll)
        self.assertIn("self.sat_roster_timer.start(350, True)",body)
        self.assertIn('PREVIEW_UI_CANDIDATES',body)
        self.assertLess(body.index('self._render_source_list(keep_index=True)'),body.index('self.sat_roster_timer.start(350, True)'))
        self.assertIn("catalog.fast_preview_mega_matches(",self.source)

    def test_late_resolution_after_verify_never_autoplays(self):
        method=next(x for x in self.preview.body if isinstance(x,ast.FunctionDef) and x.name=="_quality_poll")
        ns={"time":time,"_startup_log":lambda *args:None}
        class Mon:
            def __init__(self):
                self.stream_health={}
                self.catalog=None
                self.saves=0
            def _schedule_health_save(self):self.saves+=1
        m=Mon();ns["MONITOR"]=m
        exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])),
                    "r734_quality_poll","exec"),ns)
        class Label:
            def __init__(self):self.content=""
            def setText(self,text):self.content=text
        class Timer:
            def __init__(self):self.calls=[]
            def start(self,delay,single):self.calls.append(delay)
        class Fake:
            def __init__(self):
                self.preview_ok=False;self.current_result="VERIFY"
                self.active_fp="iptv-abcdef";self.active_sat_ref="sat-ref";self.sat_ref_string="sat-ref"
                self.quality_started_at=time.time()-3.1
                self.QUALITY_SAMPLE_WINDOW_S=2.2
                self.quality_rx_start=None;self.quality_transfer_samples=[]
                self.channel={"name":"beIN Sports 6","url":"http://192.0.2.1/bein"}
                self.quality_timer=Timer()
                self.labels={"status":Label(),"detail":Label()}
                self.stage=0
                self.quality_rx_time=self.quality_started_at
            def __getitem__(self,x):return self.labels[x]
            def _preview_player_active(self):return True
            def _video_info_now(self):
                if self.stage:
                    return {"width":1920,"height":1080,"codec":"H264","fps":25.0,"progressive":True}
                return {"width":0,"height":0}
            def _network_rx_bytes(self):return None
            def _dimensions(self):return (1920,1080) if self.stage else (0,0)
            def _evaluate_preview_audio(self,final=False):return {"state":"UNKNOWN","sat":[],"dolby":""}
            def _subtitle_languages(self):return [],False
            def _health_record(self,ch):return dict(m.stream_health.get(self.active_fp) or {})
            def _iq_score(self,*args,**kwargs):return 60
            def _open_speed_label(self,x):return "OK"
            def _audio_status_text(self,ch):return "AUDIO VERIFY"
            def _quality_checklist_text(self,ch):return "QUALITY VERIFY"
            def _update_subtitle_badge(self,**kwargs):pass
            def _render_source_list(self,keep_index=True):pass
            def _update_verify_strip(self):pass
        item=Fake()
        ns["_quality_poll"](item)
        self.assertEqual(len(item.quality_timer.calls),1,"missing dims must continue in VERIFY")
        self.assertNotIn("width",m.stream_health.get(item.active_fp,{}))
        item.stage=1
        ns["_quality_poll"](item)
        self.assertEqual(m.stream_health[item.active_fp]["width"],1920)
        self.assertEqual(m.stream_health[item.active_fp]["height"],1080)
        self.assertGreaterEqual(m.saves,1)
        self.assertFalse(item.preview_ok,"telemetry alone must never mark moving video PLAYING")
        self.assertIn("VERIFY",item.labels["status"].content)
        self.assertEqual(len(item.quality_timer.calls),1,"stop polling after valid late dimensions")

    def test_verify_branch_starts_quality_poll_without_zapping(self):
        method=next(x for x in self.preview.body if isinstance(x,ast.FunctionDef) and x.name=="_poll")
        body=ast.get_source_segment(self.source,method)
        self.assertIn('self.current_result = "VERIFY"',body)
        position=body.index('self.current_result = "VERIFY"')
        self.assertIn('self._start_quality_analysis()',body[position:position+1000])
        self.assertIn("self._r731_pts_steps < 2",body)

    def test_live_player_and_user_stores_unchanged(self):
        for name,content in self.base.items():
            if name not in (b.PLUGIN,b.CORE,b.UPDATER):
                self.assertEqual(content,self.pack[name],name)
        self.assertFalse(self.meta["receiver_tested"])
        self.assertFalse(self.meta["production_published"])
        self.assertTrue(self.meta["player_unchanged"])
        self.assertEqual(self.meta["candidate_search"],"turbo_192_first_paint_delayed_sat_roster_late_video_poll")

if __name__=="__main__":
    unittest.main()
