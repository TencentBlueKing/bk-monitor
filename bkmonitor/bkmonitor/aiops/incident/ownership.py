"""Validation at the incident synchronization trust boundary."""

import re


def normalize_host_owners(value):
    if not isinstance(value, list) or not value:
        return []
    owners = []
    for item in value:
        if not isinstance(item, str) or len(item.strip()) > 255 or not re.fullmatch(r"[\w.@+-]+", item.strip()):
            return []
        if item.strip() not in owners:
            owners.append(item.strip())
    return owners
