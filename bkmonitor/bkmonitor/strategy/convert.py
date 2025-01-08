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

"""
特殊策略的转换及还原逻辑
"""
import logging
from itertools import chain
from typing import List

from django.conf import settings
from django.utils.translation import gettext as _

from bkmonitor.models import AlgorithmModel
from bkmonitor.strategy.new_strategy import Strategy
from constants.data_source import DataSourceLabel, DataTypeLabel
from constants.strategy import (
    EVENT_DETECT_LIST,
    EVENT_QUERY_CONFIG_MAP,
    NOT_SPLIT_DIMENSIONS,
    SPLIT_CMDB_LEVEL_MAP,
    SPLIT_DIMENSIONS,
    SYSTEM_EVENT_RT_TABLE_ID,
    TEMPLATE_MAP,
    UPTIMECHECK_ERROR_CODE_MAP,
    TargetFieldType,
)
from core.drf_resource import api

logger = logging.getLogger(__name__)


class UptimeCheckConvert:
    """
    拨测策略转换
    """

    @classmethod
    def convert(cls, strategy: Strategy):
        for item in strategy.items:
            for query_config in item.query_configs:
                # 判断是否是拨测配置
                if (
                    query_config.data_source_label != DataSourceLabel.BK_MONITOR_COLLECTOR
                    or query_config.data_type_label != DataTypeLabel.TIME_SERIES
                    or not query_config.result_table_id.startswith("uptimecheck.")
                ):
                    continue

                old_metric_field = query_config.metric_field
                # 将task_id的值转换为字符型
                for condition_msg in query_config.agg_condition:
                    if condition_msg["key"] == "task_id":
                        condition_msg["value"] = [str(i) for i in condition_msg["value"]]

                if old_metric_field not in UPTIMECHECK_ERROR_CODE_MAP:
                    continue

                # 默认拨测采集任务监控维度需要任务ID
                if "task_id" not in query_config.agg_dimension:
                    raise Exception(_("监控维度请选择任务ID"))

                # 将响应内容及响应码替换真实指标，补充错误码条件
                metric_filed = "available"
                error_code = str(UPTIMECHECK_ERROR_CODE_MAP[old_metric_field])
                new_condition = [{"key": "error_code", "method": "eq", "value": [error_code]}]

                for index, condition_msg in enumerate(query_config.agg_condition):
                    if condition_msg.get("condition") == "or" and index != 0:
                        new_condition.append(
                            {"key": "error_code", "method": "eq", "value": error_code, "condition": "or"}
                        )

                    new_condition.append(condition_msg)
                    condition_msg["condition"] = "and"

                query_config.agg_condition = new_condition
                query_config.metric_field = metric_filed

            # 将部分节点数算法改为阈值算法
            algorithms = item.algorithms
            for algorithm in algorithms:
                if algorithm.type == AlgorithmModel.AlgorithmChoices.PartialNodes:
                    algorithm.type = AlgorithmModel.AlgorithmChoices.Threshold
                    algorithm.config = [[{"method": "gte", "threshold": algorithm.config.get("count", 0)}]]

    @classmethod
    def restore(cls, strategy: Strategy):
        for item in strategy.items:
            is_special_uptime_check = False
            for query_config in item.query_configs:
                # 判断是否是拨测配置
                if (
                    query_config.data_source_label != DataSourceLabel.BK_MONITOR_COLLECTOR
                    or query_config.data_type_label != DataTypeLabel.TIME_SERIES
                    or not query_config.result_table_id.startswith("uptimecheck.")
                ):
                    continue

                # 将节点数量指标转换为对展示的指标
                condition_dict = {
                    condition_msg["key"]: condition_msg["value"] for condition_msg in query_config.agg_condition
                }
                if "error_code" in condition_dict:
                    error_code_map = {value: key for key, value in UPTIMECHECK_ERROR_CODE_MAP.items()}
                    error_code = condition_dict["error_code"]
                    if isinstance(error_code, list):
                        error_code = error_code[0]
                    query_config.metric_field = error_code_map[int(error_code)]

                    # 是使用部分节点数的特殊指标
                    is_special_uptime_check = True

                new_condition = []
                for index, condition_msg in enumerate(query_config.agg_condition):
                    # 去除error_code查询条件
                    if condition_msg["key"] == "error_code":
                        if index + 1 < len(query_config.agg_condition) and condition_msg.get("condition") == "or":
                            query_config.agg_condition[index + 1]["condition"] = "or"
                        continue

                    # task_id的值转为字符型
                    if condition_msg["key"] == "task_id" and isinstance(condition_msg["value"], (tuple, list)):
                        condition_msg["value"] = [str(task_id) for task_id in condition_msg["value"]]

                    if not new_condition and "condition" in condition_msg:
                        del condition_msg["condition"]
                    new_condition.append(condition_msg)
                query_config.agg_condition = new_condition

            # 特殊指标处理
            # 响应内容及响应码的算法换回部分节点数
            if not is_special_uptime_check:
                continue

            algorithms = item.algorithms
            for algorithm in algorithms:
                if algorithm.type == AlgorithmModel.AlgorithmChoices.Threshold:
                    algorithm.type = AlgorithmModel.AlgorithmChoices.PartialNodes
                    algorithm.config = {"count": algorithm.config[0][0]["threshold"]}


class CMDBTopoNodeAggConvert:
    """
    拓扑层级聚合策略转换
    如果是监控采集的指标，监控对象是节点，且维度中不含实例维度(ip/service_instance)。
    则调用metadata创建一张特殊的表，包含bk_obj_id和bk_inst_id维度，可以基于选择的节点进行聚合计算。
    注: 由于内置的系统主机指标数据量过大，因此禁用了此逻辑。
    """

    @classmethod
    def convert(cls, strategy: Strategy):
        """
        保存时判断是否进行拓扑层级聚合
        1. 判断是否监控对象是否是拓扑节点
        2. 判断聚合维度中是否有实例维度
        3. 按每个拓扑层级调用metadata的节点聚合
        4. 修改结果表及维度配置，在extend_fields中保存原始配置
        """
        for item in strategy.items:
            target = item.target

            # 判断是否配置监控目标
            if not target or not target[0]:
                return

            # 监控对象为拓扑节点
            if target[0][0].get("field", "") not in [
                TargetFieldType.service_topo,
                TargetFieldType.host_topo,
                TargetFieldType.host_set_template,
                TargetFieldType.service_set_template,
                TargetFieldType.host_service_template,
                TargetFieldType.service_service_template,
            ]:
                return

            bk_obj_ids = {TEMPLATE_MAP.get(i["bk_obj_id"], i["bk_obj_id"]) for i in target[0][0]["value"]}
            for query_config in item.query_configs:
                if (
                    query_config.data_source_label != DataSourceLabel.BK_MONITOR_COLLECTOR
                    or query_config.data_type_label != DataTypeLabel.TIME_SERIES
                ):
                    continue

                origin_result_table_id: str = query_config.result_table_id
                origin_dimension: List[str] = query_config.agg_dimension.copy()

                # 判断是否已经进行了转换
                if len(set(origin_dimension) & set(SPLIT_DIMENSIONS)) == 2:
                    continue

                # 判断是否去掉了"最小粒度维度"
                # "bk_target_ip" OR "bk_target_service_instance_id"
                if set(NOT_SPLIT_DIMENSIONS) & set(origin_dimension):
                    continue

                # 1. 开启节点聚合 -> Y
                # 2. 开启计算平台 -> N
                # 3. 是否system库相关数据 -> N
                if not settings.IS_ALLOW_ALL_CMDB_LEVEL:
                    raise Exception(_("CMDB动态节点聚合暂不可用(原因：全局配置[IS_ALLOW_ALL_CMDB_LEVEL]未开启)"))
                if settings.IS_ACCESS_BK_DATA:
                    return
                if query_config.result_table_id.startswith("system."):
                    raise Exception(_("主机性能指标按CMDB动态节点聚合暂不可用(原因：维度未使用云区域ID + IP，目标又选择了CMDB节点)"))
                # 调用metadataCMDB拓扑节点聚合
                for bk_obj_id in bk_obj_ids:
                    try:
                        result = api.metadata.create_result_table_metric_split(
                            cmdb_level=SPLIT_CMDB_LEVEL_MAP.get(bk_obj_id, bk_obj_id),
                            table_id=origin_result_table_id,
                            operator=strategy._get_username(),
                        )
                        query_config.result_table_id = result["table_id"]
                    except Exception as e:
                        if _("不可对拆分结果表再次拆分") not in str(e):
                            raise e

                # 补充拓扑节点维度
                query_config.agg_dimension.extend(SPLIT_DIMENSIONS)
                query_config.agg_dimension = list(set(query_config.agg_dimension))

                # 记录原始结果表及维度
                query_config.origin_config = {
                    "result_table_id": origin_result_table_id,
                    "agg_dimension": origin_dimension,
                }

    @classmethod
    def restore(cls, strategy: Strategy):
        """
        将策略还原成原始配置
        从extend_fields中的origin_config还原result_table_id及agg_dimension
        """

        for query_config in chain(*[item.query_configs for item in strategy.items]):
            if (
                query_config.data_source_label != DataSourceLabel.BK_MONITOR_COLLECTOR
                or query_config.data_type_label != DataTypeLabel.TIME_SERIES
            ):
                continue

            origin_config = getattr(query_config, "origin_config", None)
            if not origin_config:
                continue

            query_config.result_table_id = origin_config["result_table_id"]
            query_config.agg_dimension = origin_config["agg_dimension"]
            delattr(query_config, "origin_config")


class CMDBTopoNodeAggConvertWithBKData:
    """
    基于计算平台的CMDB预聚合
    """

    @classmethod
    def convert(cls, strategy: Strategy):
        """
        利用计算平台计算能力，补充CMDB层级信息到原始表（按需开启）

        触发规则：如果未按最细粒度聚合，同时目标target又选择了动态节点，则开启这个逻辑
        """
        # 未开启计算平台接入，则直接返回
        if not settings.IS_ACCESS_BK_DATA:
            return

        for item in strategy.items:
            target = item.target
            # 判断是否配置监控目标
            if (
                not target
                or not target[0]
                or target[0][0].get("field", "") not in [TargetFieldType.service_topo, TargetFieldType.host_topo]
            ):
                continue

            for rt_query in item.query_configs:
                if (
                    rt_query.data_source_label != DataSourceLabel.BK_MONITOR_COLLECTOR
                    or rt_query.data_type_label != DataTypeLabel.TIME_SERIES
                ):
                    continue

                user_config_dimension = rt_query.agg_dimension
                # 如果包含了"最小粒度"维度字段，则不触发按目标动态节点聚合
                # "bk_target_ip" OR "bk_target_service_instance_id"
                if set(NOT_SPLIT_DIMENSIONS) & set(user_config_dimension):
                    continue

                try:
                    api.metadata.full_cmdb_node_info(table_id=rt_query.result_table_id)
                except Exception:  # noqa
                    logger.exception(
                        "create cmdb node info error, strategy_id({}), result_table_id({})".format(
                            strategy.id, rt_query.result_table_id
                        )
                    )
                    continue

                rt_query.agg_dimension = list(set(rt_query.agg_dimension + SPLIT_DIMENSIONS))

    @classmethod
    def restore(cls, strategy: Strategy):
        pass


class AIOPSWithBkdataConvert(object):
    """
    aiops策略配置转换
    """

    @classmethod
    def convert(cls, strategy: Strategy):
        """
        在新建的时候，由于策略还未保存，缺少一些信息，所以这部分动作挪到了外面(策略保存后), 这里不做任何处理
        """
        pass

    @classmethod
    def restore(cls, strategy: Strategy):
        """
        策略创建好之后，需要等待一段时间才能使用
        :param strategy:
        :return:
        """
        pass
        # # 未开启计算平台接入，则直接返回
        # if not settings.IS_ACCESS_BK_DATA:
        #     return
        #
        # for query_config in chain(*[item.query_configs for item in strategy.items]):
        #     if (
        #         query_config.data_source_label not in [DataSourceLabel.BK_MONITOR_COLLECTOR, DataSourceLabel.BK_DATA]
        #         or query_config.data_type_label != DataTypeLabel.TIME_SERIES
        #     ):
        #         continue
        #
        #     intelligent_detect_config = getattr(query_config, "intelligent_detect", None)
        #     if not intelligent_detect_config:
        #         continue
        #
        #     # 如果策略新建时间未超过10分钟，则不显示智能异常检测的数据
        #     if arrow.utcnow().int_timestamp - arrow.get(strategy.create_time).int_timestamp < 600:
        #         delattr(query_config, "intelligent_detect")


class FakeEventConvert:
    """
    伪系统事件型策略转换
    """

    @classmethod
    def convert(cls, strategy: Strategy):
        """
        转换成真实的查询配置
        :param strategy: 策略
        """
        for item in strategy.items:
            for query_config in item.query_configs:
                if (
                    query_config.data_source_label != DataSourceLabel.BK_MONITOR_COLLECTOR
                    or query_config.data_type_label != DataTypeLabel.EVENT
                    or query_config.metric_field not in EVENT_QUERY_CONFIG_MAP
                ):
                    continue

                # 改成真实的查询配置
                query_config.data_source_label = DataSourceLabel.BK_MONITOR_COLLECTOR
                query_config.data_type_label = DataTypeLabel.TIME_SERIES
                origin_metric_field = query_config.metric_field
                for field, value in EVENT_QUERY_CONFIG_MAP[origin_metric_field].items():
                    setattr(query_config, field, value)

                # 调整为特定的检测算法
                for algorithm in item.algorithms:
                    algorithm.type = EVENT_DETECT_LIST[origin_metric_field][0]["type"]
                    algorithm.config = EVENT_DETECT_LIST[origin_metric_field][0]["config"]

    @classmethod
    def restore(cls, strategy: Strategy):
        event_algorithm_types = [detect_config[0]["type"] for detect_config in EVENT_DETECT_LIST.values()]

        # 判断是否有事件算法
        for item in strategy.items:
            for algorithm in item.algorithms:
                if algorithm.type not in event_algorithm_types:
                    return

        for query_config in chain(*[item.query_configs for item in strategy.items]):
            if (
                query_config.data_source_label != DataSourceLabel.BK_MONITOR_COLLECTOR
                or query_config.data_type_label != DataTypeLabel.TIME_SERIES
            ):
                continue

            metric_id = f"{query_config.result_table_id}.{query_config.metric_field}"
            for metric_field, config in EVENT_QUERY_CONFIG_MAP.items():
                if metric_id == f"{config['result_table_id']}.{config['metric_field']}":
                    query_config.data_source_label = DataSourceLabel.BK_MONITOR_COLLECTOR
                    query_config.data_type_label = DataTypeLabel.EVENT
                    query_config.result_table_id = SYSTEM_EVENT_RT_TABLE_ID
                    query_config.metric_field = metric_field
                    break


class EventTobeClosedConvert:
    """
    事件恢复机制最终状态为关闭的配置
    """

    @classmethod
    def convert(cls, strategy: Strategy):
        for query_config in chain(*[item.query_configs for item in strategy.items]):
            if query_config.get_metric_id() not in settings.CLOSE_EVNET_METRIC_IDS:
                break
        else:
            strategy.detects[0].recovery_config.update({"status_setter": "close"})

    @classmethod
    def restore(cls, strategy: Strategy):
        pass


class ActionOptionConvert:
    """
    处理套餐部分配置与通知配置对齐
    """

    @classmethod
    def convert(cls, strategy: Strategy):
        for action in strategy.actions:
            action.user_groups = strategy.notice.user_groups
            action.options.update(
                {
                    "start_time": strategy.notice.options.get("start_time", "00:00:00"),
                    "end_time": strategy.notice.options.get("end_time", "23:59:59"),
                }
            )
        for query_config in chain(*[item.query_configs for item in strategy.items]):
            if query_config.get_metric_id() not in settings.CLOSE_EVNET_METRIC_IDS:
                break
        else:
            strategy.detects[0].recovery_config.update({"status_setter": "close"})

    @classmethod
    def restore(cls, strategy: Strategy):
        pass


Convertors = [
    AIOPSWithBkdataConvert,
    CMDBTopoNodeAggConvert,
    CMDBTopoNodeAggConvertWithBKData,
    FakeEventConvert,
    UptimeCheckConvert,
    EventTobeClosedConvert,
    ActionOptionConvert,
]
