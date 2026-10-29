"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from bkmonitor.documents import ActionInstanceDocument

MAPPING_COMMAND = "init_action_notice_way_mapping"
BACKFILL_COMMAND = "backfill_action_notice_way"
FIELD = "notice_way"
PHYSICAL_INDICES = {"bkfta_action_20261028_0": {}, "bkfta_action_20261029_0": {}}


class FakeIndices:
    def __init__(
        self,
        indices: dict,
        mappings: dict | None = None,
        fail_on: set | None = None,
        fail_mapping_on: set | None = None,
    ):
        self._indices = indices
        self._mappings = mappings or {}
        self._fail_on = fail_on or set()
        self._fail_mapping_on = fail_mapping_on or set()
        self.put_calls = []
        self.refresh_calls = []

    def get(self, index=None, **kwargs):
        return dict(self._indices)

    def refresh(self, index=None, **kwargs):
        self.refresh_calls.append(index)
        return {"_shards": {"total": 1, "successful": 1, "failed": 0}}

    def get_mapping(self, index=None, **kwargs):
        if index in self._fail_mapping_on:
            raise RuntimeError("get_mapping error")
        return {index: self._mappings.get(index, {"mappings": {}})}

    def put_mapping(self, index=None, body=None, **kwargs):
        if index in self._fail_on:
            raise RuntimeError("mapping error")
        self.put_calls.append((index, body))
        return {"acknowledged": True}


class FakeTasks:
    def __init__(self, statuses: list[dict]):
        self._statuses = statuses
        self.calls = 0

    def get(self, task_id=None, **kwargs):
        self.calls += 1
        if len(self._statuses) > 1:
            return self._statuses.pop(0)
        return self._statuses[0]


class FakeES:
    def __init__(self, indices, mappings=None, counts=None, task_statuses=None, fail_on=None, fail_mapping_on=None):
        self.indices = FakeIndices(indices, mappings, fail_on, fail_mapping_on)
        self.tasks = FakeTasks(task_statuses or [{"completed": True, "response": {}}])
        self._counts = list(counts or [0])
        self.update_calls = []

    def count(self, index=None, body=None, **kwargs):
        if len(self._counts) > 1:
            return {"count": self._counts.pop(0)}
        return {"count": self._counts[0]}

    def update_by_query(self, index=None, body=None, params=None, **kwargs):
        self.update_calls.append({"index": index, "body": body, "params": params})
        return {"task": "node:1"}


def _patch_es(monkeypatch, fake_es):
    monkeypatch.setattr(ActionInstanceDocument._index, "_get_connection", lambda using=None: fake_es)
    return fake_es


def _run(command: str, *args) -> str:
    out = StringIO()
    call_command(command, *args, stdout=out, stderr=StringIO())
    return out.getvalue()


# ---------------------------------------------------------------------------
# init_action_notice_way_mapping
# ---------------------------------------------------------------------------


def test_mapping_aborts_when_no_index(monkeypatch):
    _patch_es(monkeypatch, FakeES({}))

    with pytest.raises(CommandError):
        _run(MAPPING_COMMAND, "--apply")


def test_mapping_dry_run_does_not_write(monkeypatch):
    es = _patch_es(monkeypatch, FakeES(PHYSICAL_INDICES))

    output = _run(MAPPING_COMMAND)

    assert es.indices.put_calls == []
    assert "dry-run" in output


def test_mapping_applies_only_missing_field(monkeypatch):
    mappings = {name: {"mappings": {"properties": {FIELD: {"type": "keyword"}}}} for name in PHYSICAL_INDICES}
    del mappings["bkfta_action_20261029_0"]
    es = _patch_es(monkeypatch, FakeES(PHYSICAL_INDICES, mappings=mappings))

    _run(MAPPING_COMMAND, "--apply")

    assert es.indices.put_calls == [
        ("bkfta_action_20261029_0", {"properties": {FIELD: {"type": "keyword"}}}),
    ]


def test_mapping_is_idempotent(monkeypatch):
    mappings = {name: {"mappings": {"properties": {FIELD: {"type": "keyword"}}}} for name in PHYSICAL_INDICES}
    es = _patch_es(monkeypatch, FakeES(PHYSICAL_INDICES, mappings=mappings))

    _run(MAPPING_COMMAND, "--apply")

    assert es.indices.put_calls == []


def test_mapping_reports_failure_and_exits_non_zero(monkeypatch):
    _patch_es(monkeypatch, FakeES(PHYSICAL_INDICES, fail_on={"bkfta_action_20261028_0"}))

    with pytest.raises(CommandError):
        _run(MAPPING_COMMAND, "--apply")


def test_mapping_tolerates_single_index_read_failure(monkeypatch):
    es = _patch_es(
        monkeypatch,
        FakeES(PHYSICAL_INDICES, fail_mapping_on={"bkfta_action_20261028_0"}),
    )

    with pytest.raises(CommandError):
        _run(MAPPING_COMMAND, "--apply")

    # 读取失败的索引不阻断其余索引补齐
    assert es.indices.put_calls == [
        ("bkfta_action_20261029_0", {"properties": {FIELD: {"type": "keyword"}}}),
    ]


# ---------------------------------------------------------------------------
# backfill_action_notice_way
# ---------------------------------------------------------------------------


def test_backfill_aborts_when_no_index(monkeypatch):
    _patch_es(monkeypatch, FakeES({}))

    with pytest.raises(CommandError):
        _run(BACKFILL_COMMAND, "--dry-run")


def test_backfill_dry_run_only_counts_and_refreshes(monkeypatch):
    es = _patch_es(monkeypatch, FakeES(PHYSICAL_INDICES, counts=[12]))

    output = _run(BACKFILL_COMMAND, "--dry-run")

    assert es.update_calls == []
    # 统计前先刷新，避免读到旧搜索视图
    assert es.indices.refresh_calls == ["bkfta_action_20261028_0,bkfta_action_20261029_0"]
    assert "12" in output


def test_backfill_script_targets_notice_way(monkeypatch):
    es = _patch_es(monkeypatch, FakeES(PHYSICAL_INDICES, counts=[1]))

    _run(BACKFILL_COMMAND)

    source = es.update_calls[0]["body"]["script"]["source"]
    assert "ctx._source.inputs?.notice_way" in source
    assert "ctx._source.notice_way" in source
    assert "__none__" in source


def test_backfill_submits_async_task_with_expected_params(monkeypatch):
    es = _patch_es(monkeypatch, FakeES(PHYSICAL_INDICES, counts=[3]))

    output = _run(BACKFILL_COMMAND)

    assert len(es.update_calls) == 1
    call = es.update_calls[0]
    assert call["index"] == "bkfta_action_20261028_0,bkfta_action_20261029_0"
    assert call["params"]["conflicts"] == "proceed"
    assert call["params"]["wait_for_completion"] == "false"
    assert call["body"]["query"]["bool"]["must_not"] == [
        {"term": {"is_parent_action": True}},
        {"exists": {"field": FIELD}},
    ]
    assert "__none__" in call["body"]["script"]["source"]
    assert "node:1" in output


def test_backfill_wait_and_verify(monkeypatch):
    es = _patch_es(
        monkeypatch,
        FakeES(
            PHYSICAL_INDICES,
            counts=[3, 0],
            task_statuses=[{"completed": True, "response": {"updated": 3, "version_conflicts": 0, "failures": []}}],
        ),
    )

    output = _run(BACKFILL_COMMAND, "--wait")

    assert len(es.update_calls) == 1
    assert es.tasks.calls == 1
    # 统计前与复验前各刷新一次，否则 count 读到旧值会误判
    assert es.indices.refresh_calls == [
        "bkfta_action_20261028_0,bkfta_action_20261029_0",
        "bkfta_action_20261028_0,bkfta_action_20261029_0",
    ]
    assert "剩余未回填 0 条" in output


def test_backfill_wait_raises_when_documents_remain(monkeypatch):
    _patch_es(
        monkeypatch,
        FakeES(
            PHYSICAL_INDICES,
            counts=[3, 1],
            task_statuses=[{"completed": True, "response": {"updated": 2, "version_conflicts": 1, "failures": []}}],
        ),
    )

    with pytest.raises(CommandError):
        _run(BACKFILL_COMMAND, "--wait")


def test_backfill_wait_raises_on_task_failures(monkeypatch):
    _patch_es(
        monkeypatch,
        FakeES(
            PHYSICAL_INDICES,
            counts=[3],
            task_statuses=[{"completed": True, "response": {"updated": 0, "failures": [{"cause": "boom"}]}}],
        ),
    )

    with pytest.raises(CommandError):
        _run(BACKFILL_COMMAND, "--wait")


def test_backfill_filters_indices_by_date(monkeypatch):
    indices = {"bkfta_action_20260901_0": {}, "bkfta_action_20261028_0": {}}
    es = _patch_es(monkeypatch, FakeES(indices, counts=[1]))

    _run(BACKFILL_COMMAND, "--start", "2026-10-01")

    assert es.update_calls[0]["index"] == "bkfta_action_20261028_0"


def test_backfill_skips_aliases(monkeypatch):
    indices = {
        "bkfta_action_20261028_0": {},
        "bkfta_action_20261028_read": {},
        "write_20261028_bkfta_action": {},
    }
    es = _patch_es(monkeypatch, FakeES(indices, counts=[1]))

    _run(BACKFILL_COMMAND)

    assert es.update_calls[0]["index"] == "bkfta_action_20261028_0"
