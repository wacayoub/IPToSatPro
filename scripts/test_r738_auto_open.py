#!/usr/bin/env python3
"""R73.8 integration tests on the actual checksum-built IPK (not a mock plugin)."""
import ast, importlib.util, tempfile, unittest
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("build738",ROOT/"scripts/build-r738-auto-open.py")
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)

class AutoOpenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        pkg=Path(cls.tmp.name)/"r738.ipk"
        cls.meta=b.build(pkg)
        cls.files=b.b.base.pack.members_from(b.b.base.pack.unpack_ar(pkg.read_bytes())["data.tar.gz"])
        cls.source=cls.files[b.b.PLUGIN].decode()
        cls.tree=ast.parse(cls.source)
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def setUp(self):
        self.ref="1:0:19:24CD:43C:1:C00000:0:0:0:"
        self.iptv=dict(id="best",name="FR NICKELODEON HD",url="http://192.0.2.4/channel",
                       server_role="BACKUP2",server_label="STRONG8K")
        self.saved={"auto_best_lock":True,"channel_id":"best"}
        self.delayed=[]
        self.logs=[]
        t=self
        class Ref:
            def __init__(self,value):self.value=value
            def toString(self):return self.value
        class Nav:
            def __init__(self):self.ref=Ref(t.ref)
            def getCurrentlyPlayingServiceReference(self):return self.ref
        class Catalog:
            def find_fingerprint(self,fp):return t.iptv if fp=="best" else None
        class Monitor:
            def __init__(self):
                self.session=SimpleNamespace(nav=Nav())
                self.catalog=Catalog()
                self.current_sat_ref_string=t.ref
                self.current_sat_started_at=123.0
                self.current_sat_name="NICKELODEON"
                self.manual_preview_active=True
                self.fallback_active=False
                self.switch_in_progress=False
                self.video_event_seen=False
                self.tuner_state="TUNING"
                self.smartmatch_generation=0
                self.smartmatch_pending=None
                self.smartmatch_result=None
                self.smartmatch_timer=SimpleNamespace(stop=lambda:None)
                self.played=[]
                self.target_quality_rank=400
                self.plan_inputs=[]
            def _same_sat_still_playing(self):
                return self.session.nav.getCurrentlyPlayingServiceReference().toString()==self.current_sat_ref_string
            def _ensure_sat_switch_metadata(self):pass
            def _prepare_target_quality(self):pass
            def _direct_candidate_plan(self,ch,source):
                self.plan_inputs.append(source)
                return [(ch,142,{},(),0)]
            def _activate_candidate(self,idx,source):
                ch,score,_,_,_=self.candidate_plan[idx]
                self.pending_match=ch
                self.pending_score=score
                return True
            def _play_match(self,match,score,retry=False):
                self.played.append((match["id"],score,retry))
            def _log(self,*args):t.logs.append(args)
        self.monitor=Monitor()
        self.ns={
            "MONITOR":self.monitor,
            "time":__import__("time"),
            "cfg":SimpleNamespace(enabled=SimpleNamespace(value=True)),
            "sat_service_key":lambda ref:ref,
            "_load_overrides":lambda:{self.ref:self.saved},
            "channel_fingerprint":lambda ch:ch.get("id",""),
            "_startup_log":lambda *args:self.logs.append(args),
            "_defer_ui_call":lambda cb,ms:self.delayed.append((cb,ms)),
        }
        names={"_r738_autoplay_current","_r738_queue_auto_open"}
        nodes=[n for n in self.tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
        self.assertEqual(len(nodes),2)
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),
                     "r738-compiled-ipk","exec"),self.ns)
        class Screen:
            def __init__(self):
                self.session=t.monitor.session
                self.restore_ref=Ref(t.ref)
                self.sat_name="NICKELODEON"
                self._closed_for_async=False
                self.closed=0
            def close(self):
                self.closed+=1
                self._closed_for_async=True
                t.monitor.manual_preview_active=False
        self.screen=Screen()
    def run_deferred(self):
        for _ in range(6):
            if not self.delayed:break
            cb,_ms=self.delayed.pop(0)
            cb()

    def test_good_safe_candidate_auto_opens_without_remote_confirmation(self):
        self.assertTrue(self.ns["_r738_queue_auto_open"](self.screen,self.ref,"AUTO_CREATED",self.iptv))
        self.assertEqual(self.monitor.played,[])
        self.run_deferred()
        self.assertEqual(self.screen.closed,1)
        self.assertEqual(self.monitor.played,[("best",142,False)])
        self.assertEqual(self.monitor.plan_inputs,["SESSION_FAST"])
        self.assertTrue(any("AUTO_PLAY_START" in str(x) for x in self.logs))
    def test_new_auto_mapping_with_cache_current_sat_uses_same_path(self):
        self.assertTrue(self.ns["_r738_queue_auto_open"](self.screen,self.ref,"AUTO_REPLACED",self.iptv))
        self.run_deferred()
        self.assertEqual(len(self.monitor.played),1)
    def test_existing_manual_and_review_are_never_auto_opened(self):
        for state in ("REVIEW_ONLY","MANUAL_PROTECTED","NO_SAFE"):
            self.assertFalse(self.ns["_r738_queue_auto_open"](self.screen,self.ref,state,self.iptv))
        self.assertEqual(self.delayed,[])
    def test_existing_auto_mapping_from_older_build_autoplays(self):
        self.assertTrue(self.ns["_r738_queue_auto_open"](self.screen,self.ref,"ALREADY_AUTO",self.iptv))
        self.run_deferred()
        self.assertEqual(len(self.monitor.played),1)
    def test_recent_failed_autoplay_leaves_preview_open_for_manual_correction(self):
        import time
        self.monitor._r738_autoplay_last=(self.ref,"best",time.monotonic())
        self.assertFalse(self.ns["_r738_queue_auto_open"](self.screen,self.ref,"ALREADY_AUTO",self.iptv))
        self.assertEqual(self.screen.closed,0)
        self.assertEqual(self.delayed,[])
    def test_zap_while_scoring_prevents_hijack(self):
        self.assertTrue(self.ns["_r738_queue_auto_open"](self.screen,self.ref,"AUTO_CREATED",self.iptv))
        self.monitor.session.nav.ref.value="1:0:1:OTHER"
        self.run_deferred()
        self.assertEqual(self.screen.closed,0)
        self.assertEqual(self.monitor.played,[])
    def test_noncurrent_sat_never_auto_opens(self):
        self.monitor.session.nav.ref.value="OTHER"
        self.assertFalse(self.ns["_r738_queue_auto_open"](self.screen,self.ref,"AUTO_CREATED",self.iptv))
    def test_manual_override_updated_during_defer_cancels_auto(self):
        self.assertTrue(self.ns["_r738_queue_auto_open"](self.screen,self.ref,"AUTO_CREATED",self.iptv))
        self.saved={"auto_best_lock":False,"channel_id":"user-manual"}
        self.run_deferred()
        self.assertEqual(self.monitor.played,[])
    def test_native_sat_video_already_active_is_preserved(self):
        self.monitor.manual_preview_active=False
        self.monitor.tuner_state="LOCKED"
        self.monitor.video_event_seen=True
        result=self.ns["_r738_autoplay_current"](self.ref,"best")
        self.assertEqual(result,"SAT_VIDEO_ACTIVE")
        self.assertEqual(self.monitor.played,[])
    def test_player_already_busy_no_duplicate_start(self):
        self.monitor.manual_preview_active=False
        self.monitor.fallback_active=True
        result=self.ns["_r738_autoplay_current"](self.ref,"best")
        self.assertEqual(result,"PLAYER_BUSY")
        self.assertEqual(self.monitor.played,[])
    def test_same_sat_and_mapping_cannot_autostart_twice(self):
        self.monitor.manual_preview_active=False
        self.assertEqual(self.ns["_r738_autoplay_current"](self.ref,"best"),"PLAY_REQUESTED")
        self.assertEqual(self.ns["_r738_autoplay_current"](self.ref,"best"),"ALREADY_REQUESTED")
        self.assertEqual(len(self.monitor.played),1)
    def test_package_preserves_original_monitor_player_timeshift(self):
        self.assertTrue(self.meta["monitor_unchanged"])
        self.assertTrue(self.meta["player_unchanged"])
        self.assertFalse(self.meta["production_published"])
        self.assertFalse(self.meta["receiver_tested"])
        self.assertIn("budget=36",self.files[b.b.CORE].decode())
        self.assertIn("AUTO_PLAY_START",self.source)
        self.assertEqual(self.source.count("_r738_queue_auto_open(self, raw,"),2)
if __name__=="__main__":unittest.main()
