# -*- coding: utf-8 -*-
"""R74.10: mislabeled IPTV *country/region prefix* is low-trust metadata.

A real SAT service like TLC HD Austria must be able to show DE: TLC HD as an
unverified candidate when the provider's DE tag is wrong; still PREFER AT:
TLC HD. Do not AUTO LOCK/PLAY candidates with contradictory unverified tags.
Only user MANUAL_LOCK / verified evidence can resolve this ambiguity.

Never equate different service identities, service numbers or critical variants.
No change to actual SAT audio identity or playback/video decoder.
"""

def one(src, old, new):
    count=src.count(old)
    if count!=1:
        raise AssertionError("R74.10 source drift count=%d anchor=%r"%(count,old[:160]))
    return src.replace(old,new,1)

def patch_core(src):
    # Before expensive scoring, keep possible mislabeled feeds in candidate
    # pool. Correct local-feed candidates must sort ABOVE wrong-prefixed ones.
    src=one(src,
'''            country_relation,_sat_code,_ip_code=_r748_country_relation(sat_name,name)
            if country_relation=="CONFLICT":
                return None
            reordered=_r749_reordered_identity(sat_name,name)
            overlap = len(wanted_tokens.intersection(tokens))
            exact = int(bool((norm and norm == target) or
                             country_relation=="MATCH" or reordered))''',
'''            country_relation,_sat_code,_ip_code=_r748_country_relation(sat_name,name)
            reordered=_r749_reordered_identity(sat_name,name)
            overlap = len(wanted_tokens.intersection(tokens))
            # Relation CONFLICT means SAME base channel but a possibly
            # mislabelled country tag, not an independently checked mismatch.
            exact = int(bool((norm and norm == target) or
                             country_relation in ("MATCH","CONFLICT") or reordered))''')
    src=one(src,
'''            return (exact, compact, fam, overlap, market_rank, lang_rank,
                    -abs(len(tokens)-len(wanted_tokens)), -int(ch.get("server_priority") or 0))''',
'''            # Correct country prefix first, then no-country metadata, then
            # contradictory/unverified prefix. Never discard contradictory
            # labels before Preview can verify actual video/audio.
            prefix_fit=(2 if country_relation=="MATCH" else
                        0 if country_relation=="CONFLICT" else 1)
            return (exact, prefix_fit, compact, fam, overlap, market_rank, lang_rank,
                    -abs(len(tokens)-len(wanted_tokens)), -int(ch.get("server_priority") or 0))''')
    # The scorer formerly rejected an otherwise exact base channel before any
    # further video/audio identity work; now use REVIEW-only trust hint.
    src=one(src,
'''    if country_relation=="CONFLICT":
        details["reject_reason"]="Explicit SAT country %s conflicts with IPTV prefix %s"%(sat_country,iptv_country)
        details["name"]=-500.0
        return -500.0,details
    country_identity=(country_relation=="MATCH")
    reordered_identity=_r749_reordered_identity(sat_name,ch.get("name",""))
    if country_identity:
        details["country_alias_match"]=sat_country''',
'''    country_prefix_warning=(country_relation=="CONFLICT")
    country_identity=(country_relation in ("MATCH","CONFLICT"))
    reordered_identity=_r749_reordered_identity(sat_name,ch.get("name",""))
    if country_relation=="MATCH":
        details["country_alias_match"]=sat_country
    if country_prefix_warning:
        details["country_prefix_warning"]="%s IPTV label, SAT %s; country tag unverified"%(
            iptv_country,sat_country)
        details["review_reason"]=(
            "IPTV country prefix %s differs from SAT %s; verify actual video and audio"%
            (iptv_country,sat_country))
        details["prefix_evidence"]="UNVERIFIED_LABEL"''')
    # Name identity remains exact because _r748_country_relation only marks
    # conflicts for IDENTICAL channel bases; variant/number gates still apply.
    # Do not hard reject because 'DE' is a *name prefix* interpreted as German.
    # SAT audio must be checked against actual decoded IPTV audio, not provider
    # naming, when the prefix is proven unreliable.
    src=one(src,
'''    explicit_feed_lang = explicit_language_tag(ch.get("name", ""))
    sat_audio_set = [str(x).upper() for x in ((context or {}).get("audio_language_set") or []) if x]''',
'''    explicit_feed_lang = explicit_language_tag(ch.get("name", ""))
    if country_prefix_warning:
        # Name prefix DE/FR/AT/etc is already contradicted by a matching SAT
        # channel identity; it cannot prove the stream's REAL audio language.
        # Preserve manual REVIEW rather than inventing decoded audio evidence.
        explicit_feed_lang=""
    sat_audio_set = [str(x).upper() for x in ((context or {}).get("audio_language_set") or []) if x]''')
    # Other country inference code can still hard-reject title 'DE' for high
    # SAT confidence. Only downgrade those two COUNTRY-specific rejections;
    # never alter service number/variant/provider hard rejections.
    src=one(src,
'''                    else:
                        details["context"] = -58.0
                        details["reject_reason"] = "IPTV feed market %s is secondary to strong SAT market %s" % (cand_market, desired_markets[0])''',
'''                    else:
                        details["context"] = -18.0 if country_prefix_warning else -58.0
                        if country_prefix_warning:
                            details["review_reason"] = details.get("review_reason") or "Country prefix requires verification"
                        else:
                            details["reject_reason"] = "IPTV feed market %s is secondary to strong SAT market %s" % (cand_market, desired_markets[0])''')
    src=one(src,
'''                    else:
                        details["context"] = -64.0
                        details["market"] = -12.0
                        details["reject_reason"] = "IPTV feed market %s conflicts with strong SAT market %s" % (cand_market, desired_markets[0])''',
'''                    else:
                        details["context"] = -18.0 if country_prefix_warning else -64.0
                        details["market"] = -12.0
                        if country_prefix_warning:
                            details["review_reason"] = details.get("review_reason") or "Untrusted IPTV country code; verify real audio/video"
                        else:
                            details["reject_reason"] = "IPTV feed market %s conflicts with strong SAT market %s" % (cand_market, desired_markets[0])''')
    # Recalculation after update: don't reuse older hard-rejected cached entries.
    src=one(src,
'''key = self._fast_cache_key("mega-r749", sat_name, language_priorities,''',
'''key = self._fast_cache_key("mega-r7410", sat_name, language_priorities,''')
    compile(src,"core.py","exec")
    return src
