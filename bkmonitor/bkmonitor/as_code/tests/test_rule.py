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
from types import SimpleNamespace
from unittest import mock

import pytest
import xxhash
import yaml
from schema import SchemaError

from api.cmdb.define import TopoTree
from bkmonitor.as_code.parse import convert_rules
from bkmonitor.as_code.parse_yaml import StrategyConfigParser
from bkmonitor.as_code.schema import StrategySchema
from bkmonitor.strategy.new_strategy import Strategy

pytestmark = pytest.mark.django_db(databases="__all__")

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

    return get_topo_tree, get_dynamic_query, search_dynamic_group


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


def _mock_empty_strategies():
    """mock 业务下无存量策略，避免 convert_rules 前置查库受多库限制影响。"""
    strategies_qs = mock.MagicMock()
    strategies_qs.filter.return_value = []
    strategies_qs.__iter__.side_effect = lambda: iter([])
    filter_qs = mock.MagicMock()
    filter_qs.only.return_value = strategies_qs
    return mock.patch("bkmonitor.as_code.parse.StrategyModel.objects.filter", return_value=filter_qs)


def test_convert_rules_passes_issue_config():
    get_topo_tree, get_dynamic_query, search_dynamic_group = patch_cmdb_apis()
    code_config = load_rule_config("issue_config.yaml")

    with _mock_empty_strategies():
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
    # 有变更配置时仍需拉取 CMDB 映射
    get_topo_tree.assert_called_once_with(bk_biz_id=2)
    assert get_dynamic_query.call_count == 2
    search_dynamic_group.assert_called_once_with(bk_biz_id=2, bk_obj_id="host")


def test_convert_rules_skips_cmdb_when_hash_unchanged():
    """全部策略 hash 未变更时，不应发起 CMDB 远程调用。"""
    get_topo_tree, get_dynamic_query, search_dynamic_group = patch_cmdb_apis()
    code_config = load_rule_config("cpu_simple.yaml")
    hash_str = xxhash.xxh3_128_hexdigest(json.dumps(code_config))
    old_strategy = SimpleNamespace(id=1, path="cpu_simple.yaml", hash=hash_str, name="CPU单核使用率")

    strategies_qs = mock.MagicMock()
    strategies_qs.filter.return_value = [old_strategy]
    strategies_qs.__iter__.side_effect = lambda: iter([old_strategy])
    filter_qs = mock.MagicMock()
    filter_qs.only.return_value = strategies_qs

    with mock.patch("bkmonitor.as_code.parse.StrategyModel.objects.filter", return_value=filter_qs):
        records = convert_rules(
            bk_biz_id=2,
            app="app1",
            configs={"cpu_simple.yaml": deepcopy(code_config)},
            snippets={},
            notice_group_ids={"ops.yaml": 1},
            action_ids={},
        )

    assert records == []
    get_topo_tree.assert_not_called()
    get_dynamic_query.assert_not_called()
    search_dynamic_group.assert_not_called()


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


def _make_notice_db_dict(voice_notice=None):
    """构造 DB 形态的 notice 子树，仅保留 unparse 路径需要的字段。"""
    config = {
        "notify_interval": 7200,
        "interval_notify_mode": "standard",
        "template": [],
    }
    if voice_notice is not None:
        config["voice_notice"] = voice_notice
    return {
        "user_groups": [1],
        "signal": ["abnormal"],
        "options": {
            "exclude_notice_ways": {},
            "converge_config": {"need_biz_converge": True},
            "assign_mode": ["only_notice", "by_rule"],
            "chart_image_enabled": True,
        },
        "config": config,
    }


def test_strategy_parse_voice_notice_serial():
    """YAML 显式写 voice_notice=serial → parsed notice.config 透传字段。"""
    parser = make_parser(notice_group_ids={"ops.yaml": 1})
    code_config = deepcopy(load_rule_config("cpu_simple.yaml"))
    code_config["notice"]["voice_notice"] = "serial"

    parsed = parser.parse(parser.check(code_config))
    assert parsed["notice"]["config"]["voice_notice"] == "serial"


def test_strategy_parse_voice_notice_omitted():
    """YAML 未写 voice_notice → parsed notice.config 不写入字段，由后端 serializer 落到 default。"""
    parser = make_parser(notice_group_ids={"ops.yaml": 1})
    parsed = parser.parse(parser.check(load_rule_config("cpu_simple.yaml")))
    assert "voice_notice" not in parsed["notice"]["config"]


def test_strategy_unparse_voice_notice_serial_emits():
    """DB 中 voice_notice=serial → unparse YAML 写出 serial。"""
    parser = make_parser(notice_group_ids={"ops.yaml": 1})
    code_config: dict = {}
    parser.update_notice_config({"notice": _make_notice_db_dict("serial")}, code_config)

    assert code_config["notice"]["voice_notice"] == "serial"


def test_strategy_unparse_voice_notice_parallel_omitted():
    """DB 中 voice_notice=parallel（默认）→ unparse YAML 省略字段，保持 YAML 简洁。"""
    parser = make_parser(notice_group_ids={"ops.yaml": 1})
    code_config: dict = {}
    parser.update_notice_config({"notice": _make_notice_db_dict("parallel")}, code_config)

    assert "voice_notice" not in code_config["notice"]


def test_strategy_unparse_voice_notice_absent_omitted():
    """DB 中 voice_notice 字段缺失（历史数据）→ unparse YAML 省略字段，不报错。"""
    parser = make_parser(notice_group_ids={"ops.yaml": 1})
    code_config: dict = {}
    parser.update_notice_config({"notice": _make_notice_db_dict(None)}, code_config)

    assert "voice_notice" not in code_config["notice"]


def test_rule_json_schema_declares_voice_notice():
    with open("bkmonitor/as_code/json_schema/rule.json") as f:
        schema = json.load(f)

    notice_props = schema["properties"]["notice"]["properties"]
    assert "voice_notice" in notice_props
    assert notice_props["voice_notice"]["enum"] == ["parallel", "serial"]
    assert notice_props["voice_notice"]["default"] == "parallel"


def _make_schema_input(voice_notice=None):
    """构造能通过 StrategySchema 校验的最小 YAML 配置。"""
    notice: dict = {"user_groups": ["ops.yaml"]}
    if voice_notice is not None:
        notice["voice_notice"] = voice_notice
    return {
        "name": "voice_notice_schema_test",
        "query": {
            "data_source": "bk_monitor",
            "data_type": "time_series",
            "expression": "",
            "query_configs": [{"metric": "system.cpu_detail.usage", "method": "avg", "interval": 60}],
        },
        "detect": {
            "algorithm": {"fatal": [{"type": "Threshold", "config": ">1"}]},
            "trigger": "1/5/5",
        },
        "notice": notice,
    }


def test_strategy_schema_passes_voice_notice_serial():
    """YAML 显式写 voice_notice=serial → StrategySchema.validate 透传保留。

    回归保护：若该字段被加入 ignore_extra_keys 静默丢弃，parse_yaml 端的
    透传分支会变成死代码（line 472），用户配置永久失效。
    """
    validated = StrategySchema.validate(_make_schema_input("serial"))
    assert validated["notice"]["voice_notice"] == "serial"


def test_strategy_schema_passes_voice_notice_parallel():
    """YAML 显式写 voice_notice=parallel → StrategySchema.validate 透传保留。"""
    validated = StrategySchema.validate(_make_schema_input("parallel"))
    assert validated["notice"]["voice_notice"] == "parallel"


def test_strategy_schema_omits_voice_notice_when_absent():
    """YAML 未声明 voice_notice → StrategySchema.validate 不写入字段（不设 default）。

    回归保护：保留"未声明 → dict 不含 key"的语义，让 parse_yaml.py 的
    `if "voice_notice" in config["notice"]` 判定有意义；避免 DB.template_detail
    落入冗余字段，由 fta_action 运行时 .get 兜底默认 parallel。
    """
    validated = StrategySchema.validate(_make_schema_input(None))
    assert "voice_notice" not in validated["notice"]


def test_strategy_schema_rejects_invalid_voice_notice():
    """YAML 写非法值 → StrategySchema 拒绝（区别于 additionalProperties:true 静默丢字段）。"""
    with pytest.raises(SchemaError):
        StrategySchema.validate(_make_schema_input("invalid_mode"))
