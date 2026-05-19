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
    mocker.patch("metadata.task.diagnostics.settings.METRICS_KEY_PREFIX", "bkmonitor:metrics_")


def test_bmw_orphan_task_detected_and_fixed(mock_metadata_redis, mock_http, mocker):
    """孤儿 active task：检测 → 触发自愈 → broker hash 被清。"""
    _set_settings(mocker)
    client = mock_metadata_redis

    task_name = "periodic:metadata:refresh_ts_metric"
    t_key = f"{{bmw}}:{{default}}:t:{task_name}"
    lease_key = "{bmw}:{default}:lease"
    client.hset(t_key, "state", "active")
    # lease score 比 grace 还早 → 视为过期
    client.zadd(lease_key, {task_name: time.time() - 10000})

    summary = diagnostics.run_health_check(dry_run=False)

    assert any(i["code"] == "orphan_active_task" for i in summary["issues"]) is True
    assert summary["fix_failed"] == 0
    assert summary["fix_total"] >= 1
    assert client.exists(t_key) == 0
    assert client.zscore(lease_key, task_name) is None


def test_bmw_active_with_fresh_lease_is_not_orphan(mock_metadata_redis, mock_http, mocker):
    """state=active 但 lease 仍新鲜 → 不算孤儿。"""
    _set_settings(mocker)
    client = mock_metadata_redis

    task_name = "periodic:metadata:refresh_ts_metric"
    t_key = f"{{bmw}}:{{default}}:t:{task_name}"
    lease_key = "{bmw}:{default}:lease"
    client.hset(t_key, "state", "active")
    client.zadd(lease_key, {task_name: time.time()})  # 刚刚的 lease

    summary = diagnostics.run_health_check(dry_run=False)

    assert all(i["code"] != "orphan_active_task" for i in summary["issues"])
    # 没动 broker
    assert client.exists(t_key) == 1


def test_dry_run_does_not_fix(mock_metadata_redis, mock_http, mocker):
    _set_settings(mocker)
    client = mock_metadata_redis

    task_name = "periodic:metadata:refresh_ts_metric"
    t_key = f"{{bmw}}:{{default}}:t:{task_name}"
    lease_key = "{bmw}:{default}:lease"
    client.hset(t_key, "state", "active")
    client.zadd(lease_key, {task_name: time.time() - 10000})

    summary = diagnostics.run_health_check(dry_run=True)

    assert summary["dry_run_total"] >= 1
    assert summary["fix_total"] == 0
    assert client.exists(t_key) == 1  # dry-run 没动


def test_routing_detail_missing_storage_type_triggers_push(mock_metadata_redis, mock_http, mocker):
    """result_table_detail 缺 storage_type → 触发 push_table_id_detail 重写。"""
    _set_settings(mocker)
    client = mock_metadata_redis

    # 给 space_to_result_table 注一个 hash field，包一个 table_id
    from metadata.models.space.constants import (
        RESULT_TABLE_DETAIL_KEY,
        SPACE_TO_RESULT_TABLE_KEY,
    )

    table_id = "2_bkmonitor_time_series_999.__default__"
    client.hset(SPACE_TO_RESULT_TABLE_KEY, "bkcc__999", json.dumps({table_id: {"filters": []}}))
    client.hset(
        RESULT_TABLE_DETAIL_KEY,
        table_id,
        json.dumps(
            {
                "storage_id": 2,
                "db": "2_bkmonitor_time_series_999",
                "measurement": "__default__",
                "vm_rt": "",
                # 故意缺 storage_type
                "fields": [],
                "data_label": "zjtest",
                "bk_data_id": 999,
            }
        ),
    )

    push_mock = mocker.patch("metadata.models.space.space_table_id_redis.SpaceTableIDRedis.push_table_id_detail")

    summary = diagnostics.run_health_check(dry_run=False)

    assert any(i["code"] == "detail_no_storage_type" for i in summary["issues"])
    push_mock.assert_called()
    args, kwargs = push_mock.call_args
    assert kwargs.get("table_id_list") == [table_id]


def test_streak_gates_fix(mock_metadata_redis, mock_http, mocker):
    """连续 streak 阈值未到则跳过修复。"""
    _set_settings(mocker)
    mocker.patch("metadata.task.diagnostics.settings.LINK_HEALTH_FIX_AFTER_STREAK", 3)
    client = mock_metadata_redis

    task_name = "periodic:metadata:refresh_ts_metric"
    t_key = f"{{bmw}}:{{default}}:t:{task_name}"
    lease_key = "{bmw}:{default}:lease"
    client.hset(t_key, "state", "active")
    client.zadd(lease_key, {task_name: time.time() - 10000})

    summary = diagnostics.run_health_check(dry_run=False)

    # 第一次：检测到但 streak<3 → 不修
    assert any(i["code"] == "orphan_active_task" for i in summary["issues"])
    assert summary["fix_total"] == 0
    assert client.exists(t_key) == 1


def test_fix_budget_caps_actions(mock_metadata_redis, mock_http, mocker):
    """单轮修复数 > 预算 → 停手。"""
    _set_settings(mocker)
    mocker.patch("metadata.task.diagnostics.settings.LINK_HEALTH_MAX_FIX_PER_ROUND", 1)
    client = mock_metadata_redis

    # 注入两个不同 task_name 的孤儿
    for name in ("periodic:metadata:refresh_ts_metric", "periodic:metadata:refresh_datasource"):
        t_key = f"{{bmw}}:{{default}}:t:{name}"
        client.hset(t_key, "state", "active")
        client.zadd("{bmw}:{default}:lease", {name: time.time() - 10000})

    summary = diagnostics.run_health_check(dry_run=False)
    assert summary["fix_total"] == 1
