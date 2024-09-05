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
import json
import logging
from functools import reduce
from itertools import chain

from django.conf import settings
from django.db.models import Count, Q, QuerySet, Sum
from django.db.models.functions import Length
from django.forms import model_to_dict
from django.utils.translation import ugettext as _
from rest_framework.exceptions import ValidationError

from bkmonitor.models import (
    Action,
    ActionNoticeMapping,
    ItemModel,
    NoticeGroup,
    QueryConfigModel,
    StrategyLabel,
    StrategyModel,
)
from bkmonitor.models.metric_list_cache import MetricListCache
from bkmonitor.strategy.new_strategy import Strategy, get_metric_id
from bkmonitor.utils.request import get_request
from bkmonitor.utils.time_tools import strftime_local
from bkmonitor.utils.user import get_global_user
from bkmonitor.views import serializers
from constants.cmdb import TargetNodeType, TargetObjectType
from constants.data_source import DATA_CATEGORY, DataSourceLabel, DataTypeLabel
from constants.strategy import (
    UPTIMECHECK_ERROR_CODE_MAP,
    AdvanceConditionMethod,
    DataTarget,
    TargetFieldType,
)
from core.drf_resource import Resource, api, resource
from core.drf_resource.exceptions import CustomException
from core.drf_resource.management.exceptions import ResourceNotRegistered
from core.errors.strategy import StrategyNotExist
from core.unit import load_unit
from monitor_web.alert_events.constant import EventStatus
from monitor_web.commons.cc.utils import CmdbUtil
from monitor_web.models import CustomEventGroup, CustomEventItem, DataTargetMapping
from monitor_web.shield.utils import ShieldDetectManager
from monitor_web.strategies.constant import (
    DEFAULT_TRIGGER_CONFIG_MAP,
    DETECT_ALGORITHM_CHOICES,
    EVENT_METRIC_ID,
    GLOBAL_TRIGGER_CONFIG,
    Scenario,
)
from monitor_web.strategies.metric_list_cache import (
    DEFAULT_DIMENSIONS_MAP,
    FILTER_DIMENSION_LIST,
    DefaultDimensions,
)
from monitor_web.strategies.serializers import (
    handle_target,
    is_validate_target,
    validate_action_config,
    validate_agg_condition_msg,
    validate_algorithm_config_msg,
    validate_algorithm_msg,
    validate_no_data_config_msg,
    validate_recovery_config_msg,
    validate_trigger_config_msg,
)

logger = logging.getLogger(__name__)


class GetMetricListResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        data_source_label = serializers.CharField(default="", label="指标数据来源", allow_blank=True)
        data_type_label = serializers.CharField(default="", label="指标数据类型", allow_blank=True)
        result_table_label = serializers.CharField(default="", label="对象类型", allow_blank=True)
        tag = serializers.CharField(default="", label="标签", allow_blank=True)

        search_fields = serializers.DictField(default=lambda: {}, label="查询字段")
        is_exact_match = serializers.BooleanField(default=False, label="是否精确匹配")
        search_value = serializers.CharField(default="", label="查询关键字", allow_blank=True)
        page = serializers.IntegerField(required=False, label="页码")
        page_size = serializers.IntegerField(required=False, label="每页数目")

    @classmethod
    def search_filter(cls, metrics: QuerySet, params):
        """
        指标过滤&搜索
        """
        search_fields = params["search_fields"]

        # 对象过滤
        if params["result_table_label"]:
            metrics = metrics.filter(Q(result_table_label=params.get("result_table_label")))

        # 可搜索字段
        searchable_fields = [
            "related_id",
            "related_name",
            "result_table_id",
            "result_table_name",
            "metric_field",
            "metric_field_name",
            "result_table_label_name",
            "result_table_label",
            "plugin_type",
        ]
        fields_in_extend = ["scenario_name", "scenario_id", "storage_cluster_name", "bk_data_id"]

        # 指定字段搜索
        if search_fields:
            search_params = {}

            for key, value in search_fields.items():
                if key not in searchable_fields and key not in fields_in_extend:
                    continue

                if key in fields_in_extend:
                    search_params["extend_fields__icontains"] = f'"{key}": "{value}'
                    if params["is_exact_match"]:
                        search_params["extend_fields__icontains"] += '"'
                else:
                    if params["is_exact_match"]:
                        search_params[key] = value
                    else:
                        search_params[f"{key}__icontains"] = value

            metrics = metrics.filter(**search_params)

        # 模糊搜索
        search_value_list = [x for x in params["search_value"].split(";") if x]
        for search_value in search_value_list:
            search_filter = Q()
            search_filter.connector = "OR"
            for field in searchable_fields + ["extend_fields"]:
                search_filter.children.append((f"{field}__icontains", search_value))

            # 支持metric_id查询
            metric_split_list = search_value.split(".")
            if len(metric_split_list) == 3:
                result_table_id = ".".join(metric_split_list[:2])
                metric_field = metric_split_list[2]
                metrics = metrics.filter(
                    search_filter | Q(result_table_id=result_table_id, metric_field__startswith=metric_field)
                )
            if len(metric_split_list) == 2 and params["data_source_label"] == DataSourceLabel.BK_LOG_SEARCH:
                index_set_name = metric_split_list[0]
                metric_field = metric_split_list[1]
                metrics = metrics.filter(
                    search_filter | Q(related_name=index_set_name, metric_field__startswith=metric_field)
                )
            else:
                metrics = metrics.filter(search_filter)

        return metrics

    @classmethod
    def page_filter(cls, metrics: QuerySet, params) -> QuerySet:
        """
        分页过滤
        """
        # 如果监控对象为服务拨测，对其中的监控采集指标分类去重
        if (
            params.get("data_source_label", "") == DataSourceLabel.BK_MONITOR_COLLECTOR
            and params.get("data_type_label", "") == DataTypeLabel.TIME_SERIES
        ):
            uptimecheck_instance = []
            for metric_dict in cls.bkmonitor_metric:
                instance = metrics.filter(
                    result_table_id=metric_dict["result_table_id"], metric_field=metric_dict["metric_field"]
                )
                if len(instance) != 0:
                    total = instance.aggregate(use_frequency=Sum("use_frequency"))
                    instance = instance.first()
                    instance.use_frequency = total.get("use_frequency", "")
                    uptimecheck_instance.append(instance)
            metrics = sorted(uptimecheck_instance, key=lambda x: x.use_frequency, reverse=True)
        if params.get("page") and params.get("page_size"):
            # fmt: off
            metrics = metrics[(params["page"] - 1) * params["page_size"]: params["page"] * params["page_size"]]
            # fmt: on

        return metrics

    @classmethod
    def category_filter(cls, metrics: QuerySet, params):
        """
        分类过滤
        """
        if params.get("data_source_label"):
            metrics = metrics.filter(data_source_label=params["data_source_label"])
        if params.get("data_type_label"):
            metrics = metrics.filter(data_type_label=params["data_type_label"])
        return metrics.order_by("-use_frequency")

    @classmethod
    def tag_filter(cls, metrics: QuerySet, params):
        """
        标签过滤
        """
        tag = params["tag"]

        if tag == "__COMMON_USED__":
            metrics = metrics.exclude(use_frequency=0)
        elif tag:
            metrics = metrics.filter(result_table_id=tag)

        return metrics

    @classmethod
    def get_count_list(cls, metrics: QuerySet):
        """
        数据来源及类型分组统计
        """
        count_list = []
        for data_category_msg in DATA_CATEGORY:
            if (
                data_category_msg["data_source_label"] == DataSourceLabel.BK_LOG_SEARCH
                and data_category_msg["data_type_label"] == DataTypeLabel.LOG
            ):
                continue
            count_list.append(
                {
                    "count": 0,
                    "data_source_label": data_category_msg["data_source_label"],
                    "data_type_label": data_category_msg["data_type_label"],
                    "source_type": data_category_msg["type"],
                    "source_name": data_category_msg["name"],
                }
            )

        for count_msg in count_list:
            # 如果监控对象为服务拨测，对其中的监控采集指标分类计数
            if count_msg["source_type"] == "bk_monitor_time_series":
                cls.bkmonitor_metric = (
                    metrics.filter(
                        data_source_label=count_msg["data_source_label"], data_type_label=count_msg["data_type_label"]
                    )
                    .values("result_table_id", "metric_field")
                    .distinct()
                )
                count_msg["count"] = cls.bkmonitor_metric.count()
                continue
            count_msg["count"] = metrics.filter(
                data_source_label=count_msg["data_source_label"], data_type_label=count_msg["data_type_label"]
            ).count()

        return count_list

    @classmethod
    def get_tag_list(cls, metrics: QuerySet, params):
        """
        可选分类
        """
        tags = [{"id": "__COMMON_USED__", "name": _("常用")}]

        if params["search_fields"].get("related_id"):
            result_tables = metrics.values("result_table_id", "result_table_name").annotate(
                count=Count("result_table_id")
            )
            for result_table in result_tables:
                tags.append({"id": result_table["result_table_id"], "name": result_table["result_table_name"]})

        return tags

    @staticmethod
    def get_metric_remarks(metric: dict) -> list:
        """
        指标备注
        """
        if metric["data_type_label"] != "event" or metric["data_source_label"] != "bk_monitor":
            return []

        if metric["metric_field"] == "disk-full-gse":
            return [
                _("依赖bkmonitorbeat采集器, 在节点管理安装"),
            ]
        elif metric["metric_field"] == "disk-readonly-gse":
            return [
                _("依赖bkmonitorbeat采集器, 在节点管理安装"),
                _("通过对挂载磁盘的文件状态ro进行判断，类似Linux命令：fgrep ' ro,' /proc/mounts"),
            ]
        elif metric["metric_field"] == "corefile-gse":
            return [
                _("查看corefile生成路径：cat /proc/sys/kernel/core_pattern，确保在某一个目录下，例如 /data/corefile/core_%e_%t"),
                _("依赖bkmonitorbeat采集器, 在节点管理安装,会自动根据core_pattern监听文件目录"),
            ]
        elif metric["metric_field"] == "gse_custom_event":
            return [
                _("【已废弃】"),
                _("功能通过上报 自定义事件 覆盖").format(settings.LINUX_GSE_AGENT_PATH, settings.GSE_CUSTOM_EVENT_DATAID),
            ]
        elif metric["metric_field"] == "agent-gse":
            return [_("gse每隔60秒检查一次agent心跳数据。"), _("心跳数据持续未更新，24小时后将不再上报失联事件。")]
        elif metric["metric_field"] == "oom-gse":
            return [
                _("通过调用内核syslog接口获取系统日志，对out of memory:关键字匹配告警，应用进程触发的OOM告警"),
                _("通过对/proc/vmstat的oom_kill计数器进行判断告警，如递增则判断产生OOM告警，操作系统触发的OOM告警"),
            ]
        elif metric["metric_field"] == "os_restart":
            return [
                _("依赖bkmonitorbeat采集器的安装 ，在节点管理进行安装"),
                _("检测原理：通过最近2次的uptime数据对比，满足cur_uptime < pre_uptime，则判断为重启"),
            ]
        elif metric["metric_field"] == "ping-gse":
            return [
                _("依赖bk-collector采集器的安装，在节点管理进行安装"),
                _("由监控后台部署的bk-collector去探测目标IP是否存活。"),
            ]
        elif metric["metric_field"] == "proc_port":
            return [_("依赖bkmonitorbeat采集器的安装，在节点管理进行安装"), _("对CMDB中的进程端口存活状态判断，如不满足预定义数据状态，则产生告警")]

        return []

    @staticmethod
    def translate_metric(metric: dict) -> dict:
        """
        指标字段翻译
        """
        fields = [
            "result_table_name",
            "metric_field_name",
            "category_display",
            "description",
            "result_table_label_name",
        ]

        for field in fields:
            if field in metric:
                metric[field] = _(metric[field])

        for dimension in metric["dimensions"]:
            dimension["name"] = _(dimension["name"])

        return metric

    @classmethod
    def get_metric_list(cls, metrics: QuerySet, params):
        """
        指标数据
        """
        metric_list = []

        for metric in metrics:
            data = model_to_dict(metric)

            # 过滤进程托管的自定义上报指标
            if data["result_table_id"] == str(settings.GSE_PROCESS_REPORT_DATAID):
                continue

            # 默认触发条件
            data["default_trigger_config"] = (
                DEFAULT_TRIGGER_CONFIG_MAP.get(metric.data_source_label, {})
                .get(metric.data_type_label, {})
                .get(f"{metric.result_table_id}.{metric.metric_field}", GLOBAL_TRIGGER_CONFIG)
            )

            data["metric_description"] = MetricListCache.metric_description(metric=metric)
            data["remarks"] = cls.get_metric_remarks(data)

            # 拨测指标特殊处理
            if data["result_table_id"].startswith("uptimecheck."):
                # 仅对搜索任务ID和任务名时保留指标关联任务，选取后默认填充监控条件为搜索任务
                if not (params["search_fields"].get("related_id") or params["search_fields"].get("related_name")):
                    data["related_id"] = ""
                    data["related_name"] = ""

                if data["metric_field"] in ["response_code", "message"]:
                    data["method_list"] = ["COUNT"]
                else:
                    data["method_list"] = ["SUM", "AVG", "MAX", "MIN", "COUNT"]

                # 针对拨测服务采集，过滤业务/IP/云区域ID/错误码
                data["dimensions"] = [
                    dimension
                    for dimension in data["dimensions"]
                    if dimension["id"] not in ["bk_biz_id", "ip", "bk_cloud_id", "error_code"]
                ]
                for metric_msg in data["default_condition"]:
                    if metric_msg.get("key") == "task_id":
                        metric_msg["value"] = int(metric_msg["value"])
                    if metric_msg.get("key") in list(UPTIMECHECK_ERROR_CODE_MAP.keys()):
                        metric_msg["disabled"] = False if metric_msg.get("value") else True

            data = cls.translate_metric(data)

            # 单位处理
            unit = load_unit(data["unit"])
            suffix_list = unit.suffix_list if unit.suffix_list else []
            suffix_id = suffix_list[unit.suffix_idx] if unit.suffix_idx < len(suffix_list) else ""
            data["unit_suffix_list"] = [{"id": suffix, "name": f"{suffix}{unit._suffix}"} for suffix in suffix_list]
            if not data["unit_suffix_list"] and unit._suffix:
                data["unit_suffix_list"].append({"id": "", "name": unit._suffix})
                suffix_id = ""
            data["unit_suffix_id"] = suffix_id

            metric_list.append(data)

        return metric_list

    def perform_request(self, params):
        # 接口下线，不再使用，不分函数可能还在被调用
        raise ResourceNotRegistered("该接口已下线，请使用'/grafana/get_metric_list'替换")


class GetDimensionValuesResource(Resource):
    """
    获取指标维度最近上报的值
    """

    class RequestSerializer(serializers.Serializer):
        result_table_id = serializers.CharField(required=True, label="结果表名")
        metric_field = serializers.CharField(required=True, label="指标名")
        field = serializers.CharField(required=True, label="维度名")
        bk_biz_id = serializers.IntegerField(default=0, label="业务ID")
        filter_dict = serializers.DictField(default={}, label="过滤条件")
        where = serializers.ListField(default=[], label="查询条件")

    def perform_request(self, params):
        raise CustomException(_("此接口已被弃用，请联系管理员"))


class StrategyConfigListResource(Resource):
    """
    获取监控策略列表
    """

    def __init__(self):
        super(StrategyConfigListResource, self).__init__()
        self.node_manager = None
        self.label_map = None
        self.shield_manager = None

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=False, default=0, label="业务ID")
        bk_cloud_id = serializers.IntegerField(required=False, label="云区域ID")
        order_by = serializers.CharField(required=False, default="-update_time", label="排序字段")
        scenario = serializers.CharField(required=False, label="二级标签")
        page = serializers.IntegerField(required=False, label="页码")
        page_size = serializers.IntegerField(required=False, label="每页条数")
        notice_group_name = serializers.CharField(required=False, label="告警组名称")
        service_category = serializers.CharField(required=False, label="服务分类", allow_blank=True)
        task_id = serializers.IntegerField(required=False, label="任务ID")
        IP = serializers.IPAddressField(required=False, label="IP筛选")
        metric_id = serializers.CharField(required=False, label="指标ID")
        ids = serializers.ListField(required=False, label="ID列表")
        bk_event_group_id = serializers.IntegerField(required=False, label="事件分组ID")
        data_source_list = serializers.ListField(required=False, label="数据来源列表")
        conditions = serializers.ListField(label="搜索条件", required=False)
        only_using = serializers.IntegerField(required=False, label="仅统计在用的类型", default=0)

        def validate_data_source_list(self, value):
            try:
                return json.loads(value)
            except Exception as e:
                logger.exception("data_source_list参数错误, %s" % e)
                return []

    def get_label_msg(self, scenario):
        for first_label in self.label_map:
            for second_label in first_label["children"]:
                if second_label["id"] != scenario:
                    continue
                return {
                    "first_label": first_label["id"],
                    "first_label_name": first_label["name"],
                    "second_label": second_label["id"],
                    "second_label_name": second_label["name"],
                }

        return {
            "first_label": scenario,
            "first_label_name": scenario,
            "second_label": scenario,
            "second_label_name": scenario,
        }

    @staticmethod
    def get_node_type(config):
        """
        target : [
            [
            {"field":"ip", "method":"eq", "value": [{"ip":"127.0.0.1","bk_supplier_id":0,"bk_cloud_id":0},]},
            {"field":"host_topo_node", "method":"eq", "value": [{"bk_obj_id":"test","bk_inst_id":2}]}
            ],
            [
            {"field":"ip", "method":"eq", "value": [{"ip":"127.0.0.1","bk_supplier_id":0,"bk_cloud_id":0},]},
            {"field":"host_topo_node", "method":"eq", "value": [{"bk_obj_id":"test","bk_inst_id":2}]}
            ]
        ]
        target理论上支持多个列表以或关系存在，列表内部亦存在多个对象以且关系存在，
        由于目前产品形态只支持单对象的展示，因此若存在多对象，只取第一个对象返回给前端
        """
        if not config or not config[0]:
            return None

        first_target_config = config[0][0]
        node_type_map = {
            TargetFieldType.host_target_ip: "INSTANCE",
            TargetFieldType.host_ip: "INSTANCE",
            TargetFieldType.host_topo: "TOPO",
            TargetFieldType.service_topo: "TOPO",
            TargetFieldType.service_set_template: TargetNodeType.SET_TEMPLATE,
            TargetFieldType.service_service_template: TargetNodeType.SERVICE_TEMPLATE,
            TargetFieldType.host_service_template: TargetNodeType.SERVICE_TEMPLATE,
            TargetFieldType.host_set_template: TargetNodeType.SET_TEMPLATE,
        }
        return node_type_map[first_target_config.get("field")]

    @staticmethod
    def data_target(strategy_id, scenario):
        data_target_map = dict([(DataTarget.HOST_TARGET, "HOST"), (DataTarget.SERVICE_TARGET, "SERVICE")])
        query_config = QueryConfigModel.objects.filter(strategy_id=strategy_id).first()
        target = DataTargetMapping().get_data_target(
            result_table_label=scenario,
            data_source_label=query_config.data_source_label,
            data_type_label=query_config.data_type_label,
        )
        return data_target_map.get(target, "")

    def get_node_msg(self, bk_biz_id, config, strategy_id, scenario, template_map_data):
        node_msg = dict(
            [
                ("target_object_type", ""),
                ("target_node_type", ""),
                ("target_nodes_count", 0),
                ("total_instance_count", ""),
                ("add_allowed", False),
                ("service_category_data", []),
            ]
        )

        node_msg["target_object_type"] = self.data_target(strategy_id, scenario)
        # add_allowed 该字段用于页面展示， v1接口已被SaaS弃用，因此这里返回该字段为非准确值
        node_msg["add_allowed"] = True if node_msg["target_object_type"] else False
        if not config or not config[0]:
            return node_msg

        first_target_config = config[0][0]
        node_msg["target_node_type"] = self.get_node_type(config)

        node_msg["target_nodes_count"] = 0
        if node_msg["target_node_type"] == "INSTANCE":
            node_msg["total_instance_count"] = len(first_target_config.get("value"))
        elif node_msg["target_node_type"] in [TargetNodeType.SET_TEMPLATE, TargetNodeType.SERVICE_TEMPLATE]:
            total_instance_count = 0
            template_ids = [template["bk_inst_id"] for template in first_target_config.get("value", [])]
            # 获取目标节点个数和主机个数
            for template_node in template_map_data[node_msg["target_node_type"]].get("template_nodes", []):
                if template_node[node_msg["target_node_type"]] in template_ids:
                    total_instance_count += template_node["count"]
            node_msg["total_instance_count"] = total_instance_count
            node_msg["target_nodes_count"] = len(first_target_config.get("value"))
        else:
            node_msg["target_nodes_count"] = len(first_target_config.get("value"))
            result = self.node_manager.get_cc_info_by_node_list(
                bk_biz_id,
                first_target_config.get("value"),
                node_msg["target_object_type"],
                condition={"instance_count": True},
            )
            node_msg["total_instance_count"] = result["total_count"]
        return node_msg

    @staticmethod
    def get_relate_notice_group(strategy_id):
        action_instance = Action.objects.filter(strategy_id=strategy_id, action_type="notice").first()
        if not action_instance:
            return []
        mapping_ids = ActionNoticeMapping.objects.filter(action_id=action_instance.id)
        group_ids = [instance.notice_group_id for instance in mapping_ids]
        return_data = []

        for group_instance in NoticeGroup.objects.filter(id__in=group_ids):
            return_data.append({"id": group_instance.id, "display_name": group_instance.name})

        return return_data

    @staticmethod
    def get_data_source_type(strategy_id):
        query_configs = QueryConfigModel.objects.filter(strategy_id=strategy_id)
        source_type_list = []
        for query_config in query_configs:
            if query_config.metric_id in EVENT_METRIC_ID:
                source_type_list.append(_("系统事件"))
                continue

            for data_category_msg in DATA_CATEGORY:
                if all(
                    [
                        data_category_msg["data_type_label"] == query_config.data_type_label,
                        data_category_msg["data_source_label"] == query_config.data_source_label,
                    ]
                ):
                    source_type_list.append(data_category_msg["name"])
                    break

        if not source_type_list:
            source_type_list.append(_("自定义"))

        source_type_list = [str(x) for x in source_type_list]
        return ";".join(source_type_list)

    def get_shield_status(self, strategy_id):
        match_info = {"strategy_id": strategy_id, "level": [1, 2, 3]}
        return self.shield_manager.check_shield_status(match_info)

    def get_scenario_count(self, all_strategy):
        return_data = []
        for label_msg in self.label_map:
            for second_label in label_msg["children"]:
                count_msg = dict()
                count_msg["sort_msg"] = float("{}.{}".format(label_msg["index"], second_label["index"]))
                count_msg["id"] = second_label["id"]
                count_msg["display_name"] = second_label["name"]
                count_msg["count"] = all_strategy.filter(scenario=second_label["id"]).count()
                return_data.append(count_msg)
        return_data.sort(key=lambda x: x["sort_msg"])
        return return_data

    @staticmethod
    def search_notice_group(bk_biz_id, notice_group_name=None, fuzzy_search=False):
        if fuzzy_search:
            notice_groups = NoticeGroup.objects.filter(bk_biz_id=bk_biz_id)
            if notice_group_name:
                notice_groups = notice_groups.filter(name__icontains=notice_group_name)
        else:
            notice_groups = NoticeGroup.objects.filter(bk_biz_id=bk_biz_id)
            if notice_group_name:
                notice_groups = notice_groups.filter(name=notice_group_name)

        if not notice_groups:
            return []

        notice_group_ids = [notice_group.id for notice_group in notice_groups]
        action_ids = [
            map_msg.action_id for map_msg in ActionNoticeMapping.objects.filter(notice_group_id__in=notice_group_ids)
        ]
        return [action.strategy_id for action in Action.objects.filter(id__in=action_ids, action_type="notice")]

    @staticmethod
    def search_uptimecheck_strategy(all_strategy, task_id):
        if not isinstance(task_id, list):
            task_id = {str(task_id)}
        else:
            task_id = {str(_id) for _id in task_id}

        all_strategy = all_strategy.filter(scenario=Scenario.UPTIME_CHECK)
        strategy_ids = [strategy.id for strategy in all_strategy]

        uptime_strategy_ids = []
        for query_config in QueryConfigModel.objects.filter(strategy_id__in=strategy_ids):
            for condition in query_config.config.get("agg_condition", []):
                if condition["key"] != "task_id":
                    continue
                values = {str(value) for value in condition["value"]}
                if values & task_id:
                    strategy_ids.append(query_config.strategy_id)

        return uptime_strategy_ids

    def filter_by_ip(self, queryset, bk_biz_id, ip, bk_cloud_id):
        # 按主机IP筛选
        if not ip:
            return queryset

        filter_ids = []
        strategy_configs = {}
        for strategy in queryset.values():
            strategy_configs[strategy["id"]] = {"is_enabled": strategy["is_enabled"], "targets": []}

        items = ItemModel.objects.filter(strategy_id__in=list(strategy_configs.keys())).values("strategy_id", "target")

        for item in items:
            target = item["target"]
            if not target:
                continue
            if not target[0]:
                continue
            strategy_configs[item["strategy_id"]]["targets"].append(target)
            strategy_configs[item["strategy_id"]]["id"] = item["strategy_id"]

        # 搜索IP时也需要返回IP在动态拓扑里的策略
        if bk_cloud_id is not None:
            # 如果是主机详情跳转过来的，则有bk_cloud_id
            hosts = api.cmdb.get_host_by_ip(ips=[dict(ip=ip, bk_cloud_id=bk_cloud_id)], bk_biz_id=bk_biz_id)
        else:
            # 普通搜索IP
            hosts = api.cmdb.get_host_by_ip(ips=[dict(ip=ip)], bk_biz_id=bk_biz_id)
        host_modules = []
        for host in hosts:
            host_modules.extend([f"module|{module}" for module in host.bk_module_ids])
        topo_tree = api.cmdb.get_topo_tree(bk_biz_id=bk_biz_id)
        topo_link = topo_tree.convert_to_topo_link()
        # 获得该主机所有拓扑模块
        topo_set = set()
        for module in host_modules:
            topo_set.update({link.id for link in topo_link[module]})

        for strategy_config in list(strategy_configs.values()):
            is_matched = False
            for target in strategy_config["targets"]:
                # 如果已经匹配，则退出
                if is_matched:
                    break

                # 如果是动态拓扑
                if target[0][0]["field"] in ["host_topo_node", "service_topo_node"]:
                    target_topos = {f'{obj["bk_obj_id"]}|{obj["bk_inst_id"]}' for obj in target[0][0]["value"]}
                    if target_topos.intersection(topo_set):
                        is_matched = True
                        filter_ids.append(strategy_config["id"])

                # 如果是模板
                if "template" in target[0][0]["field"]:
                    template_type = (
                        TargetNodeType.SERVICE_TEMPLATE
                        if ("service_template" in target[0][0]["field"])
                        else TargetNodeType.SET_TEMPLATE
                    )
                    template_hosts = api.cmdb.get_host_by_template(
                        dict(
                            bk_biz_id=bk_biz_id,
                            bk_obj_id=template_type,
                            template_ids=[template["bk_inst_id"] for template in target[0][0]["value"]],
                        )
                    )
                    for host in hosts:
                        if host in template_hosts:
                            is_matched = True
                            filter_ids.append(strategy_config["id"])

                # 如果是静态IP
                target_values = target[0][0]["value"]
                for value in target_values:
                    # 非主机目标直接退出
                    if "bk_target_ip" not in value:
                        break
                    if ip in [value.get("bk_target_ip", "") for value in target[0][0].get("value", [])]:
                        is_matched = True
                        filter_ids.append(strategy_config["id"])

        return queryset.filter(id__in=filter_ids)

    def filter_source_type(self, data_source_list, all_strategy):
        """
        过滤数据来源
        :param data_source_list: 数据来源列表
        :param all_strategy: 策略列表
        """
        include_system_event = False
        source_type_list = []
        for source_msg in DATA_CATEGORY:
            if source_msg["type"] in data_source_list:
                if source_msg["type"] == "bk_monitor_log":
                    # 如果是日志关键字，将日志检索的日志关键字也加入其中
                    source_type_list.append(
                        {
                            "type": "bk_log_search_log",
                            "name": _("日志关键字"),
                            "data_type_label": DataTypeLabel.LOG,
                            "data_source_label": DataSourceLabel.BK_LOG_SEARCH,
                        }
                    )
                source_type_list.append(source_msg)

                if (
                    source_msg["data_source_label"] == DataSourceLabel.BK_MONITOR_COLLECTOR
                    and source_msg["data_type_label"] == DataTypeLabel.EVENT
                ):
                    include_system_event = True

        source_type_list = [x for x in DATA_CATEGORY if x["type"] in data_source_list]
        if source_type_list:
            search_msg = Q()
            for source_type_dict in source_type_list:
                search_children_msg = Q()
                search_children_msg.connector = "AND"
                search_children_msg.children.append(("data_source_label", source_type_dict["data_source_label"]))
                search_children_msg.children.append(("data_type_label", source_type_dict["data_type_label"]))
                search_msg.add(search_children_msg, "OR")

            if include_system_event:
                query_configs = QueryConfigModel.objects.filter(search_msg | Q(metric_id__in=EVENT_METRIC_ID))
            else:
                query_configs = QueryConfigModel.objects.filter(~Q(metric_id__in=EVENT_METRIC_ID)).filter(search_msg)
            strategy_ids = query_configs.values_list("strategy_id", flat=True).distinct()
            all_strategy = all_strategy.filter(id__in=strategy_ids)
        return all_strategy

    def transfer_str_list_to_int(self, str_list):
        """
        将字符串数组的元素都转为int
        :param str_list: 字符串数组
        :return: 转化后的结果
        """
        new_list = []
        for value in str_list:
            try:
                new_list.append(int(value))
            except ValueError:
                continue
        return new_list

    def filter_all_strategies_by_accurate(
        self, bk_biz_id, all_strategy, conditions, legacy_strategy_list, strategy_alert_num
    ):
        """
        精准搜索
        :param bk_biz_id: 业务ID
        :param all_strategy: 策略列表
        :param conditions: 条件
        :param legacy_strategy_list: 失效策略列表
        :param strategy_alert_num: 告警策略列表
        :return: 搜索结果
        """
        from monitor_web.strategies.resources import StrategyLabelResource

        # 旧接口限定单指标查询
        items = ItemModel.objects.annotate(expression_len=Length("expression")).filter(
            expression__lte=1, strategy_id__in=all_strategy.values_list("id", flat=True)
        )
        strategy_ids = items.values_list("strategy_id", flat=True).distinct()
        all_strategy = all_strategy.filter(id__in=strategy_ids)

        # 精准搜索ID
        if conditions.get("strategy_id"):
            conditions["strategy_id"] = self.transfer_str_list_to_int(conditions["strategy_id"])
            all_strategy = all_strategy.filter(id__in=conditions["strategy_id"])

        # 精准搜索策略名称
        if conditions.get("strategy_name"):
            all_strategy = all_strategy.filter(name__in=conditions["strategy_name"])

        # 精准搜索指标ID
        if conditions.get("metric_id"):
            q_search_list = Q()
            q_search_list.connector = "OR"
            q_search_list.children.extend(
                [("metric_id__icontains", metric_id) for metric_id in conditions["metric_id"]]
            )
            query_configs = QueryConfigModel.objects.filter(q_search_list)
            strategy_ids = [query_config.strategy_id for query_config in query_configs]
            all_strategy = all_strategy.filter(id__in=strategy_ids)

        # 精准搜索指标名/别名
        if conditions.get("metric_alias") or conditions.get("metric_name"):
            metrics = MetricListCache.objects.all()
            if conditions.get("metric_alias"):
                metrics = metrics.filter(metric_field_name__in=conditions["metric_alias"])
            if conditions.get("metric_name"):
                metrics = metrics.filter(metric_field__in=conditions["metric_name"])

            table_ids = [metric.result_table_id for metric in metrics.only("result_table_id")]
            if table_ids:
                strategy_ids = (
                    QueryConfigModel.objects.filter(strategy_id__in=strategy_ids)
                    .filter(reduce(lambda x, y: x | y, (Q(config__result_table_id=table_id) for table_id in table_ids)))
                    .values_list("strategy_id", flat=True)
                    .distinct()
                )
            else:
                strategy_ids = []
            all_strategy = all_strategy.filter(id__in=strategy_ids)

        # 精准搜索告警组
        if conditions.get("notice_group_name"):
            notice_group_name = conditions["notice_group_name"]
            all_strategy = all_strategy.filter(id__in=self.search_notice_group(bk_biz_id, notice_group_name[0]))

        # 精准搜索创建人
        if conditions.get("creators"):
            all_strategy = all_strategy.filter(create_user__in=conditions["creators"])

        # 精准搜索修改人
        if conditions.get("updaters"):
            all_strategy = all_strategy.filter(update_user__in=conditions["updaters"])

        # 精准搜索拨测任务
        if conditions.get("task_id"):
            strategy_ids = self.search_uptimecheck_strategy(all_strategy, conditions["task_id"])
            all_strategy = all_strategy.filter(id__in=strategy_ids)

        # 数据来源筛选
        if conditions.get("data_source_list"):
            all_strategy = self.filter_source_type(conditions.get("data_source_list"), all_strategy)

        # 监控对象筛选
        if conditions.get("scenario"):
            all_strategy = all_strategy.filter(scenario__in=conditions["scenario"])

        # 精准搜索状态
        if conditions.get("strategy_status"):
            strategy_status = conditions["strategy_status"]
            if "ON" in strategy_status and "OFF" not in strategy_status:
                all_strategy = all_strategy.filter(is_enabled=True)
            if "ON" not in strategy_status and "OFF" in strategy_status:
                all_strategy = all_strategy.filter(is_enabled=False)
            if "ALERT" in strategy_status:
                all_strategy = all_strategy.filter(id__in=list(strategy_alert_num.keys()))
            if "LEGACY" in strategy_status:
                all_strategy = all_strategy.filter(id__in=list(legacy_strategy_list))

        # 精准搜索IP
        if conditions.get("IP"):
            if conditions.get("bk_cloud_id"):
                for index, ip in enumerate(conditions["IP"]):
                    all_strategy = self.filter_by_ip(
                        all_strategy, bk_biz_id, ip, bk_cloud_id=int(conditions["bk_cloud_id"][index])
                    )
            else:
                all_strategy = self.filter_by_ip(all_strategy, bk_biz_id, conditions["IP"][0], bk_cloud_id=None)

        if conditions.get("label_name"):
            strategy_label_list = [
                StrategyLabelResource.gen_label_name(value) for value in conditions.get("label_name", [])
            ]
            strategy_ids = StrategyLabel.objects.filter(label_name__in=strategy_label_list).values_list(
                "strategy_id", flat=True
            )
            all_strategy = all_strategy.filter(id__in=strategy_ids)
        return all_strategy

    def filter_all_strategies(self, validated_request_data):
        self.label_map = resource.commons.get_label()
        ids = validated_request_data.get("ids")
        bk_biz_id = validated_request_data.get("bk_biz_id")
        order = validated_request_data.get("order_by")
        notice_group_name = validated_request_data.get("notice_group_name", None)
        task_id = validated_request_data.get("task_id", None)
        bk_cloud_id = validated_request_data.get("bk_cloud_id", None)
        ip = validated_request_data.get("IP", None)
        metric_id = validated_request_data.get("metric_id", None)
        bk_event_group_id = validated_request_data.get("bk_event_group_id", None)
        search = validated_request_data.get("conditions", {}).get("query", "")

        all_strategy = StrategyModel.objects.all()
        self.shield_manager = ShieldDetectManager(bk_biz_id, "strategy")
        self.node_manager = CmdbUtil(bk_biz_id)

        # 按metric_id筛选
        if metric_id:
            item_list = QueryConfigModel.objects.filter(metric_id__icontains=metric_id)
            strategy_ids = [item.strategy_id for item in item_list]
            all_strategy = all_strategy.filter(id__in=strategy_ids)

        # 按拨测任务ID筛选策略配置
        if task_id:
            strategy_ids = self.search_uptimecheck_strategy(all_strategy, task_id)
            all_strategy = all_strategy.filter(id__in=strategy_ids)

        # 按告警组名称来搜索策略配置
        if notice_group_name:
            # 优先精确匹配，若找不到数据，则进行模糊匹配
            strategy_ids = self.search_notice_group(bk_biz_id, notice_group_name) or self.search_notice_group(
                bk_biz_id, notice_group_name, fuzzy_search=True
            )
            all_strategy = all_strategy.filter(id__in=strategy_ids)

        # 按事件分组筛选
        if bk_event_group_id:
            result_table_id = CustomEventGroup.objects.get(bk_event_group_id=bk_event_group_id).table_id
            custom_event_strategy_ids = [
                custom_event.strategy_id
                for custom_event in QueryConfigModel.objects.filter(
                    data_source_label=DataSourceLabel.CUSTOM,
                    data_type_label=DataTypeLabel.EVENT,
                    config__result_table_id=result_table_id,
                )
            ]

            all_strategy = all_strategy.filter(id__in=custom_event_strategy_ids)

        if order.replace("-", "") not in [f.name for f in StrategyModel._meta.fields]:
            order = "-update_time"

        # bk_biz_id可以为空，为空则按用户拥有的业务查询
        if bk_biz_id:
            all_strategy = all_strategy.filter(bk_biz_id=bk_biz_id).order_by(order)
        else:
            all_strategy = all_strategy.filter(
                bk_biz_id__in=resource.space.get_bk_biz_ids_by_user(get_request().user)
            ).order_by(order)

        # 模糊搜索
        if search:
            all_strategy = all_strategy.filter(Q(id__icontains=search) | Q(name__icontains=search))

        # ip搜索
        if ip:
            all_strategy = self.filter_by_ip(all_strategy, bk_biz_id, ip, bk_cloud_id)

        if ids:
            all_strategy = all_strategy.filter(id__in=ids)

        return all_strategy

    def perform_request(self, validated_request_data):
        return_data = {}
        validated_request_data["conditions"] = {
            condition["key"]: condition["value"] for condition in validated_request_data.get("conditions", [])
        }

        # 获得所有失效策略
        legacy_strategy_list = resource.collecting.list_legacy_strategy(bk_biz_id=validated_request_data["bk_biz_id"])

        # 获得所有告警事件
        alert_events = resource.alert_events.query_events(
            dict(bk_biz_ids=[validated_request_data["bk_biz_id"]])
        ).filter(status=EventStatus.ABNORMAL, is_shielded=False)
        strategy_alert_num = {}
        for event in alert_events:
            if event.strategy_id not in strategy_alert_num:
                strategy_alert_num[event.strategy_id] = 1
            else:
                strategy_alert_num[event.strategy_id] += 1

        # 用于处理模糊搜索、跳转搜索及列表筛选
        all_strategy = self.filter_all_strategies(validated_request_data)

        # 精准搜索
        all_strategy = self.filter_all_strategies_by_accurate(
            validated_request_data["bk_biz_id"],
            all_strategy,
            validated_request_data["conditions"],
            legacy_strategy_list,
            strategy_alert_num,
        )

        # 查询每种分类的策略数量
        scenario_list = self.get_scenario_count(all_strategy)

        # 按场景过滤
        if validated_request_data.get("scenario"):
            all_strategy = all_strategy.filter(scenario=validated_request_data.get("scenario", ""))

        strategy_ids = [int(s["id"]) for s in all_strategy.values("id")]

        # 分页
        page = validated_request_data.get("page", 0)
        page_size = validated_request_data.get("page_size", 0)
        if all([page, page_size]):
            # fmt: off
            all_strategy = all_strategy[(page - 1) * page_size: page * page_size]
            # fmt: on

        strategies = Strategy.from_models(all_strategy)
        strategy_list = []
        # 提前提取相关数据，避免N+1
        template_map_data = {}
        for item in chain(*[strategy.items for strategy in strategies]):
            # 如果目标中含有服务模板/集群模板类型，放入字典中
            target_node_type = self.get_node_type(item.target)
            if target_node_type in [TargetNodeType.SET_TEMPLATE, TargetNodeType.SERVICE_TEMPLATE]:
                if target_node_type not in template_map_data:
                    template_map_data[target_node_type] = {}
                    template_map_data[target_node_type]["need_node_template_ids"] = set()
                first_target_config = item.target[0][0]
                need_node_template_ids = [template["bk_inst_id"] for template in first_target_config.get("value", [])]
                for template_id in need_node_template_ids:
                    template_map_data[target_node_type]["need_node_template_ids"].add(template_id)

        for template_type in template_map_data:
            # 获取所需要的模板下对应的节点
            template_nodes = resource.commons.get_nodes_by_template(
                bk_biz_id=validated_request_data["bk_biz_id"],
                bk_obj_id=template_type,
                bk_inst_ids=list(template_map_data[template_type]["need_node_template_ids"]),
                bk_inst_type=TargetObjectType.HOST,
            )
            template_map_data[template_type]["template_nodes"] = template_nodes

        for strategy in strategies:
            strategy_config = {
                "bk_biz_id": strategy.bk_biz_id,
                "name": strategy.name,
                "id": strategy.id,
                "scenario": strategy.scenario,
                "source": strategy.source,
                "is_enabled": strategy.is_enabled,
                "update_user": strategy.update_user,
                "update_time": strategy.update_time,
                "create_user": strategy.create_user,
                "create_time": strategy.create_time,
                "labels": StrategyModel(id=strategy.id).labels,
            }

            if strategy.items:
                target = strategy.items[0].target
            else:
                target = [[]]

            node_msg = self.get_node_msg(
                strategy.bk_biz_id,
                target,
                strategy.id,
                strategy.scenario,
                template_map_data,
            )
            label_msg = self.get_label_msg(strategy.scenario)
            strategy_config.update(node_msg)
            strategy_config.update(label_msg)
            strategy_config["data_source_type"] = self.get_data_source_type(strategy_config["id"])
            strategy_config["notice_group_id_list"] = self.get_relate_notice_group(strategy_config["id"])
            strategy_config["shield_info"] = self.get_shield_status(strategy_config["id"])
            strategy_config["abnormal_alert_count"] = strategy_alert_num.get(strategy_config["id"], 0)

            # 获取监控项指标说明详情
            strategy.restore()
            result_data = strategy.to_dict_v1()
            strategy_config["item_list"] = []
            for item in result_data["item_list"]:
                strategy_config["item_list"].append(StrategyConfigDetailResource.format_item_detail(item))

            if strategy_config["id"] in legacy_strategy_list:
                strategy_config["is_legacy"] = True
            else:
                strategy_config["is_legacy"] = False
            strategy_list.append(strategy_config)

        return_data["strategy_config_list"] = strategy_list
        # 查询每种分类的策略数量
        return_data["scenario_list"] = scenario_list
        return_data["data_source_list"] = self.get_data_source_list(strategy_ids)
        return_data["strategy_label_list"] = self.get_strategy_label_list(
            strategy_ids, validated_request_data["bk_biz_id"]
        )
        return_data["notice_group_list"] = self.get_notice_group_name_list(
            strategy_ids, validated_request_data["bk_biz_id"]
        )
        if validated_request_data["only_using"] > 0:
            for label_key in ["scenario_list", "data_source_list", "strategy_label_list", "notice_group_list"]:
                key_info_list = return_data[label_key]
                return_data[label_key] = list(filter(lambda item: item["count"] > 0, key_info_list))
        return return_data

    def get_notice_group_name_list(self, strategy_ids, bk_biz_id):
        action_ids = Action.objects.filter(strategy_id__in=strategy_ids)
        # 统计关联的告警策略数量
        strategy_counts = (
            ActionNoticeMapping.objects.filter(action_id__in=action_ids)
            .values("notice_group_id")
            .annotate(total=Count("action_id", distinct=True))
        )
        strategy_count_dict = {
            strategy_count["notice_group_id"]: strategy_count["total"] for strategy_count in strategy_counts
        }
        notice_group_list = []
        for ng in NoticeGroup.objects.filter(bk_biz_id=bk_biz_id).only("id", "name"):
            notice_group_list.append(
                {"notice_group_id": ng.id, "notice_group_name": ng.name, "count": strategy_count_dict.get(ng.id, 0)}
            )
        return notice_group_list

    def get_data_source_list(self, strategy_ids):
        data_source_list = []
        count_info_list = (
            QueryConfigModel.objects.filter(strategy_id__in=strategy_ids)
            .values("data_source_label", "data_type_label")
            .annotate(total=Count("strategy_id", distinct=True))
        )
        for ds in DATA_CATEGORY:
            for count_info in count_info_list:
                if (
                    ds["data_source_label"] == count_info["data_source_label"]
                    and ds["data_type_label"] == count_info["data_type_label"]
                ):
                    ds["count"] = count_info["total"]
                    break
            else:
                ds["count"] = 0
            data_source_list.append(ds)
        return data_source_list

    def get_strategy_label_list(self, strategy_ids, bk_biz_id):
        from monitor_web.strategies.resources import StrategyLabelList

        count_info_list = (
            StrategyLabel.objects.filter(strategy_id__in=strategy_ids)
            .values("label_name")
            .annotate(total=Count("strategy_id", distinct=True))
        )
        labels_info = StrategyLabelList()(bk_biz_id=bk_biz_id, strategy_id=0)
        labels = labels_info["global"] + labels_info["custom"]
        strategy_label_list = []
        for label in labels:
            for count_info in count_info_list:
                if label["id"] == count_info["label_name"]:
                    label["count"] = count_info["total"]
                    break
            else:
                label["count"] = 0
            strategy_label_list.append(label)
        return strategy_label_list


class StrategyConfigDetailResource(Resource):
    """
    获取监控策略详情
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        id = serializers.IntegerField(required=True, label="策略ID")

    @staticmethod
    def format_item_detail(item):
        item.pop("no_data_config", None)
        detect_algorithm_list = item.pop("algorithm_list")
        detect_algorithm_dict = {}
        item["detect_algorithm_list"] = []
        # 日志关键字需要的部分
        if item.get("data_type_label") == DataTypeLabel.LOG:
            if item["data_source_label"] == DataSourceLabel.BK_LOG_SEARCH:
                item["scenario_id"] = item.get("extend_fields", {}).get("scenario_id")
                item["scenario_name"] = item.get("extend_fields", {}).get("scenario_name")
                item["index_set_id"] = item.get("extend_fields", {}).get("index_set_id")
                item["metric_field_name"] = item.get("name")
                item["metric_field"] = item.get("name")
            elif item["data_source_label"] == DataSourceLabel.BK_MONITOR_COLLECTOR:
                item["metric_field_name"] = item["name"]
                item["metric_field"] = item["metric_id"].split(".")[-1]
                if item["data_type_label"] == DataTypeLabel.LOG:
                    item["metric_field"] = "event.count"
        elif item["data_source_label"] == DataSourceLabel.CUSTOM and item["data_type_label"] == DataTypeLabel.EVENT:
            try:
                custom_event_group = CustomEventGroup.objects.get(table_id=item["result_table_id"])
                item["result_table_id"] = str(custom_event_group.bk_data_id)
                metric = MetricListCache.objects.filter(
                    data_source_label=DataSourceLabel.CUSTOM,
                    data_type_label=DataTypeLabel.EVENT,
                    result_table_id=item["result_table_id"],
                    metric_field_name=item["extend_fields"]["custom_event_name"],
                ).first()
                item["metric_field"] = metric.metric_field if metric else "0"
            except CustomEventGroup.DoesNotExist:
                item["result_table_id"] = "0"
                item["metric_field"] = "0"

        if len(detect_algorithm_list) > 0:
            item["trigger_config"] = detect_algorithm_list[0]["trigger_config"]
            item["recovery_config"] = detect_algorithm_list[0]["recovery_config"]
        else:
            item["trigger_config"] = {}
            item["recovery_config"] = {}

        for algorithm in detect_algorithm_list:
            algorithm.pop("trigger_config", None)
            algorithm.pop("recovery_config", None)
            level = algorithm.pop("level")
            detect_algorithm_dict.setdefault(level, []).append(algorithm)

        for level, config in list(detect_algorithm_dict.items()):
            item["detect_algorithm_list"].append({"level": level, "algorithm_list": config})
        return item

    @classmethod
    def get_target_detail(cls, strategy_config):
        """
        target : [
                    [
                    {"field":"ip", "method":"eq", "value": [{"ip":"127.0.0.1","bk_supplier_id":0,"bk_cloud_id":0},]},
                    {"field":"host_topo_node", "method":"eq", "value": [{"bk_obj_id":"test","bk_inst_id":2}]}
                    ],
                    [
                    {"field":"ip", "method":"eq", "value": [{"ip":"127.0.0.1","bk_supplier_id":0,"bk_cloud_id":0},]},
                    {"field":"host_topo_node", "method":"eq", "value": [{"bk_obj_id":"test","bk_inst_id":2}]}
                    ]
                ]
        target理论上支持多个列表以或关系存在，列表内部亦存在多个对象以且关系存在，
        由于目前产品形态只支持单对象的展示，因此若存在多对象，只取第一个对象返回给前端
        """
        target_type_map = {
            TargetFieldType.host_target_ip: TargetNodeType.INSTANCE,
            TargetFieldType.host_ip: TargetNodeType.INSTANCE,
            TargetFieldType.host_topo: TargetNodeType.TOPO,
            TargetFieldType.service_topo: TargetNodeType.TOPO,
            TargetFieldType.service_service_template: TargetNodeType.SERVICE_TEMPLATE,
            TargetFieldType.service_set_template: TargetNodeType.SET_TEMPLATE,
            TargetFieldType.host_service_template: TargetNodeType.SERVICE_TEMPLATE,
            TargetFieldType.host_set_template: TargetNodeType.SET_TEMPLATE,
        }
        obj_type_map = {
            TargetFieldType.host_target_ip: TargetObjectType.HOST,
            TargetFieldType.host_ip: TargetObjectType.HOST,
            TargetFieldType.host_topo: TargetObjectType.HOST,
            TargetFieldType.service_topo: TargetObjectType.SERVICE,
            TargetFieldType.service_service_template: TargetObjectType.SERVICE,
            TargetFieldType.service_set_template: TargetObjectType.SERVICE,
            TargetFieldType.host_service_template: TargetObjectType.HOST,
            TargetFieldType.host_set_template: TargetObjectType.HOST,
        }
        info_func_map = {
            TargetFieldType.host_target_ip: resource.commons.get_host_instance_by_ip,
            TargetFieldType.host_ip: resource.commons.get_host_instance_by_ip,
            TargetFieldType.service_topo: resource.commons.get_service_instance_by_node,
            TargetFieldType.host_topo: resource.commons.get_host_instance_by_node,
            TargetFieldType.service_service_template: resource.commons.get_nodes_by_template,
            TargetFieldType.service_set_template: resource.commons.get_nodes_by_template,
            TargetFieldType.host_service_template: resource.commons.get_nodes_by_template,
            TargetFieldType.host_set_template: resource.commons.get_nodes_by_template,
        }
        empty_info = {
            "bk_target_type": None,
            "bk_obj_type": None,
            "bk_target_detail": None,
        }
        bk_biz_id = strategy_config["bk_biz_id"]

        if not strategy_config["item_list"]:
            return empty_info

        target = copy.deepcopy(strategy_config["item_list"][0]["target"])
        # 判断target格式是否符合预期
        if not target or not target[0]:
            return empty_info
        else:
            target = target[0][0]

        # 校验是否有item
        if not len(strategy_config["item_list"]):
            return empty_info

        field = target.get("field")
        if not field:
            return empty_info

        params = {"bk_biz_id": bk_biz_id}
        if field in [TargetFieldType.host_ip, TargetFieldType.host_target_ip]:
            params["ip_list"] = [
                {"ip": x["bk_target_ip"], "bk_cloud_id": x["bk_target_cloud_id"]} if x.get("bk_target_ip") else x
                for x in target.get("value")
            ]
            params["bk_biz_ids"] = [bk_biz_id]
        elif field in [
            TargetFieldType.host_set_template,
            TargetFieldType.host_service_template,
            TargetFieldType.service_set_template,
            TargetFieldType.service_service_template,
        ]:
            params["bk_obj_id"] = target_type_map[field]
            params["bk_inst_type"] = obj_type_map[field]
            params["bk_inst_ids"] = [inst["bk_inst_id"] for inst in target["value"]]
        else:
            node_list = target.get("value")
            for target_item in node_list:
                if "bk_biz_id" not in target_item:
                    target_item.update(bk_biz_id=bk_biz_id)
            params["node_list"] = node_list

        return {
            "bk_obj_type": obj_type_map[field],
            "bk_target_type": target_type_map[field],
            "bk_target_detail": info_func_map[field](params),
        }

    def handel_uptimecheck_strategy_data(self, result_data):
        # 处理拨测策略
        for item in result_data["item_list"]:
            if not item["result_table_id"].startswith("uptimecheck."):
                continue
            if item["metric_field"] in ["response_code", "message"]:
                item["method_list"] = ["COUNT"]
            else:
                item["method_list"] = ["SUM", "AVG", "MAX", "MIN", "COUNT"]
        return result_data

    @staticmethod
    def handle_result_data(result_data):
        # 将结果处理为前端所需结构
        result_data["no_data_config"] = result_data["item_list"][0]["no_data_config"]
        # 通知模板处理
        result_data["message_template"] = result_data["action_list"][0]["notice_template"]["anomaly_template"]
        for item in result_data["item_list"]:
            item = StrategyConfigDetailResource.format_item_detail(item)
            item["metric_description"] = MetricListCache.metric_description(item)

        for action in result_data["action_list"]:
            action.pop("notice_template", None)
            notice_group_list = action.pop("notice_group_list")
            group_id_list = []
            group_list = []
            is_snaphot_strategy = all([isinstance(x, dict) for x in notice_group_list])
            if is_snaphot_strategy:
                # 如果是快照策略数据，直接取快照相关值
                for notice_group_msg in notice_group_list:
                    group_id_list.append(notice_group_msg["id"])
                    group_list.append({"id": notice_group_msg["id"], "display_name": notice_group_msg["name"]})
            else:
                group_id_list = notice_group_list
                group_instance_list = NoticeGroup.objects.filter(id__in=group_id_list)
                group_list = [{"id": group.id, "display_name": group.name} for group in group_instance_list]
            action["notice_group_list"] = group_list
            action["notice_group_id_list"] = group_id_list

        return result_data

    def perform_request(self, validated_request_data):
        strategy_instance = StrategyModel.objects.filter(id=validated_request_data["id"]).first()
        if not strategy_instance:
            raise StrategyNotExist

        # 获取策略配置
        strategy = Strategy.from_models([strategy_instance])[0]
        strategy.restore()
        result_data = strategy.to_dict_v1()
        result_data["labels"] = strategy_instance.labels
        # 数据格式处理
        result_data = self.handle_result_data(result_data)
        result_data = self.handel_uptimecheck_strategy_data(result_data)

        # 获取target相关信息
        target_info = self.get_target_detail(result_data)
        result_data.update(**target_info)

        for item in result_data["item_list"]:
            # 产品形态目前只支持单监控目标对象，如果通过api创建了多监控目标对象，只取第一个
            if item["target"] and item["target"][0]:
                item["target"] = [[item["target"][0][0]]]

            for target_list in item["target"]:
                for target_detail in target_list:
                    if target_detail["field"] in [TargetFieldType.host_target_ip, TargetFieldType.host_ip]:
                        target_detail["field"] = TargetFieldType.host_ip
                        target_detail["value"] = list(
                            [
                                {"ip": x["bk_target_ip"], "bk_cloud_id": x["bk_target_cloud_id"]}
                                if x.get("bk_target_ip")
                                else x
                                for x in target_detail["value"]
                            ]
                        )

            # 处理单位
            unit = load_unit(item.get("unit", ""))
            suffix_list = unit.suffix_list if unit.suffix_list else []
            suffix_id = suffix_list[unit.suffix_idx] if unit.suffix_idx < len(suffix_list) else ""
            item["unit_suffix_list"] = [{"id": suffix, "name": f"{suffix}{unit._suffix}"} for suffix in suffix_list]
            if not item["unit_suffix_list"] and unit._suffix:
                item["unit_suffix_list"].append({"id": "", "name": unit._suffix})
                suffix_id = ""
            item["unit_suffix_id"] = suffix_id

            item["remarks"] = GetMetricListResource.get_metric_remarks(item)
        return result_data


class DeleteStrategyConfigResource(Resource):
    """
    删除监控策略
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        id = serializers.IntegerField(required=False, label="策略ID")
        ids = serializers.ListField(required=False, label="策略ID列表")

    def perform_request(self, params):
        if "id" not in params and "ids" not in params:
            raise ValidationError("need id or ids")

        if "id" in params:
            strategy_ids = [params["id"]]
        else:
            strategy_ids = params["ids"]

        # 删除相关联的屏蔽
        from bkmonitor.models import Shield

        shield_list = Shield.objects.filter(bk_biz_id=params["bk_biz_id"], category="strategy")
        for item in shield_list:
            if item.dimension_config.get("strategy_id") in strategy_ids:
                item.delete()

        strategy_ids = StrategyModel.objects.filter(bk_biz_id=params["bk_biz_id"], id__in=strategy_ids).values_list(
            "id", flat=True
        )

        # 删除策略
        Strategy.delete_by_strategy_ids(list(strategy_ids))


class StrategyConfigResource(Resource):
    """
    创建、修改监控策略
    """

    class RequestSerializer(serializers.Serializer):
        class ItemListSerializer(serializers.Serializer):
            class DetectAlgorithmSerializer(serializers.Serializer):
                class AlgorithmSerializer(serializers.Serializer):
                    algorithm_config = serializers.JSONField(required=True, label="检测算法配置")
                    algorithm_type = serializers.ChoiceField(
                        required=True, choices=DETECT_ALGORITHM_CHOICES, label="检测算法"
                    )
                    algorithm_unit = serializers.CharField(required=False, allow_blank=True, default="", label="算法单位")

                    def validate_algorithm_config(self, value):
                        return validate_algorithm_config_msg(value)

                level = serializers.IntegerField(required=True, label="告警级别")
                algorithm_list = AlgorithmSerializer(many=True, label="检测算法列表")

                def validate_algorithm_list(self, value):
                    return validate_algorithm_msg(value)

            id = serializers.IntegerField(required=False, label="item_id")
            name = serializers.CharField(required=True, label="监控指标别名")
            metric_field = serializers.CharField(required=True, label="监控指标别名")
            # 数据来源标签，例如：计算平台(bk_data)，监控采集器(bk_monitor_collector)
            data_source_label = serializers.CharField(required=True, label="数据来源标签")
            # 数据类型标签，例如：时序数据(time_series)，事件数据(event)，日志数据(log)
            data_type_label = serializers.CharField(required=True, label="数据类型标签")
            result_table_id = serializers.CharField(required=False, allow_blank=True, label="表名")
            agg_method = serializers.CharField(required=False, allow_blank=True, label="聚合算法")
            agg_interval = serializers.CharField(required=False, allow_blank=True, label="聚合周期")
            agg_dimension = serializers.ListField(required=False, allow_empty=True, label="聚合维度")
            agg_condition = serializers.ListField(required=False, allow_empty=True, label="聚合条件")
            unit = serializers.CharField(required=False, allow_blank=True, label="单位")
            unit_conversion = serializers.FloatField(required=False, default=1.0, label="单位换算")
            detect_algorithm_list = DetectAlgorithmSerializer(required=True, many=True, label="检测算法列表")
            trigger_config = serializers.DictField(default={}, label="告警触发配置")
            recovery_config = serializers.DictField(default={}, label="告警恢复配置")
            rule = serializers.CharField(required=False, allow_blank=True, label="组合方式")
            extend_fields = serializers.DictField(default={}, label="扩展字段")
            keywords = serializers.CharField(required=False, allow_blank=True, label="组合字段")
            keywords_query_string = serializers.CharField(required=False, allow_blank=True, label="关键字查询条件")
            target = serializers.ListField(default=[[]], label="策略目标")

            def validate_extend_fields(self, value):
                if not value:
                    return {}
                return value

            def validate_trigger_config(self, value):
                return validate_trigger_config_msg(value)

            def validate_recovery_config(self, value):
                return validate_recovery_config_msg(value)

            def validate_agg_condition(self, value):
                return validate_agg_condition_msg(value)

            def validate_target(self, value):
                is_validate_target(value)
                return handle_target(value)

            def validate_detect_algorithm_list(self, value):
                if not value:
                    raise ValidationError(_("检测算法不允许为空"))
                return value

        class ActionListSerializer(serializers.Serializer):
            id = serializers.IntegerField(required=False, label="action_id")
            action_type = serializers.CharField(required=False, default="notice", label="触发动作")
            config = serializers.DictField(required=True, label="告警相关配置")
            notice_group_list = serializers.ListField(required=False, label="通知组ID列表")

            def validate_config(self, value):
                return validate_action_config(value)

        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        name = serializers.CharField(required=True, max_length=128, label="策略名称")
        scenario = serializers.CharField(required=True, label="监控场景")
        item_list = ItemListSerializer(required=True, many=True, label="监控算法配置")
        no_data_config = serializers.DictField(required=True, label="无数据告警配置")
        message_template = serializers.CharField(required=False, allow_blank=True, label="告警模板")
        action_list = ActionListSerializer(required=True, many=True, label="触发动作")
        id = serializers.IntegerField(required=False, label="策略ID")
        source_type = serializers.CharField(required=True, label="策略配置来源")
        is_enabled = serializers.BooleanField(default=True)
        labels = serializers.ListField(child=serializers.CharField(), required=False)

        def validate_no_data_config(self, value):
            return validate_no_data_config_msg(value)

    def validate_request_data(self, request_data):
        if request_data.get("id"):
            request_serializer = self.RequestSerializer(data=request_data, partial=True)
            is_valid_request = request_serializer.is_valid()
            if not is_valid_request:
                raise ValidationError({self.get_resource_name(): {"request_data_invalid": request_serializer.errors}})
            return request_serializer.validated_data

        return super(StrategyConfigResource, self).validate_request_data(request_data)

    def handle_strategy_dict(self, strategy_dict):
        no_data_config = strategy_dict.pop("no_data_config", None)
        message_template = strategy_dict.pop("message_template", None)
        for item in strategy_dict["item_list"]:
            # 自定义事件字段处理
            if item["data_source_label"] == DataSourceLabel.CUSTOM and item["data_type_label"] == DataTypeLabel.EVENT:
                bk_event_group = CustomEventGroup.objects.get(bk_data_id=int(item["result_table_id"]))
                item["bk_event_group_id"] = bk_event_group.bk_event_group_id
                item["custom_event_id"] = item["metric_field"]
                item["result_table_id"] = bk_event_group.table_id

            item["metric_id"] = get_metric_id(**item)
            trigger_config = item.pop("trigger_config", {})
            recovery_config = item.pop("recovery_config", {})
            item.update(no_data_config=no_data_config)
            item["algorithm_list"] = []
            for algorithm in item.pop("detect_algorithm_list", []):
                if len(algorithm["algorithm_list"]) == 0:
                    item["algorithm_list"].append(
                        {
                            "level": algorithm["level"],
                            "trigger_config": trigger_config,
                            "recovery_config": recovery_config,
                        }
                    )

                # 系统事件，添加默认query_config
                item["agg_condition"] = item.get("agg_condition", [])
                for config in algorithm["algorithm_list"]:
                    item["algorithm_list"].append(
                        {
                            "algorithm_unit": config.get("algorithm_unit", ""),
                            "algorithm_type": config.get("algorithm_type", ""),
                            "algorithm_config": config.get("algorithm_config", []),
                            "level": algorithm["level"],
                            "trigger_config": trigger_config,
                            "recovery_config": recovery_config,
                        }
                    )

        for action in strategy_dict["action_list"]:
            if message_template:
                action["notice_template"] = {
                    "anomaly_template": message_template,
                }

        return strategy_dict

    def access_aiops(cls, strategy: Strategy):
        """
        智能监控接入
        (目前仅支持监控时序、计算平台时序数据)

        - 监控时序数据(以监控管理员身份配置)
            1. 走kafka接入，配置好清洗规则，接入到计算平台
            2. 走dataflow，进行downsample操作，得到一张结果表，保存到metadata的bkdatastorage表中
            3. 走dataflow，根据策略配置的查询sql，创建好实时计算节点，在节点后配置好智能检测节点
        - 计算平台数据(根据用户身份配置)
            1. 直接走dataflow，根据策略配置的查询sql，创建好实时计算节点，在节点后配置好智能检测节点
        """
        from bkmonitor.models import AlgorithmModel
        from monitor_web.tasks import (
            access_aiops_by_strategy_id,
            access_host_anomaly_detect_by_strategy_id,
        )

        # 未开启计算平台接入，则直接返回
        if not settings.IS_ACCESS_BK_DATA:
            return

        has_intelligent_algorithm = False
        for algorithm in chain(*(item.algorithms for item in strategy.items)):
            # 主机异常检测的接入逻辑跟其他智能检测不一样，因此单独接入
            if algorithm.type == AlgorithmModel.AlgorithmChoices.HostAnomalyDetection:
                access_host_anomaly_detect_by_strategy_id.delay(strategy.id)
                return

            if algorithm.type == AlgorithmModel.AlgorithmChoices.IntelligentDetect:
                has_intelligent_algorithm = True
                break

        if not has_intelligent_algorithm:
            return

        # 判断数据来源
        for query_config in chain(*(item.query_configs for item in strategy.items)):
            if query_config.data_type_label != DataTypeLabel.TIME_SERIES:
                continue

            # 如果查询条件中存在特殊的方法，则报错
            for condition in query_config.agg_condition:
                if condition["method"] in AdvanceConditionMethod:
                    raise Exception(_("智能检测算法不支持这些查询条件({})".format(AdvanceConditionMethod)))

            if query_config.data_source_label == DataSourceLabel.BK_MONITOR_COLLECTOR:
                access_aiops_by_strategy_id.delay(strategy.id)
            elif query_config.data_source_label == DataSourceLabel.BK_DATA:
                # 1. 先授权给监控项目(以创建或更新策略的用户来请求一次授权)
                from bkmonitor.dataflow import auth

                auth.ensure_has_permission_with_rt_id(
                    bk_username=get_global_user() or settings.BK_DATA_PROJECT_MAINTAINER,
                    rt_id=query_config.result_table_id,
                    project_id=settings.BK_DATA_PROJECT_ID,
                )
                # 2. 然后再创建异常检测的dataflow
                access_aiops_by_strategy_id.delay(strategy.id)

    def perform_request(self, validated_request_data):
        strategy_dict = validated_request_data
        labels = strategy_dict.pop("labels", [])

        strategy_dict = self.handle_strategy_dict(strategy_dict)
        strategy = Strategy.from_dict_v1(strategy_dict)
        strategy.convert()
        strategy.save()

        # 计算平台接入
        self.access_aiops(strategy)

        # 保存标签
        StrategyLabel.save_strategy_label(strategy_dict["bk_biz_id"], strategy.id, labels)
        return {"id": strategy.id}


class CloneStrategyConfig(Resource):
    """
    拷贝监控策略
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        id = serializers.IntegerField(required=True, label="策略ID")

    def perform_request(self, validated_request_data):
        strategy_data = resource.strategies.strategy_config_detail(validated_request_data)

        strategy_data.pop("id", None)
        strategy_data["source_type"] = "BKMONITOR"

        for action in strategy_data["action_list"]:
            action["notice_group_list"] = action["notice_group_id_list"]

        new_strategy_name = strategy_name = f"{strategy_data['name']}_copy"  # noqa

        # 判断重名
        index = 1
        while True:
            # 检查是否存在同名策略
            is_exists = StrategyModel.objects.filter(
                bk_biz_id=validated_request_data["bk_biz_id"], name=new_strategy_name
            ).exists()
            if not is_exists:
                break
            new_strategy_name = f"{strategy_name}({index})"
            index += 1

        strategy_data["name"] = new_strategy_name

        new_strategy_data = resource.strategies.strategy_config(strategy_data)

        return new_strategy_data


class BulkEditStrategyResource(Resource):
    """
    批量修改接口
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        id_list = serializers.ListField(required=True, label="批量修改的策略ID列表")
        edit_data = serializers.DictField(required=True, label="批量修改的值")

        def validate_edit_data(self, value):
            if value.get("target"):
                is_validate_target(value.get("target"))
                value["target"] = handle_target(value.get("target"))
            return value

    @staticmethod
    def update_enabled(strategy: Strategy, edit_data):
        """
        更新策略启停状态
        """
        if "is_enabled" not in edit_data:
            return
        strategy.is_enabled = edit_data["is_enabled"]

    @staticmethod
    def update_notice_group(strategy: Strategy, edit_data):
        """
        更新告警组配置
        """
        if "notice_group_list" not in edit_data:
            return

        for action in strategy.actions:
            action.notice_group_ids = edit_data["notice_group_list"]

    @staticmethod
    def update_trigger(strategy: Strategy, edit_data):
        """
        更新触发条件
        """
        if "trigger_config" not in edit_data:
            return

        for detect in strategy.detects:
            detect.trigger_config = edit_data["trigger_config"]

    @staticmethod
    def update_notice_interval(strategy: Strategy, edit_data):
        """
        更新通知间隔
        """
        if "alarm_interval" not in edit_data:
            return

        for action in strategy.actions:
            action.config["alarm_interval"] = edit_data["alarm_interval"]

    @staticmethod
    def update_recovery_alarm(strategy: Strategy, edit_data):
        """
        更新恢复通知
        """
        if "send_recovery_alarm" not in edit_data:
            return

        for action in strategy.actions:
            action.config["send_recovery_alarm"] = edit_data["send_recovery_alarm"]

    @staticmethod
    def update_recovery_config(strategy: Strategy, edit_data):
        """
        更新告警恢复通知
        """
        if "recovery_config" not in edit_data:
            return

        for detect in strategy.detects:
            detect.recovery_config = edit_data["recovery_config"]

    @staticmethod
    def update_target(strategy: Strategy, edit_data):
        """
        更新监控目标
        """
        if "target" not in edit_data:
            return

        for item in strategy.items:
            item.target = edit_data["target"]

    @staticmethod
    def update_message_template(strategy: Strategy, edit_data):
        if "message_template" not in edit_data:
            return

        for action in strategy.actions:
            action.notice_template["anomaly_template"] = edit_data["message_template"]

    @classmethod
    def update(cls, strategy: Strategy, edit_data):
        """
        更新配置
        :param strategy: 策略配置
        :param edit_data: 操作数据
        """
        cls.update_enabled(strategy, edit_data)
        cls.update_notice_group(strategy, edit_data)
        cls.update_notice_interval(strategy, edit_data)
        cls.update_recovery_alarm(strategy, edit_data)
        cls.update_recovery_config(strategy, edit_data)
        cls.update_trigger(strategy, edit_data)
        cls.update_target(strategy, edit_data)
        cls.update_message_template(strategy, edit_data)

    def perform_request(self, params):
        bk_biz_id = params["bk_biz_id"]
        edit_data = params["edit_data"]

        strategies = StrategyModel.objects.filter(bk_biz_id=bk_biz_id, id__in=params["id_list"])

        for strategy in Strategy.from_models(strategies):
            self.update(strategy, edit_data)
            strategy.save()

        return params["id_list"]


class GetDimensionListResource(Resource):
    """
    获取指标对应的维度列表
    """

    class RequestSerializer(serializers.Serializer):
        data_source_label = serializers.CharField(required=False, allow_blank=True, label="数据来源")
        data_type_label = serializers.CharField(required=False, allow_blank=True, label="数据类型")
        result_table_id = serializers.CharField(required=False, allow_blank=True, label="表名")
        custom_event_id = serializers.IntegerField(required=False, label="自定义事件ID")
        bk_event_group_id = serializers.IntegerField(required=False, label="自定义事件组ID")
        show_all = serializers.BooleanField(default=False, label="是否展示全部维度")

    def perform_request(self, validated_request_data):
        dimensions = []
        data_source_label = validated_request_data.get("data_source_label", "")
        data_type_label = validated_request_data.get("data_type_label", "")
        result_table_id = validated_request_data.get("result_table_id", "")
        custom_event_id = validated_request_data.get("custom_event_id", "")
        bk_event_group_id = validated_request_data.get("bk_event_group_id", "")

        if not result_table_id:
            return []

        if data_source_label == DataSourceLabel.BK_DATA:
            result_table = api.bkdata.get_result_table(result_table_id=result_table_id)
            for field in result_table["fields"]:
                if field["is_dimension"] and field["field_name"] not in FILTER_DIMENSION_LIST:
                    dimensions.append(
                        {
                            "id": field["field_name"],
                            "name": field["field_alias"] if field["field_alias"] else field["field_name"],
                        }
                    )

        elif data_source_label == DataSourceLabel.BK_MONITOR_COLLECTOR and data_type_label == DataTypeLabel.TIME_SERIES:
            table_msg = api.metadata.get_result_table(table_id=validated_request_data["result_table_id"])
            dimensions = [
                {
                    "id": field["field_name"],
                    "name": field["description"] if field["description"] else field["field_name"],
                }
                for field in table_msg["field_list"]
                if all(
                    [
                        field["tag"] == "dimension",
                        field["field_name"] not in ["time", "bk_supplier_id", "bk_cmdb_level"],
                    ]
                )
            ]
            groups = [field["field_name"] for field in table_msg["field_list"] if field["tag"] == "group"]
            data_target = DataTargetMapping().get_data_target(table_msg["label"], data_source_label, data_type_label)

            if not result_table_id.startswith("system.") and not result_table_id.startswith(
                "{}.".format(Scenario.UPTIME_CHECK)
            ):
                dimensions.append({"id": "bk_collect_config_id", "name": _("采集配置")})

            if any(["bk_target_ip" in groups, "bk_target_service_instance_id" in groups]):
                dimensions.extend(DEFAULT_DIMENSIONS_MAP[data_target])

            # 编辑时HTTP/UDP/TCP仅允许对指定维度配置策略,ICMP开放所有维度,与metadata保持一致
            if result_table_id.startswith("{}.".format(Scenario.UPTIME_CHECK)):
                if result_table_id.split(".")[1] != "icmp":
                    dimensions = DefaultDimensions.uptime_check

            # 隐藏部分维度
            if not validated_request_data["show_all"]:
                dimensions = [
                    dimension for dimension in dimensions if dimension["id"] not in ["ip", "bk_biz_id", "bk_cloud_id"]
                ]

        elif (
            data_source_label == DataSourceLabel.CUSTOM and data_type_label == DataTypeLabel.EVENT and bk_event_group_id
        ):
            # 获取自定义字段的维度信息
            table_msg = api.metadata.get_event_group(event_group_id=bk_event_group_id)
            for event_info in table_msg["event_info_list"]:
                if event_info["event_id"] == custom_event_id:
                    dimensions = [
                        {"id": dimension_msg, "name": dimension_msg} for dimension_msg in event_info["dimension_list"]
                    ]
        elif data_source_label == DataSourceLabel.BK_MONITOR_COLLECTOR and data_type_label == DataTypeLabel.LOG:
            event_group = CustomEventGroup.objects.filter(table_id=result_table_id).first()
            event_items = CustomEventItem.objects.filter(bk_event_group=event_group)
            event_dimensions = []
            for event_item in event_items:
                dimension_list = event_item.dimension_list
                for dimension in dimension_list:
                    event_dimensions.append(dimension["dimension_name"])
            for dimension in set(event_dimensions):
                dimensions.append({"id": dimension, "name": dimension})

        return dimensions


class PlainStrategyListResource(Resource):
    """
    获取监控策略轻量列表，供告警屏蔽选择策略配置时使用
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    def perform_request(self, validated_request_data):
        return resource.strategies.plain_strategy_list_v2(**validated_request_data)


class StrategyInfo(StrategyConfigDetailResource):
    """
    获取监控策略信息，供告警屏蔽策略展示用
    """

    def perform_request(self, params):
        strategy_instance = StrategyModel.objects.filter(bk_biz_id=params["bk_biz_id"], id=params["id"]).first()
        if not strategy_instance:
            raise StrategyNotExist

        # 获取策略配置
        strategy = Strategy.from_models([strategy_instance])[0]
        strategy.restore()
        strategy_config = {
            key: value for key, value in strategy.to_dict_v1().items() if key in ["id", "name", "item_list", "scenario"]
        }

        # 监控维度的中文名称转换
        for item in strategy_config["item_list"]:
            item["level"] = set()
            for algorithm in item.pop("algorithm_list", []):
                item["level"].add(algorithm["level"])
            item["level"] = list(item["level"])

            # 指标说明
            item["metric_description"] = MetricListCache.metric_description(item)
            dimensions = resource.strategies.get_dimension_list(
                data_source_label=item["data_source_label"],
                data_type_label=item["data_type_label"],
                result_table_id=item.get("result_table_id", ""),
                custom_event_id=item.get("custom_event_id", 0),
                bk_event_group_id=item.get("bk_event_group_id", 0),
            )
            dimension_mapping = {}
            for dimension in dimensions:
                dimension_mapping[dimension["id"]] = dimension["name"]

            item["agg_dimension"] = [dimension_mapping.get(d, d) for d in item.get("agg_dimension", [])]

            for condition in item.get("agg_condition", []):
                condition["key"] = dimension_mapping.get(condition["key"], condition["key"])

        return strategy_config


class GetIndexSetListResource(Resource):
    """
    获取索引集
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        index_set_id = serializers.IntegerField(default=-1, label="查询索引集")

    def index_filter(self, data):
        res = []
        count_list = []
        for index_set in data:
            temp_scenario_dict = {"id": index_set.get("scenario_id"), "name": index_set.get("scenario_name")}
            if temp_scenario_dict not in count_list:
                count_list.append({"id": index_set.get("scenario_id"), "name": index_set.get("scenario_name")})
            # 数据源
            scenario_id = index_set.get("scenario_id")
            scenario_name = index_set.get("scenario_name")
            # 索引集
            index_set_id = index_set.get("index_set_id")
            metric_field = index_set.get("index_set_name")
            default_time_field = index_set.get("time_field")
            # 其余
            storage_cluster_id = index_set.get("storage_cluster_id")

            # 临时的索引,索引集中的索引
            temp_metric_name = []
            temp_metric_id = []
            # 根据拆索引集获取索引
            for index in index_set.get("indices", []):
                temp_metric_id.append(str(index["result_table_id"]))
                temp_metric_name.append(index.get("result_table_name"))
                # 索引
                result_table_id = ",".join(temp_metric_id)
                # 拼接的注释
                metric_description = _("数据来源：日志平台")
                time_field = default_time_field

                data = {
                    # 索引集id
                    "index_set_id": index_set_id,
                    # 索引集名称
                    "name": metric_field,
                    "metric_field": metric_field,
                    "metric_field_name": metric_field,
                    # 索引
                    "result_table_id": result_table_id,
                    # 数据源id和名称
                    "scenario_id": scenario_id,
                    "scenario_name": scenario_name,
                    "data_source_label": DataSourceLabel.BK_LOG_SEARCH,
                    "metric_description": metric_description,
                    "collect_interval": 1,
                    "id": None,
                    "data_type_label": "log",
                    "unit_conversion": 1.0,
                    "result_table_label": "log",
                    "default_trigger_config": {"count": 1, "check_window": 5},
                    "extend_fields": {
                        "index_set_id": index_set_id,
                        "scenario_id": scenario_id,
                        "scenario_name": scenario_name,
                        "storage_cluster_id": storage_cluster_id,
                        "time_field": time_field,
                    },
                    "result_table_name": "",
                    "default_condition": [],
                    "default_dimensions": [],
                    "related_name": "",
                    "collect_config_ids": [],
                    "unit": "",
                    "related_id": "",
                    "dimensions": [],
                    "collect_config": "",
                    "data_target": "",
                    "category_display": "",
                    "description": "",
                    "result_table_label_name": "",
                    "bk_biz_id": "",
                    "plugin_type": "",
                }
                res.append(data)

        return res, count_list

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        index_set_id = validated_request_data["index_set_id"]
        data = api.log_search.search_index_set(bk_biz_id=bk_biz_id)

        if index_set_id != -1:
            filter_data = []
            for i in data:
                if i.get("index_set_id") == index_set_id:
                    filter_data.append(i)
                    break
            data = filter_data
        metric_list, count_list = self.index_filter(data)
        return {"metric_list": metric_list, "count_list": count_list}


class GetLogFields(Resource):
    """
    获取日志关键字的维度
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        index_set_id = serializers.IntegerField(required=True, label="索引集ID")

    def perform_request(self, validated_request_data):
        index_set_id = validated_request_data["index_set_id"]
        bk_biz_id = validated_request_data["bk_biz_id"]
        # 获取监控方法
        operators_temp = api.log_search.operators(bk_biz_id=bk_biz_id)
        operators = [
            {"id": operator.get("operator"), "name": operator.get("label"), "placeholder": operator.get("placeholder")}
            for operator in operators_temp
        ]

        # 获取监控维度
        fields = api.log_search.search_index_fields(bk_biz_id=bk_biz_id, index_set_id=index_set_id)
        fields = fields.get("fields", "")
        res_fields = []
        for i in fields:
            if i["es_doc_values"] and i.get("field_type") != "date":
                temp = {"id": i["field_name"], "name": i["field_name"], "description": i["field_alias"]}
                res_fields.append(temp)

        result = {"dimension": res_fields, "condition": operators}
        return result


class BackendStrategyConfigListResource(StrategyConfigListResource):
    """
    批量获取策略列表详情
    """

    @staticmethod
    def handle_value_time(value):
        if value.get("create_time"):
            value["create_time"] = strftime_local(value["create_time"])
        if value.get("update_time"):
            value["update_time"] = strftime_local(value["update_time"])
        return value

    def perform_request(self, params):
        strategy_query = self.filter_all_strategies(params)

        # 分页
        page = params.get("page", 0)
        page_size = params.get("page_size", 0)
        if all([page, page_size]):
            # fmt: off
            strategy_query = strategy_query[(page - 1) * page_size: page * page_size]
            # fmt: on

        strategies = Strategy.from_models(strategy_query)
        configs = [strategy.to_dict_v1(config_type="backend") for strategy in strategies]
        return configs


class BackendStrategyConfigResource(Resource):
    class RequestSerializer(serializers.Serializer):
        class ItemListSerializer(serializers.Serializer):
            class AlgorithmSerializers(serializers.Serializer):
                class TriggerConfigSerializers(serializers.Serializer):
                    count = serializers.IntegerField(required=True, label="触发次数")
                    check_window = serializers.IntegerField(required=True, label="检测周期")

                class RecoveryConfigSerializers(serializers.Serializer):
                    check_window = serializers.IntegerField(required=True, label="检测周期")

                trigger_config = TriggerConfigSerializers()
                algorithm_type = serializers.ChoiceField(required=False, choices=DETECT_ALGORITHM_CHOICES, label="检测算法")
                algorithm_unit = serializers.CharField(required=False, allow_blank=True, label="算法单位")
                recovery_config = RecoveryConfigSerializers()
                message_template = serializers.CharField(required=False, allow_blank=True, label="通知模板")
                algorithm_config = serializers.JSONField(required=False, label="检测算法配置")
                level = serializers.IntegerField(required=True, label="告警级别")

                def validate_algorithm_config(self, value):
                    return validate_algorithm_config_msg(value)

                def validate_trigger_config(self, value):
                    return validate_trigger_config_msg(value)

                def validate_recovery_config(self, value):
                    return validate_recovery_config_msg(value)

            class RtQueryConfigSerializers(serializers.Serializer):
                metric_field = serializers.CharField(required=False, label="监控指标别名")
                unit_conversion = serializers.FloatField(required=False, default=1.0, label="单位换算")
                unit = serializers.CharField(required=False, allow_blank=True, label="单位")
                extend_fields = serializers.JSONField(required=False, allow_null=True, label="扩展字段")
                agg_dimension = serializers.ListField(required=False, allow_empty=True, label="聚合维度")
                result_table_id = serializers.CharField(required=False, allow_blank=True, label="表名")
                agg_method = serializers.CharField(required=False, allow_blank=True, label="聚合算法")
                agg_interval = serializers.CharField(required=False, allow_blank=True, label="聚合周期")
                agg_condition = serializers.ListField(required=False, allow_empty=True, label="聚合条件")
                rule = serializers.CharField(required=False, allow_blank=True, label="组合方式")
                keywords = serializers.CharField(required=False, allow_blank=True, label="组合字段")
                keywords_query_string = serializers.CharField(required=False, allow_blank=True, label="关键字查询条件")
                bk_event_group_id = serializers.IntegerField(required=False, label="自定义事件分组ID")
                custom_event_id = serializers.IntegerField(required=False, label="自定义事件分组ID")

                def validate_extend_fields(self, value):
                    if not value:
                        return {}
                    return value

            id = serializers.IntegerField(required=False, label="item_id")
            name = serializers.CharField(required=True, label="监控指标别名")
            # 数据类型标签，例如：时序数据(time_series)，事件数据(event)，日志数据(log)
            data_type_label = serializers.CharField(required=True, label="数据类型标签")
            metric_id = serializers.CharField(required=True, label="指标标识")
            # 数据来源标签，例如：数据平台(bk_data)，监控采集器(bk_monitor_collector)
            data_source_label = serializers.CharField(required=True, label="数据来源标签")
            algorithm_list = AlgorithmSerializers(required=True, many=True, label="")
            no_data_config = serializers.DictField(required=True, label="无数据告警配置")
            rt_query_config = RtQueryConfigSerializers(required=True, allow_null=True, label="查询表")
            target = serializers.ListField(default=[[]], label="策略目标")
            result_table_id = serializers.CharField(required=False, label="表名（用于GSE进程事件默认创建）")

            def validate_no_data_config(self, value):
                return validate_no_data_config_msg(value)

            def validate_agg_condition(self, value):
                return validate_agg_condition_msg(value)

            def validate_algorithm_list(self, value):
                return validate_algorithm_msg(value)

        class ActionListSerializer(serializers.Serializer):
            class NoticeTemplateSerializer(serializers.Serializer):
                anomaly_template = serializers.CharField(required=False, allow_blank=True, label="告警发生通知模板")
                recovery_template = serializers.CharField(required=False, allow_blank=True, label="告警恢复通知模板")

            id = serializers.IntegerField(required=False, label="action_id")
            action_type = serializers.CharField(required=False, default="notice", label="触发动作")
            config = serializers.DictField(required=True, label="告警相关配置")
            notice_group_list = serializers.ListField(default=[], label="通知组ID列表")
            notice_template = NoticeTemplateSerializer()

            def validate_config(self, value):
                return validate_action_config(value)

        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        name = serializers.CharField(required=True, max_length=128, label="策略名称")
        scenario = serializers.CharField(required=True, label="监控场景")
        id = serializers.IntegerField(required=False, label="策略ID")
        source = serializers.CharField(required=False, label="策略配置来源")
        item_list = serializers.ListField(
            child=ItemListSerializer(required=True, label="监控算法配置"),
            min_length=1,
        )
        action_list = serializers.ListField(
            child=ActionListSerializer(required=True, label="触发动作"),
        )
        is_enabled = serializers.BooleanField(label="是否启用", default=True)

        def validate_target(self, value):
            is_validate_target(value)
            return handle_target(value)

        def validate_no_data_config(self, value):
            return validate_no_data_config_msg(value)

    def perform_request(self, validated_request_data):
        # 补全算法单位
        item_list = validated_request_data["item_list"]
        for item in item_list:
            if not item["rt_query_config"]:
                continue

            for algorithm in item["algorithm_list"]:
                if "algorithm_unit" in algorithm:
                    continue

                unit = load_unit(item["rt_query_config"].get("unit", ""))
                algorithm["algorithm_unit"] = unit.unit

        for item in validated_request_data["item_list"]:
            rt_query_config = item.get("rt_query_config", {})
            if item["data_source_label"] != DataSourceLabel.CUSTOM or item["data_type_label"] != DataTypeLabel.EVENT:
                continue

            if "result_table_id" in rt_query_config:
                continue

            event_group = CustomEventGroup.objects.get(
                bk_biz_id=validated_request_data["bk_biz_id"], bk_event_group_id=rt_query_config["bk_event_group_id"]
            )
            rt_query_config["result_table_id"] = event_group.table_id

        strategy_config = Strategy.from_dict_v1(validated_request_data)
        strategy_config.save()
        return {"id": strategy_config.id}
