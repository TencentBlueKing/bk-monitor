"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
import json
import re
import time
from collections import OrderedDict, deque
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from django.db.models import Q

from bkmonitor.action.serializers.strategy import UserGroupSlz
from bkmonitor.models.strategy import UserGroup
from bkmonitor.utils.request import get_request_tenant_id
from bkmonitor.utils.user import get_global_user
from bkmonitor.views import serializers
from common.log import logger
from constants.alert import EVENT_STATUS_DICT, EventStatus
from core.drf_resource import api, resource
from core.drf_resource.base import Resource
from fta_web.alert.handlers.alert import AlertQueryHandler
from metadata import models
from metadata.models.space.space_data_source import get_real_biz_id
from monitor_web.datalink.storage import get_storager
from monitor_web.models.collecting import CollectConfigMeta
from monitor_web.models.plugin import CollectorPluginMeta, PluginVersionHistory
from monitor_web.strategies.loader.datalink_loader import (
    DatalinkDefaultAlarmStrategyLoader,
    DataLinkStage,
    DatalinkStrategy,
    DataLinkStrategyInfo,
)


class QueryBizByBkBase(Resource):
    """
    根据计算平台相关信息（RT/data_id），查询对应业务信息
    """

    class RequestSerializer(serializers.Serializer):
        bk_base_data_id_list = serializers.ListField(
            label="计算平台data_id列表", child=serializers.IntegerField(), required=False, default=[]
        )
        bk_base_vm_table_id_list = serializers.ListField(
            label="计算平台RT列表", child=serializers.CharField(), required=False, default=[]
        )

        def validate(self, data: OrderedDict) -> OrderedDict:
            # 判断参数不能同时为空
            if not (data.get("bk_base_data_id_list") or data.get("bk_base_vm_table_id_list")):
                raise ValueError("params is null")
            return data

    def perform_request(self, data):
        bk_base_data_id_list = data.get("bk_base_data_id_list") or []
        bk_base_vm_table_id_list = data.get("bk_base_vm_table_id_list") or []

        # 获取 table id
        table_id_bk_base_data_ids = self.get_table_id_bk_base_data_ids(bk_base_data_id_list, bk_base_vm_table_id_list)

        # 获取对应的业务信息
        table_id_biz_ids = self.get_table_id_biz_ids(table_id_bk_base_data_ids.keys())

        # 获取0业务的真实业务ID
        bk_base_data_id_biz_id = self.get_zero_biz_id_mapping(table_id_biz_ids, table_id_bk_base_data_ids)

        return bk_base_data_id_biz_id  # 最终返回一个字典{data_id: bk_biz_id} 数据类型均为int

    def get_table_id_bk_base_data_ids(self, bk_base_data_id_list, bk_base_vm_table_id_list):
        return {
            qs["result_table_id"]: qs["bk_base_data_id"]
            for qs in models.AccessVMRecord.objects.filter(
                Q(bk_base_data_id__in=bk_base_data_id_list) | Q(vm_result_table_id__in=bk_base_vm_table_id_list)
            ).values("result_table_id", "bk_base_data_id")
        }

    def get_table_id_biz_ids(self, table_ids):
        return {
            qs["table_id"]: qs["bk_biz_id"]
            for qs in models.ResultTable.objects.filter(table_id__in=table_ids).values("table_id", "bk_biz_id")
        }

    def get_zero_biz_id_mapping(self, table_id_biz_ids, table_id_bk_base_data_ids):
        zero_biz_table_id_list = [table_id for table_id, biz_id in table_id_biz_ids.items() if biz_id == 0]

        # 获取对应的 data id
        table_id_data_ids = self.get_table_id_data_ids(zero_biz_table_id_list)

        # 获取 data name 和 space_uid
        data_id_names, data_id_space_uid_map = self.get_data_names_and_space_uids(table_id_data_ids.values())

        # 查询是否在指定的表中
        data_id_ts_group_flag = self.get_data_id_group_flag(models.TimeSeriesGroup, zero_biz_table_id_list)
        data_id_event_group_flag = self.get_data_id_group_flag(models.EventGroup, zero_biz_table_id_list)

        bk_base_data_id_biz_id = {}

        # 获取对应的数据
        for table_id, bk_biz_id in table_id_biz_ids.items():
            # 跳过没有匹配到数据
            bk_base_data_id = table_id_bk_base_data_ids.get(table_id)
            if not bk_base_data_id:
                continue
            # NOTE: 应该不会有小于 0 的业务，当业务 ID 大于 0 时，直接返回
            if bk_biz_id > 0:
                bk_base_data_id_biz_id[bk_base_data_id] = bk_biz_id
                continue

            # 获取 0 业务对应的真实业务 ID
            data_id = table_id_data_ids.get(table_id)
            if not data_id:
                bk_base_data_id_biz_id[bk_base_data_id] = 0
                continue

            data_name = data_id_names.get(data_id)
            space_uid = data_id_space_uid_map.get(data_id)
            is_in_ts_group = data_id_ts_group_flag.get(data_id) or False
            is_in_event_group = data_id_event_group_flag.get(data_id) or False
            bk_biz_id = get_real_biz_id(data_name, is_in_ts_group, is_in_event_group, space_uid)
            # 若业务ID仍然为0，则去SaaS侧CollectorPluginMeta查询插件业务ID
            if bk_biz_id == 0:
                bk_biz_id = self.get_biz_id_from_collector_plugin_meta(table_id)
            bk_base_data_id_biz_id[bk_base_data_id] = bk_biz_id

        return bk_base_data_id_biz_id

    def get_table_id_data_ids(self, zero_biz_table_id_list):
        return {
            qs["table_id"]: qs["bk_data_id"]
            for qs in models.DataSourceResultTable.objects.filter(table_id__in=zero_biz_table_id_list).values(
                "bk_data_id", "table_id"
            )
        }

    def get_data_names_and_space_uids(self, data_ids):
        data_id_names = {}
        data_id_space_uid_map = {}
        for qs in models.DataSource.objects.filter(bk_data_id__in=data_ids).values(
            "bk_data_id", "data_name", "space_uid"
        ):
            data_id_names[qs["bk_data_id"]] = qs["data_name"]
            data_id_space_uid_map[qs["bk_data_id"]] = qs["space_uid"]
        return data_id_names, data_id_space_uid_map

    def get_data_id_group_flag(self, model, zero_biz_table_id_list):
        return {
            obj["bk_data_id"]: True
            for obj in model.objects.filter(table_id__in=zero_biz_table_id_list).values("bk_data_id")
        }

    def get_biz_id_from_collector_plugin_meta(self, table_id: str) -> int:
        """
        @summary: 若在元数据中无法找到VM对应的业务ID，则去空间插件表中查询
        @param table_id: 元数据中的RT
        @return: 业务ID
        """
        try:
            real_key = table_id.split("_", 1)[-1].rsplit(".", 1)[0]  # 根据插件规则，将RT转换为对应的plugin_id
            plugin_meta = CollectorPluginMeta.objects.get(bk_tenant_id=get_request_tenant_id(), plugin_id=real_key)
            return plugin_meta.bk_biz_id
        except Exception:  # pylint: disable=broad-except
            return 0


class BaseStatusResource(Resource):
    def __init__(self):
        super().__init__()
        self.collect_config_id: int = None
        self.collect_config: CollectConfigMeta = None
        self.stage: str = None
        self.strategy_map: map[int, DataLinkStrategyInfo] = {}
        self.strategy_ids: list[int] = []
        self.loader: DatalinkDefaultAlarmStrategyLoader = None
        self._init = False

    def init_data(self, bk_biz_id: int, collect_config_id: str, stage: DataLinkStage = None):
        self.bk_biz_id = bk_biz_id
        self.collect_config_id = collect_config_id
        self.collect_config: CollectConfigMeta = CollectConfigMeta.objects.get(
            id=self.collect_config_id, bk_biz_id=bk_biz_id
        )
        self.stage = stage
        if self.stage:
            self.loader = DatalinkDefaultAlarmStrategyLoader(
                collect_config=self.collect_config, user_id=get_global_user()
            )
            self.strategy_map = self.loader.load_strategy_map(self.stage)
            self.strategy_ids = list(self.strategy_map.keys())
        self._init = True

    def get_alert_strategies(self) -> tuple[list[int], list[dict]]:
        """检索告警配置"""
        strategies = [
            resource.strategies.get_strategy_v2(bk_biz_id=self.collect_config.bk_biz_id, id=sid)
            for sid in self.strategy_ids
        ]
        return strategies

    def get_strategy_desc(self, strategy_id: int):
        """获取采集配置描述"""
        return self.strategy_map.get(strategy_id, {}).get("strategy_desc", "")

    def get_strategy_user_groups(self) -> list[UserGroup]:
        user_groups = []
        for v in self.strategy_map.values():
            user_groups.extend(v["rule"]["user_groups"])
        return UserGroup.objects.filter(id__in=user_groups)

    def search_alert_histogram(self, time_range: int = 3600) -> list[list]:
        start_time, end_time = int(time.time() - time_range), int(time.time())
        request_data = {
            "bk_biz_ids": [self.collect_config.bk_biz_id],
            "query_string": self.build_alert_query_string(),
            "start_time": start_time,
            "end_time": end_time,
        }
        handler = AlertQueryHandler(**request_data)
        data = list(handler.date_histogram().values())[0]
        series = [
            {"data": list(series.items()), "name": status, "display_name": EVENT_STATUS_DICT[status]}
            for status, series in data.items()
        ]
        abnormal_series = [s for s in series if s["name"] == EventStatus.ABNORMAL][0]
        return abnormal_series["data"]

    def get_metrics_json(self) -> list[dict]:
        """查询采集插件配置的指标维度信息"""
        metric_json: list[dict] = copy.deepcopy(self.collect_config.deployment_config.metrics)
        plugin = self.collect_config.plugin
        # 如果插件id在time_series_group能查到，则可以认为是分表的，否则走原有逻辑
        group_list = api.metadata.query_time_series_group(
            time_series_group_name=f"{plugin.plugin_type}_{plugin.plugin_id}"
        )
        for table in metric_json:
            # 分表模式下，这里table_id都为__default__
            table["table_name"] = table["table_name"] if not group_list else "__default__"
            table["table_id"] = self.get_result_table_id(self.bk_biz_id, plugin, table["table_name"])
            metric_names: list[str] = list()
            for field in table["fields"]:
                if not field["is_active"]:
                    continue
                if field["monitor_type"] != "metric":
                    continue
                metric_names.append(field["name"])
            table["metric_names"] = metric_names
        return metric_json

    @staticmethod
    def get_result_table_id(bk_biz_id: int, plugin: CollectorPluginMeta, table_name: str) -> str:
        """通过采集插件配置，拼接最终 RT_ID"""
        # 适配自定义上报版本的进程采集
        if plugin.plugin_type == CollectorPluginMeta.PluginType.PROCESS:
            tsg = api.metadata.query_time_series_group(
                time_series_group_name=f"process_{table_name}", bk_biz_id=bk_biz_id
            )
            if tsg:
                return tsg[0]["table_id"].split(".")[0] + ".__default__"

        return PluginVersionHistory.get_result_table_id(plugin, table_name).lower()

    def has_strategies(self) -> bool:
        return len(self.strategy_ids) > 0

    def build_alert_query_string(self) -> str:
        query_string = "({strategy}) AND ({collection})".format(
            strategy=" OR ".join(f"strategy_id : {sid}" for sid in self.strategy_ids),
            collection=f"tags.bk_collect_config_id: {self.collect_config_id}",
        )
        return query_string


class AlertStatusResource(BaseStatusResource):
    """查询数据链路各个阶段的告警状态"""

    class RequestSerilizer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        collect_config_id = serializers.IntegerField(required=True, label="采集配置ID")
        stage = serializers.ChoiceField(
            required=True, label="告警阶段", choices=[stage.value for stage in list(DataLinkStage)]
        )

    def perform_request(self, validated_request_data: dict) -> dict:
        self.init_data(
            validated_request_data["bk_biz_id"],
            validated_request_data["collect_config_id"],
            DataLinkStage(validated_request_data["stage"]),
        )
        if not self.has_strategies():
            return {"has_strategies": False}
        strategies = self.get_alert_strategies()
        alert_histogram = self.search_alert_histogram()
        return {
            "has_strategies": True,
            "has_alert": alert_histogram[-1][1],
            "alert_histogram": alert_histogram,
            "alert_config": {
                "user_group_list": [UserGroupSlz(ug).data for ug in self.get_strategy_user_groups()],
                "strategies": [
                    {
                        "name": strategy["name"],
                        "description": self.get_strategy_desc(strategy["id"]),
                        "id": strategy["id"],
                    }
                    for strategy in strategies
                ],
            },
            "alert_query": self.build_alert_query_string(),
        }


class UpdateAlertUserGroupsResource(BaseStatusResource):
    class RequestSerilizer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        collect_config_id = serializers.IntegerField(required=True, label="采集配置ID")
        stage = serializers.ChoiceField(
            required=True, label="告警阶段", choices=[stage.value for stage in list(DataLinkStage)]
        )
        notice_group_list = serializers.ListField(required=True, child=serializers.IntegerField())

    def perform_request(self, validated_request_data: dict):
        self.init_data(
            validated_request_data["bk_biz_id"],
            validated_request_data["collect_config_id"],
            DataLinkStage(validated_request_data["stage"]),
        )
        strategy_tuples: list[tuple[int, DatalinkStrategy]] = []
        for sid in self.strategy_ids:
            strategy_tuples.append((sid, self.strategy_map.get(sid)))
        self.loader.update_rule_group(
            user_group_ids=validated_request_data["notice_group_list"],
            strategy_tuples=strategy_tuples,
        )
        return "ok"


class CollectingTargetStatusResource(BaseStatusResource):
    class RequestSerilizer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        collect_config_id = serializers.IntegerField(required=True, label="采集配置ID")

    def perform_request(self, validated_request_data: dict) -> dict:
        self.init_data(
            validated_request_data["bk_biz_id"], validated_request_data["collect_config_id"], DataLinkStage.COLLECTING
        )

        instance_status = resource.collecting.collect_instance_status(
            id=self.collect_config_id, bk_biz_id=self.collect_config.bk_biz_id
        )
        # 提取关联的所有主机ID
        bk_host_ids = []
        for group in instance_status["contents"]:
            for child in group["child"]:
                if "bk_host_id" not in child:
                    continue
                bk_host_ids.append(str(child["bk_host_id"]))

        targets_alert_histogram = {}
        if self.has_strategies() and bk_host_ids:
            alert_histogram = self.search_target_alert_histogram(bk_host_ids)
            targets_alert_histogram = alert_histogram["targets"]

        # 填充主机的告警信息
        for group in instance_status["contents"]:
            for child in group["child"]:
                if "bk_host_id" not in child:
                    child["alert_histogram"] = None
                else:
                    child["alert_histogram"] = targets_alert_histogram.get(str(child["bk_host_id"]), None)
        return instance_status

    def search_target_alert_histogram(self, targets: list[str], time_range: int = 3600) -> dict:
        """按照主机维度，检索最近的告警分布，默认取最近一小时"""
        if len(targets) == 0:
            return {"total": [], "targets": {}}

        request_data = {
            "bk_biz_ids": [self.collect_config.bk_biz_id],
            "query_string": self.build_alert_query_string(),
        }

        handler = AlertQueryHandler(**request_data)
        # 计算检索的时长和步长
        start_time, end_time = int(time.time() - time_range), int(time.time())
        interval = handler.calculate_agg_interval(start_time, end_time, interval="auto")
        start_time = start_time // interval * interval
        end_time = end_time // interval * interval + interval
        # 以 ElastcisartchDSL 提供的语法组装 DSL 语句
        search_object = handler.get_search_object(start_time=start_time, end_time=end_time)
        search_object = handler.add_query_string(search_object)
        search_object.aggs.bucket("end_time", "filter", {"range": {"end_time": {"lte": end_time}}}).bucket(
            "end_alert", "filter", {"terms": {"status": [EventStatus.RECOVERED, EventStatus.CLOSED]}}
        ).bucket("targets", "terms", field="event.bk_host_id").bucket(
            "time", "date_histogram", field="end_time", fixed_interval=f"{interval}s"
        )
        search_object.aggs.bucket(
            "begin_time", "filter", {"range": {"begin_time": {"gte": start_time, "lte": end_time}}}
        ).bucket("targets", "terms", field="event.bk_host_id").bucket(
            "time", "date_histogram", field="begin_time", fixed_interval=f"{interval}s"
        )
        search_object.aggs.bucket("init_alert", "filter", {"range": {"begin_time": {"lt": start_time}}}).bucket(
            "targets", "terms", field="event.bk_host_id"
        )
        logger.info(f"Search collecting alerts, statement = {json.dumps(search_object.to_dict())}")
        search_result = search_object[:0].execute()
        # 检索后的数据整理后，按照主机ID分桶存放，启动和结束记录还需要按照时间分桶存放
        init_alerts: dict[str, int] = dict()
        begine_alerts: dict[str, dict[int][int]] = dict()
        end_alerts: dict[str, dict[int][int]] = dict()
        if search_result.aggs:
            for target_bucket in search_result.aggs.init_alert.targets.buckets:
                init_alerts[target_bucket.key] = target_bucket.doc_count
            for target_bucket in search_result.aggs.begin_time.targets.buckets:
                begine_alerts[target_bucket.key] = {}
                # 时间分桶的 KEY 默认是毫秒值
                for time_bucket in target_bucket.time.buckets:
                    begine_alerts[target_bucket.key][int(time_bucket.key_as_string) * 1000] = time_bucket.doc_count
            for target_bucket in search_result.aggs.end_time.end_alert.targets.buckets:
                end_alerts[target_bucket.key] = {}
                for time_bucket in target_bucket.time.buckets:
                    end_alerts[target_bucket.key][int(time_bucket.key_as_string) * 1000] = time_bucket.doc_count
        logger.info(
            f"Search collecting alerts, init_alert={init_alerts}, begine_alerts={begine_alerts}, end_alerts={end_alerts}"
        )

        # 初始化主机分桶信息，每个分桶里按照时间分桶初始化 0
        ts_buckets = range(start_time, end_time, interval)
        targets_series: dict[str, list] = {target: [[ts * 1000, 0] for ts in ts_buckets] for target in targets}
        for target, series in targets_series.items():
            init_cnt = init_alerts.get(target, 0)
            # 以一个主机例子，从最小时间开始迭代，比如初始3个告警，在第一个时间桶遇到2个新增，1个关闭，则最终为 3+2-1=4 个告警，以此类推
            for item in series:
                ts = item[0]
                begine_cnt = begine_alerts.get(target, {}).get(ts, 0)
                end_cnt = end_alerts.get(target, {}).get(ts, 0)
                item[1] = init_cnt + begine_cnt - end_cnt
                init_cnt = item[1]
        # 汇总计算总的告警数
        total_series: list = []
        for idx, item in enumerate(next(iter(targets_series.values()))):
            ts = item[0]
            cnt = sum(targets_series[target][idx][1] for target in targets)
            total_series.append([ts, cnt])

        return {"total": total_series, "targets": targets_series}


class IntervalOption(Enum):
    MINUTE = "minute"
    DAY = "day"
    HOUR = "hour"


class TransferCountSeriesResource(BaseStatusResource):
    """查询数据量曲线，目前只支持分钟级和天级"""

    class RequestSerilizer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        collect_config_id = serializers.IntegerField(required=True, label="采集配置ID")
        start_time = serializers.IntegerField(required=True, label="开始时间")
        end_time = serializers.IntegerField(required=True, label="结束时间")
        interval_option = serializers.CharField(required=False, label="间隔选项", default=IntervalOption.MINUTE.value)

    def perform_request(self, validated_request_data: dict):
        self.init_data(validated_request_data["bk_biz_id"], validated_request_data["collect_config_id"])
        interval_option = IntervalOption(validated_request_data["interval_option"])
        start_time = validated_request_data["start_time"]
        end_time = validated_request_data["end_time"]
        if interval_option == IntervalOption.MINUTE:
            interval = 1
            interval_unit = "m"
        elif interval_option == IntervalOption.HOUR:
            interval = 60
            interval_unit = "m"
        else:
            interval = 1440
            interval_unit = "m"

        # 读取采集相关的指标列表, 最多20个表
        promqls = [
            """sum(count_over_time({{
                __name__=~"bkmonitor:{table_id}:.*",
                bk_collect_config_id="{collect_config_id}"}}[{interval}{unit}])) or vector(0)
            """.format(
                table_id=table.split(".")[0] if not table.endswith(".__default__") else table,
                collect_config_id=self.collect_config_id,
                interval=interval,
                unit=interval_unit,
            )
            for table in {t["table_id"] for t in self.get_metrics_json()[-1:]}
        ]

        # 没有指标配置，返回空序列
        if len(promqls) == 0:
            return []

        query_params = {
            "bk_biz_id": self.collect_config.bk_biz_id,
            "query_configs": [
                {
                    "data_source_label": "prometheus",
                    "data_type_label": "time_series",
                    "promql": " + ".join(promqls),
                    "interval": interval * 60,
                    "alias": "result",
                }
            ],
            "expression": "",
            "alias": "result",
            "start_time": start_time,
            "end_time": end_time,
            "slimit": 500,
            "down_sample_range": "",
        }
        logger.info(f"Search transfer metric count, statement = {json.dumps(query_params)}")
        return resource.grafana.graph_unify_query(query_params)["series"]


class TransferLatestMsgResource(BaseStatusResource):
    class RequestSerilizer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        collect_config_id = serializers.IntegerField(required=True, label="采集配置ID")

    def perform_request(self, validated_request_data):
        self.init_data(validated_request_data["bk_biz_id"], validated_request_data["collect_config_id"])
        messages = []
        for table in {t["table_id"] for t in self.get_metrics_json()}:
            messages.extend(self.query_latest_metric_msg(table))
            if len(messages) > 10:
                return messages[:10]
        return messages

    def find_timestamps(self, series: dict) -> str:
        """
        基于广度优先搜索 (BFS) 快速提取时间值
        支持任意嵌套层级的 dict/list/tuple 结构
        返回去重后的时间值列表（保持原始顺序）
        """
        logger.info(f"kafka tail series: {series}")

        # 目标键名集合
        target_keys = {"utctime", "timestamp", "@timestamp"}
        # 预编译正则提高效率
        iso8601_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d{1,3})?Z?$")
        # 结果集（有序且去重）
        result = []
        seen = set()
        # BFS队列初始化
        queue = deque([series])

        def _is_valid_time_value(value, iso_pattern) -> bool:
            """
            校验时间值是否符合以下格式
            ```python
            [
                # int类型 时间戳
                1640995200,
                1640995200000,
                # str类型 时间戳
                "1640995200",
                "1640995200000",
                # str类型 ISO 8601格式
                "2023-01-01T00:00:00Z",
                "2023-01-01 00:00:00",
                "2025-02-26T09:59:39.407Z",
            ]
            ```
            """
            if isinstance(value, int):
                return 1_000_000_000 <= value < 10_000_000_000_000  # 10位 ~ 13位
            if isinstance(value, str):
                if value.isdigit():
                    length = len(value)
                    if length not in (10, 13):
                        return False
                    try:
                        num = int(value)
                        return 1_000_000_000 <= num < 10_000_000_000_000
                    except ValueError:
                        return False
                return bool(iso_pattern.match(value))

            return False

        def _add_unique_value(value: str | int, result: list, seen: set):
            """去重并保持顺序"""
            if isinstance(value, int):
                key = ("int", value)
            else:
                key = ("str", value.strip().lower())  # 字符串忽略大小写和空格
            if key not in seen:
                seen.add(key)
                result.append(value)

        def convert_to_string(ts):
            """
            格式化时间戳
            示例: 2022-01-01 00:00:00
            """
            if isinstance(ts, str):
                if len(ts) == 10:  # 10位字符串时间戳（秒）
                    dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
                elif len(ts) == 13:  # 13位字符串时间戳（毫秒）
                    dt = datetime.fromtimestamp(int(ts) / 1000, tz=timezone.utc)
                else:
                    if re.match(
                        r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d{1,3})?Z$", ts
                    ):  # ISO 8601 格式: %Y-%m-%dT%H:%M:%SZ
                        dt = datetime.fromisoformat(ts[:-1])  # 去掉最后的 'Z'
                    else:
                        dt = datetime.fromisoformat(ts)
            elif isinstance(ts, int):
                if len(str(ts)) == 10:  # 10位整数时间戳（秒）
                    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                elif len(str(ts)) == 13:  # 13位整数时间戳（毫秒）
                    dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)

            return dt.strftime("%Y-%m-%d %H:%M:%S")

        """
        广度优先搜索，遍历数据结构，找出符合以下时间戳格式的值, 并保存到 result 中
        ```
        [
            1640995200, 1640995200000,
            "1640995200","1640995200000",
            "2023-01-01T00:00:00Z","2023-01-01 00:00:00", "2025-02-26T09:59:39.407Z"
        ]
        ```
        """
        while queue:
            current = queue.popleft()

            if isinstance(current, dict):
                for k, v in current.items():
                    if k in target_keys:
                        if _is_valid_time_value(v, iso8601_pattern):
                            _add_unique_value(v, result, seen)
                    queue.append(v)
            elif isinstance(current, list | tuple):
                queue.extend(current)

        logger.info(f"find_timestamps: {result}")
        return convert_to_string(result[0]) if result else ""

    def query_latest_metric_msg(self, table_id: str, size: int = 10) -> list[dict]:
        """查询一个指标的最新数据"""

        series: list[dict] = api.metadata.kafka_tail({"table_id": table_id, "size": size})
        msgs = []
        for s in series:
            time = self.find_timestamps(s)

            msgs.append(
                {
                    "message": json.dumps(s),
                    "time": time,
                    "raw": s,
                }
            )
        return msgs


class StorageStatusResource(BaseStatusResource):
    """获取存储状态"""

    class RequestSerilizer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        collect_config_id = serializers.IntegerField(required=True, label="采集配置ID")

    def perform_request(self, validated_request_data: dict[str, Any]):
        bk_biz_id = validated_request_data["bk_biz_id"]
        collect_config_id = validated_request_data["collect_config_id"]

        try:
            collect_config = CollectConfigMeta.objects.get(id=collect_config_id, bk_biz_id=bk_biz_id)
        except CollectConfigMeta.DoesNotExist:
            return {}

        plugin = collect_config.plugin

        group_list = api.metadata.query_time_series_group(
            time_series_group_name=f"{plugin.plugin_type}_{plugin.plugin_id}"
        )
        if group_list:
            table_id = PluginVersionHistory.get_result_table_id(plugin, "__default__")
        else:
            metric_json = collect_config.deployment_config.metrics
            if not metric_json:
                return {}
            table_id = self.get_result_table_id(bk_biz_id, plugin, metric_json[0]["table_name"])

        # 同一个采集项下所有表存储配置都是一致的，取第一个结果表即可
        storager = get_storager(table_id=table_id)
        return {"info": storager.get_info(), "status": storager.get_status()}
