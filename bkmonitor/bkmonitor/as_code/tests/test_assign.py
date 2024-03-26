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
import pytest
import yaml
from django.test import TestCase

from bkmonitor.action.serializers import BatchSaveAssignRulesSlz
from bkmonitor.as_code.parse import convert_assign_groups
from bkmonitor.as_code.parse_yaml import AssignGroupRuleParser
from bkmonitor.models import AlertAssignGroup, AlertAssignRule, DutyArrange, UserGroup

TestCase.databases = {"default", "monitor_api"}
pytestmark = pytest.mark.django_db
DATA_PATH = "bkmonitor/as_code/tests/data/"


@pytest.fixture()
def setup():
    UserGroup.objects.all().delete()
    DutyArrange.objects.all().delete()
    AlertAssignGroup.objects.all().delete()
    AlertAssignRule.objects.all().delete()


def test_assign_parse():
    with open(f"{DATA_PATH}assign/normal_assign.yaml", "r") as f:
        code_config = yaml.safe_load(f.read())
    notice_group_ids = {"日常运维": 1}
    action_ids = {"test": 23}
    p = AssignGroupRuleParser(2, notice_group_ids=notice_group_ids, action_ids=action_ids)
    code_config = p.check(code_config)
    config = p.parse(code_config)
    assert config
    assert config.get("id") is None
    assert config["bk_biz_id"] == 2
    rule = config["rules"][0]
    assert rule["is_enabled"]
    assert rule["user_groups"] == [1]
    notice_action = rule["actions"][0]
    assert notice_action["action_type"] == "notice"
    assert notice_action["is_enabled"]
    assert notice_action["upgrade_config"]["user_groups"] == [1]
    itsm_action = rule["actions"][1]
    assert itsm_action["action_type"] == "itsm"
    assert itsm_action["action_id"] == 23


def test_convert_assign(setup):
    with open(f"{DATA_PATH}assign/normal_assign.yaml", "r") as f:
        code_config = yaml.safe_load(f.read())
    notice_group_ids = {"日常运维": 1, "开发": 2}
    action_ids = {"test": 23}
    code_config["rules"][0]["user_groups"] = ["开发"]

    records = convert_assign_groups(
        2,
        "default",
        snippets={},
        configs={"test": code_config},
        notice_group_ids=notice_group_ids,
        action_ids=action_ids,
    )

    assert records
    assert isinstance(records[0]["obj"], BatchSaveAssignRulesSlz)
    result = records[0]["obj"].save(records[0]["obj"].data)
    assign_group = AlertAssignGroup.objects.get(id=result["assign_group_id"])

    assert assign_group.bk_biz_id == 2
    assert AlertAssignRule.objects.all().count() == 1


def test_convert_assign_error(setup):
    with open(f"{DATA_PATH}assign/normal_assign.yaml", "r") as f:
        code_config = yaml.safe_load(f.read())
    notice_group_ids = {"日常运维": 1, "开发": 2}
    action_ids = {"test111": 23}
    code_config["rules"][0]["user_groups"] = ["开发"]

    records = convert_assign_groups(
        2,
        "default",
        snippets={},
        configs={"test": code_config},
        notice_group_ids=notice_group_ids,
        action_ids=action_ids,
    )

    assert records[0]["parse_error"] is not None


def test_assign_unparse():
    """
    测试从DB数据结构转为用户数据
    """

    rule_config = {
        'name': '分派测试',
        'priority': 1,
        "id": 123,
        'rules': [
            {
                'user_groups': [1],
                'enabled': True,
                'conditions': [{'field': 'bcs_cluster_id', 'value': ['123'], 'method': 'eq', 'condition': 'and'}],
                'actions': [
                    {
                        'action_type': 'notice',
                        'is_enabled': False,
                        'upgrade_config': {'user_groups': [1], 'upgrade_interval': 1440, 'is_enabled': True},
                    },
                    {'action_type': 'itsm', 'is_enabled': True, 'action_id': 23},
                ],
                'alert_severity': 1,
                'additional_tags': [{'key': 'key1', 'value': '123value'}],
                'id': 0,
                'is_enabled': True,
            },
            {
                'user_groups': [1],
                'enabled': True,
                'conditions': [{'field': 'bcs_cluster_id', 'value': ['123'], 'method': 'eq', 'condition': 'and'}],
                'actions': [
                    {
                        'action_type': 'notice',
                        'is_enabled': True,
                        'upgrade_config': {'user_groups': [1], 'upgrade_interval': 1440, 'is_enabled': True},
                    },
                    {'action_type': 'itsm', 'is_enabled': True, 'action_id': 23},
                ],
                'alert_severity': 1,
                'additional_tags': [{'key': 'key1', 'value': '123value'}],
                'id': 0,
                'is_enabled': True,
            },
        ],
    }
    notice_group_ids = {"日常运维": 1}
    action_ids = {"test": 23}
    p = AssignGroupRuleParser(2, notice_group_ids=notice_group_ids, action_ids=action_ids)
    config = p.unparse(rule_config)
    rule = config["rules"][0]
    assert rule["user_groups"] == ["日常运维"]
    assert rule["notice_enabled"] is False
    upgrade_config = rule["upgrade_config"]
    assert upgrade_config["user_groups"] == ["日常运维"]
    itsm_action = rule["actions"][0]
    assert itsm_action["type"] == "itsm"
    assert itsm_action["name"] == "test"
    assert itsm_action["enabled"]

    last_rule = config["rules"][-1]
    assert "notice_enabled" not in last_rule
