"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from schema import And, Optional, Or, Regex, Schema, SchemaError, Use

from bkmonitor.as_code.constants import MaxVersion, MinVersion
from constants.action import ActionSignal
from constants.common import DutyCategory, DutyGroupType
from constants.data_source import DataSourceLabel, DataTypeLabel

DEFAULT_TEMPLATE_TITLE = "{{business.bk_biz_name}} - {{alarm.name}}{{alarm.display_type}}"
DEFAULT_TEMPLATE_CONTENT = """{{content.level}}
{{content.begin_time}}
{{content.time}}
{{content.duration}}
{{content.target_type}}
{{content.data_source}}
{{content.content}}
{{content.current_value}}
{{content.biz}}
{{content.target}}
{{content.dimension}}
{{content.detail}}
{{content.assign_detail}}
{{content.related_info}}"""

BkMonitorQuerySchema = Schema(
    {
        Optional("name", default=""): And(str, lambda p: 255 >= len(p) >= 0),
        Optional("type", default="bk_monitor"): "bk_monitor",
        "data_source": Or(
            DataSourceLabel.BK_MONITOR_COLLECTOR,
            DataSourceLabel.CUSTOM,
            DataSourceLabel.BK_DATA,
            DataSourceLabel.BK_FTA,
            DataSourceLabel.BK_LOG_SEARCH,
            DataSourceLabel.BK_APM,
            DataSourceLabel.PROMETHEUS,
            DataSourceLabel.DASHBOARD,
        ),
        "data_type": Or(
            DataTypeLabel.TIME_SERIES, DataTypeLabel.LOG, DataTypeLabel.EVENT, DataTypeLabel.ALERT, DataTypeLabel.TRACE
        ),
        Optional("expression", default="a"): str,
        Optional("functions", default=lambda: []): [str],
        "query_configs": [
            {
                Optional("metric", default=""): str,
                Optional("query_string", default="*"): str,
                Optional("method", default=""): str,
                Optional("interval", default=60): int,
                Optional("group_by", default=lambda: []): [str],
                Optional("functions", default=lambda: []): [str],
                Optional("where", default=""): str,
                Optional("alias", default="a"): str,
                Optional("time_field"): str,
                Optional("unit", default=""): str,
                Optional("dashboard_uid", default=""): str,
                Optional("panel_id", default=""): int,
                Optional("ref_id", default=""): str,
                Optional("variables", default=lambda: {}): dict,
            }
        ],
        Optional("target"): {
            "type": Or("host", "topo", "set_template", "service_template", "dynamic_group"),
            "nodes": [str],
        },
    },
    ignore_extra_keys=True,
)


class QuerySchema(Schema):
    allowed_type = ["bk_monitor"]
    schemas: dict[str, Schema] = {"bk_monitor": BkMonitorQuerySchema}

    def validate(self, data, **kwargs):
        query_type = data.get("type", "bk_monitor")
        if query_type not in self.allowed_type:
            raise SchemaError([], "query.type not exists")

        return self.schemas[query_type].validate(data)


UserSchema = Regex(r"^(user#|group#)?[a-zA-Z0-9-_]+$")

StrategySchema = Schema(
    {
        "name": And(str, lambda p: 128 >= len(p) > 0),
        Optional(
            "version",
            default=MinVersion.STRATEGY,
            description=f"策略支持版本号范围：{MinVersion.STRATEGY}-{MaxVersion.STRATEGY}",
        ): And(Use(str), lambda s: MinVersion.STRATEGY <= s <= MaxVersion.STRATEGY),
        Optional("labels", default=lambda: []): [str],
        Optional("enabled", default=True): bool,
        Optional("active_time", default="00:00 -- 23:59"): Regex(
            r"\d{2}:\d{2} *-- *\d{2}:\d{2}(,\d{2}:\d{2} *-- *\d{2}:\d{2})*"
        ),
        Optional("priority", default=None): Or(And(int, lambda p: 10000 >= p >= 0), None),
        Optional("priority_group_key", default=""): str,
        Optional("active_calendars", default=lambda: []): [int],  # deprecated
        Optional("calendars", default=lambda: {"active": [], "not_active": []}): dict,
        "query": QuerySchema({}),
        "detect": {
            "algorithm": {
                Optional("unit", default=None): Or(None, str),
                Optional("operator", default="and"): Or("and", "or"),
                Or("remind", "warning", "fatal", only_one=False): [
                    {
                        "type": str,
                        "config": Or(list, dict, str),
                    }
                ],
            },
            "trigger": Regex(r"[1-9]\d*/[1-9]\d*/[1-9]\d*"),
            Optional(
                "nodata", default=lambda: {"enabled": False, "continuous": 5, "dimensions": [], "level": "warning"}
            ): {
                Optional("enabled", default=True): bool,
                "continuous": int,
                Optional("dimensions", default=lambda: []): [str],
                Optional("level", default="warning"): Or("remind", "warning", "fatal"),
            },
        },
        "notice": {
            Optional("signal", default=lambda: ["abnormal", "no_data"]): [
                Or(
                    ActionSignal.ABNORMAL,
                    ActionSignal.RECOVERED,
                    ActionSignal.CLOSED,
                    ActionSignal.NO_DATA,
                    ActionSignal.EXECUTE,
                    ActionSignal.EXECUTE_SUCCESS,
                    ActionSignal.EXECUTE_FAILED,
                    ActionSignal.ACK,
                )
            ],
            Optional("exclude_notice_ways", default=lambda: {"recovered": [], "closed": []}): {
                Optional("closed", default=lambda: []): [str],
                Optional("recovered", default=lambda: []): [str],
            },
            "user_groups": [str],
            Optional("biz_converge", default=True): bool,
            Optional("noise_reduce", default=lambda: {"enabled": False, "dimensions": [], "abnormal_ratio": 10}): {
                "enabled": bool,
                "dimensions": [str],
                "abnormal_ratio": int,
            },
            Optional("upgrade_config", default=lambda: {"enabled": False, "user_groups": [], "interval": 1440}): {
                "enabled": bool,
                "user_groups": [str],
                "interval": int,
            },
            Optional("assign_mode", default=lambda: ["only_notice", "by_rule"]): And(
                [Or("only_notice", "by_rule")], lambda x: len(x) > 0
            ),
            Optional("chart_image_enabled", default=True): bool,
            Optional("interval_mode", default="standard"): Or("standard", "increasing"),
            Optional("interval", default=120): int,
            Optional(
                "template",
                default=lambda: {
                    "abnormal": {"title": DEFAULT_TEMPLATE_TITLE, "content": DEFAULT_TEMPLATE_CONTENT},
                    "recovered": {"title": DEFAULT_TEMPLATE_TITLE, "content": DEFAULT_TEMPLATE_CONTENT},
                    "closed": {"title": DEFAULT_TEMPLATE_TITLE, "content": DEFAULT_TEMPLATE_CONTENT},
                },
            ): {
                Optional("abnormal", default={"title": DEFAULT_TEMPLATE_TITLE, "content": DEFAULT_TEMPLATE_CONTENT}): {
                    Optional("title", default=DEFAULT_TEMPLATE_TITLE): str,
                    Optional("content", default=DEFAULT_TEMPLATE_CONTENT): str,
                },
                Optional("recovered", default={"title": DEFAULT_TEMPLATE_TITLE, "content": DEFAULT_TEMPLATE_CONTENT}): {
                    Optional("title", default=DEFAULT_TEMPLATE_TITLE): str,
                    Optional("content", default=DEFAULT_TEMPLATE_CONTENT): str,
                },
                Optional("closed", default={"title": DEFAULT_TEMPLATE_TITLE, "content": DEFAULT_TEMPLATE_CONTENT}): {
                    Optional("title", default=DEFAULT_TEMPLATE_TITLE): str,
                    Optional("content", default=DEFAULT_TEMPLATE_CONTENT): str,
                },
            },
        },
        Optional("actions", default=lambda: []): [
            {
                "signal": [str],
                "action": str,
                Optional(
                    "converge", default={"interval": 1, "count": 1, "func": "skip_when_success", "enabled": False}
                ): {
                    Optional("enabled", default=True): bool,
                    Optional("interval", default=1): int,
                    Optional("count", default=1): int,
                    Optional("func", default="skip_when_success"): str,
                },
            }
        ],
    },
    ignore_extra_keys=True,
)

TimeRangeSchema = Schema(Regex(r"^\d{2}:\d{2}(:\d{2})? *-- *\d{2}:\d{2}(:\d{2})?$"))

UserGroupSchema = Schema(
    {
        "name": str,
        Optional(
            "version",
            default=MinVersion.USER_GROUP,
            description=f"通知组支持版本号范围：{MinVersion.USER_GROUP}-{MaxVersion.USER_GROUP}",
        ): And(Use(str), lambda s: MinVersion.USER_GROUP <= s <= MaxVersion.USER_GROUP),
        Optional("users", default=lambda: []): [str],
        Optional("channels", default=lambda: []): [str],
        Optional("mention_list", default=lambda: []): [{"member_type": str, "id": str}],
        Optional("description", default=""): str,
        "action": {
            TimeRangeSchema: {
                "execute": {
                    Optional("type", default=lambda: []): [str],
                    Optional("chatids", default=lambda: []): [str],
                    Optional("notice_ways", default=lambda: []): [
                        {"name": str, Optional("receivers", default=lambda: []): [str]}
                    ],
                },
                "execute_success": {
                    Optional("type", default=lambda: []): [str],
                    Optional("chatids", default=lambda: []): [str],
                    Optional("notice_ways", default=lambda: []): [
                        {"name": str, Optional("receivers", default=lambda: []): [str]}
                    ],
                },
                "execute_failed": {
                    Optional("type", default=lambda: []): [str],
                    Optional("chatids", default=lambda: []): [str],
                    Optional("notice_ways", default=lambda: []): [
                        {"name": str, Optional("receivers", default=lambda: []): [str]}
                    ],
                },
            }
        },
        "alert": {
            TimeRangeSchema: {
                "remind": {
                    Optional("type", default=lambda: []): [str],
                    Optional("chatids", default=lambda: []): [str],
                    Optional("notice_ways", default=lambda: []): [
                        {"name": str, Optional("receivers", default=lambda: []): [str]}
                    ],
                },
                "warning": {
                    Optional("type", default=lambda: []): [str],
                    Optional("chatids", default=lambda: []): [str],
                    Optional("notice_ways", default=lambda: []): [
                        {"name": str, Optional("receivers", default=lambda: []): [str]}
                    ],
                },
                "fatal": {
                    Optional("type", default=lambda: []): [str],
                    Optional("chatids", default=lambda: []): [str],
                    Optional("notice_ways", default=lambda: []): [
                        {"name": str, Optional("receivers", default=lambda: []): [str]}
                    ],
                },
            }
        },
        Optional("duties", default=lambda: []): [
            {
                "user_groups": [[UserSchema]],
                "type": Or("daily", "weekly", "monthly"),
                Optional("handover"): {Optional("date", default=1): int, "time": Regex(r"^\d{2}:\d{2}$")},
                "work": {"days": [int], "time_range": Regex(r"^\d{2}:\d{2} *-- *\d{2}:\d{2}$")},
                "effective_time": Regex(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$"),
            }
        ],
        Optional("duty_rules", default=lambda: []): [str],
    },
    ignore_extra_keys=True,
)

ActionSchema = Schema(
    {
        Optional(
            "version",
            default=MinVersion.ACTION,
            description=f"处理套餐支持版本号范围：{MinVersion.ACTION}-{MaxVersion.ACTION}",
        ): And(Use(str), lambda s: MinVersion.ACTION <= s <= MaxVersion.ACTION),
        "name": str,
        Optional("description", default=""): str,
        Optional("enabled", default=True): bool,
        "type": str,
        "timeout": int,
        Optional("template_id", default=""): Or(int, str),
        "template_detail": dict,
    },
    ignore_extra_keys=True,
)

AssignGroupRuleSchema = Schema(
    {
        Optional("assign_group_id"): int,
        "priority": int,
        "name": str,
        "rules": [
            {
                Optional("id", default=0): int,
                "enabled": bool,
                "user_groups": [str],
                "conditions": [
                    {
                        "field": str,
                        "value": [str],
                        "method": Or("eq", "neq", "include", "exclude", "reg", "nreg", "issuperset"),
                        Optional("condition", default="and"): Or("and"),
                    }
                ],
                Optional("notice_enabled"): bool,
                Optional("upgrade_config", default=lambda: {"enabled": False, "user_groups": [], "interval": 1440}): {
                    "enabled": bool,
                    "user_groups": [str],
                    "interval": int,
                },
                Optional("actions", default=lambda: []): [
                    {
                        Optional("enabled", default=False): bool,
                        "type": str,
                        "name": str,
                    }
                ],
                Optional("alert_severity", default=0): int,
                Optional("additional_tags", default=lambda: []): [{"key": str, "value": str}],
            }
        ],
    },
    ignore_extra_keys=True,
)

DutyRuleSchema = Schema(
    {
        "name": str,
        Optional("labels", default=lambda: []): [str],
        "enabled": bool,
        "effective_time": Regex(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$"),
        Optional("end_time", default=""): str,
        Optional("category", default=DutyCategory.REGULAR): Or(DutyCategory.REGULAR, DutyCategory.HANDOFF),
        "arranges": [
            {
                "time": [
                    {
                        Optional("is_custom"): bool,
                        "type": str,
                        "work": {
                            "days": [int],
                            "date_range": [Regex(r"^\d{4}-\d{2}-\d{2} *-- *\d{4}-\d{2}-\d{2}$")],
                            Optional("time_range"): [Regex(r"^\d{2}:\d{2} *--*\d{2}:\d{2}$")],
                            Optional("datetime_range"): [Regex(r"^\d{2} \d{2}:\d{2} *-- *\d{2} \d{2}:\d{2}$")],
                        },
                        Optional("period_settings", default=lambda: {}): {
                            "window_unit": Or("day", "hour"),
                            "duration": int,
                        },
                    }
                ],
                "users": [[UserSchema]],
                "group": {"type": Or(DutyGroupType.SPECIFIED, DutyGroupType.AUTO), Optional("number", default=0): int},
            }
        ],
    },
    ignore_extra_keys=True,
)
