import html
import json
import logging
import os
import re
from collections import defaultdict

import yaml
from bk_monitor_base.strategy import get_metric_id
from django.conf import settings
from django.utils.translation import gettext as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bk_dataview.api import get_or_create_org
from bkmonitor.action.serializers import UserGroupDetailSlz
from bkmonitor.models import ActionSignal, MetricMappingConfigModel, UserGroup
from constants.alert import DEFAULT_NOTICE_MESSAGE_TEMPLATE
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import api, resource
from core.drf_resource.base import Resource
from monitor_web.grafana.resources import ConvertGrafanaPromqlDashboardResource
from monitor_web.promql_import.utils import check_metric_field

logger = logging.getLogger(__name__)


class ImportBaseResource(Resource):
    re_label_values = re.compile(r"label_values\((?P<metric>.*),(?P<dimension>.*)\)")
    re_all_label_values = re.compile(r"label_values\((.*?)\)")
    re_variable = re.compile(r"(\$.*?)")
    re_all_variables = re.compile(r"(\$[A-Za-z0-9_]+)")
    k8s_dimension_map = {"cluster_id": "bcs_cluster_id"}

    def perform_request(self, validated_request_data):
        pass

    @classmethod
    def convert_k8s_dimension(cls, promql: str) -> str:
        return ConvertGrafanaPromqlDashboardResource.convert_metric_id(promql, [])

    @classmethod
    def convert_metric_field(cls, promql: str, params: dict) -> tuple[str, str]:
        scenario = "kubernetes"

        try:
            mapping_config = MetricMappingConfigModel.objects.get(
                config_field=params.get("config_field", ""), bk_biz_id=params["bk_biz_id"]
            ).__dict__
        except MetricMappingConfigModel.DoesNotExist:
            mapping_config = None

        if not mapping_config or mapping_config.get("range_type") == "kubernetes":
            promql = cls.convert_k8s_dimension(promql)
            return promql, scenario

        if cls.re_all_label_values.match(promql):
            if cls.re_label_values.match(promql):
                query_dict = cls.re_label_values.match(promql).groupdict()
                metric_fields = [query_dict["metric"]]
            else:
                raise ValidationError(_("暂不支持获取所有指标下维度值的label_values方法"))
        else:
            try:
                origin_config = api.unify_query.promql_to_struct(promql=promql)["data"]
            except Exception:
                raise ValidationError(_("解析promql失败，请检查是否存在语法错误: {}").format(promql))
            metric_fields = [query["field_name"] for query in origin_config["query_list"]]
        for metric_field in metric_fields:
            check_result = check_metric_field(metric_field, mapping_config)
            scenario = check_result["scenario"]
            if not check_result["is_exist"]:
                raise ValidationError(_("不存在的指标名{}").format(metric_field))
            config = {
                "data_source_label": DataSourceLabel.CUSTOM
                if mapping_config["range_type"] == "customTs"
                else DataSourceLabel.BK_MONITOR_COLLECTOR,
                "data_type_label": DataTypeLabel.TIME_SERIES,
                "result_table_id": check_result["table_id"],
                "data_label": check_result.get("data_label", ""),
                "metric_field": metric_field,
            }
            new_metric_id = get_metric_id(**config)
            new_metric_id = new_metric_id.replace(".", ":")
            promql = promql.replace(metric_field, new_metric_id)
            promql = cls.convert_k8s_dimension(promql)
        return promql, scenario


class ImportGrafanaDashboard(ImportBaseResource):
    re_label_values = re.compile(r"label_values\((?P<metric>.*),(?P<dimension>.*)\)")
    re_all_label_values = re.compile(r"label_values\((.*?)\)")
    re_variable = re.compile(r"(\$.*?)")
    re_all_variables = re.compile(r"(\$[A-Za-z0-9_]+)")
    k8s_dimension_map = {"cluster_id": "bcs_cluster_id"}

    class RequestSerializer(serializers.Serializer):
        file_list = serializers.ListField(label="导入文件列表", required=False)
        config_field = serializers.CharField(label="映射配置名称", required=False)
        bk_biz_id = serializers.IntegerField(label="业务id")

    @classmethod
    def read(cls, name):
        file_path = os.path.join(settings.BASE_DIR, f"{name}.json")
        with open(file_path) as f:
            return json.loads(f.read())

    @classmethod
    def create_dashboard(cls, grafana_config, bk_biz_id):
        org_id = get_or_create_org(bk_biz_id)["id"]
        result = api.grafana.import_dashboard(dashboard=grafana_config, org_id=org_id)
        return result

    @classmethod
    def convert_variables(cls, templating, params):
        # 转换变量
        error_msg = []
        for variable in templating.get("list", []):
            if variable.get("type") == "query":
                variable["datasource"] = None
                promql = variable["query"]
                if isinstance(promql, dict):
                    promql = promql["query"]
                try:
                    promql, scenario = cls.convert_metric_field(promql, params)
                except ValidationError as e:
                    error_msg.append("-".join([_("变量转换失败"), variable["name"], str(e)]))
                variable["query"] = {
                    "promql": promql,
                    "queryType": "prometheus",
                }
                variable["definition"] = promql

                if variable.get("regex"):
                    variable["regex"] = cls.convert_k8s_dimension(variable["regex"])
        return templating, error_msg

    @classmethod
    def handle_origin_config(cls, grafana_config, params):
        templating = grafana_config.get("templating", {})
        error_msg = []
        if templating:
            grafana_config["templating"], error_msg = cls.convert_variables(templating, params)
        for index, grafana_require in enumerate(grafana_config.get("__requires", [])):
            if grafana_require["type"] == "datasource":
                grafana_config["__requires"].pop(index)
        for index, grafana_input in enumerate(grafana_config.get("__inputs", [])):
            if grafana_input["type"] == "datasource":
                grafana_config["__inputs"].pop(index)
        return grafana_config, error_msg

    def perform_request(self, validated_request_data):
        from django.utils.translation import gettext_lazy as _

        if not validated_request_data.get("file_list"):
            raise ValidationError(_("导入失败，未上传任何文件"))

        file_dict = defaultdict(list)
        for f in validated_request_data["file_list"]:
            grafana_config = json.loads(f.read())
            name = f.name
            grafana_config, variable_error_msg = self.handle_origin_config(grafana_config, validated_request_data)
            if variable_error_msg:
                file_dict[name].append(
                    {"status": "fail", "message": _("变量转换失败：") + ", ".join(variable_error_msg)}
                )
            for row in grafana_config.get("rows", grafana_config.get("panels", [])):
                new_panels = []
                if row.get("type") == "row" or "rows" in grafana_config:
                    row["datasource"] = None
                    row_panels = row.get("panels") or []
                else:
                    row_panels = [row]
                for panel in row_panels:
                    panel["datasource"] = None
                    new_targets = []
                    for target in panel.get("targets", []):
                        if not target.get("expr"):
                            continue
                        try:
                            source, scenario = self.convert_metric_field(target["expr"], validated_request_data)
                        except Exception as e:
                            source = target["expr"]
                            file_dict[name].append(
                                {"status": "fail", "message": "-".join([panel["title"], target["expr"], str(e)])}
                            )
                        if panel["type"] == "table":
                            target_format = "table"
                        elif panel["type"] == "heatmap":
                            target_format = "heatmap"
                        else:
                            target_format = "time_series"
                        promqlAlias, scenario = ConvertGrafanaPromqlDashboardResource.convert_legend(
                            target.get("legendFormat", "")
                        )
                        new_targets.append(
                            {
                                "format": target_format,
                                "type": "range",
                                "mode": "code",
                                "refId": target.get("refId", "A"),
                                "step": "",
                                "expressionList": [],
                                "source": source,
                                "promqlAlias": promqlAlias,
                            }
                        )
                    panel["targets"] = new_targets
                    new_panels.append(panel)
                if "rows" in grafana_config:
                    row["rows"] = new_panels
                elif row.get("type") == "row":
                    row["panels"] = new_panels
            if file_dict[name]:
                file_dict[name].append(
                    {
                        "status": "fail",
                        "message": _("存在转换失败情况，下载promql直查模式转换后json文件,并尝试创建仪表盘..."),
                    }
                )
            try:
                grafana_config.pop("id", None)
                result = self.create_dashboard(grafana_config, validated_request_data["bk_biz_id"])
                if result["result"]:
                    file_dict[name].append(
                        {"status": "success", "message": _("导入仪表盘创建成功"), "json": grafana_config}
                    )
                else:
                    file_dict[name].append(
                        {
                            "status": "fail",
                            "message": _("导入仪表盘创建失败: {}").format(result["message"]),
                            "json": grafana_config,
                        }
                    )
            except Exception as e:
                logger.exception(f"创建仪表盘请求异常: {e}")
                file_dict[name].append(
                    {"status": "fail", "message": _("创建仪表盘请求异常:{}").format(e), "json": grafana_config}
                )
        return file_dict


class UploadFileResource(Resource):
    class RequestSerializer(serializers.Serializer):
        upload_file = serializers.FileField(required=True, label="文件内容")

    def perform_request(self, validated_request_data):
        return {"response_id": 1}


class ImportAlertRule(ImportBaseResource):
    NOTICE_WAY_MAP = {"wechat": "weixin", "wechat_work": "rtx", "email": "mail", "sms": "sms", "phone": "voice"}
    allowed_threshold_method = {
        ">": "gt",
        ">=": "gte",
        "<": "lt",
        "<=": "lte",
        "==": "eq",
        "!=": "neq",
    }

    class RequestSerializer(serializers.Serializer):
        file_list = serializers.ListField(label="导入文件列表")
        config_field = serializers.CharField(label="映射配置名称", required=False)
        bk_biz_id = serializers.IntegerField(label="业务id")

    @classmethod
    def get_or_create_notice_group(cls, bk_biz_id, name, receiver_configs):
        """
        获取或创建通知组
        :param bk_biz_id: 业务ID
        :return: 通知组ID
        """
        user_groups = receiver_configs.get("esb_notice_configs", [])
        notice_group_ids = []
        group_count = 0
        if not user_groups:
            return [UserGroup.objects.get(bk_biz_id=bk_biz_id, name=_("运维")).id]
        for user_group in user_groups:
            group_name = name
            group_count += 1
            if UserGroup.objects.filter(name=name, bk_biz_id=bk_biz_id).exists():
                group_name = f"{name}_{group_count}"
            receivers = user_group.pop("receivers")
            notify_type = [
                cls.NOTICE_WAY_MAP.get(key)
                for key, value in user_group.items()
                if value and cls.NOTICE_WAY_MAP.get(key)
            ]
            user_group_serializer = UserGroupDetailSlz(
                data={
                    "bk_biz_id": bk_biz_id,
                    "name": group_name,
                    "duty_arranges": [{"users": [{"type": "user", "id": user} for user in receivers]}],
                    "desc": "",
                    "alert_notice": [
                        {
                            "time_range": "00:00:00--23:59:59",
                            "notify_config": [
                                {"level": 1, "type": notify_type},
                                {"level": 2, "type": notify_type},
                                {"level": 3, "type": notify_type},
                            ],
                        }
                    ],
                    "action_notice": [
                        {
                            "time_range": "00:00:00--23:59:59",
                            "notify_config": [
                                {"phase": 1, "type": notify_type},
                                {"phase": 2, "type": notify_type},
                                {"phase": 3, "type": notify_type},
                            ],
                        }
                    ],
                }
            )
            try:
                user_group_serializer.is_valid(raise_exception=True)
                user_group_serializer.save()
            except ValidationError as e:
                logger.exception(f"创建告警组失败: {e}")
                # 暂不做处理，勾选默认运维组
                return [UserGroup.objects.get(bk_biz_id=bk_biz_id, name=_("运维")).id]
            notice_group_ids.append(UserGroup.objects.get(bk_biz_id=bk_biz_id, name=group_name).id)
        return notice_group_ids

    def perform_request(self, validated_request_data):
        if not validated_request_data["file_list"]:
            raise ValidationError(_("导入失败，未上传告警规则文件"))
        file_dict = defaultdict(list)
        for f in validated_request_data["file_list"]:
            alert_rules = yaml.safe_load(f.read())
            for rule in alert_rules.get("rules", ""):
                if not rule.get("expr", ""):
                    continue
                try:
                    params = {"bk_biz_id": validated_request_data["bk_biz_id"]}
                    if validated_request_data.get("config_field"):
                        params["config_field"] = validated_request_data.get("config_field")
                    promql, scenario = self.convert_metric_field(rule["expr"], params)
                    query_config = {
                        "query_configs": [
                            {
                                "data_source_label": "prometheus",
                                "data_type_label": "time_series",
                                "promql": promql,
                                "agg_interval": 60,
                                "alias": "a",
                            }
                        ],
                    }
                except ValidationError as e:
                    file_dict[f.name].append(
                        {
                            "status": "fail",
                            "message": "-".join([rule.get("alertname", ""), rule.get("expr", ""), str(e.detail)]),
                        }
                    )
                    continue
                notice_group_ids = self.get_or_create_notice_group(
                    validated_request_data["bk_biz_id"],
                    rule.get("alertname", ""),
                    rule["notice_config"].get("receiver_configs", {}),
                )
                strategy_config = {
                    "bk_biz_id": validated_request_data["bk_biz_id"],
                    "name": str(rule.get("alertname", "")),
                    "source": "bk_monitorv3",
                    "scenario": scenario,
                    "type": "monitor",
                    "labels": [_("k8s_导入")],
                    "detects": [
                        {
                            "expression": "",
                            "connector": "and",
                            "level": 1,
                            "trigger_config": {
                                "count": 10 if rule.get("for", 1) > 10 else 1,
                                "check_window": 15 if rule.get("for", 5) > 15 else 5,
                            },
                            "recovery_config": {
                                "check_window": 1,
                                "status_setter": "close",
                            },
                        }
                    ],
                    "items": [
                        {
                            "name": str(rule.get("alertname", "")),
                            "no_data_config": {"level": 2, "continuous": 10, "is_enabled": False, "agg_dimension": []},
                            "algorithms": [
                                {
                                    "level": 1,
                                    "config": [
                                        [
                                            {
                                                "method": self.allowed_threshold_method.get(
                                                    rule.get("operator", ">"), "gt"
                                                ),
                                                "threshold": rule.get("threshold", "0"),
                                            }
                                        ]
                                    ],
                                    "type": "Threshold",
                                }
                            ],
                            "target": [],
                            **query_config,
                        }
                    ],
                    "notice": {
                        "user_groups": notice_group_ids,
                        "signal": [ActionSignal.ABNORMAL, ActionSignal.NO_DATA],
                        "options": {
                            "converge_config": {
                                "need_biz_converge": True,
                            },
                            "start_time": "00:00:00",
                            "end_time": "23:59:59",
                        },
                        "config": {
                            "interval_notify_mode": "standard",
                            "notify_interval": 2 * 60 * 60,
                            "template": DEFAULT_NOTICE_MESSAGE_TEMPLATE,
                        },
                    },
                    "actions": [],
                }
                try:
                    resource.strategies.save_strategy_v2(**strategy_config)
                except Exception as e:
                    logger.exception(f"创建策略失败: {e}")
                    file_dict[f.name].append(
                        {
                            "status": "fail",
                            "message": "-".join(
                                [rule.get("alertname", ""), rule.get("expr", ""), _("创建策略失败: %s") % e]
                            ),
                        }
                    )
        return file_dict


class GetMappingConfig(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        config_field = serializers.CharField(label="配置名称", required=False)

    def perform_request(self, validated_request_data):
        return list(MetricMappingConfigModel.objects.filter(bk_biz_id=validated_request_data["bk_biz_id"]).values())


class CreateMappingConfig(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        file_data = serializers.FileField(required=False, label="文件内容")
        mapping_range = serializers.CharField(required=False, label="映射范围")
        range_type = serializers.CharField(label="数据范围类型")
        config_field = serializers.CharField(label="配置名称")

    def perform_request(self, validated_request_data):
        config_field = html.unescape(validated_request_data["config_field"]).strip()
        if MetricMappingConfigModel.objects.filter(config_field=config_field).exists():
            raise ValidationError(_("映射配置名称{}已存在").format(validated_request_data["config_field"]))
        configs = {}
        if validated_request_data["range_type"] == "kubernetes":
            # k8s内置指标无需指定映射范围
            mapping_range = []
        else:
            if validated_request_data.get("mapping_range"):
                mapping_range = validated_request_data["mapping_range"].split(",")
            else:
                raise ValidationError(_("创建映射规则需指定映射范围"))
        if validated_request_data.get("file_data"):
            configs = yaml.load(validated_request_data["file_data"], Loader=yaml.FullLoader)
        mapping_config = MetricMappingConfigModel.objects.create(
            bk_biz_id=validated_request_data["bk_biz_id"],
            config_field=config_field,
            mapping_range=mapping_range,
            mapping_detail=configs,
            range_type=validated_request_data["range_type"],
        )
        return {"result": True, "detail": {"config_id": mapping_config.id}}


class DeleteMappingConfig(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        config_field = serializers.CharField(label="配置名称")

    def perform_request(self, validated_request_data):
        config = MetricMappingConfigModel.objects.filter(
            bk_biz_id=validated_request_data["bk_biz_id"], config_field=validated_request_data["config_field"]
        )
        if not config:
            raise ValidationError(_("映射配置{}不存在").format(validated_request_data["config_field"]))
        return config.delete()
