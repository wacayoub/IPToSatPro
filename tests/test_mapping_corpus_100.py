"""100 actual, deterministic identity-scoring scenarios on real shipped r69 core.

Does not test a receiver or IPTV playback. It tests the native
scoring and channel-number protections for 100 SAT/OTT name pairs.
"""
import ast
import base64
import io
from pathlib import Path
import subprocess
import tempfile
import tarfile
import types
import unittest

ROOT=Path(__file__).resolve().parents[1]
raw=base64.b64decode((ROOT/"payload/r69-beta.b64").read_bytes())
with tempfile.TemporaryDirectory(prefix="core-identity-") as d:
    ipk=Path(d)/"base.ipk"
    ipk.write_bytes(raw)
    data=subprocess.check_output(["ar","p",str(ipk),"data.tar.gz"])
with tarfile.open(fileobj=io.BytesIO(data),mode="r:gz") as t:
    code=t.extractfile("./usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/core.py").read().decode("utf-8")
ns={"__name__":"audit_core"}
exec(compile(code,"core.py","exec"),ns)
score=ns["match_score_details"]
decision=ns["match_decision"]
_cases=[]


def sample(sat, iptv, market, lang, good, label):
    ch={"name":iptv,"market":market,"language":lang,"url":"fake://unit"}
    ctx={"market":market,"confidence":"LOW","language_priorities":[lang]}
    _cases.append((sat,ch,ctx,lang,good,label))


for i in range(1,21):
    sample("beIN SPORTS %d"%i,"AR BEIN SPORTS %d FHD"%i,
           "AR","AR",True,"same-number-bein")
    sample("beIN SPORTS %d"%i,"AR BEIN SPORTS %d FHD"%(i+1),
           "AR","AR",False,"different-number-bein")
    sample("TREK %d"%i,"FR TREK %d FHD"%i,
           "FR","FR",True,"french-prefix-trek")
    sample("Mezzo TV %d"%i,"PL MEZZO TV %d HD"%i,
           "PL","PL",True,"polish-prefix-mezzo")
    sample("beIN SPORTS %d"%i,"TOD EVENT SPORTS %d FHD"%(i+5),
           "AR","AR",False,"tod-event-does-not-equal-bein")

assert len(_cases)==100


class MappingCorpus100(unittest.TestCase):
    def test_all_one_hundred_scoring_and_number_safety_cases(self):
        passed=0
        for i,(sat,ch,ctx,lang,should_match,label) in enumerate(_cases,1):
            with self.subTest(case=i,scenario=label,sat=sat,iptv=ch["name"]):
                value,details=score(sat,ch,[lang],ctx,"best")
                outcome=decision(value,details,82.0)
                if should_match:
                    self.assertIn(outcome,("SAFE","ALLOWED"))
                else:
                    self.assertEqual(outcome,"REJECT")
                passed+=1
        self.assertEqual(passed,100)
        print("100/100 native core identity/scoring scenarios passed (OFFLINE ONLY).")


if __name__=="__main__":
    unittest.main()
