"""Search the visible space directory without materializing a user's full directory."""

import hashlib
import json
import re
from functools import lru_cache

from django.core import signing
from opentelemetry import trace
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bkm_space.api import SpaceApi
from bkmonitor.space.pinyin import selector_reading
from iam_engine.exceptions import ProviderUnavailable

CURSOR_SALT = "monitor.space-directory.page.v1"


class SpacePageRequestSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=["page"], required=False)
    query = serializers.CharField(max_length=256, allow_blank=True, default="")
    type = serializers.CharField(max_length=64, allow_blank=True, default="")
    page_size = serializers.IntegerField(min_value=1, max_value=100, default=20)
    cursor = serializers.CharField(max_length=4096, allow_blank=True, default="")
    bk_biz_ids = serializers.CharField(max_length=2000, required=False)
    space_uids = serializers.CharField(max_length=20000, required=False)

    def validate(self, attrs):
        if attrs.get("mode") != "page":
            return attrs
        if "bk_biz_ids" in attrs and "space_uids" in attrs:
            raise serializers.ValidationError("Supply either bk_biz_ids or space_uids.")
        for field in ("bk_biz_ids", "space_uids"):
            if field not in attrs:
                continue
            values = [value.strip() for value in attrs[field].split(",")]
            if len(values) > 100 or not all(values):
                raise serializers.ValidationError({field: "Supply up to 100 non-empty values."})
            if field == "bk_biz_ids":
                if not all(re.fullmatch(r"-?[0-9]{1,19}", value) for value in values):
                    raise serializers.ValidationError({field: "Invalid business ID."})
                values = [str(int(value)) for value in values]
            elif not all("__" in value and all(value.split("__", 1)) for value in values):
                raise serializers.ValidationError({field: "Invalid space UID."})
            attrs[field] = frozenset(values)
        return attrs


@lru_cache(maxsize=8192)
def _pinyin_part(part):
    from pypinyin import lazy_pinyin

    syllables = lazy_pinyin(part)
    legacy = [selector_reading(char) for char in part]
    return (
        "".join(syllables).lower(),
        "".join(s[:1] for s in syllables).lower(),
        "".join(legacy),
        "".join(s[:1] for s in legacy),
    )


def _match_rank(pk, kind, sid, name, code, type_name, query, search_pinyin):
    biz_id = sid if kind == "bkcc" else str(-pk)
    keys = [name.lower(), sid.lower(), str(pk), biz_id, f"{kind}__{sid}".lower()]
    if search_pinyin and not name.isascii():
        # Cache Chinese text runs, so numbered or suffixed names share the same conversion.
        pieces = [
            _pinyin_part(part) if not part.isascii() else (part.lower(),) * 4
            for part in re.findall(r"[^\x00-\x7f]+|[\x00-\x7f]+", name)
        ]
        keys.extend("".join(reading) for reading in zip(*pieces))
    if query in keys:
        return 0
    keys.extend((type_name.lower(), (code or "").lower()))
    if kind == "bkci" and code:
        keys.append("容器项目")
    return 1 if any(query in value for value in keys) else None


def _position(cursor, fingerprint):
    if not cursor:
        return [], (0, 0)
    try:
        owner, pending, resume = signing.loads(cursor, salt=CURSOR_SALT)
        if owner == fingerprint:
            return pending, resume
    except (TypeError, ValueError, signing.BadSignature):
        pass
    raise ValidationError({"cursor": "Invalid cursor for this directory query."})


def search_space_page(tenant, username, params, access, *, external=False, namespace="directory"):
    query = params["query"].strip().lower()
    space_type = params["type"]
    known_ids = params.get("bk_biz_ids")
    known_uids = params.get("space_uids")
    page_size = params["page_size"]
    signature = json.dumps(
        [namespace, tenant, username, external, query, space_type, sorted(known_ids or []), sorted(known_uids or [])]
    )
    fingerprint = hashlib.sha256(signature.encode()).hexdigest()
    pending, resume = _position(params.get("cursor"), fingerprint)
    query_ids = access.ids if access.matches_policy is None else None
    if known_ids is not None:
        query_ids = known_ids if query_ids is None else known_ids.intersection(query_ids)
    type_names = SpaceApi.read_space_page_types()
    scanned = 0
    items = []
    search_pinyin = query.isascii() and any("a" <= character <= "z" for character in query)

    def query_matches(position):
        nonlocal scanned
        rank, after = position
        # Retain only a few pages of IDs. A continuation can travel between workers without shared state.
        capacity = min(100, page_size * 4)
        buckets = [[], []]
        for key in SpaceApi.iter_space_search_keys(
            tenant,
            query_ids,
            space_type,
            after if rank == 1 else 0,
            space_uids=known_uids,
            type_names=type_names,
            text_filter=query,
            search_pinyin=search_pinyin,
        ):
            scanned += 1
            pk, kind, sid = key[:3]
            if not access.allows(sid if kind == "bkcc" else -pk):
                continue
            match = _match_rank(*key, query, search_pinyin)
            if match is None or match < rank or (match == rank and pk <= after):
                continue
            if len(buckets[match]) <= capacity:
                buckets[match].append((match, pk))
            if len(buckets[rank]) > capacity:
                break
        ranked = buckets[0] + buckets[1]
        if len(ranked) <= capacity:
            return ranked, None
        first_omitted_rank, first_omitted_pk = ranked[capacity]
        return ranked[:capacity], (first_omitted_rank, first_omitted_pk - 1)

    with trace.get_tracer(__name__).start_as_current_span("space.search_authorized_page") as span:
        while len(items) <= page_size and (pending or resume is not None):
            if not query:
                rank, after = resume
                limit = max(128, page_size + 1) if access.matches_policy else page_size + 1
                rows = SpaceApi.read_space_page_candidates(
                    tenant, query_ids, space_type, after, limit, space_uids=known_uids, type_names=type_names
                )
                scanned += len(rows)
                items.extend((0, row) for row in rows if access.allows(row["bk_biz_id"]))
                resume = (0, rows[-1]["id"]) if len(rows) == limit else None
            else:
                if not pending:
                    pending, resume = query_matches(resume)
                    if not pending:
                        break
                window, pending = pending[: page_size + 1], pending[page_size + 1 :]
                rows = SpaceApi.read_space_page_candidates(
                    tenant,
                    query_ids,
                    space_type,
                    0,
                    len(window),
                    space_uids=known_uids,
                    type_names=type_names,
                    row_ids=[pk for _, pk in window],
                )
                by_id = {row["id"]: row for row in rows}
                for rank, pk in window:
                    row = by_id.get(pk)
                    if (
                        row
                        and access.allows(row["bk_biz_id"])
                        and _match_rank(
                            pk,
                            row["space_type_id"],
                            row["space_id"],
                            row["space_name"],
                            row["space_code"],
                            row["type_name"],
                            query,
                            search_pinyin,
                        )
                        == rank
                    ):
                        items.append((rank, row))
        next_cursor = None
        if len(items) > page_size:
            if query:
                pending = [(rank, row["id"]) for rank, row in items[page_size:]] + pending
            else:
                resume = (0, items[page_size][1]["id"] - 1)
            next_cursor = signing.dumps([fingerprint, pending, resume], salt=CURSOR_SALT, compress=True)
        span.set_attribute("space.page.candidates", scanned)
        span.set_attribute("space.page.items", min(len(items), page_size))
        span.set_attribute("space.page.partial", access.partial)
    if access.partial and not items:
        raise ProviderUnavailable("Could not confirm a complete space directory")
    result = {"items": [row for _, row in items[:page_size]], "next_cursor": next_cursor}
    if access.partial:
        result["partial"] = True
    return result
