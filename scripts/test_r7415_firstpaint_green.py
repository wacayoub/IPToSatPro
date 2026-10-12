"""R7415 regression tests from the real generated R74 package.

Verify (a) initial incomplete EMPTY cache gets immediate candidate render,
(b) legacy fuzzy score is not used for first paint, (c) manual GREEN locks a
highlighted candidate without OK/video even with SAT/LEFT focus, (d) safe
rollback, (e) no player/monitor changes.
"""
import ast
import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]


def load(name,filename):
    sp=importlib.util.spec_from_file_location(name,ROOT/"scripts"/filename)
    module=importlib.util.module_from_spec(sp)
    sp.loader.exec_module(module)
    return module


builder=load("builder7415","build-r74-unified.py")
fix11=load("patch7411_7415","r7411_preview_persist_priority_hotfix.py")
fix12=load("patch7412_7415","r7412_preview_fast_shortlist_hotfix.py")
fix13=load("patch7413_7415","r7413_preview_inline_hotfix.py")
fix14=load("patch7414_7415","r7414_fast_candidates_manual_lock.py")
fix15=load("patch7415","r7415_firstpaint_green_any_focus.py")


class Label:
    def __init__(self,store,name):
        self.store,self.name=store,name
    def setText(self,message):
        self.store.append((self.name,message))


class Timer:
    def __init__(self,store):self.store=store
    def start(self,ms,once=True):self.store.append(("timer",ms))
    def stop(self):self.store.append(("stop",))


class PreviewGreenAnyFocusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        file=Path(cls.tmp.name)/"r74.ipk"
        builder.build(file)
        package=builder.b.b.base.pack
        files=package.members_from(package.unpack_ar(file.read_bytes())["data.tar.gz"])
        cls.original=files[builder.PLUGIN].decode()
        cls.s11=fix11.patch_plugin(cls.original)[0]
        cls.s12=fix12.patch(cls.s11)[0]
        cls.s13=fix13.patch(cls.s12)[0]
        cls.s14=fix14.patch(cls.s13)[0]
        cls.s15,cls.state=fix15.patch(cls.s14)
        cls.tree=ast.parse(cls.s15)
        cls.preview=next(n for n in cls.tree.body if isinstance(n,ast.ClassDef)
                         and n.name=="SatIPTVBridgePreview")
        cls.methods={n.name:n for n in cls.preview.body if isinstance(n,ast.FunctionDef)}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    @classmethod
    def method(cls,name,env):
        code=ast.fix_missing_locations(ast.Module(body=[cls.methods[name]],type_ignores=[]))
        scope=dict(env)
        exec(compile(code,"real-r7415.py","exec"),scope)
        return scope[name]

    def test_real_package_all_hotfixes_and_compile(self):
        self.assertEqual(self.state,"ready")
        self.assertEqual(fix15.patch(self.s15)[1],"already-installed")
        self.assertIn(fix15.TAG,self.s15)
        self.assertIn("PREVIEW_STAY_OPEN",self.s15)
        self.assertIn("candidate_budget = 192 if self._r71_worker_deep else 24",self.s15)
        self.assertIn("_r7413_keep_preview_visible()",self.s15)

    def test_first_paint_from_initial_empty_cache(self):
        events=[]
        channel=dict(id="candidate-1",name="AR BEIN SPORTS 2 FHD",
                     url="http://example.invalid/stream.ts",
                     _manual_candidate=True)
        key="satref"
        class Fake:
            def __init__(self):
                self.sat_name="beIN SPORTS EN 2"
                self.sat_ref_string=key
                self.context={}
                self._candidate_cache={key:("beIN SPORTS EN 2",{},[],False)}
                self._r732_auto_rows=[]
                self._r732_auto_page=0
                self.channels=[]
                self.selected_index=0
                self._source_pos_by_sat={}
                self._preview_results={}
                self._sat_rows_loaded=True
                self.focus="left"
                self.candidate_expand_timer=Timer(events)
            def _selected_sat_row(self):
                return {"ref":key,"name":"beIN SPORTS EN 2"}
            def _refresh_epg_now_next(self,raw):
                events.append(("epg",raw))
            def _refresh_mapping_caches(self,*a,**kw):
                events.append(("mapping",))
            def _render_sat_list(self,**kw):
                events.append(("render_sat",))
            def _render_source_list(self,**kw):
                events.append(("render_iptv",))
            def _update_header(self):
                events.append(("header",))
            def _set_focus(self,name):
                self.focus=name
            def _r74_filters_active(self):
                return False
            def __getitem__(self,name):
                return Label(events,name)
        log=[]
        fn=self.method("_load_selected_sat_candidates",{
            "sat_service_key":lambda value:value,
            "_preview_candidate_cache_get":lambda raw:None,
            "_r7414_fast_exact_seed":lambda sat,cat:[dict(channel)],
            "MONITOR":SimpleNamespace(catalog=object()),
            "clean_display_name":lambda s:s,
            "channel_fingerprint":lambda item:item.get("id",""),
            "PREVIEW_LAST_SOURCE_BY_SAT":{},
            "_startup_log":lambda *a:log.append(a)
        })
        v=Fake()
        fn(v)
        self.assertEqual(v.channels[0]["name"],channel["name"])
        self.assertEqual(v._candidate_cache[key][3],False)
        self.assertTrue(any(x[0]=="PREVIEW_INSTANT_SEED" for x in log))
        self.assertLess(events.index(("render_iptv",)),events.index(("epg",key)))
        self.assertIn(("timer",20),events)

    def test_nonempty_cache_preserved(self):
        self.assertIn("if not complete and not (cached[2] or []):",self.s15)
        self.assertIn("if seeded:",self.s15)

    def test_exact_zero_falls_back_to_index_pool(self):
        method=next(n for n in self.tree.body if isinstance(n,ast.FunctionDef)
                    and n.name=="_r7414_fast_exact_seed")
        body=ast.get_source_segment(self.s15,method)
        self.assertIn('catalog._fast_candidate_pool(',body)
        self.assertIn("total_cap=48",body)
        self.assertIn('sources[:96]',body)
        self.assertNotIn("match_score_details(",body)

    def test_green_when_focus_is_left_locks_without_playback(self):
        events=[];logs=[]
        ch={"id":"x","name":"AR BEIN SPORTS 2 FHD",
            "url":"http://example.invalid/live", "_preview_score":0,
            "_preview_details":{"review_reason":"instant seed"}}
        class Fake:
            def __init__(self):
                self.focus="left"
                self.channels=[ch]
                self.sat_ref_string="satref"
                self.sat_name="beIN SPORTS EN 2"
                self.context={}
                self._preview_results={}
                self._preview_audio={}
                self.active_fp=""
                self.active_sat_ref=""
                self.preview_ok=False
                self.current_result="UNKNOWN"
            def _set_focus(self,where):
                events.append(("focus",where))
                self.focus=where
            def _selected_channel(self):return dict(ch)
            def _sat_key(self):return "satref"
            def _candidate_decision(self,x):return "REVIEW"
            def _refresh_mapping_caches(self,**kw):events.append(("refresh",))
            def _render_sat_list(self,**kw):events.append(("sat",))
            def _render_source_list(self,**kw):events.append(("iptv",))
            def _update_header(self):pass
            def _update_verify_strip(self):pass
            def __getitem__(self,name):return Label(events,name)
        fn=self.method("_lock",{
            "channel_fingerprint":lambda row:row["id"],
            "_remove_user_rejection":lambda *a:None,
            "_save_override":lambda *a,**kw:events.append(("saved",kw)),
            "_startup_log":lambda *args:logs.append(args)})
        v=Fake()
        fn(v)
        self.assertEqual(v.focus,"right")
        self.assertIn(("focus","right"),events)
        self.assertTrue(any(x[0]=="saved" and x[1].get("forced") for x in events if isinstance(x,tuple)))
        self.assertEqual(v.current_result,"MANUAL LOCKED")
        self.assertFalse(v.preview_ok)
        self.assertTrue(any(x[0]=="PREVIEW_MANUAL_UNVERIFIED" for x in logs))
        self.assertNotIn(("satref","x"),v._preview_results)

    def test_green_with_no_candidates_does_not_save(self):
        p=ast.get_source_segment(self.s15,self.methods["_lock"])
        self.assertIn('if not self.channels:',p)
        self.assertIn('self._set_focus("right")',p)

    def test_no_unverified_autolock(self):
        self.assertIn('item["_manual_candidate"] = True',self.s15)
        self.assertIn('item["_preview_score"] = 0.0',self.s15)
        self.assertIn('if complete and self._r732_auto_rows:',self.s15)

    def test_check_apply_and_rollback_bit_identical(self):
        with tempfile.TemporaryDirectory() as temp:
            target=Path(temp)/"plugin.py"
            target.write_text(self.s14)
            self.assertEqual(fix15.main(["--check","--target",str(target)]),0)
            self.assertEqual(target.read_text(),self.s14)
            self.assertEqual(fix15.main(["--apply","--target",str(target)]),0)
            self.assertEqual(target.read_text(),self.s15)
            self.assertEqual(fix15.main(["--rollback","--target",str(target)]),0)
            self.assertEqual(target.read_text(),self.s14)

if __name__=="__main__":
    unittest.main()
