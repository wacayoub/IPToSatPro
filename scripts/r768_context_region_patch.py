#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R76.8: context-sensitive regional shortlist and REVIEW scoring.

Never infer a verified IPTV language from a name prefix. MENA satellite location
is a PRIORITY hint, not proof of audio/video identity. Existing manual locks,
decoders, players, mappings, provider identity gates and exact numbers stay intact.
"""
TAG = "R768_CONTEXT_REGION_PRIORITY"
OLD_RETURN = '''            return (exact, prefix_fit, compact, fam, overlap, market_rank, lang_rank,
                    -abs(len(tokens)-len(wanted_tokens)), -int(ch.get("server_priority") or 0))'''
NEW_RETURN = '''            # R768_CONTEXT_REGION_PRIORITY: explicit matching market tags
            # get nominated before equally plausible foreign region variants.
            # Metadata alone never marks a candidate SAFE.
            requested=list(context.get("market_preferences") or ())
            first=str(requested[0] or "").upper() if requested else ""
            market_source=str(ch.get("market_source") or "").lower()
            regional_priority=1
            if (first and str(context.get("confidence") or "").upper()=="HIGH"
                    and not context.get("global_fallback")
                    and market and market_source=="name"):
                regional_priority=2 if market==first else 0
            return (regional_priority, exact, prefix_fit, compact, fam, overlap,
                    market_rank, lang_rank, -abs(len(tokens)-len(wanted_tokens)),
                    -int(ch.get("server_priority") or 0))'''
WRAPPER = '''
# R768_CONTEXT_REGION_PRIORITY: keep original identity and safety gates intact.
_r768_original_match_score_details = match_score_details

def match_score_details(sat_name, channel, priorities=None, context=None,
                        quality_mode="best", preview=False):
    score, details = _r768_original_match_score_details(
        sat_name, channel, priorities, context, quality_mode, preview)
    ctx = context or {}
    if not isinstance(details, dict) or score <= -100 or details.get("reject_reason"):
        return score, details
    if str(ctx.get("confidence") or "").upper() != "HIGH" or ctx.get("global_fallback"):
        return score, details
    markets = list(ctx.get("market_preferences") or ())
    preferred = str(markets[0] or "").upper() if markets else ""
    if not preferred:
        return score, details
    ch = channel if isinstance(channel, dict) else {}
    # Only an explicit, recognized regional/country prefix, never a guessed
    # market from playlist group, is downgraded. VIP:/ONE: are NOT countries.
    candidate_region, _base = _r748_explicit_country(ch.get("name") or "")
    if not candidate_region or candidate_region == preferred:
        return score, details
    if candidate_region in markets:
        # A real secondary SAT region is not necessarily a wrong feed.
        return score, details
    # Original SAT DVB audio evidence overrides a weak location assumption.
    real_audio = set(str(x).upper() for x in (ctx.get("audio_language_set") or ()) if x)
    same_audio = bool(real_audio and MARKET_TO_LANG.get(candidate_region, "") in real_audio)
    reason=str(ctx.get("reason") or "").lower()
    orbital_only=bool(reason.startswith("sat:") and "," not in reason)
    # Lower the visible similarity score but keep the source as REVIEW, not REJECT:
    # a playlist prefix may be mislabeled and human verification remains possible.
    penalty = 6.0 if same_audio else (22.0 if orbital_only else 32.0)
    revised=dict(details)
    revised["regional_priority"]="SECONDARY"
    revised["regional_evidence"]="SATELLITE_HINT" if orbital_only else "CHANNEL_OR_PROVIDER"
    revised["region_score_adjustment"]=-penalty
    revised["penalty"]=float(revised.get("penalty") or 0.0)-penalty
    revised["review_reason"]=revised.get("review_reason") or (
        "IPTV regional prefix %s differs from SAT preference %s; "
        "verify video and actual audio before manual lock"
        % (candidate_region, preferred))
    return max(-999.0, float(score)-penalty), revised

'''
def patch_core(src):
    if TAG in src:
        return src
    if src.count(OLD_RETURN)!=1:
        raise AssertionError("R768 nomination source drift count=%d" % src.count(OLD_RETURN))
    src=src.replace(OLD_RETURN,NEW_RETURN,1)
    needle="\ndef match_score_details("
    if src.count(needle)!=1:
        raise AssertionError("R768 expected one original scorer")
    start=src.index(needle)+1
    end=src.find("\ndef ",start+1)
    if end<0:
        raise AssertionError("R768 next global function not found")
    src=src[:end]+"\n"+WRAPPER+src[end:]
    compile(src,"core.py","exec")
    assert TAG in src and "_r768_original_match_score_details" in src
    return src

if __name__=="__main__":
    print("R768_SAFE_REGION_PATCH_READY")
