"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
from copy import deepcopy
from unittest import mock

import pytest
import yaml

from api.cmdb.define import TopoTree
from bkmonitor.as_code.parse import convert_rules
from bkmonitor.as_code.parse_yaml import StrategyConfigParser
from bkmonitor.strategy.new_strategy import Strategy

pytestmark = pytest.mark.django_db

DATA_PATH = "bkmonitor/as_code/tests/data/"


def load_rule_config(filename: str) -> dict:
    with open(f"{DATA_PATH}rule/{filename}") as f:
        return yaml.safe_load(f.read())


def make_parser(notice_group_ids=None, action_ids=None):
    return StrategyConfigParser(
        2,
        notice_group_ids or {},
        action_ids or {},
        {},
        {},
        {},
        {},
    )


def patch_cmdb_apis():
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

    search_dynamic_group = mock.patch("bkmonitor.as_code.parse.api.cmdb.search_dynamic_group").start()
    search_dynamic_group.side_effect = lambda *args, **kwargs: []


def test_strategy_parse_issue_config():
    parser = make_parser(notice_group_ids={"ops.yaml": 1})
    code_config = parser.check(load_rule_config("issue_config.yaml"))
    config = parser.parse(code_config)

    assert config["issue_config"] == {
        "is_enabled": True,
        "aggregate_dimensions": ["bk_target_ip"],
        "conditions": [
            {"key": "bk_target_ip", "method": "eq", "value": ["127.0.0.1"]},
            {"key": "bk_target_cloud_id", "method": "neq", "value": ["0"], "condition": "and"},
        ],
        "alert_levels": [1, 2],
    }


def test_strategy_parse_issue_config_absent_and_null():
    parser = make_parser(notice_group_ids={"ops.yaml": 1})

    config_without_issue = parser.parse(parser.check(load_rule_config("cpu_simple.yaml")))
    assert config_without_issue["issue_config"] is None

    null_issue_config = load_rule_config("issue_config.yaml")
    null_issue_config["issue_config"] = None
    config_with_null_issue = parser.parse(parser.check(null_issue_config))
    assert config_with_null_issue["issue_config"] is None


def test_convert_rules_passes_issue_config():
    patch_cmdb_apis()
    code_config = load_rule_config("issue_config.yaml")

    records = convert_rules(
        bk_biz_id=2,
        app="app1",
        configs={"issue_config.yaml": code_config},
        snippets={},
        notice_group_ids={"ops.yaml": 1},
        action_ids={},
    )

    assert len(records) == 1
    assert records[0]["validate_error"] is None
    assert records[0]["obj"] is not None
    assert records[0]["obj"].issue_config is not None
    assert records[0]["obj"].issue_config.to_dict() == {
        "is_enabled": True,
        "aggregate_dimensions": ["bk_target_ip"],
        "conditions": [
            {"key": "bk_target_ip", "method": "eq", "value": ["127.0.0.1"]},
            {"key": "bk_target_cloud_id", "method": "neq", "value": ["0"], "condition": "and"},
        ],
        "alert_levels": [1, 2],
    }


def test_strategy_unparse_issue_config_round_trip():
    parser = make_parser(notice_group_ids={"ops.yaml": 1})
    parsed = parser.parse(parser.check(load_rule_config("issue_config.yaml")))
    strategy = Strategy(**parsed)

    unparsed = parser.unparse(strategy.to_dict())

    # is_enabled=True 为默认值，不应出现在导出的 YAML 中
    assert unparsed["issue_config"] == {
        "dimensions": ["bk_target_ip"],
        "levels": ["fatal", "warning"],
        "conditions": 'bk_target_ip="127.0.0.1" and bk_target_cloud_id!="0"',
    }


def test_strategy_unparse_issue_config_disabled_emits_enabled_false():
    parser = make_parser(notice_group_ids={"ops.yaml": 1})
    code_config = deepcopy(load_rule_config("issue_config.yaml"))
    code_config["issue_config"]["enabled"] = False

    parsed = parser.parse(parser.check(code_config))
    strategy = Strategy(**parsed)
    unparsed = parser.unparse(strategy.to_dict())

    assert unparsed["issue_config"]["enabled"] is False


def test_strategy_unparse_without_issue_config():
    parser = make_parser(notice_group_ids={"ops.yaml": 1})
    parsed = parser.parse(parser.check(load_rule_config("cpu_simple.yaml")))
    strategy = Strategy(**parsed)

    unparsed = parser.unparse(strategy.to_dict())

    assert "issue_config" not in unparsed


def test_strategy_unparse_issue_config_null():
    parser = make_parser(notice_group_ids={"ops.yaml": 1})
    parsed = parser.parse(parser.check(load_rule_config("issue_config.yaml")))
    parsed["issue_config"] = None
    strategy = Strategy(**parsed)

    unparsed = parser.unparse(strategy.to_dict())

    assert "issue_config" not in unparsed


def test_strategy_issue_config_levels_round_trip():
    parser = make_parser(notice_group_ids={"ops.yaml": 1})
    code_config = deepcopy(load_rule_config("issue_config.yaml"))
    code_config["issue_config"]["levels"] = ["remind"]

    parsed = parser.parse(parser.check(code_config))
    strategy = Strategy(**parsed)
    unparsed = parser.unparse(strategy.to_dict())

    assert parsed["issue_config"]["alert_levels"] == [3]
    assert unparsed["issue_config"]["levels"] == ["remind"]


def test_rule_json_schema_contains_issue_config():
    with open("bkmonitor/as_code/json_schema/rule.json") as f:
        schema = json.load(f)

    issue_config_schema = schema["properties"]["issue_config"]["anyOf"][1]
    assert issue_config_schema["properties"]["levels"]["items"]["enum"] == ["fatal", "warning", "remind"]
    assert issue_config_schema["properties"]["conditions"]["type"] == "string"
