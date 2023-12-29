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

from bkmonitor.action.serializers import DutyRuleDetailSlz
from bkmonitor.as_code.parse_yaml import DutyRuleParser
from bkmonitor.models import DutyArrange, DutyRule, UserGroup

TestCase.databases = {"default", "monitor_api"}
pytestmark = pytest.mark.django_db
DATA_PATH = "bkmonitor/as_code/tests/data/duty"


@pytest.fixture()
def setup():
    UserGroup.objects.all().delete()
    DutyArrange.objects.all().delete()
    DutyRule.objects.all().delete()


def test_duty_parse(setup):
    with open(f"{DATA_PATH}/normal_rule.yaml", "r") as f:
        code_config = yaml.safe_load(f.read())
    p = DutyRuleParser(bk_biz_id=2)
    code_config = p.check(code_config)
    config = p.parse(code_config)
    print("config", config)
    assert config
    assert config["bk_biz_id"] == 2
    assert config["enabled"]
    assert config["effective_time"] == "2023-11-24 17:35:00"
    assert config["duty_arranges"]

    slz = DutyRuleDetailSlz(data=config)
    slz.is_valid(raise_exception=True)
    slz.save()

    rule = DutyRule.objects.get(name=code_config["name"])
    assert DutyArrange.objects.filter(duty_rule_id=rule.id).count() == 2


def test_unparse():
    """
    测试从DB数据结构转为用户数据
    """
    rule_config = {
        'name': '轮值规则测试',
        'labels': ['test', 'aaa'],
        'enabled': True,
        'effective_time': '2023-11-24 17:35:00',
        'category': 'regular',
        'end_time': '',
        'bk_biz_id': 2,
        'duty_arranges': [
            {
                'duty_time': [
                    {
                        'work_type': 'daily',
                        'work_days': [],
                        'work_date_range': [],
                        'work_time_type': 'time_range',
                        'work_time': ['00:00--23:59'],
                        'period_settings': {},
                    }
                ],
                'backups': [],
                'duty_users': [[{'id': 'bk_operator', 'type': 'group'}, {'id': 'xxx', 'type': 'user'}]],
                'group_number': 0,
                'group_type': 'specified',
            },
            {
                'duty_time': [
                    {
                        'work_type': 'weekly',
                        'work_days': [1, 2, 3, 4, 5],
                        'work_date_range': [],
                        'work_time_type': 'datetime_range',
                        'work_time': ['01 00:00--05 23:59'],
                        'period_settings': {},
                    }
                ],
                'backups': [],
                'duty_users': [[{'id': 'bk_operator', 'type': 'group'}, {'id': 'xxx', 'type': 'user'}]],
                'group_number': 0,
                'group_type': 'specified',
            },
        ],
    }

    p = DutyRuleParser(2)
    config = p.unparse(rule_config)
    print("config ", config)
    assert config["enabled"]
    assert len(config["arranges"]) == 2
