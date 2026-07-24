"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import inspect
import json

import pytest
import xxhash
from django.db import connections
from django.test.utils import CaptureQueriesContext

from bkmonitor.as_code import parse
from bkmonitor.as_code.parse import convert_notices
from bkmonitor.models import ActionConfig, DutyRule, UserGroup

pytestmark = pytest.mark.django_db(databases="__all__")

BK_BIZ_ID = 2
APP = "app1"
RECORD_COUNT = 3
# bkmonitor app 模型走 monitor_api 库，CaptureQueriesContext 需用对应 connection
DB_ALIAS = "monitor_api"


@pytest.fixture
def seeded_as_code_resources():
    DutyRule.objects.filter(bk_biz_id=BK_BIZ_ID).delete()
    UserGroup.objects.filter(bk_biz_id__in=[BK_BIZ_ID, 0]).delete()
    ActionConfig.objects.filter(bk_biz_id__in=[str(BK_BIZ_ID), "0", BK_BIZ_ID, 0]).delete()

    for i in range(RECORD_COUNT):
        DutyRule.objects.create(
            bk_biz_id=BK_BIZ_ID,
            name=f"duty-rule-{i}",
            path=f"duty-{i}.yaml",
            app=APP,
            enabled=True,
        )
        UserGroup.objects.create(
            bk_biz_id=BK_BIZ_ID,
            name=f"notice-group-{i}",
            path=f"notice-{i}.yaml",
            app=APP,
            desc="",
        )
        ActionConfig.objects.create(
            bk_biz_id=BK_BIZ_ID,
            name=f"action-{i}",
            path=f"action-{i}.yaml",
            app=APP,
            plugin_id="1",
            execute_config={},
        )


def test_import_code_config_only_includes_app():
    """回归：import_code_config 映射查询的 only() 必须包含 app。"""
    source = inspect.getsource(parse.import_code_config)
    assert '.only("name", "id", "path", "app")' in source
    assert '.only("id", "path", "name", "app")' in source
    assert '"plugin_id", "app"' in source


def test_convert_notices_uses_database_app_matching(seeded_as_code_resources):
    """app 路径匹配应遵循数据库 collation，而不是 Python 的大小写敏感比较。"""
    group = UserGroup.objects.get(bk_biz_id=BK_BIZ_ID, path="notice-0.yaml")
    group.app = APP.upper()
    group.hash = xxhash.xxh3_128_hexdigest(json.dumps({}))
    group.save(update_fields=["app", "hash"])

    records = convert_notices(
        bk_biz_id=BK_BIZ_ID,
        app=APP,
        configs={"notice-0.yaml": {}},
        snippets={},
        duty_rules={},
    )

    assert records == []


def test_duty_rule_mapping_with_app_has_no_n_plus_one(seeded_as_code_resources):
    """与 import_code_config 相同 only 字段：访问 app 不应按行补查。"""
    with CaptureQueriesContext(connections[DB_ALIAS]) as ctx:
        duty_rules = {}
        for duty_rule in DutyRule.objects.filter(bk_biz_id=BK_BIZ_ID).only("name", "id", "path", "app"):
            if duty_rule.path and duty_rule.app == APP:
                duty_rules[duty_rule.path] = duty_rule.id
            duty_rules[duty_rule.name] = duty_rule.id

    assert len(ctx.captured_queries) == 1
    assert len([k for k in duty_rules if k.endswith(".yaml")]) == RECORD_COUNT


def test_user_group_mapping_with_app_has_no_n_plus_one(seeded_as_code_resources):
    """与 import_code_config 相同 only 字段：访问 app 不应按行补查。"""
    with CaptureQueriesContext(connections[DB_ALIAS]) as ctx:
        notice_group_ids = {}
        for user_group in UserGroup.objects.filter(bk_biz_id__in=[BK_BIZ_ID, 0]).only("id", "path", "name", "app"):
            if user_group.path and user_group.app == APP:
                notice_group_ids[user_group.path] = user_group.id
            notice_group_ids[user_group.name] = user_group.id

    assert len(ctx.captured_queries) == 1
    assert len([k for k in notice_group_ids if k.endswith(".yaml")]) == RECORD_COUNT


def test_action_mapping_with_app_has_no_n_plus_one(seeded_as_code_resources):
    """与 import_code_config 相同 only 字段：访问 app 不应按行补查。"""
    with CaptureQueriesContext(connections[DB_ALIAS]) as ctx:
        action_ids = {}
        for action in ActionConfig.objects.filter(bk_biz_id__in=[BK_BIZ_ID, 0]).only(
            "id", "path", "name", "plugin_id", "app"
        ):
            if action.path and action.app == APP:
                action_ids[action.path] = action.id
            action_ids[action.name] = action.id

    assert len(ctx.captured_queries) == 1
    assert len([k for k in action_ids if k.endswith(".yaml")]) == RECORD_COUNT


def test_only_without_app_triggers_n_plus_one(seeded_as_code_resources):
    """对照：only 漏掉 app 后访问 .app 会产生 N 次补查。"""
    qs = list(UserGroup.objects.filter(bk_biz_id=BK_BIZ_ID).only("id", "path", "name"))
    assert len(qs) == RECORD_COUNT
    assert "app" in qs[0].get_deferred_fields()

    with CaptureQueriesContext(connections[DB_ALIAS]) as ctx:
        for user_group in qs:
            _ = user_group.app

    assert len(ctx.captured_queries) == RECORD_COUNT
