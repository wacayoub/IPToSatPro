# -*- coding: utf-8 -*-
"""R74.9: precise word-order identity for 'FilmBox One' ↔ 'ONE: FILMBOX'.

Keep exact channel number, country feed, public-brand variant, original DVB audio
and server roles. Nominate reordered candidates BEFORE bounded Preview scoring;
mark safely identical normalized token multisets as exact only when the full
identity (including number tokens) is equal. Never allow partial fuzzy bags.
"""

def one(src,old,new):
    count=src.count(old)
    if count!=1:
        raise AssertionError("R74.9 source drift %d: %r"%(count,old[:155]))
    return src.replace(old,new,1)

HELPER='''
def _r749_reordered_identity(sat_name, candidate_name):
    """True only for EXACT same normalized word multiset in different order.

    "FilmBox One" -> "filmbox 1" == "1 filmbox" <- "ONE: FILMBOX".
    No substring/fuzzy swap, never bypass different numbers or variants.
    """
    a=normalize_preview_name(sat_name or "")
    b=normalize_preview_name(candidate_name or "")
    if not a or not b or a==b:
        return False
    left=a.split(); right=b.split()
    if len(left)!=len(right) or not (2<=len(left)<=12):
        return False
    if sorted(left)!=sorted(right):
        return False
    if _preview_numbers(sat_name)!=_preview_numbers(candidate_name):
        return False
    # Avoid promoting generic technical-only permutations (HD/RAW/etc.).
    common=set(left)
    return bool(any(len(token)>2 and not token.isdigit()
                    and token not in _GENERIC_IDENTITY_TOKENS
                    for token in common))

'''
def patch_core(src):
    src=one(src,'''def _r748_explicit_country(name):''',HELPER+'''def _r748_explicit_country(name):''')
    src=one(src,'''            country_relation,_sat_code,_ip_code=_r748_country_relation(sat_name,name)
            if country_relation=="CONFLICT":
                return None
            overlap = len(wanted_tokens.intersection(tokens))
            exact = int(bool((norm and norm == target) or country_relation=="MATCH"))''',
'''            country_relation,_sat_code,_ip_code=_r748_country_relation(sat_name,name)
            if country_relation=="CONFLICT":
                return None
            reordered=_r749_reordered_identity(sat_name,name)
            overlap = len(wanted_tokens.intersection(tokens))
            exact = int(bool((norm and norm == target) or
                             country_relation=="MATCH" or reordered))''')
    src=one(src,'''    country_identity=(country_relation=="MATCH")
    if country_identity:
        details["country_alias_match"]=sat_country''',
'''    country_identity=(country_relation=="MATCH")
    reordered_identity=_r749_reordered_identity(sat_name,ch.get("name",""))
    if country_identity:
        details["country_alias_match"]=sat_country
    if reordered_identity:
        details["name_order_alias"]="SAME_WORDS_DIFFERENT_ORDER"''')
    src=one(src,'''    if country_identity or sat_norm == ip_norm or preview_provider_exact or (preview and _preview_compact_key(sat_name) and _preview_compact_key(sat_name) == _preview_compact_key(ch.get("name", ""))):
        base = 100.0''',
'''    if country_identity or reordered_identity or sat_norm == ip_norm or preview_provider_exact or (preview and _preview_compact_key(sat_name) and _preview_compact_key(sat_name) == _preview_compact_key(ch.get("name", ""))):
        base = 100.0''')
    src=one(src,'''        elif country_identity or sat_norm == ip_norm or _preview_compact_key(sat_name) == _preview_compact_key(ch.get("name", "")):
            identity_ok, identity_reason = True, "country alias identity" if country_identity else "preview exact identity"''',
'''        elif country_identity or reordered_identity or sat_norm == ip_norm or _preview_compact_key(sat_name) == _preview_compact_key(ch.get("name", "")):
            identity_ok, identity_reason = True, (
                "country alias identity" if country_identity else
                "exact reordered identity" if reordered_identity else "preview exact identity")''')
    src=one(src,'''        if country_identity:
            identity_ok, identity_reason = True, "country alias identity"
    if not identity_ok:''',
'''        if country_identity:
            identity_ok, identity_reason = True, "country alias identity"
        elif reordered_identity:
            identity_ok, identity_reason = True, "exact reordered identity"
    if not identity_ok:''')
    src=one(src,'''    if not equivalence and not country_identity and sat_norm != ip_norm and base < 72.0:''',
'''    if not equivalence and not country_identity and not reordered_identity and sat_norm != ip_norm and base < 72.0:''')
    # A new scorer policy must not serve a previous in-memory index result.
    src=one(src,'''key = self._fast_cache_key("mega-r732", sat_name, language_priorities,''',
                '''key = self._fast_cache_key("mega-r749", sat_name, language_priorities,''')
    compile(src,"core.py","exec")
    return src
