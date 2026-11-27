"""Conservative MySQL prefilter for the same pypinyin readings used by directory search."""

from collections import defaultdict
from functools import lru_cache
from itertools import groupby
from string import ascii_lowercase

from bkmonitor.space.pinyin_legacy import SELECTOR_READINGS

_SELECTOR_BY_CHAR = {c: reading for reading, characters in SELECTOR_READINGS.items() for c in characters}


@lru_cache(maxsize=8192)
def selector_reading(character):
    from pypinyin import lazy_pinyin

    return _SELECTOR_BY_CHAR.get(character) or lazy_pinyin(character)[0].lower()


@lru_cache(maxsize=1)
def _letter_codes():
    from pypinyin.constants import PHRASES_DICT, PINYIN_DICT
    from pypinyin.contrib.tone_convert import to_normal

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

    for character, reading in _SELECTOR_BY_CHAR.items():
        add(ord(character), (reading,))

    return {letter: tuple(sorted({ord(letter), ord(letter.upper()), *codes})) for letter, codes in by_letter.items()}


def _anchor_letters(query):
    codes = _letter_codes()
    return sorted(set(query).intersection(codes), key=lambda letter: (len(codes[letter]), letter))[:2]


def pinyin_search_codepoints(query):
    """Possible original code points for each required query letter, including both ASCII cases."""
    codes = _letter_codes()
    return [codes[letter] for letter in _anchor_letters(query)]


@lru_cache(maxsize=26)
def _unicode_pattern(letter):
    ranges = [letter, letter.upper()]
    for _, run in groupby(enumerate(c for c in _letter_codes()[letter] if c > 127), lambda pair: pair[1] - pair[0]):
        points = [chr(code) for _, code in run]
        ranges.append(points[0] + "-" + points[-1] if len(points) > 2 else "".join(points))
    return "[" + "".join(ranges) + "]"


def pinyin_search_patterns(query):
    """Every matching phonetic string contains each selected letter somewhere in its source name."""
    return [_unicode_pattern(letter) for letter in _anchor_letters(query)]
