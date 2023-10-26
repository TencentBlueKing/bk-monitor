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
import mock
import pytest
import yaml

from api.cmdb.define import TopoTree
from bkmonitor.as_code.parse import import_strategy
from bkmonitor.as_code.parse_yaml import SnippetRenderer, StrategyConfigParser
from bkmonitor.models import StrategyModel

pytestmark = pytest.mark.django_db

DATA_PATH = "bkmonitor/as_code/tests/data/"


def test_strategy_parse():
    with open(f"{DATA_PATH}rule/snippets/base.yaml", "r") as f:
        snippet = yaml.safe_load(f.read())

    with open(f"{DATA_PATH}rule/all.yaml", "r") as f:
        code_config = yaml.safe_load(f.read())
        result, message, code_config = SnippetRenderer.render(code_config, {"base.yaml": snippet})

    p = StrategyConfigParser(2, {}, {}, {}, {}, {})
    result, code_config = p.check(code_config)
    assert result
    config = p.parse(code_config)
    assert config

    with open(f"{DATA_PATH}rule/cpu_simple.yaml", "r") as f:
        code_config = yaml.safe_load(f.read())
        result, message, code_config = SnippetRenderer.render(code_config, {"base.yaml": snippet})

    p = StrategyConfigParser(2, {}, {}, {}, {}, {})
    result, code_config = p.check(code_config)
    assert result
    config = p.parse(code_config)
    assert config


def test_strategy_import():
    get_topo_tree = mock.patch("bkmonitor.as_code.parse.api.cmdb.get_topo_tree").start()
    get_topo_tree.side_effect = lambda *args, **kwargs: TopoTree(
        {
            "bk_inst_id": 2,
            "bk_inst_name": "blueking",
            "bk_obj_id": "biz",
            "bk_obj_name": "business",
            "child": [
                {
                    "bk_inst_id": 3,
                    "bk_inst_name": "job",
                    "bk_obj_id": "set",
                    "bk_obj_name": "set",
                    "child": [
                        {
                            "bk_inst_id": 5,
                            "bk_inst_name": "job",
                            "bk_obj_id": "module",
                            "bk_obj_name": "module",
                            "child": [],
                        }
                    ],
                }
            ],
        }
    )

    get_dynamic_query = mock.patch("bkmonitor.as_code.parse.api.cmdb.get_dynamic_query").start()
    get_dynamic_query.side_effect = lambda *args, **kwargs: {"children": []}

    configs = {}
    with open(f"{DATA_PATH}rule/all.yaml", "r") as f:
        configs["all.yaml"] = yaml.safe_load(f.read())

    with open(f"{DATA_PATH}rule/cpu_simple.yaml", "r") as f:
        configs["cpu_simple.yaml"] = yaml.safe_load(f.read())

    with open(f"{DATA_PATH}rule/cpu_simple_with_snippet.yaml", "r") as f:
        configs["cpu_simple_with_snippet.yaml"] = yaml.safe_load(f.read())

    with open(f"{DATA_PATH}rule/snippets/base.yaml", "r") as f:
        snippet = yaml.safe_load(f.read())

    import_strategy(
        bk_biz_id=2,
        app="app1",
        configs=configs,
        snippets={"base.yaml": snippet},
        notice_group_ids={},
        action_ids={},
    )

    assert StrategyModel.objects.filter(bk_biz_id=2, app="app1", path__in=list(configs.keys())).count() == 3
