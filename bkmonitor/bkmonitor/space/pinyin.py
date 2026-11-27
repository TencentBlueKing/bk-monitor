"""Conservative MySQL prefilter for the same pypinyin readings used by directory search."""

from collections import defaultdict
from functools import lru_cache
from itertools import groupby
from string import ascii_lowercase

from pypinyin.constants import PHRASES_DICT, PINYIN_DICT
from pypinyin.contrib.tone_convert import to_normal


@lru_cache(maxsize=1)
def _letter_patterns():
    # Use every reading, including phrase-specific overrides. The final name match resolves polyphones.
    by_letter = defaultdict(set)
    normalized = {}

    def add(codepoint, readings):
        for reading in readings:
            if reading not in normalized:
                normalized[reading] = set(to_normal(reading).lower()).intersection(ascii_lowercase)
            for letter in normalized[reading]:
                by_letter[letter].add(codepoint)

    for codepoint, readings in PINYIN_DICT.items():
        add(codepoint, readings.split(","))
    for phrase, readings in PHRASES_DICT.items():
        for character, variants in zip(phrase, readings):
            add(ord(character), variants)

    patterns = {}
    for letter, codes in by_letter.items():
        # A literal ASCII run can join a phonetic run (e.g. "A蓝鲸"). Keep the original letter too.
        ranges = [letter, letter.upper()]
        for _, run in groupby(enumerate(sorted(c for c in codes if c > 127)), lambda pair: pair[1] - pair[0]):
            points = [chr(code) for _, code in run]
            ranges.append(points[0] + "-" + points[-1] if len(points) > 2 else "".join(points))
        patterns[letter] = (len(codes), "[" + "".join(ranges) + "]")
    return patterns


def pinyin_search_patterns(query):
    """Every matching phonetic string contains each selected letter somewhere in its source name."""
    patterns = _letter_patterns()
    letters = sorted(set(query).intersection(patterns), key=lambda letter: (patterns[letter][0], letter))
    return [patterns[letter][1] for letter in letters[:2]]
