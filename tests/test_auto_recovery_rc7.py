"""r70-rc7 tests: failed pinned sources recover without manual Preview visits."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "r70"))
from auto_recovery_rc7 import attach_auto_recovery, _review_exact

class Timer:
    def __init__(self): self.callback=[]; self.armed=False
    def start(self, ms, one): self.armed=True
    def stop(self): self.armed=False
    def fire(self):
        if self.armed:
            self.armed=False
            for cb in self.callback: cb()

class Catalog:
    def __init__(self, rows):
        self.rows=rows
        self.channels=[{"id":"x"}]
        self.calls=0
    def fast_rank_matches_all_servers(self,*args,**kw):
        self.calls+=1
        return self.rows

def ch(i, name=None):
    return {"id":i,"name":name or i,"url":"fake://"+i,
            "server_priority":1}

def row(i, name, score, detail):
    return (ch(i,name),float(score),dict(detail))

class Monitor:
    def __init__(self, candidates, enabled=True):
        self.catalog=Catalog(candidates)
        self.cfg=SimpleNamespace(
            auto_recover_failed_mapping=SimpleNamespace(value=enabled),
            match_threshold=SimpleNamespace(value=82.0),
            quality_mode=SimpleNamespace(value="best"),
        )
        self.current_sat_ref_string="SAT:BEIN1"
        self.current_sat_name="beIN SPORTS 1"
        self.target_quality_rank=0
        self.current_match_name="beIN SPORTS 1"
        self.expected_iptv_ref_string="IPTV:OLD"
        self.current_sat_ref=True
        self.last_match_source="MANUAL_LOCK"
        self.pending_match=ch("locked","TOD EVENT SPORTS 7 FHD")
        self.last_match=self.pending_match
        self.failed_candidate_ids=set()
        self.candidate_plan=[(self.pending_match,150.0,{},(0,0,0,0,0,0),0)]
        self.candidate_index=0
        self.stream_health={}
        self.sat_context={}
        self.logged=[]
        self.schedules=[]
        self.records=[]
        self.restored=[]
        self.session=SimpleNamespace(
            nav=SimpleNamespace(getCurrentlyPlayingServiceReference=lambda:
                                SimpleNamespace(toString=lambda:"IPTV:OLD")))
    def _ref_valid(self,ref):return bool(ref)
    def _user_languages(self):return ["EN","AR"]
    def _user_rejected_ids(self):return set()
    def _health_blocked(self,ch):return False
    def _no_4k_upscale_enabled(self):return True
    def _record_health(self,ch,success,reason=""):self.records.append((ch["id"],reason))
    def _log(self,event,msg):self.logged.append(event)
    def _set_state(self,*args):pass
    def _final_restore_sat(self,why):self.restored.append(why)
    def _schedule_next_candidate(self, reason, mark_failure=True):
        self.schedules.append((reason,mark_failure))
        if self.candidate_index+1 >= len(self.candidate_plan):
            self._final_restore_sat("none")
            return False
        self.candidate_index+=1
        self.pending_match=self.candidate_plan[self.candidate_index][0]
        return True
    def _build_candidate_plan(self,ranked,pinned=None):
        return [(c,score,d,(0,0,0,0,0,0),1)
                for c,score,d in ranked
                if score>=82 and not d.get("reject_reason")
                and c["id"] not in self.failed_candidate_ids]
    def _stop_probe_timers(self):return None
    def _stop_all_timers(self):return None

def fingerprint(c):return c.get("id", "") if isinstance(c,dict) else ""
def normalize(s):
    return " ".join(str(s or "").lower().split())
def decision(score,details,threshold):
    if details.get("reject_reason"):return "REJECT"
    if score>=threshold:return "SAFE"
    return "REVIEW"

class RC7Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        attach_auto_recovery(Monitor, dict(eTimer=Timer,
            channel_fingerprint=fingerprint,normalize_name=normalize,
            match_decision=decision,
            effective_quality_info=lambda c:(
                "UHD" if c.get("quality_rank")==600 else "FHD",
                c.get("quality_rank",300),c.get("quality_source","guess"))))
    def test_manual_failed_lock_selects_alternative_automatically(self):
        m=Monitor([row("safe","beIN SPORTS 1",110,{"name":100}),
                   row("wrong","TOD EVENT SPORTS 8",110,{"name":100})])
        self.assertTrue(m._schedule_next_candidate("No decoded video"))
        self.assertEqual(m.catalog.calls,1)
        m._r70_rc7_worker.join(3)
        m._r70_rc7_timer.fire()
        self.assertEqual(m.pending_match["id"],"safe")
        self.assertEqual(m.records,[("locked","No decoded video")])
        self.assertEqual(m.schedules,[("No decoded video",False)])
        self.assertIn("AUTO_RESCUE_PLAN",m.logged)
        self.assertEqual(m.restored,[])
    def test_exact_review_automaps_only_precise_channel(self):
        m=Monitor([row("exact","beIN SPORTS 1",60,{"name":100}),
                   row("different","TOD EVENT SPORTS 7",60,{"name":100}),
                   row("market-conflict","beIN SPORTS 1",60,{"name":100,"market":-18})])
        rows=m._build_candidate_plan(m.catalog.rows)
        self.assertEqual([r[0]["id"] for r in rows],["exact"])
    def test_failed_manual_no_other_valid_keeps_sat(self):
        m=Monitor([row("wrong","TOD EVENT SPORTS 7",60,{"name":100})])
        m._schedule_next_candidate("EOF")
        m._r70_rc7_worker.join(3)
        m._r70_rc7_timer.fire()
        self.assertEqual(len(m.restored),1)
        self.assertIn("AUTO_RESCUE_EMPTY",m.logged)
    def test_do_not_override_good_direct_source_before_failure(self):
        m=Monitor([row("safe","beIN SPORTS 1",110,{"name":100})])
        self.assertEqual(m.catalog.calls,0)
        self.assertFalse(hasattr(m,"_r70_rc7_pending"))
    def test_opt_out_retains_original_failure(self):
        m=Monitor([row("safe","beIN SPORTS 1",110,{"name":100})],enabled=False)
        self.assertFalse(m._schedule_next_candidate("EOF"))
        self.assertEqual(m.catalog.calls,0)
        self.assertEqual(len(m.restored),1)
    def test_stale_nav_ignores_background_result(self):
        m=Monitor([row("safe","beIN SPORTS 1",110,{"name":100})])
        m._schedule_next_candidate("EOF")
        m._r70_rc7_worker.join(3)
        m.session.nav.getCurrentlyPlayingServiceReference=lambda:SimpleNamespace(toString=lambda:"OTHER:IPTV")
        m._r70_rc7_timer.fire()
        self.assertEqual(m.schedules,[])
        self.assertEqual(m.restored,[])
    def test_no_repeated_background_search_same_failure_cycle(self):
        m=Monitor([row("safe","beIN SPORTS 1",110,{"name":100})])
        m._schedule_next_candidate("EOF")
        self.assertEqual(m.catalog.calls,1)
        m._r70_rc7_worker.join(3)
        m._r70_rc7_timer.fire()
        m.candidate_index=len(m.candidate_plan)-1
        m.last_match_source="MANUAL_LOCK"
        m._schedule_next_candidate("Again")
        self.assertEqual(m.catalog.calls,1)
    def test_explicit_user_reject_is_not_in_plan(self):
        m=Monitor([row("bad","beIN SPORTS 1",60,{"name":100}),
                   row("good","beIN SPORTS 1",60,{"name":100})])
        m._user_rejected_ids=lambda:{"bad"}
        self.assertEqual([a[0]["id"] for a in m._build_candidate_plan(m.catalog.rows)],["good"])
    def test_forced_review_preserves_no_4k_upscale(self):
        candidate=row("wrong4k","beIN SPORTS 1",60,{"name":100})
        candidate[0]["quality_rank"]=600
        m=Monitor([candidate])
        m.target_quality_rank=500
        self.assertEqual(m._build_candidate_plan(m.catalog.rows),[])

    def test_forced_review_uhd_unknown_quality_is_not_automapped(self):
        candidate=row("unknown","beIN SPORTS 1",60,{"name":100})
        m=Monitor([candidate])
        m.target_quality_rank=600
        self.assertEqual(m._build_candidate_plan(m.catalog.rows),[])

    def test_forced_review_allows_observed_compatible_quality(self):
        candidate=row("fhd","beIN SPORTS 1",60,{"name":100})
        candidate[0].update(quality_rank=500,quality_source="observed")
        m=Monitor([candidate])
        m.target_quality_rank=500
        self.assertEqual(m._build_candidate_plan(m.catalog.rows)[0][0]["id"],"fhd")

    def test_cancel_stops_pending_timer(self):
        m=Monitor([row("safe","beIN SPORTS 1",110,{"name":100})])
        m._schedule_next_candidate("EOF")
        m._stop_all_timers()
        self.assertFalse(m._r70_rc7_timer.armed)
        self.assertIsNone(m._r70_rc7_pending)

if __name__=="__main__":unittest.main()
