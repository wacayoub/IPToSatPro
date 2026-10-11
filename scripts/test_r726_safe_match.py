#!/usr/bin/env python3
"""Tests run *actual shipped R72.6* monitor candidate plan, not a copy."""
import ast,base64,hashlib,importlib.util,tempfile,types,unittest
from pathlib import Path
sp=importlib.util.spec_from_file_location("r726",Path(__file__).with_name("build-r726-safe-match.py"))
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)
class Cfg:
    def __init__(self,val):self.value=val

class Fake:
    def __init__(self,**opt):
        self.cfg=types.SimpleNamespace(match_threshold=Cfg(82),resolution_policy=Cfg("source_strict"),
                                       fallback_no_signal=Cfg(opt.get("enabled",True)))
        self.current_match_name=opt.get("sat","Digi 24")
        self.current_sat_name=self.current_match_name
        self.current_sat_ref_string="1:0:1:1:11:01:170000:0:0:0:" if opt.get("ref",True) else ""
        self.tuner_state=opt.get("state","TUNE_FAILED")
        self.fallback_active=opt.get("fallback",False)
        self.same=opt.get("same",True)
        self.target_quality_rank=0
        self.target_hdr=""
        self.target_quality="AUTO"
        self.sat_context={"confidence":"MEDIUM"}
        self.stream_health={}
        self.MAX_CANDIDATE_PLAN=5
        self.rejected=opt.get("rejected",set())
        self.logged=[]
    def _same_sat_still_playing(self):return self.same
    def _user_rejected_ids(self):return self.rejected
    def _health_blocked(self,ch):return False
    def _no_4k_upscale_enabled(self):return True
    def _log(self,event,msg):self.logged.append((event,msg))

def decision(score,details,threshold):
    if details.get("reject_reason"):return "REJECT"
    if details.get("review_reason"):return "REVIEW"
    return "SAFE" if score>=threshold else "REVIEW"

class CandidateGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.pkg=Path(cls.tmp.name)/"r726.ipk"
        cls.meta=b.build(cls.pkg)
        cls.files=b.pack.members_from(b.pack.unpack_ar(cls.pkg.read_bytes())["data.tar.gz"])
        cls.old=b.pack.members_from(b.pack.unpack_ar(base64.b64decode(b.BASE.read_bytes()))["data.tar.gz"])
        oldtree=ast.parse(cls.old[b.MONITOR])
        tree=ast.parse(cls.files[b.MONITOR])
        def method(tree):
            target=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=="SatFallbackMonitor")
            return next(x for x in target.body if isinstance(x,ast.FunctionDef) and x.name=="_build_candidate_plan")
        fn=method(tree);mod=ast.Module(body=[fn],type_ignores=[])
        ast.fix_missing_locations(mod)
        ns={"channel_fingerprint":lambda ch:ch["name"]+":"+ch.get("server_role",""),
            "match_decision":decision,
            "effective_quality_info":lambda ch:("HD",400,"name"),
            "effective_hdr_info":lambda ch:("",0,"")}
        exec(compile(mod,"actual_r726_monitor.py","exec"),ns)
        cls.plan_fn=staticmethod(ns["_build_candidate_plan"])
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def trial(self,score=71,**kw):
        name=kw.pop("name","RO: DIGI 24 HD")
        market=kw.pop("market","RO")
        lang=kw.pop("lang","RO")
        review=kw.pop("review","explicit IPTV market RO differs from ambiguous SAT market hint NL")
        reject=kw.pop("reject","")
        f=Fake(**kw)
        ch={"name":name,"market":market,"language":lang,"server_role":"PRIMARY",
            "server_priority":0}
        details={"name":100.0,"market":-10.0,"language":-8.0,"quality":0.0,"variant":0.0,
                 "context":-11.0,"family":0.0,"equivalence":0.0,"penalty":0.0,
                 "reject_reason":reject,"review_reason":review}
        result=self.plan_fn(f,[(ch,score,details)])
        return f,result
    def test_real_digi24_71_is_allowed_after_tuner_failure(self):
        monitor,plan=self.trial()
        self.assertEqual(len(plan),1)
        self.assertEqual(plan[0][2]["decision"],"ALLOWED")
        self.assertEqual(plan[0][1],71)
        self.assertEqual(monitor.logged[0][0],"DIGI24_RO_NO_SIGNAL_ALLOW")
    def test_reject_wrong_language_country_name_and_hard_mismatch(self):
        cases=[
          {"name":"RO: DIGI 25 HD"},{"name":"CZ: DIGI 24 HD"},
          {"name":"RO: DIGI 24 SPORTS HD"},{"market":"CZ"},
          {"lang":"FR"},{"reject":"IPTV feed language RO conflicts with SAT audio FR"},
          {"review":"IPTV feed audio conflict / verify"},
          {"sat":"Digi 24 News HD"}]
        for kw in cases:
            with self.subTest(**kw):
                _,p=self.trial(**kw);self.assertFalse(p)
    def test_working_sat_other_stream_and_user_block_preserved(self):
        for kw in [{"state":"LOCKED"},{"state":"ACQUIRING"},{"state":"TUNING"},
                   {"state":"UNKNOWN"},{"enabled":False},{"same":False},
                   {"fallback":True},{"ref":False},
                   {"rejected":{"RO: DIGI 24 HD:PRIMARY"}}]:
            with self.subTest(**kw):
                _,p=self.trial(**kw);self.assertFalse(p)
        _,p=self.trial(score=60);self.assertFalse(p)
        _,p=self.trial(score=64.99);self.assertFalse(p)
    def test_quality_and_global_score_guard_unchanged(self):
        _,p=self.trial(score=82,review="")
        self.assertEqual(len(p),1)
        self.assertEqual(p[0][2]["decision"],"SAFE")
        before=ast.parse(self.old[b.MONITOR])
        after=ast.parse(self.files[b.MONITOR])
        def d(tree):
            cls=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=="SatFallbackMonitor")
            return {m.name:ast.dump(m,include_attributes=False) for m in cls.body if isinstance(m,ast.FunctionDef)}
        old,new=d(before),d(after)
        self.assertEqual(set(old),set(new))
        self.assertEqual({k for k in old if old[k]!=new[k]},{"_build_candidate_plan"})
        self.assertEqual(set(self.files),set(self.old)|{b.CHANGELOG})
        for f,blob in self.old.items():
            if f not in (b.MONITOR,b.PLUGIN,b.UPDATER):
                self.assertEqual(blob,self.files[f],f)
    def test_package_reproducible_and_no_main_production(self):
        other=Path(self.tmp.name)/"again.ipk"
        info=b.build(other)
        self.assertEqual(self.pkg.read_bytes(),other.read_bytes())
        self.assertEqual(info["sha256"],hashlib.sha256(other.read_bytes()).hexdigest())
        self.assertFalse(info["receiver_tested"])
        self.assertFalse(info["production_published"])
if __name__=="__main__":unittest.main()
