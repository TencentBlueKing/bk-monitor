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
from schema import SchemaError

from bkmonitor.as_code.constants import MinVersion
from bkmonitor.as_code.parse_yaml import NoticeGroupConfigParser, SnippetRenderer

pytestmark = pytest.mark.django_db
TestCase.databases = {"default", "monitor_api"}

DATA_PATH = "bkmonitor/as_code/tests/data/"


def test_notice_parse():
    with open(f"{DATA_PATH}notice/snippets/base.yaml", "r") as f:
        snippet = yaml.safe_load(f.read())

    with open(f"{DATA_PATH}notice/ops.yaml", "r") as f:
        code_config = yaml.safe_load(f.read())
        result, message, code_config = SnippetRenderer.render(code_config, {"base.yaml": snippet})

    p = NoticeGroupConfigParser(2)
    code_config = p.check(code_config)
    config = p.parse(code_config)
    assert config

    with open(f"{DATA_PATH}notice/ops_duty.yaml", "r") as f:
        code_config = yaml.safe_load(f.read())
        result, message, code_config = SnippetRenderer.render(code_config, {"base.yaml": snippet})
    duty_rules = {"test rules": 1}
    p = NoticeGroupConfigParser(2, duty_rules)
    code_config = p.check(code_config)
    assert code_config["duty_rules"] == ["test rules"]

    config = p.parse(code_config)
    assert config
    print("config", config)
    assert config["duty_rules"] == [1]

    with open(f"{DATA_PATH}notice/duty.yaml", "r") as f:
        code_config = yaml.safe_load(f.read())
        result, message, code_config = SnippetRenderer.render(code_config, {"base.yaml": snippet})

    p = NoticeGroupConfigParser(2)
    code_config = p.check(code_config)
    assert code_config["version"] == MinVersion.USER_GROUP
    config = p.parse(code_config)
    assert config
    assert config["duty_rules"]


def test_invalid_version_notice_parse():
    with open(f"{DATA_PATH}notice/snippets/base.yaml", "r") as f:
        snippet = yaml.safe_load(f.read())

    with open(f"{DATA_PATH}notice/ops_invalid_version.yaml", "r") as f:
        code_config = yaml.safe_load(f.read())
        result, message, code_config = SnippetRenderer.render(code_config, {"base.yaml": snippet})

    p = NoticeGroupConfigParser(2)
    with pytest.raises(SchemaError):
        code_config = p.check(code_config)
    code_config["version"] = "1.0"
    code_config = p.check(code_config)
    config = p.parse(code_config)
    assert config


def test_valid_version_notice_parse():
    with open(f"{DATA_PATH}notice/snippets/base.yaml", "r") as f:
        snippet = yaml.safe_load(f.read())

    with open(f"{DATA_PATH}notice/ops_valid_version.yaml", "r") as f:
        code_config = yaml.safe_load(f.read())
        result, message, code_config = SnippetRenderer.render(code_config, {"base.yaml": snippet})

    p = NoticeGroupConfigParser(2)
    code_config = p.check(code_config)
    assert code_config["version"] == "1.0"
