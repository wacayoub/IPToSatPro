#!/usr/bin/env python3
"""Run read-only real r69 Preview/SmartMatch scoring probes in GitHub CI."""
from pathlib import Path
import tempfile
import sys
import importlib.util
from audit_r70_baseline import load_release, PREFIX

def core_module():
    raw = load_release()[PREFIX + "core.py"]
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp)/"core.py"
        source.write_bytes(raw)
        spec = importlib.util.spec_from_file_location("r70_original_core", source)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

def main():
    m = core_module()
    ctx = {"confidence":"HIGH", "market_preferences":["FR"],
           "language_priorities":["FR"], "audio_language_set":["FR"],
           "audio_language_target":"FR", "provider":"ABSat",
           "sat_provider":"ABSat", "orbital_position":130}
    cases = [
        ("Ushuaia TV HD","FR: Ushuaia TV HD","FRANCE", "FR"),
        ("Ushuaia TV HD","IT: Ushuaia TV HD","ITALY", "IT"),
        ("Ushuaia TV HD","Ushuaia TV FHD","ITALY", "FR"),
        ("Canal+ Golf HD","FR: Canal+ Golf FHD","FRANCE", "FR"),
        ("Canal+ Golf HD","PL: Canal+ Golf FHD","POLAND", "PL"),
        ("beIN Sports 6 HD","FR: beIN Sports 6 HD","FRANCE","FR"),
        ("beIN Sports 6 HD","FR: beIN Sports 8 HD","FRANCE","FR"),
        ("Ushuaia TV HD","Ushuaia TV HD","ITALY", "FR"),
    ]
    for sat,name,group,language in cases:
        ch = {"name":name, "group":group, "language":language,
              "server_priority":1, "url":"http://127.0.0.1/NOT_USED"}
        for preview in [False, True]:
            try:
                score, det = m.match_score_details(
                    sat,ch,["FR"],ctx,"best",preview=preview)
                state = m.match_decision(score,det,82.0)
                print("PROBE",repr(sat),repr(name),group,language,
                      "manual_preview" if preview else "auto",
                      "SCORE",score,"STATE",state,
                      "REJECT",det.get("reject_reason"),
                      "REVIEW",det.get("review_reason"),
                      "MKT",det.get("market"),
                      "LANG",det.get("language"))
            except Exception as exc:
                print("PROBE_ERROR",repr(sat),repr(name),str(exc))
                raise
    print("BASELINE_CORE_SMOKE_OK")
if __name__ == "__main__":
    main()
