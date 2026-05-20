# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import json
import time

import pytest
from mockredis import mock_redis_client

from metadata.task import diagnostics

pytestmark = pytest.mark.django_db


@pytest.fixture
def mock_metadata_redis(mocker):
    from metadata.utils.redis_tools import RedisTools

    client = mock_redis_client()
    original = RedisTools.metadata_redis_client
    RedisTools.metadata_redis_client = client
    mocker.patch.object(diagnostics, "_bmw_broker_client", return_value=client)
    mocker.patch.object(diagnostics, "_transfer_redis_client", return_value=client)
    yield client
    RedisTools.metadata_redis_client = original


@pytest.fixture
def mock_http(mocker):
    resp_ok = mocker.MagicMock(status_code=204, text="", raise_for_status=lambda: None)
    return mocker.patch("metadata.task.diagnostics.requests.get", return_value=resp_ok)


def _set_settings(mocker):
    mocker.patch("metadata.task.diagnostics.settings.LINK_HEALTH_FIX_AFTER_STREAK", 1)
    mocker.patch("metadata.task.diagnostics.settings.LINK_HEALTH_FIX_COOLDOWN_SECONDS", 60)
    mocker.patch("metadata.task.diagnostics.settings.LINK_HEALTH_MAX_FIX_PER_ROUND", 10)
    mocker.patch("metadata.task.diagnostics.settings.LINK_HEALTH_SAMPLE_SIZE", 10)
    mocker.patch("metadata.task.diagnostics.settings.LINK_HEALTH_BMW_LEASE_GRACE_SECONDS", 600)
    mocker.patch("metadata.task.diagnostics.settings.LINK_HEALTH_AUTOREMEDIATE", True)
    mocker.patch("metadata.task.diagnostics.settings.LINK_HEALTH_EXCLUDE_TABLE_IDS", [])
    mocker.patch("metadata.task.diagnostics.settings.LINK_HEALTH_UQ_COUNTER_DELTA_THRESHOLD", 5)
    mocker.patch("metadata.task.diagnostics.settings.METRICS_KEY_PREFIX", "bkmonitor:metrics_")
    mocker.patch("metadata.task.diagnostics.settings.FETCH_TIME_SERIES_METRIC_INTERVAL_SECONDS", 7200)


def _seed_orphan_task(client, task_name="periodic:metadata:refresh_ts_metric"):
    t_key = f"{{bmw}}:{{default}}:t:{task_name}"
    lease_key = "{bmw}:{default}:lease"
    client.hset(t_key, "state", "active")
    client.zadd(lease_key, task_name, time.time() - 10000)
    return t_key, lease_key


def test_bmw_orphan_task_detected_and_fixed(mock_metadata_redis, mock_http, mocker):
    """孤儿 active task：检测 → 触发自愈 → broker hash 被清。"""
    _set_settings(mocker)
    client = mock_metadata_redis
    t_key, lease_key = _seed_orphan_task(client)

    summary = diagnostics.run_health_check(dry_run=False)

    assert any(i["code"] == "orphan_active_task" for i in summary["issues"]) is True
    assert summary["fix_failed"] == 0
    assert summary["fix_total"] >= 1
    assert client.exists(t_key) == 0
    assert client.zscore(lease_key, "periodic:metadata:refresh_ts_metric") is None


def test_bmw_active_with_fresh_lease_is_not_orphan(mock_metadata_redis, mock_http, mocker):
    """state=active 但 lease 仍新鲜 → 不算孤儿。"""
    _set_settings(mocker)
    client = mock_metadata_redis

    task_name = "periodic:metadata:refresh_ts_metric"
    t_key = f"{{bmw}}:{{default}}:t:{task_name}"
    lease_key = "{bmw}:{default}:lease"
    client.hset(t_key, "state", "active")
    client.zadd(lease_key, task_name, time.time())

    summary = diagnostics.run_health_check(dry_run=False)

    assert all(i["code"] != "orphan_active_task" for i in summary["issues"])
    assert client.exists(t_key) == 1


def test_dry_run_does_not_fix(mock_metadata_redis, mock_http, mocker):
    _set_settings(mocker)
    client = mock_metadata_redis
    t_key, _ = _seed_orphan_task(client)

    summary = diagnostics.run_health_check(dry_run=True)

    assert summary["dry_run_total"] >= 1
    assert summary["fix_total"] == 0
    assert client.exists(t_key) == 1


def test_routing_storage_type_missing_is_not_an_issue(mock_metadata_redis, mock_http, mocker):
    """storage_type 字段缺失/任意值不再被视为故障——实证 unify-query 不依赖该字段。"""
    _set_settings(mocker)
    client = mock_metadata_redis

    from metadata.models.space.constants import (
        RESULT_TABLE_DETAIL_KEY,
        SPACE_TO_RESULT_TABLE_KEY,
    )

    cases = [
        ("system.cpu_summary", {"db": "system", "measurement": "cpu_summary", "vm_rt": ""}),
        ("2_bkmonitor_time_series_999.__default__", {"db": "2_bkmonitor_time_series_999", "vm_rt": ""}),
        ("2_vm_backed.__default__", {"db": "2_vm_backed", "vm_rt": "vm_some_table"}),
        ("2_weird.__default__", {"db": "x", "vm_rt": "y", "storage_type": "elasticsearch"}),
    ]
    space_payload = {}
    for tid, extra in cases:
        space_payload[tid] = {"filters": []}
        base = {"storage_id": 1, "fields": [], "bk_data_id": 999}
        base.update(extra)
        client.hset(RESULT_TABLE_DETAIL_KEY, tid, json.dumps(base))
    client.hset(SPACE_TO_RESULT_TABLE_KEY, "bkcc__999", json.dumps(space_payload))

    summary = diagnostics.run_health_check(dry_run=False)

    routing_issues = [i for i in summary["issues"] if i["stage"] == "routing"]
    assert routing_issues == [], f"unexpected routing issues: {routing_issues}"


def test_routing_detail_missing_is_autofixed(mock_metadata_redis, mock_http, mocker):
    """space_to_result_table 引用了某 table_id 但 result_table_detail 里查不到 → 真实路由不完整，自愈重建。"""
    _set_settings(mocker)
    client = mock_metadata_redis

    from metadata.models.space.constants import SPACE_TO_RESULT_TABLE_KEY

    table_id = "2_truly_missing.__default__"
    client.hset(SPACE_TO_RESULT_TABLE_KEY, "bkcc__111", json.dumps({table_id: {"filters": []}}))
    # 关键：不写 result_table_detail，制造路由缺失场景

    push_mock = mocker.patch("metadata.models.space.space_table_id_redis.SpaceTableIDRedis.push_table_id_detail")

    summary = diagnostics.run_health_check(dry_run=False)

    assert any(i["code"] == "detail_missing" for i in summary["issues"])
    push_mock.assert_called()
    _, kwargs = push_mock.call_args
    assert kwargs.get("table_id_list") == [table_id]
    assert kwargs.get("is_publish") is True


def test_streak_gates_fix(mock_metadata_redis, mock_http, mocker):
    """连续 streak 阈值未到则跳过修复，并入 ledger。"""
    _set_settings(mocker)
    mocker.patch("metadata.task.diagnostics.settings.LINK_HEALTH_FIX_AFTER_STREAK", 3)
    client = mock_metadata_redis
    t_key, _ = _seed_orphan_task(client)

    summary = diagnostics.run_health_check(dry_run=False)

    assert any(i["code"] == "orphan_active_task" for i in summary["issues"])
    assert summary["fix_total"] == 0
    assert summary["skipped_total"] >= 1
    assert any(s["reason"].startswith("streak") for s in summary["skipped"])
    assert client.exists(t_key) == 1


def test_cooldown_blocks_second_fix_in_same_window(mock_metadata_redis, mock_http, mocker):
    """同 gate_key 在 cooldown 内仅放行一次。"""
    _set_settings(mocker)
    client = mock_metadata_redis
    _seed_orphan_task(client)

    first = diagnostics.run_health_check(dry_run=False)
    assert first["fix_total"] >= 1

    # 第二轮再人为造一次同样的孤儿
    _seed_orphan_task(client)
    second = diagnostics.run_health_check(dry_run=False)
    assert second["fix_total"] == 0
    assert any(s["reason"] == "cooldown" for s in second["skipped"])


def test_fix_budget_caps_actions(mock_metadata_redis, mock_http, mocker):
    """单轮修复数 > 预算 → 停手。"""
    _set_settings(mocker)
    mocker.patch("metadata.task.diagnostics.settings.LINK_HEALTH_MAX_FIX_PER_ROUND", 1)
    client = mock_metadata_redis

    for name in ("periodic:metadata:refresh_ts_metric", "periodic:metadata:refresh_datasource"):
        _seed_orphan_task(client, task_name=name)

    summary = diagnostics.run_health_check(dry_run=False)
    assert summary["fix_total"] == 1
    assert any(s["reason"] == "budget_exhausted" for s in summary["skipped"])


def test_unify_query_no_delta_no_issue(mock_metadata_redis, mocker):
    """unify-query counter 与上一轮一致 → 不产生 router_anomaly_* issue。"""
    _set_settings(mocker)
    body = (
        'unify_query_space_router_total{metric="",reason="SPACE_IS_NOT_EXISTS",result_table="",space_uid="bkcc__0"} 9\n'
        'unify_query_space_router_total{metric="x",reason="SPACE_TABLE_ID_FIELD_IS_NOT_EXISTS",'
        'result_table="",space_uid="bkcc__2"} 11\n'
    )
    resp = mocker.MagicMock(status_code=200, text=body, raise_for_status=lambda: None)
    mocker.patch("metadata.task.diagnostics.requests.get", return_value=resp)

    first = diagnostics.run_health_check(dry_run=False)
    assert all(not i["code"].startswith("router_anomaly_") for i in first["issues"])

    second = diagnostics.run_health_check(dry_run=False)
    assert all(not i["code"].startswith("router_anomaly_") for i in second["issues"])


def test_unify_query_delta_above_threshold_reports(mock_metadata_redis, mocker):
    """unify-query counter 增量过阈 → 按分类生成 router_anomaly_* issue。"""
    _set_settings(mocker)
    space_qs = mocker.MagicMock()
    space_qs.values.return_value.first.return_value = None  # space 不存在 → space_not_registered
    mocker.patch("metadata.task.diagnostics.models.Space.objects.filter", return_value=space_qs)

    _set_uq_responses(
        mocker,
        first_value=9,
        second_value=20,
        reason="SPACE_IS_NOT_EXISTS",
        space_uid="bkcc__0",
    )

    diagnostics.run_health_check(dry_run=False)
    summary = diagnostics.run_health_check(dry_run=False)

    assert any(i["code"].startswith("router_anomaly_") for i in summary["issues"])


def _wrap_metrics_text(*lines):
    return "\n".join(lines) + "\n"


def _uq_metric_line(reason, space_uid, value, metric="", result_table=""):
    return (
        f'unify_query_space_router_total{{metric="{metric}",reason="{reason}",'
        f'result_table="{result_table}",space_uid="{space_uid}"}} {value}'
    )


def _set_uq_responses(mocker, first_value, second_value, **labels):
    """连续两轮 metrics，第二轮触发 delta 阈值。"""
    line_a = _uq_metric_line(value=first_value, **labels)
    line_b = _uq_metric_line(value=second_value, **labels)
    first = mocker.MagicMock(status_code=200, text=_wrap_metrics_text(line_a), raise_for_status=lambda: None)
    second = mocker.MagicMock(status_code=200, text=_wrap_metrics_text(line_b), raise_for_status=lambda: None)
    req = mocker.patch("metadata.task.diagnostics.requests.get")
    req.side_effect = [first, second]
    return req


def test_uq_classify_space_not_registered(mock_metadata_redis, mocker):
    """SPACE_IS_NOT_EXISTS + DB 中无该 space → space_not_registered，仅告警不自愈。"""
    _set_settings(mocker)
    _set_uq_responses(mocker, 0, 20, reason="SPACE_IS_NOT_EXISTS", space_uid="bkcc__0")
    space_qs = mocker.MagicMock()
    space_qs.values.return_value.first.return_value = None
    mocker.patch("metadata.task.diagnostics.models.Space.objects.filter", return_value=space_qs)

    diagnostics.run_health_check(dry_run=False)
    summary = diagnostics.run_health_check(dry_run=False)

    issues = [i for i in summary["issues"] if i["stage"] == "unify_query"]
    assert any(i["code"] == "router_anomaly_space_not_registered" for i in issues)
    assert summary["fix_total"] == 0


def test_uq_classify_space_archived(mock_metadata_redis, mocker):
    """SPACE_IS_NOT_EXISTS + DB 中 status=disabled → space_archived_still_queried，仅告警。"""
    _set_settings(mocker)
    _set_uq_responses(mocker, 0, 30, reason="SPACE_IS_NOT_EXISTS", space_uid="bkcc__14")
    space_qs = mocker.MagicMock()
    space_qs.values.return_value.first.return_value = {"status": "disabled"}
    mocker.patch("metadata.task.diagnostics.models.Space.objects.filter", return_value=space_qs)

    diagnostics.run_health_check(dry_run=False)
    summary = diagnostics.run_health_check(dry_run=False)

    issues = [i for i in summary["issues"] if i["stage"] == "unify_query"]
    assert any(i["code"] == "router_anomaly_space_archived_still_queried" for i in issues)
    assert summary["fix_total"] == 0


def test_uq_classify_space_normal_triggers_router_push(mock_metadata_redis, mocker):
    """SPACE_IS_NOT_EXISTS + status=normal → space_router_not_pushed，自愈调 push_and_publish_space_router。"""
    _set_settings(mocker)
    _set_uq_responses(mocker, 0, 12, reason="SPACE_IS_NOT_EXISTS", space_uid="bkcc__77")
    space_qs = mocker.MagicMock()
    space_qs.values.return_value.first.return_value = {"status": "normal"}
    mocker.patch("metadata.task.diagnostics.models.Space.objects.filter", return_value=space_qs)
    push_mock = mocker.patch("metadata.task.sync_space.push_and_publish_space_router")

    diagnostics.run_health_check(dry_run=False)
    summary = diagnostics.run_health_check(dry_run=False)

    issues = [i for i in summary["issues"] if i["stage"] == "unify_query"]
    assert any(i["code"] == "router_anomaly_space_router_not_pushed" for i in issues)
    push_mock.assert_called()
    _, kwargs = push_mock.call_args
    assert kwargs.get("space_type") == "bkcc"
    assert kwargs.get("space_id") == "77"


def test_uq_classify_metric_unknown_rt(mock_metadata_redis, mocker):
    """SPACE_TABLE_ID_FIELD_IS_NOT_EXISTS + result_table 空 → metric_unknown_rt，告警。"""
    _set_settings(mocker)
    _set_uq_responses(
        mocker,
        0,
        15,
        reason="SPACE_TABLE_ID_FIELD_IS_NOT_EXISTS",
        space_uid="bkcc__2",
        metric="kube_hpa_status_current_replicas",
        result_table="",
    )

    diagnostics.run_health_check(dry_run=False)
    summary = diagnostics.run_health_check(dry_run=False)

    issues = [i for i in summary["issues"] if i["stage"] == "unify_query"]
    assert any(i["code"] == "router_anomaly_metric_unknown_rt" for i in issues)
    assert summary["fix_total"] == 0


def test_uq_classify_metric_not_collected(mock_metadata_redis, mocker):
    """rt 是 TSGroup 但 transfer redis 无该 metric → metric_not_collected，告警不自愈。"""
    _set_settings(mocker)
    _set_uq_responses(
        mocker,
        0,
        10,
        reason="SPACE_TABLE_ID_FIELD_IS_NOT_EXISTS",
        space_uid="bkcc__2",
        metric="bk_apm_count",
        result_table="2_bkapm_metric_test.__default__",
    )
    tsg_qs = mocker.MagicMock()
    tsg_qs.values.return_value.first.return_value = {"time_series_group_id": 16, "bk_data_id": 1572873}
    mocker.patch("metadata.task.diagnostics.models.TimeSeriesGroup.objects.filter", return_value=tsg_qs)
    transfer_client = mocker.MagicMock()
    transfer_client.zscore.return_value = None  # 关键：没该 metric
    mocker.patch("metadata.task.diagnostics._transfer_redis_client", return_value=transfer_client)

    diagnostics.run_health_check(dry_run=False)
    summary = diagnostics.run_health_check(dry_run=False)

    issues = [i for i in summary["issues"] if i["stage"] == "unify_query"]
    assert any(i["code"] == "router_anomaly_metric_not_collected" for i in issues)
    assert summary["fix_total"] == 0


def test_uq_classify_metric_drift_collectable_triggers_fix(mock_metadata_redis, mocker):
    """rt 是 TSGroup 且 transfer redis 有 metric → metric_drift_collectable，自愈触发 F3 修复。"""
    _set_settings(mocker)
    _set_uq_responses(
        mocker,
        0,
        8,
        reason="SPACE_TABLE_ID_FIELD_IS_NOT_EXISTS",
        space_uid="bkcc__2",
        metric="latency_ms",
        result_table="2_drift_table.__default__",
    )
    filter_qs = mocker.MagicMock()
    filter_qs.values.return_value.first.return_value = {"time_series_group_id": 99, "bk_data_id": 9999}
    mocker.patch("metadata.task.diagnostics.models.TimeSeriesGroup.objects.filter", return_value=filter_qs)
    transfer_client = mocker.MagicMock()
    transfer_client.zscore.return_value = 1.0  # 有该 metric
    mocker.patch("metadata.task.diagnostics._transfer_redis_client", return_value=transfer_client)
    ts_group_obj = mocker.MagicMock()
    ts_group_obj.update_time_series_metrics.return_value = True
    mocker.patch("metadata.task.diagnostics.models.TimeSeriesGroup.objects.get", return_value=ts_group_obj)
    push_mock = mocker.patch("metadata.models.space.space_table_id_redis.SpaceTableIDRedis.push_table_id_detail")

    diagnostics.run_health_check(dry_run=False)
    summary = diagnostics.run_health_check(dry_run=False)

    issues = [i for i in summary["issues"] if i["stage"] == "unify_query"]
    assert any(i["code"] == "router_anomaly_metric_drift_collectable" for i in issues)
    ts_group_obj.update_time_series_metrics.assert_called_once()
    push_mock.assert_called()


def test_skipped_records_persist_to_ledger(mock_metadata_redis, mock_http, mocker):
    """跳过的 issue 同样写入 fix_history ledger，便于复盘。"""
    _set_settings(mocker)
    mocker.patch("metadata.task.diagnostics.settings.LINK_HEALTH_FIX_AFTER_STREAK", 3)
    client = mock_metadata_redis
    _seed_orphan_task(client)

    diagnostics.run_health_check(dry_run=False)

    history = client.lrange(diagnostics.FIX_HISTORY_REDIS_KEY, 0, -1)
    assert history, "skipped 也应入 ledger"
    payloads = [json.loads(item.decode("utf-8") if isinstance(item, bytes) else item) for item in history]
    assert any("reason" in p and p["reason"].startswith("streak") for p in payloads)
