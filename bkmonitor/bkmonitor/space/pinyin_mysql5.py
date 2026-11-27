"""A byte-oriented phonetic prefilter for MySQL 5's regular expression engine."""

from collections import defaultdict
from functools import lru_cache
from itertools import groupby

from bkmonitor.space.pinyin import pinyin_search_codepoints


def _byte_class(values):
    # Only ASCII letters, '?' and GB2312 bytes above 0xA0 enter this class.
    ranges = []
    for _, run in groupby(enumerate(sorted(values)), lambda pair: pair[1] - pair[0]):
        points = bytes(value for _, value in run)
        ranges.append(points[:1] + b"-" + points[-1:] if len(points) > 3 else points)
    return b"[" + b"".join(ranges) + b"]"


@lru_cache(maxsize=26)
def _letter_pattern(codepoints):
    # GB2312's 3,755 first-level Chinese characters are in phonetic order.
    # Grouping their byte ranges keeps the expression small. Second-level
    # characters and lossy conversions pass through for application matching.
    single_bytes = {ord("?")}
    trails_by_lead = defaultdict(set)
    for codepoint in codepoints:
        encoded = chr(codepoint).encode("gb2312", errors="replace")
        if len(encoded) == 1:
            single_bytes.add(encoded[0])
        elif encoded[0] < 0xD8:
            trails_by_lead[encoded[0]].add(encoded[1])

    leads_by_trail_class = defaultdict(set)
    for lead, trails in trails_by_lead.items():
        leads_by_trail_class[_byte_class(trails)].add(lead)

    alternatives = [_byte_class(single_bytes), b"[\xd8-\xf7]"]
    alternatives.extend(_byte_class(leads) + trails for trails, leads in leads_by_trail_class.items())
    # Match at a character boundary. GB2312 uses one byte for ASCII and two
    # for all other characters. UNHEX keeps regex bytes independent of the
    # MySQL connection charset and of SQL string literal escaping.
    pattern = b"^([^\xa1-\xf7]|[\xa1-\xf7].)*(" + b"|".join(alternatives) + b")"
    return pattern.hex()


def pinyin_hex_search_patterns(query):
    """Predicates for BINARY CONVERT(space_name USING gb2312) REGEXP UNHEX(%s)."""
    return [_letter_pattern(points) for points in pinyin_search_codepoints(query)]
