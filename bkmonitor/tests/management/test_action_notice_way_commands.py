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
from elasticsearch.exceptions import NotFoundError

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
        not_found_on: set | None = None,
    ):
        self._indices = indices
        self._mappings = mappings or {}
        self._fail_on = fail_on or set()
        self._fail_mapping_on = fail_mapping_on or set()
        self._not_found_on = not_found_on or set()
        self.put_calls = []
        self.refresh_calls = []

    def get(self, index=None, **kwargs):
        return dict(self._indices)

    def refresh(self, index=None, **kwargs):
        self.refresh_calls.append(index)
        return {"_shards": {"total": 1, "successful": 1, "failed": 0}}

    def get_mapping(self, index=None, **kwargs):
        if index in self._not_found_on:
            raise NotFoundError(404, "index_not_found_exception", {})
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
    def __init__(
        self,
        indices,
        mappings=None,
        counts=None,
        task_statuses=None,
        fail_on=None,
        fail_mapping_on=None,
        count_failed=None,
        not_found_on=None,
    ):
        self.indices = FakeIndices(indices, mappings, fail_on, fail_mapping_on, not_found_on)
        self.tasks = FakeTasks(task_statuses or [{"completed": True, "response": {}}])
        self._counts = list(counts or [0])
        self._count_failed = list(count_failed or [0])
        self.update_calls = []

    def count(self, index=None, body=None, **kwargs):
        count = self._counts.pop(0) if len(self._counts) > 1 else self._counts[0]
        failed = self._count_failed.pop(0) if len(self._count_failed) > 1 else self._count_failed[0]
        return {
            "count": count,
            "_shards": {"total": 1, "successful": 1, "skipped": 0, "failed": failed},
        }

    def update_by_query(self, index=None, body=None, params=None, **kwargs):
        self.update_calls.append({"index": index, "body": body, "params": params})
        return {"task": "node:1"}


def _make_es(indices=None, **kwargs):
    """构造已带 notice_way mapping 的假客户端（回填命令会先校验字段是否存在）"""
    indices = indices or PHYSICAL_INDICES
    mappings = {name: {"mappings": {"properties": {FIELD: {"type": "keyword"}}}} for name in indices}
    return FakeES(indices, mappings=mappings, **kwargs)


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


def test_mapping_dry_run_still_reports_not_found(monkeypatch):
    """预览也不能把"索引不存在"吞掉，否则 dry-run exit 0 会让脚本误判"""
    indices = {"bkfta_action_20261028_0": {}, "bkfta_action_20991231_0": {}}
    mappings = {"bkfta_action_20261028_0": {"mappings": {"properties": {}}}}
    es = _patch_es(
        monkeypatch,
        FakeES(indices, mappings=mappings, not_found_on={"bkfta_action_20991231_0"}),
    )

    with pytest.raises(CommandError, match="索引不存在"):
        _run(MAPPING_COMMAND)

    assert es.indices.put_calls == []


def test_mapping_dry_run_exits_non_zero_when_mapping_unreadable(monkeypatch):
    """预览里出现读不到的索引时也要非 0 退出，但不应写入"""
    indices = {"bkfta_action_20261028_0": {}, "bkfta_action_20261029_0": {}}
    mappings = {"bkfta_action_20261029_0": {"mappings": {"properties": {}}}}
    es = _patch_es(
        monkeypatch,
        FakeES(indices, mappings=mappings, fail_mapping_on={"bkfta_action_20261028_0"}),
    )

    with pytest.raises(CommandError, match="读取失败"):
        _run(MAPPING_COMMAND)

    assert es.indices.put_calls == []


def test_mapping_reports_missing_index_name(monkeypatch):
    """物理索引名合法但不存在时，应提示索引不存在，而不是读取 mapping 失败"""
    es = _patch_es(
        monkeypatch,
        _make_es(PHYSICAL_INDICES, not_found_on={"bkfta_action_20991231_0"}),
    )

    with pytest.raises(CommandError, match="不存在"):
        _run(MAPPING_COMMAND, "--apply", "--indices", "bkfta_action_20991231_0")

    assert es.indices.put_calls == []


def test_mapping_not_found_aborts_before_write(monkeypatch):
    """存在不存在的索引时先中止，不要先补一部分再报错"""
    indices = {"bkfta_action_20261028_0": {}, "bkfta_action_20991231_0": {}}
    # 20261028 缺字段，20991231 读 mapping 时 404
    mappings = {"bkfta_action_20261028_0": {"mappings": {"properties": {}}}}
    es = _patch_es(
        monkeypatch,
        FakeES(indices, mappings=mappings, not_found_on={"bkfta_action_20991231_0"}),
    )

    with pytest.raises(CommandError, match="索引不存在"):
        _run(MAPPING_COMMAND, "--apply")

    assert es.indices.put_calls == []


def test_mapping_rejects_alias_in_indices(monkeypatch):
    es = _patch_es(monkeypatch, _make_es(PHYSICAL_INDICES))

    with pytest.raises(CommandError, match="只支持物理索引名"):
        _run(MAPPING_COMMAND, "--apply", "--indices", "bkfta_action_20261028_read")

    assert es.indices.put_calls == []


def test_mapping_tolerates_single_index_read_failure(monkeypatch):
    es = _patch_es(
        monkeypatch,
        FakeES(PHYSICAL_INDICES, fail_mapping_on={"bkfta_action_20261028_0"}),
    )

    with pytest.raises(CommandError) as exc:
        _run(MAPPING_COMMAND, "--apply")

    # 读取失败的索引不阻断其余索引补齐
    assert es.indices.put_calls == [
        ("bkfta_action_20261029_0", {"properties": {FIELD: {"type": "keyword"}}}),
    ]
    # 只展示真实存在的失败类型，不出现"补齐失败 0 个"
    assert "读取失败 1 个" in str(exc.value)
    assert "补齐失败" not in str(exc.value)


# ---------------------------------------------------------------------------
# backfill_action_notice_way
# ---------------------------------------------------------------------------


def test_backfill_aborts_when_no_index(monkeypatch):
    _patch_es(monkeypatch, FakeES({}))

    with pytest.raises(CommandError):
        _run(BACKFILL_COMMAND)


def test_backfill_defaults_to_dry_run_and_refreshes(monkeypatch):
    es = _patch_es(monkeypatch, _make_es(PHYSICAL_INDICES, counts=[12]))

    output = _run(BACKFILL_COMMAND)

    # 不带 --apply 时只预览，不提交任何写操作
    assert es.update_calls == []
    # 统计前先刷新，避免读到旧搜索视图
    assert es.indices.refresh_calls == ["bkfta_action_20261028_0,bkfta_action_20261029_0"]
    assert "12" in output
    assert "--apply" in output


def test_backfill_aborts_when_initial_count_has_failed_shards(monkeypatch):
    es = _patch_es(monkeypatch, _make_es(PHYSICAL_INDICES, counts=[5], count_failed=[1]))

    with pytest.raises(CommandError) as exc:
        _run(BACKFILL_COMMAND, "--apply")

    assert "分片失败" in str(exc.value)
    assert "检查集群" in str(exc.value)
    assert es.update_calls == []


def test_backfill_aborts_when_mapping_missing(monkeypatch):
    """索引没有字段 mapping 时，回填只写 _source、不进索引，必须提前拦截"""
    es = _patch_es(monkeypatch, FakeES(PHYSICAL_INDICES))

    with pytest.raises(CommandError) as exc:
        _run(BACKFILL_COMMAND, "--apply")

    # 只缺字段时给出补 mapping 的建议，不应出现"读取失败"噪音
    assert "缺 notice_way 字段" in str(exc.value)
    assert "init_action_notice_way_mapping --apply" in str(exc.value)
    assert "读取 mapping 失败" not in str(exc.value)
    assert es.update_calls == []
    assert es.indices.refresh_calls == []


def test_backfill_reports_mapping_read_failure_separately(monkeypatch):
    """只有读取失败时，提示检查连接/权限，不能建议去补 mapping"""
    es = _patch_es(monkeypatch, FakeES(PHYSICAL_INDICES, fail_mapping_on=set(PHYSICAL_INDICES)))

    with pytest.raises(CommandError) as exc:
        _run(BACKFILL_COMMAND, "--apply")

    message = str(exc.value)
    assert "读取 mapping 失败" in message
    assert "检查 ES 连接/权限" in message
    assert "缺 notice_way 字段" not in message
    assert es.update_calls == []


def test_backfill_reports_missing_index_name(monkeypatch):
    """物理索引名合法但不存在时，应提示索引不存在，而不是读取 mapping 失败"""
    es = _patch_es(
        monkeypatch,
        _make_es(PHYSICAL_INDICES, counts=[1], not_found_on={"bkfta_action_20991231_0"}),
    )

    with pytest.raises(CommandError, match="索引不存在"):
        _run(BACKFILL_COMMAND, "--apply", "--indices", "bkfta_action_20991231_0")

    assert es.update_calls == []


def test_backfill_rejects_alias_in_indices(monkeypatch):
    """别名第三段不是日期，且写别名只覆盖单个索引，必须拒绝"""
    es = _patch_es(monkeypatch, _make_es(PHYSICAL_INDICES, counts=[1]))

    with pytest.raises(CommandError, match="只支持物理索引名"):
        _run(BACKFILL_COMMAND, "--apply", "--indices", "bkfta_action_20261028_read")

    assert es.update_calls == []


def test_backfill_reports_indices_filtered_out_by_date(monkeypatch):
    """显式索引被日期过滤为空时，不能报"未找到索引" """
    indices = {"bkfta_action_20260901_0": {}}
    es = _patch_es(monkeypatch, _make_es(indices, counts=[1]))

    with pytest.raises(CommandError, match="不在 --start/--end 范围内"):
        _run(
            BACKFILL_COMMAND,
            "--apply",
            "--indices",
            "bkfta_action_20260901_0",
            "--start",
            "2026-10-01",
        )

    assert es.update_calls == []


def test_backfill_wait_without_apply_is_rejected(monkeypatch):
    """--wait 单独使用应报错，而不是静默按 dry-run 成功退出"""
    es = _patch_es(monkeypatch, _make_es(PHYSICAL_INDICES, counts=[3]))

    with pytest.raises(CommandError, match="需配合 --apply"):
        _run(BACKFILL_COMMAND, "--wait")

    # 参数校验在连 ES 之前，不应有任何查询/写入
    assert es.update_calls == []
    assert es.indices.refresh_calls == []


def test_backfill_reports_nothing_to_do(monkeypatch):
    es = _patch_es(monkeypatch, _make_es(PHYSICAL_INDICES, counts=[0]))

    output = _run(BACKFILL_COMMAND, "--apply")

    assert "无需回填" in output
    assert es.update_calls == []


def test_backfill_script_targets_notice_way(monkeypatch):
    es = _patch_es(monkeypatch, _make_es(PHYSICAL_INDICES, counts=[1]))

    _run(BACKFILL_COMMAND, "--apply")

    source = es.update_calls[0]["body"]["script"]["source"]
    assert "ctx._source.inputs?.notice_way" in source
    assert "ctx._source.notice_way" in source
    assert "__none__" in source


def test_backfill_submits_async_task_with_expected_params(monkeypatch):
    es = _patch_es(monkeypatch, _make_es(PHYSICAL_INDICES, counts=[3]))

    output = _run(BACKFILL_COMMAND, "--apply")

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
    # 进度提示必须是真实 task id，不能把 {task_id} 原样打出来
    assert "_tasks/node:1" in output
    assert "{task_id}" not in output


def test_backfill_wait_and_verify(monkeypatch):
    es = _patch_es(
        monkeypatch,
        _make_es(
            PHYSICAL_INDICES,
            counts=[3, 0],
            task_statuses=[{"completed": True, "response": {"updated": 3, "version_conflicts": 0, "failures": []}}],
        ),
    )

    output = _run(BACKFILL_COMMAND, "--apply", "--wait")

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
        _make_es(
            PHYSICAL_INDICES,
            counts=[3, 1],
            task_statuses=[{"completed": True, "response": {"updated": 2, "version_conflicts": 1, "failures": []}}],
        ),
    )

    with pytest.raises(CommandError):
        _run(BACKFILL_COMMAND, "--apply", "--wait")


def test_backfill_verification_rejects_failed_shards(monkeypatch):
    """复验 count=0 但有分片失败时不能判定为完成"""
    _patch_es(
        monkeypatch,
        _make_es(
            PHYSICAL_INDICES,
            counts=[3, 0],
            count_failed=[0, 1],
            task_statuses=[{"completed": True, "response": {"updated": 3, "failures": []}}],
        ),
    )

    with pytest.raises(CommandError):
        _run(BACKFILL_COMMAND, "--apply", "--wait")


def test_backfill_wait_raises_on_task_failures(monkeypatch):
    _patch_es(
        monkeypatch,
        _make_es(
            PHYSICAL_INDICES,
            counts=[3],
            task_statuses=[{"completed": True, "response": {"updated": 0, "failures": [{"cause": "boom"}]}}],
        ),
    )

    with pytest.raises(CommandError):
        _run(BACKFILL_COMMAND, "--apply", "--wait")


def test_backfill_filters_indices_by_date(monkeypatch):
    indices = {"bkfta_action_20260901_0": {}, "bkfta_action_20261028_0": {}}
    es = _patch_es(monkeypatch, _make_es(indices, counts=[1]))

    _run(BACKFILL_COMMAND, "--apply", "--start", "2026-10-01")

    assert es.update_calls[0]["index"] == "bkfta_action_20261028_0"


def test_backfill_skips_aliases(monkeypatch):
    indices = {
        "bkfta_action_20261028_0": {},
        "bkfta_action_20261028_read": {},
        "write_20261028_bkfta_action": {},
    }
    es = _patch_es(monkeypatch, _make_es(indices, counts=[1]))

    _run(BACKFILL_COMMAND, "--apply")

    assert es.update_calls[0]["index"] == "bkfta_action_20261028_0"
