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
import copy
import datetime
import re
from abc import abstractmethod
from copy import deepcopy
from typing import Dict, List, Optional, Tuple

from django.conf import settings
from rest_framework.exceptions import ValidationError

from bkmonitor.action.serializers import DutyRuleDetailSlz
from bkmonitor.as_code.constants import MaxVersion
from bkmonitor.as_code.ply.error import ParseError
from bkmonitor.as_code.ply.expression import expression_lexer, expression_parser
from bkmonitor.as_code.schema import (
    DEFAULT_TEMPLATE_CONTENT,
    DEFAULT_TEMPLATE_TITLE,
    ActionSchema,
    AssignGroupRuleSchema,
    DutyRuleSchema,
    StrategySchema,
    UserGroupSchema,
)
from bkmonitor.as_code.utils import (
    create_conditions_expression,
    create_function_expression,
    create_threshold_expression,
    get_metric_id,
    parse_conditions,
    parse_function,
    parse_metric_id,
    parse_threshold,
    parse_user,
)
from bkmonitor.models import ActionPlugin, AlgorithmModel, DutyRule, MetricListCache
from bkmonitor.strategy.new_strategy import Algorithm
from bkmonitor.utils.dict import nested_diff, nested_update
from constants.action import DEFAULT_CONVERGE_CONFIG, NoticeChannel, NoticeWay
from constants.common import DutyCategory, DutyGroupType
from constants.data_source import DataSourceLabel, DataTypeLabel

LEVEL_NAME_TO_ID = {"fatal": 1, "warning": 2, "remind": 3}
LEVEL_ID_TO_NAME = {v: k for k, v in LEVEL_NAME_TO_ID.items()}
ACTION_PHASE_NAME_TO_ID = {"execute_failed": 1, "execute_success": 2, "execute": 3}
ACTION_PHASE_ID_TO_NAME = {v: k for k, v in ACTION_PHASE_NAME_TO_ID.items()}


class SnippetRenderer:
    """
    片段渲染
    """

    @classmethod
    def render(cls, config: Dict, snippets: Dict[str, Dict]) -> Tuple[bool, str, Optional[Dict]]:
        """
        片段渲染
        """
        config = deepcopy(config)

        snippet_name = config.pop("snippet", None)
        if not snippet_name:
            return True, "", config

        snippet = snippets.get(snippet_name)
        if not snippet:
            return False, "snippet not exists", None

        return True, "", nested_update(snippet, config)

    @classmethod
    def unrender(cls, config: Dict, snippet_name: str, snippet: Dict):
        """
        片段逆渲染
        """
        diff = nested_diff(config, snippet)
        diff["snippet"] = snippet_name
        return diff


class BaseConfigParser:
    """
    配置解析器 基类
    """

    def __init__(self, bk_biz_id: int):
        self.bk_biz_id = bk_biz_id

    @abstractmethod
    def check(self, config: Dict) -> Tuple[bool, Optional[Dict]]:
        """
        配置正确性校验
        """

    @abstractmethod
    def parse(self, config: Dict) -> Dict:
        """
        配置解析
        """

    @abstractmethod
    def unparse(self, config: Dict) -> Dict:
        """
        配置反解析
        """


class StrategyConfigParser(BaseConfigParser):
    """
    策略配置解析器
    """

    def __init__(
        self,
        bk_biz_id: int,
        notice_group_ids: Dict[str, int],
        action_ids: Dict[str, int],
        topo_nodes: Dict[str, Dict],
        service_templates: Dict[str, Dict],
        set_templates: Dict[str, Dict],
        dynamic_groups: Dict[str, Dict],
    ):
        super(StrategyConfigParser, self).__init__(bk_biz_id)

        self.topo_nodes = topo_nodes
        self.service_templates = service_templates
        self.set_templates = set_templates
        self.dynamic_groups = dynamic_groups
        self.notice_group_ids = notice_group_ids
        self.action_ids = action_ids

        self.reverse_topo_nodes = {f"{v['bk_obj_id']}|{v['bk_inst_id']}": k for k, v in topo_nodes.items()}
        self.reverse_service_templates = {str(v["bk_inst_id"]): k for k, v in service_templates.items()}
        self.reverse_set_templates = {str(v["bk_inst_id"]): k for k, v in set_templates.items()}
        self.reverse_dynamic_groups = {v["dynamic_group_id"]: k for k, v in dynamic_groups.items()}
        self.reverse_notice_group_ids = {v: k for k, v in notice_group_ids.items()}
        self.reverse_action_ids = {v: k for k, v in action_ids.items()}

    @classmethod
    def parse_algorithm(cls, config: Dict) -> Dict:
        algorithm_type = config["type"]
        algorithm_config = {}
        if algorithm_type == AlgorithmModel.AlgorithmChoices.Threshold:
            algorithm_config = parse_threshold(config["config"])
        else:
            serializer_class = Algorithm.Serializer.AlgorithmSerializers.get(algorithm_type)
            if serializer_class:
                serializer = serializer_class(data=config["config"])
                serializer.is_valid()
                algorithm_config = serializer.validated_data
        return {"type": algorithm_type, "config": algorithm_config, "unit_prefix": "", "level": 0}

    @staticmethod
    def get_time_ranges(config: Dict) -> list:
        time_ranges = []
        for time_range in config["active_time"].split(","):
            if not time_range:
                continue
            start, end = time_range.split("--")
            time_ranges.append({"start": start.strip(), "end": end.strip()})

        return time_ranges

    def get_query_configs_n_name(self, config: dict, detect: dict) -> Tuple[list, str, str]:
        # 查询配置
        query_configs = []

        try:
            expression_tokens = expression_parser.parse(config["query"]["expression"], lexer=expression_lexer)
        except ParseError:
            expression_tokens = [config["query"]["expression"]]

        if not config["query"]["query_configs"]:
            raise Exception("query_configs is empty")

        scenario = "other_rt"
        for origin_config in config["query"]["query_configs"]:
            # grafana类型策略处理
            if config["query"]["data_source"] == DataSourceLabel.DASHBOARD:
                query_configs.append(
                    {
                        "data_source_label": config["query"]["data_source"],
                        "data_type_label": config["query"]["data_type"],
                        "alias": origin_config["alias"],
                        "dashboard_id": origin_config["dashboard_id"],
                        "panel_id": origin_config["panel_id"],
                        "ref_id": origin_config["ref_id"],
                        "variables": origin_config.get("variables", {}),
                    }
                )
                continue

            # fta依赖detect表达式进行检测
            if config["query"]["data_type"] == DataTypeLabel.ALERT:
                detect["expression"] = config["query"]["expression"]

            metric_dict = parse_metric_id(
                config["query"]["data_source"], config["query"]["data_type"], origin_config["metric"]
            )
            query_config = {
                "data_source_label": config["query"]["data_source"],
                "data_type_label": config["query"]["data_type"],
                "alias": origin_config["alias"],
                "query_string": origin_config["query_string"],
                "functions": [parse_function(function) for function in origin_config["functions"]],
                "agg_method": origin_config["method"].upper(),
                "agg_interval": origin_config["interval"],
                "agg_dimension": origin_config["group_by"],
                "agg_condition": parse_conditions(origin_config["where"]),
                "unit": origin_config["unit"],
                **metric_dict,
            }

            query_configs.append(query_config)

            # 补充时间字段
            if "time_field" in origin_config:
                query_config["time_field"] = origin_config["time_field"]

            metric_query_params = {
                "data_source_label": query_config["data_source_label"],
                "data_type_label": query_config["data_type_label"],
            }
            if query_config.get("metric_field"):
                metric_query_params["metric_field"] = query_config["metric_field"]
            if query_config.get("index_set_id"):
                metric_query_params["related_id"] = query_config["index_set_id"]
            elif "result_table_id" in query_config:
                metric_query_params["result_table_id"] = query_config["result_table_id"]

            # 只查询时序型或日志型指标
            if metric_query_params.get("related_id") or metric_query_params.get("metric_field"):
                metric = MetricListCache.objects.filter(
                    bk_biz_id__in=[0, self.bk_biz_id], **metric_query_params
                ).first()
            else:
                metric = None
            # 根据指标信息获取场景及时间字段
            if metric:
                scenario = metric.result_table_label
                if metric.extend_fields.get("time_field"):
                    query_config["time_field"] = metric.extend_fields["time_field"]

                # 替换表达式中的别名
                for index, token in enumerate(expression_tokens):
                    if token == origin_config["alias"]:
                        expression_tokens[index] = f"{query_config['agg_method']}({metric.metric_field_name})"
                        break

        # 如果是promql，使用promql作为名称，否则使用表达式作为名称
        if query_configs[0].get("promql"):
            name = query_configs[0]["promql"]
        else:
            name = " ".join(expression_tokens)
        return query_configs, name, scenario

    def parse(self, config: Dict) -> Dict:
        # 生效时间段解析 yaml -> config
        time_ranges = self.get_time_ranges(config)

        # 检测配置解析
        trigger_count, trigger_window, recovery_count = [int(i) for i in config["detect"]["trigger"].split("/")]
        recovery_config = {"check_window": recovery_count, "status_setter": "recovery"}
        trigger_config = {
            "check_window": trigger_window,
            "count": trigger_count,
            "uptime": {"calendars": config["active_calendars"], "time_ranges": time_ranges},
        }
        detect = {
            "connector": config["detect"]["algorithm"]["operator"],
            "expression": "",
            "recovery_config": recovery_config,
            "trigger_config": trigger_config,
        }

        if DataTypeLabel.ALERT == config["query"]["data_type"]:
            detect["expression"] = config["query"]["expression"]

        detects = [
            dict({"level": level}, **detect)
            for level_name, level in LEVEL_NAME_TO_ID.items()
            if level_name in config["detect"]["algorithm"]
        ]

        # 无数据告警配置
        no_data_config = {
            "is_enabled": config["detect"]["nodata"]["enabled"],
            "continuous": config["detect"]["nodata"]["continuous"],
            "agg_dimension": config["detect"]["nodata"]["dimensions"],
            "level": LEVEL_NAME_TO_ID[config["detect"]["nodata"]["level"]],
        }

        # 查询配置解析
        query_configs, name, scenario = self.get_query_configs_n_name(config, detect)

        # 监控目标
        if "target" in config["query"]:
            target_type = config["query"]["target"]["type"]
            target_nodes = config["query"]["target"]["nodes"]
            nodes = []
            field = ""
            target_prefix = "service" if scenario in ("component", "service_module", "service_process") else "host"
            if target_type == "host":
                for node in target_nodes:
                    result = node.split("|")
                    if len(result) == 2:
                        ip, bk_cloud_id = result
                    elif len(result) == 1:
                        ip = result[0]
                        bk_cloud_id = 0
                    else:
                        continue
                    nodes.append({"ip": ip, "bk_cloud_id": int(bk_cloud_id)})
                field = "ip"
            elif target_type == "topo":
                field = f"{target_prefix}_topo_node"
                nodes = [self.topo_nodes[node] for node in target_nodes if node in self.topo_nodes]
            elif target_type == "service_template":
                field = f"{target_prefix}_service_template"
                nodes = [self.service_templates[node] for node in target_nodes if node in self.service_templates]
            elif target_type == "set_template":
                field = f"{target_prefix}_set_template"
                nodes = [self.set_templates[node] for node in target_nodes if node in self.set_templates]
            elif target_type == "dynamic_group":
                field = "dynamic_group"
                nodes = [self.dynamic_groups[node] for node in target_nodes if node in self.dynamic_groups]

            if nodes:
                target = [[{"field": field, "method": "eq", "value": nodes}]]
            else:
                target = [[]]
        else:
            target = [[]]

        # 算法配置
        algorithms = []
        unit_prefix = config["detect"]["algorithm"]["unit"] or ""
        for level_name, level in LEVEL_NAME_TO_ID.items():
            if level_name not in config["detect"]["algorithm"] or config["query"]["data_type"] == DataTypeLabel.ALERT:
                continue

            if (config["query"]["data_source"], config["query"]["data_type"]) == (
                DataSourceLabel.BK_MONITOR_COLLECTOR,
                DataTypeLabel.EVENT,
            ):
                algorithms.append({"type": "", "config": [], "unit_prefix": "", "level": level})
                break

            for algorithm_config in config["detect"]["algorithm"][level_name]:
                algorithm = self.parse_algorithm(algorithm_config)
                algorithm["level"] = level
                algorithm["unit_prefix"] = unit_prefix
                algorithms.append(algorithm)

        item = {
            "name": name,
            "algorithms": algorithms,
            "no_data_config": no_data_config,
            "query_configs": query_configs,
            "expression": config["query"]["expression"],
            "functions": [parse_function(function) for function in config["query"].get("functions", [])],
            "target": target,
        }

        # 通知配置
        signal = set(config["notice"]["signal"])
        if "abnormal" in signal:
            signal.add("no_data")

        notice_group_ids = []
        for notice_group in config["notice"]["user_groups"]:
            if notice_group not in self.notice_group_ids:
                raise Exception(f"notice_group({notice_group}) not exists")
            notice_group_ids.append(self.notice_group_ids[notice_group])

        upgrade_groups = []
        for upgrade_group in config["notice"].get("upgrade_config", {}).get("user_groups", []):
            if upgrade_group not in self.notice_group_ids:
                raise Exception(f"notice_group({upgrade_group}) not exists")
            upgrade_groups.append(self.notice_group_ids[upgrade_group])
        notice_converge_config = copy.deepcopy(DEFAULT_CONVERGE_CONFIG)
        # 告警风暴默认打开
        notice_converge_config["need_biz_converge"] = config["notice"].get("biz_converge", True)
        notice = {
            "user_groups": notice_group_ids,
            "signal": list(signal),
            "options": {
                "converge_config": notice_converge_config,
                "exclude_notice_ways": {
                    "recovered": config["notice"]["exclude_notice_ways"]["recovered"],
                    "closed": config["notice"]["exclude_notice_ways"]["closed"],
                },
                "noise_reduce_config": {}
                if not config["notice"].get("noise_reduce", {}).get("enabled")
                else {
                    "count": config["notice"]["noise_reduce"]["abnormal_ratio"],
                    "dimensions": config["notice"]["noise_reduce"]["dimensions"],
                    "is_enabled": True,
                    "timedelta": 5,
                    "unit": "percent",
                },
                "assign_mode": config["notice"]["assign_mode"],
                "chart_image_enabled": config["notice"]["chart_image_enabled"],
                "upgrade_config": {}
                if not config["notice"].get("upgrade_config")
                else {
                    "is_enabled": config["notice"]["upgrade_config"]["enabled"],
                    "user_groups": upgrade_groups,
                    "upgrade_interval": config["notice"]["upgrade_config"]["interval"],
                },
                "start_time": "00:00:00",
                "end_time": "23:59:59",
            },
            "relate_type": "NOTICE",
            "config": {
                "need_poll": True,
                "notify_interval": config["notice"]["interval"] * 60,
                "interval_notify_mode": config["notice"]["interval_mode"],
                "template": [
                    {
                        "signal": "abnormal",
                        "message_tmpl": config["notice"]["template"]["abnormal"]["content"],
                        "title_tmpl": config["notice"]["template"]["abnormal"]["title"],
                    },
                    {
                        "signal": "recovered",
                        "message_tmpl": config["notice"]["template"]["recovered"]["content"],
                        "title_tmpl": config["notice"]["template"]["recovered"]["title"],
                    },
                    {
                        "signal": "closed",
                        "message_tmpl": config["notice"]["template"]["closed"]["content"],
                        "title_tmpl": config["notice"]["template"]["closed"]["title"],
                    },
                ],
            },
        }

        # 动作配置
        actions = []
        for action in config["actions"]:
            if action["action"] not in self.action_ids:
                raise Exception(f"action({action['action']}) not exists")

            actions.append(
                {
                    "user_groups": notice_group_ids,
                    "signal": action["signal"],
                    "options": {
                        "converge_config": {
                            "is_enabled": action["converge"]["enabled"],
                            "converge_func": action["converge"]["func"],
                            "timedelta": action["converge"]["interval"] * 60,
                            "count": action["converge"]["count"],
                            "condition": [{"dimension": "action_info", "value": ["self"]}],
                            "need_biz_converge": False,
                        },
                        "start_time": "00:00:00",
                        "end_time": "23:59:59",
                    },
                    "relate_type": "ACTION",
                    "config_id": self.action_ids[action["action"]],
                    "config": {},
                }
            )

        strategy = {
            "bk_biz_id": self.bk_biz_id,
            "scenario": scenario,
            "is_enabled": config["enabled"],
            "labels": config["labels"],
            "name": config["name"],
            "priority": config["priority"],
            "items": [item],
            "detects": detects,
            "notice": notice,
            "actions": actions,
        }

        return strategy

    @staticmethod
    def update_active_time(config: Dict, code_config: Dict):
        uptime = config["detects"][0]["trigger_config"].get("uptime")
        if uptime:
            active_times = []
            for time_range in uptime.get("time_ranges", []):
                active_times.append(f"{time_range['start']} -- {time_range['end']}")
            active_time = ",".join(active_times)
            if active_time and active_time != "00:00 -- 23:59":
                code_config["active_time"] = active_time

            calendars = uptime.get("calendars", [])
            if calendars:
                code_config["active_calendar"] = calendars

    @staticmethod
    def update_algorithm_config(data_source: str, data_type: str, config: dict, item: dict, detect: dict):
        # 关联告警不需要配置算法
        if data_type == DataTypeLabel.ALERT:
            level_name = LEVEL_ID_TO_NAME[config["detects"][0]["level"]]
            detect["algorithm"][level_name] = []
        else:
            algorithm_configs = item["algorithms"]
            for algorithm_config in algorithm_configs:
                if algorithm_config.get("unit_prefix"):
                    detect["algorithm"]["unit"] = algorithm_config["unit_prefix"]

                if algorithm_config["type"] == "Threshold":
                    algorithm = {"type": "Threshold", "config": create_threshold_expression(algorithm_config["config"])}
                else:
                    algorithm = {"type": algorithm_config["type"], "config": algorithm_config["config"]}
                level_name = LEVEL_ID_TO_NAME[algorithm_config["level"]]
                if level_name not in detect["algorithm"]:
                    detect["algorithm"][level_name] = []
                if (data_source, data_type) != (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.EVENT):
                    detect["algorithm"][level_name].append(algorithm)

    def update_target(self, item: dict, query: dict):
        # 监控目标配置
        if item["target"] and item["target"][0]:
            target = item["target"][0][0]
            nodes = []
            if target["field"].endswith("topo_node"):
                target_type = "topo"
                for value in target["value"]:
                    if value["bk_obj_id"] == "biz":
                        continue
                    node = f"{value['bk_obj_id']}|{value['bk_inst_id']}"
                    if node not in self.reverse_topo_nodes:
                        continue
                    nodes.append(self.reverse_topo_nodes[node])
            elif target["field"].endswith("service_template"):
                target_type = "service_template"
                for value in target["value"]:
                    template_id = str(value["bk_inst_id"])
                    if template_id not in self.reverse_service_templates:
                        continue
                    nodes.append(self.reverse_service_templates[template_id])
            elif target["field"].endswith("set_template"):
                target_type = "set_template"
                for value in target["value"]:
                    template_id = str(value["bk_inst_id"])
                    if template_id not in self.reverse_set_templates:
                        continue
                    nodes.append(self.reverse_set_templates[template_id])
            elif target["field"] in ["ip", "bk_target_ip"]:
                target_type = "host"
                for value in target["value"]:
                    ip = value.get("ip") or value["bk_target_ip"]
                    bk_cloud_id = value.get("bk_cloud_id", value.get("bk_target_cloud_id", 0))
                    nodes.append(f"{ip}|{bk_cloud_id}")
            elif target["field"] == "dynamic_group":
                target_type = "dynamic_group"
                for value in target["value"]:
                    dynamic_group_id = value["dynamic_group_id"]
                    if dynamic_group_id not in self.reverse_dynamic_groups:
                        continue
                    nodes.append(self.reverse_dynamic_groups[dynamic_group_id])

            if nodes:
                query["target"] = {"type": target_type, "nodes": nodes}

    def update_notice_config(self, config: dict, code_config: dict):
        # 通知配置
        notice_config = config["notice"]
        notice = {
            "user_groups": [],
            "signal": [signal for signal in notice_config["signal"] if signal != "no_data"],
        }
        for notice_group_id in notice_config["user_groups"]:
            if notice_group_id in self.reverse_notice_group_ids:
                notice["user_groups"].append(self.reverse_notice_group_ids[notice_group_id])
            else:
                raise Exception(f"notice_group({notice_group_id}) not exists in rule({config['name']})")

        # 通知模板
        notice_template = {}
        for template_config in notice_config["config"]["template"]:
            if (
                template_config["title_tmpl"] == DEFAULT_TEMPLATE_TITLE
                and template_config["message_tmpl"] == DEFAULT_TEMPLATE_CONTENT
            ):
                continue

            notice_template[template_config["signal"]] = {
                "title": template_config["title_tmpl"],
                "content": template_config["message_tmpl"],
            }
        if notice_template:
            notice["template"] = notice_template

        exclude_notice_ways = copy.deepcopy(notice_config["options"].get("exclude_notice_ways", {}))
        if "closed" in exclude_notice_ways and not exclude_notice_ways["closed"]:
            del exclude_notice_ways["closed"]
        if "recovered" in exclude_notice_ways and not exclude_notice_ways["recovered"]:
            del exclude_notice_ways["recovered"]
        if "ack" in exclude_notice_ways and not exclude_notice_ways["ack"]:
            del exclude_notice_ways["ack"]
        if exclude_notice_ways:
            notice["exclude_notice_ways"] = exclude_notice_ways

        noise_reduce = notice_config["options"].get("noise_reduce_config", {})
        if noise_reduce and noise_reduce.get("is_enabled"):
            notice["noise_reduce"] = {
                "enabled": True,
                "dimensions": noise_reduce["dimensions"],
                "abnormal_ratio": noise_reduce["count"],
            }

        biz_converge = notice_config["options"]["converge_config"]["need_biz_converge"]
        if not biz_converge:
            notice["biz_converge"] = biz_converge

        notice["assign_mode"] = notice_config["options"].get("assign_mode") or ["only_notice", "by_rule"]

        if notice_config["options"].get("chart_image_enabled") is False:
            notice["chart_image_enabled"] = False

        upgrade_config = notice_config["options"].get("upgrade_config") or {}
        if upgrade_config.get("is_enabled"):
            upgrade_groups = []
            for group_id in upgrade_config["user_groups"]:
                if group_id in self.reverse_notice_group_ids:
                    upgrade_groups.append(self.reverse_notice_group_ids[group_id])
                else:
                    raise Exception(f"upgrade_notice_group({group_id}) not exists in rule({config['name']})")
            notice["upgrade_config"] = {
                "enabled": True,
                "user_groups": upgrade_groups,
                "interval": upgrade_config["upgrade_interval"],
            }

        interval_mode = notice_config["config"]["interval_notify_mode"]
        if interval_mode != "standard":
            notice["interval_mode"] = interval_mode

        interval = notice_config["config"]["notify_interval"] // 60
        if interval != 120:
            notice["interval"] = interval

        code_config["notice"] = notice

    def unparse(self, config: Dict) -> Dict:
        # config --> yaml
        code_config = {"name": config["name"], "version": MaxVersion.STRATEGY}

        if config["priority"] is not None:
            code_config["priority"] = config["priority"]

        if config["labels"]:
            code_config["labels"] = config["labels"]
        if not config["is_enabled"]:
            code_config["enabled"] = config["is_enabled"]

        # 生效时间
        self.update_active_time(config, code_config)

        item = config["items"][0]

        # 查询配置
        query_configs = item["query_configs"]
        data_source = query_configs[0]["data_source_label"]
        data_type = query_configs[0]["data_type_label"]
        query = {"data_source": data_source, "data_type": data_type, "query_configs": []}
        for query_config in query_configs:
            # grafana类型策略处理
            if data_source == DataSourceLabel.DASHBOARD:
                code_query_config = {
                    "dashboard_id": query_config["dashboard_id"],
                    "panel_id": query_config["panel_id"],
                    "ref_id": query_config["ref_id"],
                    "variables": query_config.get("variables", {}),
                }
                query["query_configs"].append(code_query_config)
                continue

            code_query_config = {"metric": get_metric_id(data_source, data_type, query_config)}
            # 如果需要的话，自定义上报和插件采集类指标导出时将结果表ID部分替换为 data_label
            data_label = query_config.get("data_label", None)
            if (
                settings.ENABLE_DATA_LABEL_EXPORT
                and data_label
                and (
                    query_config.get("data_source_label", None)
                    in [DataSourceLabel.BK_MONITOR_COLLECTOR, DataSourceLabel.CUSTOM]
                )
            ):
                code_query_config["metric"] = re.sub(
                    rf"\b{query_config['result_table_id']}\b", data_label, code_query_config["metric"]
                )
            field_mapping = {
                "query_string": "query_string",
                "agg_method": "method",
                "agg_interval": "interval",
                "agg_dimension": "group_by",
                "unit": "unit",
            }

            for field, code_field in field_mapping.items():
                if query_config.get(field):
                    code_query_config[code_field] = query_config[field]

            if (data_source, data_type) in (
                (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES),
                (DataSourceLabel.CUSTOM, DataTypeLabel.TIME_SERIES),
            ) or data_source == DataSourceLabel.BK_FTA:
                code_query_config["alias"] = query_config["alias"]

            if query_config.get("functions"):
                code_query_config["functions"] = [
                    create_function_expression(function) for function in query_config["functions"]
                ]

            if query_config.get("agg_condition"):
                code_query_config["where"] = create_conditions_expression(query_config["agg_condition"])

            query["query_configs"].append(code_query_config)

        # 多指标计算及关联告警表达式
        if data_type == DataTypeLabel.ALERT:
            query["expression"] = config["detects"][0]["expression"]
        elif (data_source, data_type) in (
            (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES),
            (DataSourceLabel.CUSTOM, DataTypeLabel.TIME_SERIES),
        ):
            query["expression"] = item["expression"]

        # 表达式
        if item["functions"]:
            query["functions"] = [create_function_expression(function) for function in item["functions"]]

        self.update_target(item, query)
        code_config["query"] = query

        # 检测配置
        trigger_config = config["detects"][0]["trigger_config"]
        recovery_config = config["detects"][0]["recovery_config"]
        detect = {
            "algorithm": {},
            "trigger": f"{trigger_config['count']}/{trigger_config['check_window']}/{recovery_config['check_window']}",
        }

        # 算法配置
        if config["detects"][0]["connector"] != "and":
            detect["algorithm"]["operator"] = config["detects"][0]["connector"]

        self.update_algorithm_config(data_source, data_type, config, item, detect)

        # 无数据配置
        no_data_config = item["no_data_config"]
        if no_data_config["is_enabled"]:
            detect["nodata"] = {
                "continuous": int(no_data_config["continuous"]),
                "level": LEVEL_ID_TO_NAME[no_data_config.get("level", 2)],
                "dimensions": no_data_config.get("agg_dimension", []),
            }
        code_config["detect"] = detect

        self.update_notice_config(config, code_config)

        actions = []
        for action_config in config["actions"]:
            if action_config["config_id"] not in self.reverse_action_ids:
                raise Exception(f"action({action_config['config_id']}) not exists in rule({config['name']})")

            action = {
                "signal": action_config["signal"],
                "action": self.reverse_action_ids[action_config["config_id"]],
            }

            converge_config = action_config["options"].get("converge_config", {})
            if converge_config.get("is_enabled"):
                action["converge"] = {
                    "interval": converge_config["timedelta"] // 60,
                    "count": converge_config["count"],
                    "func": converge_config["converge_func"],
                }
            actions.append(action)

        if actions:
            code_config["actions"] = actions

        return code_config

    def check(self, config: Dict) -> Dict:
        """
        scenario&指标类型检查自动补充
        name唯一性检查
        data_source/data_type检查
        unit配置检查
        """
        return StrategySchema.validate(config)


class NoticeGroupConfigParser(BaseConfigParser):
    """
    通知组配置解析器
    """

    def __init__(self, bk_biz_id, duty_rules=None, overwrite: bool = False):
        if not duty_rules:
            duty_rules = {}
        # 老版本的数据里，包含了部分携带轮值的信息，需要做兼容，此时也需要根据历史数据是否存在做判断
        self.overwrite = overwrite
        self.duty_rules = duty_rules
        self.reverse_duty_rules = {v: k for k, v in duty_rules.items()}
        super(NoticeGroupConfigParser, self).__init__(bk_biz_id)

    @staticmethod
    def translate_notice_ways(notice_way_config):
        notice_ways = []
        for notice_type in notice_way_config["type"]:
            notice_way = {"name": notice_type}
            if notice_type == NoticeWay.WX_BOT:
                notice_way["receivers"] = notice_way_config.get("chatids", "").split(",")
            notice_ways.append(notice_way)
        notice_way_config["notice_ways"] = notice_ways

    def translate_duty_rule(self, config, notice_group):
        """
        翻译老版本的轮值规则
        """
        # 轮值配置解析
        notice_group["need_duty"] = True

        # 沿用用户组的名字加一个AsCode作为标记
        duty_rule = {
            "name": f"[AsCode]{notice_group['name']}",
            "category": DutyCategory.REGULAR,
            "bk_biz_id": notice_group["bk_biz_id"],
            "duty_arranges": [],
            "effective_time": "",
        }
        for duty in config["duties"]:
            user_groups = []
            for users in duty["user_groups"]:
                user_group = []
                for user in users:
                    user_dict = parse_user(user)
                    if not user_dict:
                        continue
                    user_group.append(user_dict)
                user_groups.append(user_group)

            # 交接配置
            work_days = duty["work"]["days"]
            if "handover" in duty:
                duty_rule["category"] = DutyCategory.HANDOFF
                handover_date = duty["handover"]["date"]
                if handover_date in work_days:
                    index = work_days.index(duty["handover"]["date"])
                    work_days = work_days[index:] + work_days[:index]
            # 多个轮值组的生效时间取最早生效的那个作为整个轮值规则组的生效开始时间
            duty_rule["effective_time"] = min(duty_rule["effective_time"], duty["effective_time"])

            duty_rule["duty_arranges"].append(
                {
                    "duty_time": [
                        {
                            "work_type": duty["type"],
                            "work_days": work_days,
                            "work_time": [duty["work"]["time_range"]],
                            "work_time_type": "time_range",
                        }
                    ],
                    "backups": [],
                    "duty_users": user_groups,
                    "group_number": 0,
                    "group_type": DutyGroupType.SPECIFIED,
                }
            )
        rule_instance = None
        if not duty_rule["effective_time"]:
            duty_rule["effective_time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:00")
        if duty_rule["name"] in self.duty_rules:
            # 判断一下是不是曾经有过
            try:
                rule_instance = DutyRule.objects.get(id=self.duty_rules[duty_rule["name"]])
            except DutyRule.DoesNotExist:
                rule_instance = None
        rule_slz = DutyRuleDetailSlz(data=duty_rule, instance=rule_instance)
        rule_slz.is_valid(raise_exception=True)
        if rule_instance and rule_slz.data["hash"] != rule_instance.hash and not self.overwrite:
            raise ValidationError("Duty rule is existed but overwrite if not allowed")
        rule_instance = rule_slz.save()
        notice_group["duty_rules"] = [rule_instance.id]

    def parse(self, config: Dict) -> Dict:
        #  yaml -> config
        notice_group = {
            "bk_biz_id": self.bk_biz_id,
            "name": config["name"],
            "desc": config["description"],
            "channels": config["channels"] or NoticeChannel.DEFAULT_CHANNELS,
            "mention_list": config["mention_list"] or [],
            "action_notice": [],
            "alert_notice": [],
            "duty_arranges": [],
            "duty_rules": [],
        }

        notice_group["mention_list"] = [
            {"type": mention_member["member_type"], "id": mention_member["id"]}
            for mention_member in notice_group["mention_list"]
        ]

        # 通知方式配置
        for time_range, alert_config in config["alert"].items():
            # 时间段标准化
            start, end = time_range.split("--")
            start, end = start.strip(), end.strip()
            if len(start) == 5:
                start += ":00"
            if len(end) == 5:
                end += ":59"
            time_range = f"{start}--{end}"

            notice = {"time_range": time_range, "notify_config": []}
            for level_name in alert_config:
                level = LEVEL_NAME_TO_ID[level_name]
                notify_config = {"level": level, "notice_ways": alert_config[level_name]["notice_ways"]}
                if not notify_config["notice_ways"]:
                    # 如果是历史的数据结构，需要进行转换
                    notice_way_config = {
                        "type": alert_config[level_name]["type"],
                        "chatids": ",".join(alert_config[level_name]["chatids"]),
                    }
                    self.translate_notice_ways(notice_way_config)
                    notify_config.update(notice_way_config)

                notice["notify_config"].append(notify_config)
            notice_group["alert_notice"].append(notice)

        for time_range, action_config in config["action"].items():
            notice = {"time_range": time_range, "notify_config": []}
            for phase_name in action_config:
                phase = ACTION_PHASE_NAME_TO_ID[phase_name]
                notify_config = {
                    "notice_ways": action_config[phase_name]["notice_ways"],
                    "phase": phase,
                }
                if action_config[phase_name]["type"]:
                    # 如果是历史的数据结构，需要进行转换
                    notice_way_config = {
                        "type": action_config[phase_name]["type"],
                        "chatids": ",".join(action_config[phase_name]["chatids"]),
                    }
                    self.translate_notice_ways(notice_way_config)
                    notify_config.update(notice_way_config)
                if not notify_config.get("chatids"):
                    notify_config.pop("chatids", None)
                notice["notify_config"].append(notify_config)
            notice_group["action_notice"].append(notice)

        if config["duty_rules"]:
            # 当存在duty_rules的时候, 表示是新的轮值结构
            notice_group["need_duty"] = True
            notice_group["duty_rules"] = [
                self.duty_rules[name] for name in config["duty_rules"] if name in self.duty_rules
            ]
        elif config["duties"]:
            self.translate_duty_rule(config, notice_group)
        else:
            # 非轮值配置
            users = []
            for user in config["users"]:
                splits = user.split("#")
                if len(splits) == 1:
                    users.append({"id": splits[0], "type": "user"})
                elif len(splits) == 2:
                    users.append({"id": splits[1], "type": splits[0]})

            notice_group["duty_arranges"].append({"duty_type": "always", "work_time": "always", "users": users})

        return notice_group

    def unparse(self, config: Dict) -> Dict:
        # config -> yaml
        notice_group = {
            "name": config["name"],
            "channels": config["channels"] or NoticeChannel.DEFAULT_CHANNELS,
            "version": MaxVersion.USER_GROUP,
            "action": {},
            "alert": {},
            "duty_rules": [],
        }

        if config["mention_list"]:
            notice_group["mention_list"] = [
                {"member_type": mention_member["type"], "id": mention_member["id"]}
                for mention_member in config["mention_list"]
            ]

        if config["desc"]:
            notice_group["description"] = config["desc"]

        for action_config in config["action_notice"]:
            time_range = action_config["time_range"]
            start, end = time_range.split("--")
            start, end = start.strip()[:5], end.strip()[:5]
            time_range = f"{start}--{end}"

            phase_configs = {}

            for notice in action_config["notify_config"]:
                phase_config = {"notice_ways": notice.get("notice_ways")}
                phase_name = ACTION_PHASE_ID_TO_NAME[notice["phase"]]
                if not phase_config["notice_ways"]:
                    # 如果没有通知方式，表示可能是以前的数据结构
                    self.translate_notice_ways(notice)
                    phase_config["notice_ways"] = notice["notice_ways"]
                else:
                    phase_config["notice_ways"] = []
                    for notice_way in notice["notice_ways"]:
                        notice_way_config = {"name": notice_way["name"]}
                        if notice_way.get("receivers"):
                            notice_way_config["receivers"] = notice_way["receivers"]
                        phase_config["notice_ways"].append(notice_way_config)

                phase_configs[phase_name] = phase_config

            notice_group["action"][time_range] = phase_configs

        for alert_config in config["alert_notice"]:
            time_range = alert_config["time_range"]
            start, end = time_range.split("--")
            start, end = start.strip()[:5], end.strip()[:5]
            time_range = f"{start}--{end}"

            level_configs = {}
            for notice in alert_config["notify_config"]:
                level_config = {"notice_ways": notice.get("notice_ways")}
                level_name = LEVEL_ID_TO_NAME[notice["level"]]
                if not level_config["notice_ways"]:
                    self.translate_notice_ways(notice)
                    level_config["notice_ways"] = notice["notice_ways"]
                else:
                    level_config["notice_ways"] = []
                    for notice_way in notice["notice_ways"]:
                        notice_way_config = {"name": notice_way["name"]}
                        if notice_way.get("receivers"):
                            notice_way_config["receivers"] = notice_way["receivers"]
                        level_config["notice_ways"].append(notice_way_config)
                level_configs[level_name] = level_config

            notice_group["alert"][time_range] = level_configs

        if not config["need_duty"]:
            notice_group["users"] = []
            if config["duty_arranges"]:
                for user in config["duty_arranges"][0]["users"]:
                    notice_group["users"].append(f"group#{user['id']}" if user["type"] == "group" else user["id"])
        notice_group["duty_rules"] = [
            self.reverse_duty_rules[duty_id] for duty_id in config["duty_rules"] if duty_id in self.reverse_duty_rules
        ]
        return notice_group

    def check(self, config: Dict) -> Dict:
        return UserGroupSchema.validate(config)


class ActionConfigParser(BaseConfigParser):
    """
    处理套餐配置解析器
    """

    def __init__(self, bk_biz_id: int, action_plugins: List[ActionPlugin]):
        super(ActionConfigParser, self).__init__(bk_biz_id)

        self.plugin_key_to_id = {plugin.plugin_key: plugin.id for plugin in action_plugins}
        self.plugin_id_to_key = {plugin.id: plugin.plugin_key for plugin in action_plugins}

    def parse(self, config: Dict) -> Dict:
        result = {
            "bk_biz_id": self.bk_biz_id,
            "is_enabled": config["enabled"],
            "name": config["name"],
            "plugin_id": self.plugin_key_to_id[config["type"]],
            "desc": config["description"],
            "execute_config": {
                "timeout": config["timeout"],
                "template_detail": config["template_detail"],
            },
        }

        if config["template_id"] != "":
            result["execute_config"]["template_id"] = config["template_id"]
        return result

    def unparse(self, config: Dict) -> Dict:
        # config -> yaml
        code_config = {
            "name": config["name"],
            "version": MaxVersion.ACTION,
            "template_detail": config["execute_config"]["template_detail"],
            "type": self.plugin_id_to_key[config["plugin_id"]],
            "timeout": config["execute_config"]["timeout"],
        }

        if "template_id" in config["execute_config"]:
            code_config["template_id"] = config["execute_config"]["template_id"]

        if config["desc"]:
            code_config["description"] = config["desc"]

        if not config["is_enabled"]:
            code_config["enabled"] = config["is_enabled"]

        return code_config

    def check(self, config: Dict) -> Dict:
        return ActionSchema.validate(config)


class AssignGroupRuleParser(BaseConfigParser):
    """
    处理套餐配置解析器
    """

    def __init__(self, bk_biz_id: int, notice_group_ids: Dict[str, int], action_ids: Dict[str, int]):
        super(AssignGroupRuleParser, self).__init__(bk_biz_id)

        self.notice_group_ids = notice_group_ids
        self.reverse_notice_group_ids = {v: k for k, v in notice_group_ids.items()}
        self.action_ids = action_ids
        self.reverse_action_ids = {v: k for k, v in action_ids.items()}

    def parse(self, config: Dict) -> Dict:
        # yaml -> config
        config["bk_biz_id"] = self.bk_biz_id
        for rule in config["rules"]:
            upgrade_config = rule.pop("upgrade_config", {})
            upgrade_config["upgrade_interval"] = upgrade_config.pop("interval", 1440)
            upgrade_config["is_enabled"] = upgrade_config.pop("enabled", False)
            rule["user_groups"] = self.get_notice_group_ids(rule["user_groups"])
            upgrade_config["user_groups"] = self.get_notice_group_ids(upgrade_config.get("user_groups", []))
            rule["is_enabled"] = rule["enabled"]

            for action in rule["actions"]:
                action["is_enabled"] = action.pop("enabled")

                if action["name"] not in self.action_ids:
                    raise Exception(f"action({action['name']}) in assign rule not exists")
                action["action_id"] = self.action_ids[action["name"]]
                action["action_type"] = action["type"]

            # 将通知升级的内容转到actions中
            rule["actions"].insert(
                0,
                {
                    "action_type": "notice",
                    "is_enabled": rule.get("notice_enabled", True),
                    "upgrade_config": upgrade_config,
                },
            )

        return config

    def unparse(self, config: Dict) -> Dict:
        # config -> yaml
        # 原参数需要的path剔除
        config.pop("path", "")
        for rule in config["rules"]:
            rule["user_groups"] = self.get_notice_group_names(rule["user_groups"])
            rule["enabled"] = rule.pop("is_enabled", False)
            rule.pop("bk_biz_id", None)
            rule.pop("id", None)
            rule.pop("assign_group_id", None)
            actions = []
            for action in rule.pop("actions", []):
                if action["action_type"] == "notice":
                    if not action.get("is_enabled"):
                        rule["notice_enabled"] = False
                    rule["upgrade_config"] = action["upgrade_config"]
                    rule["upgrade_config"]["enabled"] = rule["upgrade_config"].pop("is_enabled", False)
                    rule["upgrade_config"]["interval"] = rule["upgrade_config"].pop("upgrade_interval", 1440)
                    rule["upgrade_config"]["user_groups"] = self.get_notice_group_names(
                        rule["upgrade_config"]["user_groups"]
                    )
                else:
                    action["enabled"] = action.pop("is_enabled", False)
                    action["name"] = self.reverse_action_ids[action.pop("action_id")]
                    action["type"] = action.pop("action_type")
                    actions.append(action)
            rule["actions"] = actions
        return config

    def get_notice_group_names(self, group_ids):
        """
        根据group_id反查告警名称
        """
        group_names = []
        for group_id in group_ids:
            if group_id in self.reverse_notice_group_ids:
                group_names.append(self.reverse_notice_group_ids[group_id])
            else:
                raise Exception(f"notice_group_id({group_id}) in assign rule not exists")
        return group_names

    def get_notice_group_ids(self, group_names):
        """
        根据group_id反查告警名称
        """
        group_ids = []
        for group_name in group_names:
            if group_name in self.notice_group_ids:
                group_ids.append(self.notice_group_ids[group_name])
            else:
                raise Exception(f"notice_group_name({group_name}) in assign rule not exists")
        return group_ids

    def check(self, config: Dict) -> Dict:
        return AssignGroupRuleSchema.validate(config)


class DutyRuleParser(BaseConfigParser):
    """
    处理套餐配置解析器
    """

    def __init__(self, bk_biz_id: int):
        super(DutyRuleParser, self).__init__(bk_biz_id)

    def parse(self, config: Dict) -> Dict:
        # yaml -> config
        config["bk_biz_id"] = self.bk_biz_id
        config["duty_arranges"] = []

        for duty in config.pop("arranges", []):
            duty_users = []
            for users in duty["users"]:
                user_group = []
                for user in users:
                    user_dict = parse_user(user)
                    if not user_dict:
                        continue
                    user_group.append(user_dict)
                duty_users.append(user_group)
            duty_times = []
            for duty_time in duty["time"]:
                work_time_type = "time_range" if "time_range" in duty_time["work"] else "datetime_range"
                duty_times.append(
                    {
                        "work_type": duty_time["type"],
                        "work_days": duty_time["work"]["days"],
                        "work_date_range": duty_time["work"]["date_range"],
                        "work_time_type": work_time_type,
                        "work_time": duty_time["work"].get(work_time_type, ["00:00--23:59"]),
                        "period_settings": duty_time["period_settings"],
                    }
                )

            config["duty_arranges"].append(
                {
                    "duty_time": duty_times,
                    "backups": [],
                    "duty_users": duty_users,
                    "group_number": duty["group"].get("number", 0),
                    "group_type": duty["group"]["type"],
                }
            )
        return config

    def unparse(self, config: Dict) -> Dict:
        # config -> yaml
        parsed_config = {
            "category": config["category"],
            "effective_time": config["effective_time"],
            "enabled": config["enabled"],
            "labels": config["labels"],
            "name": config["name"],
            "arranges": [],
        }
        if config["end_time"]:
            parsed_config["end_time"] = config["end_time"]
        config["arranges"] = []
        for duty_arrange in config.pop("duty_arranges", []):
            #     反向解析
            arrange = {"time": [], "users": []}
            for time_item in duty_arrange.pop("duty_time", []):
                time_type = time_item.get("work_time_type", "time_range")
                work = {
                    "days": time_item.get("work_days", []),
                    "date_range": time_item.get("work_date_range", []),
                    time_type: time_item.get("work_time", []),
                }
                arrange_time = {"type": time_item.get("work_type", "daily"), "work": work}
                if time_item.get("is_custom"):
                    arrange_time["is_custom"] = True
                if time_item.get("period_settings"):
                    arrange_time["period_settings"] = time_item["period_settings"]
                arrange["time"].append(arrange_time)
            arrange["users"] = []
            for user_list in duty_arrange.pop("duty_users", []):
                arrange["users"].append(
                    [f"group#{user['id']}" if user["type"] == "group" else user["id"] for user in user_list]
                )
            arrange["group"] = {"type": duty_arrange.pop("group_type", DutyGroupType.SPECIFIED)}
            if duty_arrange.get("group_number", 0) > 0:
                arrange["group"]["number"] = duty_arrange.pop("group_number")
            parsed_config["arranges"].append(arrange)
        return parsed_config

    def check(self, config: Dict) -> Dict:
        return DutyRuleSchema.validate(config)
