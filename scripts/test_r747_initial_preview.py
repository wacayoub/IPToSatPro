#!/usr/bin/env python3
"""R74.7 real-IPK Preview first SAT regression: 1 seed -> full background scan."""
import ast
import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("r747builder",ROOT/"scripts/build-r74-unified.py")
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)

REF="1:0:19:24CD:43C:1:C00000:0:0:0:"
CH={"name":"FR NICKELODEON HD","url":"http://example.invalid/live/1.ts",
    "server_role":"BACKUP2","_preview_score":150}

class ETimer:
    def __init__(self):self.started=[];self.stopped=0
    def start(self,ms,once=True):self.started.append(ms)
    def stop(self):self.stopped+=1

class FirstSatCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        file=Path(cls.tmp.name)/"r747.ipk"
        cls.meta=builder.build(file)
        fs=builder.b.b.base.pack.members_from(builder.b.b.base.pack.unpack_ar(file.read_bytes())["data.tar.gz"])
        cls.plugin=fs[builder.PLUGIN].decode()
        tree=ast.parse(cls.plugin)
        c=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=="SatIPTVBridgePreview")
        cls.methods={n.name:n for n in c.body if isinstance(n,ast.FunctionDef)}
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def isolate(self,name,env):
        code=ast.fix_missing_locations(ast.Module(body=[self.methods[name]],type_ignores=[]))
        exec(compile(code,"r747-real-IPK.py","exec"),env)
        return env[name]

    def make_view(self,rows=None,complete=False):
        rows=list(rows if rows is not None else [CH])
        logs=[]
        class Fake:
            def __init__(self):
                self.sat_name="NICKELODEON"
                self.sat_ref_string=REF
                self.context={}
                self.focus="left"
                self.sat_rows=[{"ref":REF,"name":"NICKELODEON"}]
                self._candidate_cache={REF:("NICKELODEON",{},rows,complete)}
                self._r732_auto_rows=[]
                self._r732_auto_page=0
                self._sat_rows_loaded=True
                self._source_pos_by_sat={}
                self._preview_results={}
                self._candidate_expand_timer=ETimer()
                self.candidate_expand_timer=self._candidate_expand_timer
                self.sat_roster_timer=ETimer()
                self.selected_index=0
                self.channels=[]
                self.current_result="UNKNOWN"
                self.lines={}
                self._user_rejected_ids=set()
            def _selected_sat_row(self):return self.sat_rows[0]
            def _refresh_epg_now_next(self,raw):pass
            def _refresh_mapping_caches(self):pass
            def _render_sat_list(self,keep_index=True):pass
            def _render_source_list(self,keep_index=False):pass
            def _update_header(self):pass
            def _set_focus(self,focus):pass
            def __getitem__(self,item):
                return SimpleNamespace(setText=lambda t:self.lines.__setitem__(item,t))
        f=Fake()
        env={
            "sat_service_key":lambda x:x,
            "channel_fingerprint":lambda ch:ch.get("name",""),
            "clean_display_name":lambda s:s,
            "_startup_log":lambda *args:logs.append(args),
            "_preview_candidate_cache_get":lambda raw:None,
            "PREVIEW_LAST_SOURCE_BY_SAT":{},
        }
        return f,self.isolate("_load_selected_sat_candidates",env),logs

    def test_one_manual_lock_seed_is_visible_and_full_rank_is_scheduled(self):
        f,run,logs=self.make_view()
        run(f)
        self.assertEqual(len(f.channels),1)
        self.assertEqual(f.channels[0]["name"],CH["name"])
        self.assertEqual(f.candidate_expand_timer.started,[20])
        self.assertIn("searching ALL IPTV servers",f.lines.get("status",""))
        self.assertTrue(any(x[0]=="PREVIEW_SEED_EXPAND" for x in logs))

    def test_partial_two_candidate_cache_also_expands(self):
        f,run,logs=self.make_view([CH,dict(CH,name="NICKELODEON HD alternative")],False)
        run(f)
        self.assertEqual(len(f.channels),2)
        self.assertEqual(f.candidate_expand_timer.started,[20])

    def test_truly_completed_single_source_cache_does_not_repeat_rank(self):
        f,run,logs=self.make_view([CH],True)
        run(f)
        self.assertEqual(len(f.channels),1)
        self.assertEqual(f.candidate_expand_timer.started,[])

    def test_no_cached_results_still_triggers_worker(self):
        f,run,logs=self.make_view([],False)
        run(f)
        self.assertEqual(f.candidate_expand_timer.started,[20])

    def test_workers_busy_rearm_without_running_second_worker(self):
        events=[]
        class Fake:
            _closed_for_async=False
            _expand_worker=SimpleNamespace(is_alive=lambda:True)
            _r71_deep_requested=False
            _r71_deep_target_ref=""
            _candidate_cache={}
            candidate_expand_timer=ETimer()
            def _selected_sat_row(self):return {"ref":REF,"name":"NICKELODEON"}
        f=Fake()
        env={
            "sat_service_key":lambda x:x,
            "_preview_candidate_cache_get":lambda raw:None,
            "_startup_log":lambda *x:events.append(x),
            "clean_display_name":lambda s:s,
        }
        run=self.isolate("_expand_selected_sat_candidates",env)
        run(f)
        self.assertEqual(f.candidate_expand_timer.started,[150])
        self.assertTrue(any(x[0]=="PREVIEW_EXPAND_WAIT" for x in events))

    def test_complete_candidate_count_will_use_192_slots_from_all_servers(self):
        self.assertIn("candidate_budget = 192",self.plugin)
        self.assertIn("candidate_per_server = 64",self.plugin)
        self.assertIn('per_server=candidate_per_server, topn=candidate_budget',self.plugin)
        self.assertIn("self._merge_locked_candidate(key, channels, sat_name, ctx)",self.plugin)
        self.assertIn("selected_raw != raw",self.plugin)

    def test_mapping_and_player_runtime_untouched(self):
        self.assertTrue(self.meta["preview_initial_seed_fix"])
        self.assertFalse(self.meta["receiver_tested"])
        self.assertTrue(self.meta["monitor_black_decision"])

if __name__=="__main__":
    unittest.main()
