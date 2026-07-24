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
from copy import deepcopy

import pytest
import yaml

from bkmonitor.as_code.parse import (
    convert_actions,
    convert_notices,
    get_errors,
    save_notice_and_action_records,
)
from bkmonitor.models import ActionConfig, ActionPlugin, UserGroup

pytestmark = pytest.mark.django_db(databases="__all__")

DATA_PATH = "bkmonitor/as_code/tests/data/"
BK_BIZ_ID = 2
APP = "app1"


@pytest.fixture
def clean_notice_and_action():
    UserGroup.objects.filter(bk_biz_id=BK_BIZ_ID).delete()
    ActionConfig.objects.filter(bk_biz_id__in=[str(BK_BIZ_ID), BK_BIZ_ID]).delete()


def _load_yaml(relative_path: str) -> dict:
    with open(f"{DATA_PATH}{relative_path}") as f:
        return yaml.safe_load(f.read())


def test_save_notice_and_action_records_uses_update_not_instance_save():
    """回归：元数据应走 QuerySet.update，避免二次 instance.save 双写修改时间。"""
    source = inspect.getsource(save_notice_and_action_records)
    assert ".objects.filter(pk=" in source
    assert ".update(" in source
    assert "instance.save(" not in source
    # 元数据 update 不应携带修改时间字段
    assert "update_time=" not in source


def test_notice_serializer_clears_hash_and_update_restores_meta(clean_notice_and_action):
    """序列化器 save 清空 hash/snippet 后，update 写回元数据且不刷新 update_time。"""
    snippet = _load_yaml("notice/snippets/base.yaml")
    config = _load_yaml("notice/ops.yaml")
    path = "ops.yaml"

    records = convert_notices(
        bk_biz_id=BK_BIZ_ID,
        app=APP,
        configs={path: deepcopy(config)},
        snippets={"base.yaml": snippet},
        duty_rules={},
    )
    assert get_errors(records) == {}
    assert len(records) == 1

    slz = records[0]["obj"]
    slz.save()
    slz.instance.refresh_from_db()
    assert slz.instance.hash == ""
    assert slz.instance.snippet == ""
    update_time_after_business_save = slz.instance.update_time

    type(slz.instance).objects.filter(pk=slz.instance.pk).update(
        path=records[0]["path"],
        app=APP,
        hash=records[0]["hash"],
        snippet=records[0]["snippet"],
    )

    group = UserGroup.objects.get(bk_biz_id=BK_BIZ_ID, name=config["name"])
    assert group.app == APP
    assert group.path == path
    assert group.hash == records[0]["hash"]
    assert group.hash
    # TextField 会对 dict 做 str() 落库
    assert group.snippet == str(records[0]["snippet"])
    assert group.update_time == update_time_after_business_save


def test_save_notice_and_action_records_persists_notice_meta(clean_notice_and_action):
    """通知组完整保存路径应落库 as_code 元数据。"""
    snippet = _load_yaml("notice/snippets/base.yaml")
    config = _load_yaml("notice/ops.yaml")
    path = "ops.yaml"

    records = convert_notices(
        bk_biz_id=BK_BIZ_ID,
        app=APP,
        configs={path: deepcopy(config)},
        snippets={"base.yaml": snippet},
        duty_rules={},
    )
    assert get_errors(records) == {}

    save_notice_and_action_records(records, APP)

    group = UserGroup.objects.get(bk_biz_id=BK_BIZ_ID, name=config["name"])
    assert group.app == APP
    assert group.path == path
    assert group.hash == records[0]["hash"]
    assert group.snippet == str(records[0]["snippet"])


def test_save_notice_and_action_records_persists_action_meta(clean_notice_and_action):
    """套餐完整保存路径应落库 as_code 元数据。"""
    if not ActionPlugin.objects.filter(plugin_key="webhook").exists():
        ActionPlugin.objects.create(
            plugin_type="webhook",
            plugin_key="webhook",
            name="webhook",
            category="webhook",
            config_schema={},
            backend_config={},
        )

    snippet = _load_yaml("action/snippets/base.yaml")
    config = _load_yaml("action/webhook.yaml")
    path = "webhook.yaml"

    records = convert_actions(
        bk_biz_id=BK_BIZ_ID,
        app=APP,
        configs={path: deepcopy(config)},
        snippets={"base.yaml": snippet},
    )
    assert get_errors(records) == {}
    assert len(records) == 1

    save_notice_and_action_records(records, APP)

    action = ActionConfig.objects.get(name=config["name"], bk_biz_id__in=[str(BK_BIZ_ID), BK_BIZ_ID])
    assert action.app == APP
    assert action.path == path
    assert action.hash == records[0]["hash"]
    assert action.hash
    assert action.snippet == str(records[0]["snippet"])
