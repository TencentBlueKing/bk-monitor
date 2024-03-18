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
import time
from datetime import datetime
from enum import Enum
from typing import Dict, List, Tuple

from bkmonitor.action.serializers.strategy import UserGroupSlz
from bkmonitor.models.strategy import UserGroup
from bkmonitor.utils.user import get_global_user
from bkmonitor.views import serializers
from common.log import logger
from constants.alert import EventStatus, EVENT_STATUS_DICT
from core.drf_resource import api, resource
from core.drf_resource.base import Resource
from core.errors.datalink import CollectorPluginMetaError
from fta_web.alert.handlers.alert import AlertQueryHandler
from monitor_web.datalink.storage import get_storager
from monitor_web.models.collecting import CollectConfigMeta
from monitor_web.models.plugin import PluginVersionHistory
from monitor_web.strategies.loader.datalink_loader import (
    DatalinkDefaultAlarmStrategyLoader,
    DataLinkStage,
    DatalinkStrategy,
    DataLinkStrategyInfo,
)


class BaseStatusResource(Resource):
    def __init__(self):
        super().__init__()
        self.collect_config_id: int = None
        self.collect_config: CollectConfigMeta = None
        self.stage: str = None
        self.strategy_map: map[int, DataLinkStrategyInfo] = {}
        self.strategy_ids: List[int] = []
        self.loader: DatalinkDefaultAlarmStrategyLoader = None
        self._init = False

    def init_data(self, collect_config_id: str, stage: DataLinkStage = None):
        self.collect_config_id = collect_config_id
        self.collect_config: CollectConfigMeta = CollectConfigMeta.objects.get(id=self.collect_config_id)
        self.stage = stage
        if self.stage:
            self.loader = DatalinkDefaultAlarmStrategyLoader(
                collect_config=self.collect_config, user_id=get_global_user()
            )
            self.strategy_map = self.loader.load_strategy_map(self.stage)
            self.strategy_ids = list(self.strategy_map.keys())
        self._init = True

    def get_alert_strategies(self) -> Tuple[List[int], List[Dict]]:
        """检索告警配置"""
        strategies = [
            resource.strategies.get_strategy_v2(bk_biz_id=self.collect_config.bk_biz_id, id=sid)
            for sid in self.strategy_ids
        ]
        return strategies

    def get_strategy_desc(self, strategy_id: int):
        """获取采集配置描述"""
        return self.strategy_map.get(strategy_id, {}).get("strategy_desc", "")

    def get_strategy_user_groups(self) -> List[UserGroup]:
        user_groups = []
        for v in self.strategy_map.values():
            user_groups.extend(v["rule"]["user_groups"])
        return UserGroup.objects.filter(id__in=user_groups)

    def search_alert_histogram(self, time_range: int = 3600) -> List[List]:
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

    def get_metrics_json(self) -> List[Dict]:
        """查询采集插件配置的指标维度信息"""
        metric_json = copy.deepcopy(self.collect_config.deployment_config.metrics)
        plugin = self.collect_config.plugin
        # 如果插件id在time_series_group能查到，则可以认为是分表的，否则走原有逻辑
        group_list = api.metadata.query_time_series_group(
            time_series_group_name=f"{plugin.plugin_type}_{plugin.plugin_id}"
        )
        for table in metric_json:
            # 分表模式下，这里table_id都为__default__
            table["table_name"] = table["table_name"] if not group_list else "__default__"
            table["table_id"] = self.get_result_table_id(table["table_name"])
            metric_names: List[str] = list()
            for field in table["fields"]:
                if not field["is_active"]:
                    continue
                if field["monitor_type"] != "metric":
                    continue
                metric_names.append(field["name"])
            table["metric_names"] = metric_names
        if len(metric_json) == 0:
            raise CollectorPluginMetaError(
                "No metric config in collector plugin({})".format(self.collect_config.plugin.plugin_id)
            )
        return metric_json

    def get_result_table_id(self, table_name: str) -> str:
        """通过采集插件配置，拼接最终 RT_ID"""
        return PluginVersionHistory.get_result_table_id(self.collect_config.plugin, table_name).lower()

    def has_strategies(self) -> bool:
        return len(self.strategy_ids) > 0

    def build_alert_query_string(self) -> str:
        query_string = "({strategy}) AND ({collection})".format(
            strategy=" OR ".join(f"strategy_id : {sid}" for sid in self.strategy_ids),
            collection="tags.bk_collect_config_id: {}".format(self.collect_config_id),
        )
        return query_string


class AlertStatusResource(BaseStatusResource):
    """查询数据链路各个阶段的告警状态"""

    class RequestSerilizer(serializers.Serializer):
        collect_config_id = serializers.IntegerField(required=True, label="采集配置ID")
        stage = serializers.ChoiceField(
            required=True, label="告警阶段", choices=[stage.value for stage in list(DataLinkStage)]
        )

    def perform_request(self, validated_request_data: Dict) -> Dict:
        self.init_data(validated_request_data["collect_config_id"], DataLinkStage(validated_request_data["stage"]))
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
        collect_config_id = serializers.IntegerField(required=True, label="采集配置ID")
        stage = serializers.ChoiceField(
            required=True, label="告警阶段", choices=[stage.value for stage in list(DataLinkStage)]
        )
        notice_group_list = serializers.ListField(required=True, child=serializers.IntegerField())

    def perform_request(self, validated_request_data: Dict):
        self.init_data(validated_request_data["collect_config_id"], DataLinkStage(validated_request_data["stage"]))
        strategy_tuples: List[Tuple[int, DatalinkStrategy]] = []
        for sid in self.strategy_ids:
            strategy_tuples.append((sid, self.strategy_map.get(sid)))
        self.loader.update_rule_group(
            user_group_ids=validated_request_data["notice_group_list"],
            strategy_tuples=strategy_tuples,
        )
        return "ok"


class CollectingTargetStatusResource(BaseStatusResource):
    class RequestSerilizer(serializers.Serializer):
        collect_config_id = serializers.IntegerField(required=True, label="采集配置ID")

    def perform_request(self, validated_request_data: Dict) -> Dict:
        self.init_data(validated_request_data["collect_config_id"], DataLinkStage.COLLECTING)

        instance_status = resource.collecting.collect_instance_status(id=self.collect_config_id)
        # 提取关联的所有主机ID
        bk_host_ids = []
        for group in instance_status["contents"]:
            for child in group["child"]:
                bk_host_ids.append(str(child["bk_host_id"]))

        targets_alert_histogram = {}
        if self.has_strategies():
            alert_histogram = self.search_target_alert_histogram(bk_host_ids)
            targets_alert_histogram = alert_histogram["targets"]

        # 填充主机的告警信息
        for group in instance_status["contents"]:
            for child in group["child"]:
                child["alert_histogram"] = targets_alert_histogram.get(str(child["bk_host_id"]), None)
        return instance_status

    def search_target_alert_histogram(self, targets: List[str], time_range: int = 3600) -> Dict:
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
        logger.info("Search collecting alerts, statement = {}".format(json.dumps(search_object.to_dict())))
        search_result = search_object[:0].execute()
        # 检索后的数据整理后，按照主机ID分桶存放，启动和结束记录还需要按照时间分桶存放
        init_alerts: Dict[str, int] = dict()
        begine_alerts: Dict[str, Dict[int][int]] = dict()
        end_alerts: Dict[str, Dict[int][int]] = dict()
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
            "Search collecting alerts, init_alert={}, begine_alerts={}, end_alerts={}".format(
                init_alerts, begine_alerts, end_alerts
            )
        )

        # 初始化主机分桶信息，每个分桶里按照时间分桶初始化 0
        ts_buckets = range(start_time, end_time, interval)
        targets_series: Dict[str, List] = {target: [[ts * 1000, 0] for ts in ts_buckets] for target in targets}
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
        total_series: List = []
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
        collect_config_id = serializers.IntegerField(required=True, label="采集配置ID")
        start_time = serializers.IntegerField(required=True, label="开始时间")
        end_time = serializers.IntegerField(required=True, label="结束时间")
        interval_option = serializers.CharField(required=False, label="间隔选项", default=IntervalOption.MINUTE.value)

    def perform_request(self, validated_request_data: Dict):
        self.init_data(validated_request_data["collect_config_id"])
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

        # 读取采集相关的指标列表
        promqls = [
            """sum(count_over_time({{
                __name__=~"bkmonitor:{table_id}:.*",
                bk_collect_config_id="{collect_config_id}"}}[{interval}{unit}])) or vector(0)
            """.format(
                table_id=table["table_id"],
                collect_config_id=self.collect_config_id,
                interval=interval,
                unit=interval_unit,
            )
            for table in self.get_metrics_json()
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
        logger.info("Search transfer metric count, statement = {}".format(json.dumps(query_params)))
        return resource.grafana.graph_unify_query(query_params)["series"]


class TransferLatestMsgResource(BaseStatusResource):
    class RequestSerilizer(serializers.Serializer):
        collect_config_id = serializers.IntegerField(required=True, label="采集配置ID")

    def perform_request(self, validated_request_data):
        self.init_data(validated_request_data["collect_config_id"])
        messages = []
        for table in self.get_metrics_json():
            for metric_name in table["metric_names"]:
                messages.extend(self.query_latest_metric_msg(table["table_id"], metric_name))
                if len(messages) > 10:
                    return messages[:10]
        return messages

    def query_latest_metric_msg(self, table_id: str, metric_name: str, time_range: int = 600) -> List[str]:
        """查询一个指标最近10分钟的最新数据"""
        start_time, end_time = int(time.time() - time_range), int(time.time())
        query_params = {
            "bk_biz_id": self.collect_config.bk_biz_id,
            "query_configs": [
                {
                    "data_source_label": "prometheus",
                    "data_type_label": "time_series",
                    "promql": "bkmonitor:{table}:{metric}{{{conds}}}[1m]".format(
                        table=table_id.replace('.', ':'),
                        metric=metric_name,
                        conds=f"bk_collect_config_id=\"{self.collect_config_id}\"",
                    ),
                    "interval": 60,
                    "alias": "a",
                }
            ],
            "expression": "",
            "alias": "a",
            "start_time": start_time,
            "end_time": end_time,
            "slimit": 500,
            "down_sample_range": "",
        }
        series = resource.grafana.graph_unify_query(query_params)["series"]
        msgs = []
        for s in series:
            val = s["datapoints"][-1][0]
            ts = s["datapoints"][-1][1]
            target = s["target"]
            # 组装消息
            msg = "{metric}{target} {val}".format(metric=metric_name, target=target, val=val)
            # 原始数据拼接
            raw = s["dimensions"]
            raw[metric_name] = val
            raw["time"] = ts

            msgs.append(
                {
                    "message": msg,
                    "time": datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M:%S"),
                    "raw": raw,
                }
            )
        return msgs


class StorageStatusResource(BaseStatusResource):
    """获取存储状态"""

    class RequestSerilizer(serializers.Serializer):
        collect_config_id = serializers.IntegerField(required=True, label="采集配置ID")

    def perform_request(self, validated_request_data):
        self.init_data(validated_request_data["collect_config_id"])
        metric_json = self.get_metrics_json()
        # 同一个采集项下所有表存储配置都是一致的，取第一个结果表即可
        storager = get_storager(metric_json[0]["table_id"])
        return {"info": storager.get_info(), "status": storager.get_status()}
