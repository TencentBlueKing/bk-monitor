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

from bkmonitor.as_code.parse import import_action
from bkmonitor.as_code.parse_yaml import ActionConfigParser, SnippetRenderer
from bkmonitor.models import ActionConfig, ActionPlugin

pytestmark = pytest.mark.django_db

DATA_PATH = "bkmonitor/as_code/tests/data/"


def test_action_parse():
    with open(f"{DATA_PATH}action/snippets/base.yaml", "r") as f:
        snippet = yaml.safe_load(f.read())

    with open(f"{DATA_PATH}action/job.yaml", "r") as f:
        code_config = yaml.safe_load(f.read())
        result, message, code_config = SnippetRenderer.render(code_config, {"base.yaml": snippet})

    p = ActionConfigParser(2, [ActionPlugin(name="job", plugin_key="job", id=1, config_schema={}, backend_config={})])
    result, code_config = p.check(code_config)
    assert result
    config = p.parse(code_config)
    assert config

    with open(f"{DATA_PATH}action/webhook.yaml", "r") as f:
        code_config = yaml.safe_load(f.read())
        result, message, code_config = SnippetRenderer.render(code_config, {"base.yaml": snippet})

    p = ActionConfigParser(
        2, [ActionPlugin(name="webhook", plugin_key="webhook", id=1, config_schema={}, backend_config={})]
    )
    result, code_config = p.check(code_config)
    assert result
    config = p.parse(code_config)
    assert config


def test_notice_import():
    configs = {}
    with open(f"{DATA_PATH}action/job.yaml", "r") as f:
        configs["job.yaml"] = yaml.safe_load(f.read())

    with open(f"{DATA_PATH}action/webhook.yaml", "r") as f:
        configs["webhook.yaml"] = yaml.safe_load(f.read())

    with open(f"{DATA_PATH}action/snippets/base.yaml", "r") as f:
        snippet = yaml.safe_load(f.read())

    action_ids = import_action(
        bk_biz_id=2,
        app="app1",
        configs=configs,
        snippets={"base.yaml": snippet},
    )

    assert len(action_ids) == 2
    assert ActionConfig.objects.filter(bk_biz_id=2, app="app1", path__in=list(configs.keys())).count() == 2
