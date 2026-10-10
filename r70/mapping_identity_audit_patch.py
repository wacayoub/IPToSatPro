"""OFFLINE audit patch for the SHA-pinned r69 core.py. NEVER installed.

Reconcile real Hot Bird TREK French / Tipik Belgian broadcaster identity.
The patch uses exact source anchors and refuses unexpected source revisions.
Frozen persisted Catalog *objects* still need a separate off-GUI index migration.
"""


def improve(source):
    def once(old, new):
        nonlocal source
        found = source.count(old)
        if found != 1:
            raise AssertionError("Audit identity patch anchor mismatch: %d %s" % (found, old[:90]))
        source = source.replace(old, new, 1)

    once(
        '''    "AR": ("ar", "arab", "arabic", "arabe", "arabes", "mena", "middle east", "moyen orient", "nilesat", "badr"),''',
        '''    "AR": ("ar", "arab", "arabic", "arabe", "arabes", "mena", "middle east", "moyen orient", "nilesat", "badr"),
    # Belgian market, not a general English 'be' word or a generic language.
    "BE": ("belgium", "belgique", "belgie", "belgian", "belge"),'''
    )
    once(
        '''def market_from_text(text):
    if not text:
        return ""
    raw = _strip_accents(text).lower()
    code = _tag_code(raw, MARKET_ALIASES.keys())
    if code:
        return code''',
        r'''def market_from_text(text):
    if not text:
        return ""
    raw_label = clean_display_name(text)
    # BE: channel or BE Tipik are explicit broadcaster tags; do not
    # misclassify BE MOVIES / BE HAPPY TV simply because 'be' is a word.
    if re.match(r"(?i)^\s*be(?:\s*[:|]\s*|\s+(?:tipik|rtbf\s+tipik)\b)", raw_label):
        return "BE"
    raw = _strip_accents(text).lower()
    code = _tag_code(raw, MARKET_ALIASES.keys())
    if code == "BE":
        code = ""
    if code:
        return code'''
    )
    once(
        '''    name = clean_display_name(name)
    # UHD1 is a real Astra demonstration-channel brand''',
        r'''    name = clean_display_name(name)
    # Remove the country label only for public identities proven by this
    # audit. Do not remove arbitrary BE text or a BE-VIP platform label.
    # "TIPIK VISION" remains a distinct variant; "(13)" retains its number.
    name = re.sub(r"(?i)^\s*BE\s*(?::|[|]|\s)\s*(?:RTBF\s+)?(?=TIPIK\b)",
                  " ", name)
    # A Belgian TREK feed may be shown for review but must not automatically
    # replace the French SAT feed after the market safety check.
    name = re.sub(r"(?i)^\s*BE\s*(?::|[|])\s*(?=TREK\b)", " ", name)
    # UHD1 is a real Astra demonstration-channel brand'''
    )
    once(
        '''def _channel_market(sat_name):
    # National channel hints must match the service identity from the beginning.  A raw''',
        '''def _channel_market(sat_name):
    # These public broadcaster brands override an unreliable broad IT/PL
    # Hot Bird 13E market prior. Exact equality prevents STAR TREK matches.
    exact = normalize_name(sat_name or "")
    if exact == "trek":
        return "FR"
    if exact == "tipik":
        return "BE"
    # National channel hints must match the service identity from the beginning.  A raw'''
    )
    once(
        '''def _channel_language_hint(sat_name, provider=""):
    norm = normalize_name(sat_name or "")''',
        '''def _channel_language_hint(sat_name, provider=""):
    norm = normalize_name(sat_name or "")
    if norm == "tipik":
        return "FR"'''
    )
    once(
        '''def _enrich_channel(item):
    item = dict(item or {})''',
        r'''def _legacy_be_identity_stale(row):
    """Detect affected cached v11 name/market entries without a full rescan."""
    if not isinstance(row, dict):
        return False
    name = str(row.get("name") or "")
    if not re.match(r"(?i)^\s*be(?=\s*[:|]\s*|\s+(?:tipik|rtbf\s+tipik)\b)", name):
        return False
    return (row.get("norm") != normalize_name(name) or
            str(row.get("market") or "").upper() != market_from_text(name))


def _enrich_channel(item):
    item = dict(item or {})
    if item.get("_e") == 11 and _legacy_be_identity_stale(item):
        item["_e"] = 0'''
    )
    once(
        '''        if isinstance(channel, dict) and channel.get("_e") == 11 and channel.get("norm") and channel.get("claimed_quality_rank") is not None:''',
        '''        if (isinstance(channel, dict) and channel.get("_e") == 11 and
                channel.get("norm") and channel.get("claimed_quality_rank") is not None and
                not _legacy_be_identity_stale(channel)):'''
    )
    return source
