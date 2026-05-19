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


def test_routing_storage_type_fix_writes_storage_type_back(mock_metadata_redis, mock_http, mocker):
    """F5/F7 防回归：detail 缺 storage_type → 修复后 redis 里 storage_type=influxdb，且原其他字段保留。"""
    _set_settings(mocker)
    client = mock_metadata_redis

    from metadata.models.space.constants import (
        RESULT_TABLE_DETAIL_KEY,
        SPACE_TO_RESULT_TABLE_KEY,
    )

    table_id = "2_bkmonitor_time_series_999.__default__"
    client.hset(SPACE_TO_RESULT_TABLE_KEY, "bkcc__999", json.dumps({table_id: {"filters": []}}))
    original_detail = {
        "storage_id": 2,
        "db": "2_bkmonitor_time_series_999",
        "measurement": "__default__",
        "vm_rt": "",
        "fields": ["cpu_load"],
        "data_label": "zjtest",
        "bk_data_id": 999,
    }
    client.hset(RESULT_TABLE_DETAIL_KEY, table_id, json.dumps(original_detail))

    # 关键：不 mock push_table_id_detail，确保自愈走的是 _ensure_storage_type（局部 HSET）路径，
    # 而不是会擦字段的 push。
    push_mock = mocker.patch("metadata.models.space.space_table_id_redis.SpaceTableIDRedis.push_table_id_detail")

    summary = diagnostics.run_health_check(dry_run=False)

    assert any(i["code"] == "detail_no_storage_type" for i in summary["issues"])
    assert summary["fix_total"] >= 1

    raw = client.hget(RESULT_TABLE_DETAIL_KEY, table_id)
    assert raw is not None
    written = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
    assert written["storage_type"] == "influxdb"
    # 原字段必须保留
    assert written["db"] == original_detail["db"]
    assert written["fields"] == original_detail["fields"]
    assert written["data_label"] == original_detail["data_label"]
    # storage_type 修复路径不应该调 push_table_id_detail（会擦字段）
    push_mock.assert_not_called()


def test_routing_storage_type_fix_chooses_vm_when_vm_rt_present(mock_metadata_redis, mock_http, mocker):
    """detail.vm_rt 非空时 storage_type 应推断为 victoria_metrics。"""
    _set_settings(mocker)
    client = mock_metadata_redis

    from metadata.models.space.constants import (
        RESULT_TABLE_DETAIL_KEY,
        SPACE_TO_RESULT_TABLE_KEY,
    )

    table_id = "2_vm_table.__default__"
    client.hset(SPACE_TO_RESULT_TABLE_KEY, "bkcc__888", json.dumps({table_id: {"filters": []}}))
    client.hset(
        RESULT_TABLE_DETAIL_KEY,
        table_id,
        json.dumps(
            {
                "storage_id": 7,
                "db": "",
                "measurement": "",
                "vm_rt": "vm_2_table",
                "fields": [],
                "data_label": "vm_label",
                "bk_data_id": 888,
            }
        ),
    )
    mocker.patch("metadata.models.space.space_table_id_redis.SpaceTableIDRedis.push_table_id_detail")

    diagnostics.run_health_check(dry_run=False)

    raw = client.hget(RESULT_TABLE_DETAIL_KEY, table_id)
    written = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
    assert written["storage_type"] == "victoria_metrics"


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
    """unify-query counter 与上一轮一致 → 不报警。"""
    _set_settings(mocker)
    body = (
        'unify_query_space_router_total{reason="SPACE_IS_NOT_EXISTS",space_uid="bkcc__0"} 9\n'
        'unify_query_space_router_total{reason="SPACE_TABLE_ID_FIELD_IS_NOT_EXISTS",space_uid="bkcc__2"} 11\n'
    )
    resp = mocker.MagicMock(status_code=200, text=body, raise_for_status=lambda: None)
    mocker.patch("metadata.task.diagnostics.requests.get", return_value=resp)

    # 第一轮：种 baseline
    first = diagnostics.run_health_check(dry_run=False)
    assert all(i["code"] != "space_router_anomaly_delta" for i in first["issues"])

    # 第二轮：完全相同 → delta=0
    second = diagnostics.run_health_check(dry_run=False)
    assert all(i["code"] != "space_router_anomaly_delta" for i in second["issues"])


def test_unify_query_delta_above_threshold_reports(mock_metadata_redis, mocker):
    """unify-query counter 增量过阈 → 报警。"""
    _set_settings(mocker)
    mocker.patch("metadata.task.diagnostics.settings.LINK_HEALTH_UQ_COUNTER_DELTA_THRESHOLD", 5)

    metric_line = 'unify_query_space_router_total{reason="SPACE_IS_NOT_EXISTS",space_uid="bkcc__0"} %s\n'
    first_resp = mocker.MagicMock(status_code=200, text=metric_line % "9", raise_for_status=lambda: None)
    second_resp = mocker.MagicMock(status_code=200, text=metric_line % "20", raise_for_status=lambda: None)

    request_get = mocker.patch("metadata.task.diagnostics.requests.get")
    request_get.return_value = first_resp
    diagnostics.run_health_check(dry_run=False)

    request_get.return_value = second_resp
    summary = diagnostics.run_health_check(dry_run=False)

    assert any(i["code"] == "space_router_anomaly_delta" for i in summary["issues"])


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
