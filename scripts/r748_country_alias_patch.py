# -*- coding: utf-8 -*-
"""R74.8 — country name / two-letter IPTV prefix equivalence for all sources.

A SAT service like 'TLC HD Austria' should nominate/score 'AT: TLC HD'
regardless of PRIMARY/BACKUP1/BACKUP2. Do not confuse ISO-country tokens
with the actual DVB audio language and never erase service numbers/variants.
"""
def one(src,old,new):
    n=src.count(old)
    if n!=1:raise AssertionError("R74.8 source drift %d anchor=%r"%(n,old[:130]))
    return src.replace(old,new,1)

HELPER = '''
# R74.8 explicit *country* names for SAT ↔ IPTV label identity.
# AR in this MENA-oriented catalogue means Arabic/MENA, NOT ISO Argentina;
# AL=Albania, AF=Afghanistan. AU=Australia and AT=Austria are distinct.
_R748_COUNTRY_LABELS = {
    "AT": ("austria","osterreich","oesterreich","autriche","austrias"),
    "DE": ("germany","deutschland","allemagne"),
    "FR": ("france","francia"),
    "ES": ("spain","espana","espagne","españa"),
    "UK": ("united kingdom","great britain","britain","royaume uni"),
    "US": ("united states","united states of america","etats unis","america"),
    "IT": ("italy","italia","italie"),
    "PT": ("portugal",),
    "NL": ("netherlands","nederland","holland","pays bas"),
    "BE": ("belgium","belgique","belgie"),
    "CH": ("switzerland","suisse","schweiz","svizzera"),
    "LU": ("luxembourg",),
    "PL": ("poland","polska","pologne"),
    "CZ": ("czech republic","czechia","tchequie"),
    "SK": ("slovakia","slovensko","slovaquie"),
    "HU": ("hungary","magyarorszag","hongrie"),
    "RO": ("romania","roumanie"),
    "BG": ("bulgaria","bulgarie"),
    "GR": ("greece","grece","hellas"),
    "CY": ("cyprus","chypre"),
    "TR": ("turkey","turkiye","turquie"),
    "AL": ("albania","shqiperia","albanie"),
    "AF": ("afghanistan",),
    "HR": ("croatia","croatie","hrvatska"),
    "RS": ("serbia","serbie","srbija"),
    "BA": ("bosnia","bosnia herzegovina","bosnie"),
    "SI": ("slovenia","slovenie","slovenija"),
    "ME": ("montenegro",),
    "MK": ("north macedonia","macedonia","macedoine"),
    "XK": ("kosovo",),
    "NO": ("norway","norge","norvege"),
    "SE": ("sweden","sverige","suede"),
    "DK": ("denmark","danmark","danemark"),
    "FI": ("finland","suomi","finlande"),
    "IS": ("iceland","islande","island"),
    "IE": ("ireland","eire","irlande"),
    "EE": ("estonia","estonie","eesti"),
    "LV": ("latvia","lettonie"),
    "LT": ("lithuania","lituanie","lietuva"),
    "UA": ("ukraine",),
    "RU": ("russia","russie","rossiya"),
    "BY": ("belarus","bielorussie"),
    "AU": ("australia","australie"),
    "NZ": ("new zealand","nouvelle zelande"),
    "CA": ("canada",),
    "BR": ("brazil","brasil","bresil"),
    "MX": ("mexico","mexique"),
    "MA": ("morocco","maroc","maghreb"),
    "DZ": ("algeria","algerie","algerien"),
    "TN": ("tunisia","tunisie"),
    "EG": ("egypt","egypte"),
    "LY": ("libya","libye"),
    "SA": ("saudi arabia","saudi","arabie saoudite"),
    "AE": ("united arab emirates","uae","emirates","emirats"),
    "QA": ("qatar",),
    "BH": ("bahrain","bahrein"),
    "KW": ("kuwait","koweit"),
    "OM": ("oman",),
    "IQ": ("iraq",),
    "JO": ("jordan","jordanie"),
    "LB": ("lebanon","liban"),
    "SY": ("syria","syrie"),
    "YE": ("yemen",),
    "PS": ("palestine",),
    "SD": ("sudan","soudan"),
    "MR": ("mauritania","mauritanie"),
    "ZA": ("south africa","afrique du sud"),
    "IN": ("india","inde"),
    "PK": ("pakistan",),
    "BD": ("bangladesh",),
    "LK": ("sri lanka",),
    "IR": ("iran",),
    "ID": ("indonesia","indonesie"),
    "MY": ("malaysia","malaisie"),
    "SG": ("singapore","singapour"),
    "TH": ("thailand","thailande"),
    "VN": ("vietnam","viet nam"),
    "PH": ("philippines",),
    "CN": ("china","chine"),
    "JP": ("japan","japon"),
    "KR": ("south korea","korea","coree du sud"),
    "IL": ("israel",),
    "AR": ("arabic","arab","mena"),  # Arabic regional feed, not Argentina
}

# Keep audio language detection completely separate. Nationality is metadata,
# not permission to override the original SAT decoder's language preference.
for _r748_code,_r748_labels in _R748_COUNTRY_LABELS.items():
    if _r748_code not in MARKET_ALIASES:
        MARKET_ALIASES[_r748_code]=tuple(_r748_labels)
    elif _r748_code=="AR":
        pass
    else:
        MARKET_ALIASES[_r748_code]=tuple(dict.fromkeys(
            tuple(MARKET_ALIASES[_r748_code])+tuple(_r748_labels)))

def _r748_explicit_country(name):
    """Return (code, stripped-title) only for COUNTRY WORD at END or TAG at START.

    Do not rewrite 'France 2', 'AT THE RACES', or 'BBC Arabic' public brands.
    Country codes require an UPPERCASE prefix; full words use an end suffix,
    parentheses, or a colon-delimited prefix, not arbitrary substring matches.
    """
    raw=clean_display_name(name or "").strip()
    if not raw:return "",raw
    raw_ascii=_strip_accents(raw)
    # Full word suffix, longest phrase first. Never interpret country word
    # when it is the first lexical token of a national channel brand.
    for code,aliases in _R748_COUNTRY_LABELS.items():
        for alias in sorted(aliases,key=len,reverse=True):
            norm_alias=_strip_accents(alias)
            pat=r"(?i)^(.*?)\s*(?:\(\s*%s\s*\)|\[\s*%s\s*\]|\s+%s)\s*$"%(re.escape(norm_alias),re.escape(norm_alias),re.escape(norm_alias))
            m=re.match(pat,raw_ascii)
            if m and m.group(1).strip():
                base=raw[:len(m.group(1))].strip(" :-_|/[]()")
                if base and any(c.isalpha() for c in base):
                    return code,base
    # Prefix code from IPTV labels: AT: TLC HD, DE TLC HD or (AT) TLC HD.
    p=re.match(r"^\s*(?:\[([A-Z]{2})\]|\(([A-Z]{2})\)|([A-Z]{2})(?=[:|\s_-]))[\s:|_-]*(\S.*)$",raw)
    if p:
        code=p.group(1) or p.group(2) or p.group(3)
        rest=p.group(4).strip()
        if code in _R748_COUNTRY_LABELS and rest and len(rest)>2:
            # AR as a feed region is not a substitute for a measured audio language.
            return code,rest
    # Full country at start only when explicit delimiter follows the country.
    for code,aliases in _R748_COUNTRY_LABELS.items():
        for alias in sorted(aliases,key=len,reverse=True):
            m=re.match(r"(?i)^\s*%s\s*[:|]\s*(\S.*)$"%re.escape(_strip_accents(alias)),raw_ascii)
            if m:
                return code,raw[len(raw)-len(m.group(1)):]
    return "",raw

def _r748_country_relation(sat_name,iptv_name):
    """MATCH/CONFLICT/UNKNOWN plus country code; compare FULL base identity."""
    sat_code,sat_base=_r748_explicit_country(sat_name)
    ip_code,ip_base=_r748_explicit_country(iptv_name)
    if not sat_code or not ip_code:
        return "UNKNOWN",sat_code,ip_code
    left=normalize_preview_name(sat_base)
    right=normalize_preview_name(ip_base)
    # Never match different brands, numbered services or 'Junior' variants
    # solely from the country abbreviation.
    if not left or not right or left!=right:
        return "UNKNOWN",sat_code,ip_code
    return ("MATCH" if sat_code==ip_code else "CONFLICT"),sat_code,ip_code

'''

def patch_core(src):
    src=one(src,'\nMARKET_TO_LANG = {', '\n'+HELPER+'MARKET_TO_LANG = {')
    # Nominator: country-matched exact service from each server takes priority,
    # cannot be displaced from the budget by wrong regional feeds.
    src=one(src,'''            overlap = len(wanted_tokens.intersection(tokens))
            exact = int(bool(norm and norm == target))''',
'''            country_relation,_sat_code,_ip_code=_r748_country_relation(sat_name,name)
            if country_relation=="CONFLICT":
                return None
            overlap = len(wanted_tokens.intersection(tokens))
            exact = int(bool((norm and norm == target) or country_relation=="MATCH"))''')
    src=one(src,'''    if not sat_norm or not ip_norm:
        return -999.0, details

    # r43 Preview-only provider identity:''',
'''    if not sat_norm or not ip_norm:
        return -999.0, details
    country_relation,sat_country,iptv_country=_r748_country_relation(
        sat_name,ch.get("name",""))
    if country_relation=="CONFLICT":
        details["reject_reason"]="Explicit SAT country %s conflicts with IPTV prefix %s"%(sat_country,iptv_country)
        details["name"]=-500.0
        return -500.0,details
    country_identity=(country_relation=="MATCH")
    if country_identity:
        details["country_alias_match"]=sat_country

    # r43 Preview-only provider identity:''')
    src=one(src,'''    if sat_norm == ip_norm or preview_provider_exact or (preview and _preview_compact_key(sat_name) and _preview_compact_key(sat_name) == _preview_compact_key(ch.get("name", ""))):
        base = 100.0''',
'''    if country_identity or sat_norm == ip_norm or preview_provider_exact or (preview and _preview_compact_key(sat_name) and _preview_compact_key(sat_name) == _preview_compact_key(ch.get("name", ""))):
        base = 100.0''')
    # Long-country alias equivalence must also satisfy subsequent identity
    # checks, not just the first name-score calculation.
    src=one(src,'''        elif sat_norm == ip_norm or _preview_compact_key(sat_name) == _preview_compact_key(ch.get("name", "")):
            identity_ok, identity_reason = True, "preview exact identity"''',
'''        elif country_identity or sat_norm == ip_norm or _preview_compact_key(sat_name) == _preview_compact_key(ch.get("name", "")):
            identity_ok, identity_reason = True, "country alias identity" if country_identity else "preview exact identity"''')
    src=one(src,'''    else:
        identity_ok, identity_reason = _identity_is_safe(sat_name, ch.get("name", ""), base, equivalence)
    if not identity_ok:''',
'''    else:
        identity_ok, identity_reason = _identity_is_safe(sat_name, ch.get("name", ""), base, equivalence)
        if country_identity:
            identity_ok, identity_reason = True, "country alias identity"
    if not identity_ok:''')
    src=one(src,'''    if not equivalence and sat_norm != ip_norm and base < 72.0:''',
'''    if not equivalence and not country_identity and sat_norm != ip_norm and base < 72.0:''')
    compile(src,"core.py","exec")
    return src
