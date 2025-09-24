# -*- coding: utf-8 -*-
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
import logging
from itertools import product

from django.conf import settings
from django.utils.translation import gettext as _
from rest_framework.exceptions import ValidationError

from bkmonitor.models import (
    Action,
    ActionNoticeMapping,
    BaseAlarmQueryConfig,
    CustomEventQueryConfig,
    DetectAlgorithm,
    Item,
    NoticeGroup,
    NoticeTemplate,
    ResultTableDSLConfig,
    ResultTableSQLConfig,
    Strategy,
)
from constants.data_source import DataSourceLabel, DataTypeLabel
from constants.strategy import (
    NOT_SPLIT_DIMENSIONS,
    SPLIT_CMDB_LEVEL_MAP,
    SPLIT_DIMENSIONS,
    AdvanceConditionMethod,
    TargetFieldType,
)
from core.drf_resource import api
from core.errors.strategy import (
    CreateStrategyError,
    StrategyConfigInitError,
    StrategyNotExist,
    UpdateStrategyError,
)
from monitor_web.strategies.constant import EVENT_METRIC_ID

logger = logging.getLogger(__name__)


class StrategyConfig(object):
    # 需要的字段
    STRATEGY_FIELDS = [
        "id",
        "name",
        "bk_biz_id",
        "scenario",
        "create_time",
        "update_time",
        "create_user",
        "update_user",
        "is_enabled",
    ]

    ITEM_FIELDS = ["id", "name", "metric_id", "data_source_label", "data_type_label", "no_data_config", "target"]

    DETECT_ALGORITHM_FIELDS = [
        "id",
        "algorithm_type",
        "algorithm_unit",
        "algorithm_config",
        "trigger_config",
        "recovery_config",
        "level",
    ]

    ACTION_FIELDS = ["id", "config", "action_type"]

    NOTICE_GROUP_FIELDS = ["id", "name", "notice_receiver", "notice_way", "message"]

    NOTICE_TEMPLATE_FIELDS = ["anomaly_template", "recovery_template"]

    DATA_SOURCE_FIELDS = []

    DATA_SOURCE_MODEL = {
        "ResultTableSQLConfig": {
            "fields": [
                "result_table_id",
                "agg_method",
                "agg_interval",
                "agg_dimension",
                "agg_condition",
                "unit",
                "unit_conversion",
                "metric_field",
                "extend_fields",
            ],
            "model": ResultTableSQLConfig,
        },
        "ResultTableDSLConfig": {
            "fields": [
                "result_table_id",
                "agg_method",
                "agg_interval",
                "agg_dimension",
                "keywords_query_string",
                "rule",
                "keywords",
                "extend_fields",
                "agg_condition",
            ],
            "model": ResultTableDSLConfig,
        },
        "CustomEventQueryConfig": {
            "fields": [
                "bk_event_group_id",
                "custom_event_id",
                "agg_method",
                "agg_interval",
                "agg_dimension",
                "agg_condition",
                "extend_fields",
            ],
            "model": CustomEventQueryConfig,
        },
        "BaseAlarmQueryConfig": {"fields": ["agg_condition"], "model": BaseAlarmQueryConfig},
    }

    INSTANCE_DISPLAY_NAME = {
        "Strategy": "strategy",
        "Item": "item",
        "DetectAlgorithm": "algorithm",
        "ResultTableSQLConfig": "rt_conf",
        "ResultTableDSLConfig": "rt_conf",
        "Action": "action",
        "NoticeGroup": "notice_group",
    }

    def __init__(self, bk_biz_id, strategy_id):
        """
        strategy_dict示例数据
        {
            'name': 'cpu单核使用率策略',
            'bk_biz_id': 2,
            'source_type': 'BKMONITOR',
            'scenario': '主机',
            'item_list': [
                {
                    'name': '监控项1',
                    'data_source_type': 'TSDB',
                    'no_data_config': '',
                    'result_table_id': '',
                    'agg_method': 'MAX',
                    'agg_interval': 60,
                    'agg_dimension': '',
                    'agg_condition': '',
                    'metric_field': 'cpu_usage',
                    'unit': '',
                    'unit_conversion': 1.0,
                    'extend_fields': '',
                    'algorithm_list': [
                        {
                            'algorithm_type': 'Threshold',
                            'algorithm_config': '',
                            'level': 1,
                            'trigger_config': '{}',
                            'recovery_config': '{}',
                        }
                    ],
                    'target': '[{"ip": "127.0.0.1", "bk_cloud_id": 0}]'
                }

            ],
            'action_list': [
                {
                    'config': {
                        "alarm_interval": 1440,
                        "alarm_end_time": "23:59",
                        "alarm_start_time": "00:00",
                        "send_recovery_alarm": true
                    },
                    'action_type': 'notice',
                    'notice_group_list': [1,2],
                    'notice_template': {
                        'anomaly_template': '',
                        'recovery_template': ''
                    }
                }
            ]
        }
        :param strategy_id:
        :return:
        """
        self.id = None
        self.bk_biz_id = bk_biz_id

        # 将当前策略相关的model对象保存在实例变量中
        self.strategy = None
        # item.id: item
        self.item_data = {}
        # item.id: data_source
        self.data_source_data = {}
        # algorithm_id: detect_algorithm
        self.detect_algorithm_data = {}
        # action_id: action
        self.action_data = {}
        # action_id: action_template
        self.notice_template_data = {}
        # id: notice_group
        self.action_notice_mappings = {}
        self.conversion_result_table_id = True

        if isinstance(strategy_id, int):
            self.id = strategy_id
            self.get_object()
        elif isinstance(strategy_id, Strategy):
            self.strategy = strategy_id
            self.id = strategy_id.id
        else:
            raise StrategyConfigInitError

    @classmethod
    def _set_dict_value(cls, dict_obj, model_fields, model_obj, conversion_result_table_id=True):
        """根据指定的model_fields从model对象中提取需要的字段写入字典"""
        if not model_obj:
            return

        for field in model_fields:
            value = getattr(model_obj, field)
            if value and field == "extend_fields" and value.get("origin_config", {}).get("result_table_id"):
                dict_obj["result_table_id"] = value.get("origin_config", {}).get("result_table_id", "")
                dict_obj["agg_dimension"] = value.get("origin_config", {}).get("agg_dimension", [])

            dict_obj[field] = value
            # 对id,name做特殊处理，增加前缀
            model_name = model_obj.__class__.__name__
            if field in ["id", "name"] and model_name in cls.INSTANCE_DISPLAY_NAME:
                key = "{}_{}".format(cls.INSTANCE_DISPLAY_NAME[model_name], field)
                dict_obj[key] = value

    @staticmethod
    def _update_obj_by_dict(model_obj, dict_obj):
        """根据字典更新model对象的值"""
        if not (model_obj and dict_obj):
            return

        for k, v in list(dict_obj.items()):
            setattr(model_obj, k, v)

        model_obj.save()

    @property
    def strategy_dict(self):
        strategy_dict = {"labels": self.strategy.labels}
        self._set_dict_value(strategy_dict, self.STRATEGY_FIELDS, self.strategy)
        strategy_dict.update(item_list=[], action_list=[])
        for item in list(self.item_data.values()):
            item_dict = dict(algorithm_list=[])
            self._set_dict_value(item_dict, self.ITEM_FIELDS, item)
            self._set_dict_value(
                item_dict, self.DATA_SOURCE_FIELDS, self.data_source_data.get(item.id), self.conversion_result_table_id
            )
            for algorithm in list(self.detect_algorithm_data.values()):
                if algorithm.item_id == item.id:
                    algorithm_dict = dict()
                    self._set_dict_value(algorithm_dict, self.DETECT_ALGORITHM_FIELDS, algorithm)
                    item_dict["algorithm_list"].append(algorithm_dict)

            strategy_dict["item_list"].append(item_dict)

        for action in list(self.action_data.values()):
            action_dict = dict()
            self._set_dict_value(action_dict, self.ACTION_FIELDS, action)
            notice_template_dict = {field: "" for field in self.NOTICE_TEMPLATE_FIELDS}
            if action.id in self.notice_template_data:
                self._set_dict_value(
                    notice_template_dict, self.NOTICE_TEMPLATE_FIELDS, self.notice_template_data[action.id]
                )

            action_dict["notice_template"] = notice_template_dict

            action_dict.update(
                notice_group_list=[
                    mapping.notice_group_id
                    for mapping in list(self.action_notice_mappings.values())
                    if mapping.action_id == action.id
                ]
            )
            strategy_dict["action_list"].append(action_dict)

        return strategy_dict

    @property
    def strategy_info(self):
        """
        策略信息，供屏蔽页展示用
        """
        strategy_dict = {
            "id": self.strategy.id,
            "name": self.strategy.name,
            "scenario": self.strategy.scenario,
            "item_list": [],
        }
        for item in list(self.item_data.values()):
            item_dict = dict(level=set())
            self._set_dict_value(item_dict, self.ITEM_FIELDS, item)
            self._set_dict_value(item_dict, self.DATA_SOURCE_FIELDS, self.data_source_data.get(item.id))
            for algorithm in list(self.detect_algorithm_data.values()):
                if algorithm.item_id == item.id:
                    item_dict["level"].add(algorithm.level)
            item_dict["level"] = list(item_dict["level"])
            strategy_dict["item_list"].append(item_dict)
        return strategy_dict

    def get_data_source_model(self, data_source_label, data_type_label):
        model_obj = Item.get_query_config_model(data_source_label, data_type_label)
        if not model_obj:
            return

        model_info = self.DATA_SOURCE_MODEL.get(model_obj.__name__)
        if model_info:
            self.DATA_SOURCE_FIELDS = model_info.get("fields", [])
            return model_info.get("model", None)

    def get_object(self):
        # 获取strategies
        try:
            self.strategy = Strategy.objects.get(id=self.id, bk_biz_id=self.bk_biz_id)
        except Strategy.DoesNotExist:
            raise StrategyNotExist

        item_list = Item.objects.filter(strategy_id=self.id)
        for item in item_list:
            self.item_data[item.id] = item
            # 获取data_source表
            data_source_model = self.get_data_source_model(item.data_source_label, item.data_type_label)
            if data_source_model:
                try:
                    data_source = data_source_model.objects.get(id=item.rt_query_config_id)
                    self.data_source_data[item.id] = data_source
                except data_source_model.DoesNotExist:
                    pass

            detect_algorithm_list = DetectAlgorithm.objects.filter(item_id=item.id)
            for algorithm in detect_algorithm_list:
                self.detect_algorithm_data[algorithm.id] = algorithm

        actions = Action.objects.filter(strategy_id=self.id)
        for action in actions:
            self.action_data[action.id] = action

            mappings = ActionNoticeMapping.objects.filter(action_id=action.id)
            for row in mappings:
                self.action_notice_mappings[row.id] = row

            notice_template_obj = NoticeTemplate.objects.filter(action_id=action.id).first()
            if notice_template_obj:
                self.notice_template_data[notice_template_obj.action_id] = notice_template_obj

    def access_aiops(self):
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
        from monitor_web.tasks import (
            access_aiops_by_strategy_id,
            access_host_anomaly_detect_by_strategy_id,
        )

        # 未开启计算平台接入，则直接返回
        if not settings.IS_ACCESS_BK_DATA:
            return

        has_intelligent_algorithm = False
        for algorithm in list(self.detect_algorithm_data.values()):
            # 主机异常检测的接入逻辑跟其他智能检测不一样，因此单独接入
            if algorithm.algorithm_type == DetectAlgorithm.AlgorithmChoices.HostAnomalyDetection:
                access_host_anomaly_detect_by_strategy_id.delay(self.id)
                return

            if algorithm.algorithm_type == DetectAlgorithm.AlgorithmChoices.IntelligentDetect:
                has_intelligent_algorithm = True
                break

        if not has_intelligent_algorithm:
            return

        # 判断数据来源
        for item in list(self.item_data.values()):
            if item.data_type_label != DataTypeLabel.TIME_SERIES:
                continue

            if item.data_source_label == DataSourceLabel.BK_MONITOR_COLLECTOR:
                rt_query_config = ResultTableSQLConfig.objects.get(id=item.rt_query_config_id)
                # 如果查询条件中存在特殊的方法，查询条件置为空
                for condition in rt_query_config.agg_condition:
                    if condition["method"] in AdvanceConditionMethod:
                        raise Exception(_("智能检测算法不支持这些查询条件({})".format(AdvanceConditionMethod)))
                access_aiops_by_strategy_id.delay(self.id)

            elif item.data_source_label == DataSourceLabel.BK_DATA:
                rt_query_config = ResultTableSQLConfig.objects.get(id=item.rt_query_config_id)
                # 1. 先授权给监控项目(以创建或更新策略的用户来请求一次授权)
                from bkmonitor.dataflow import auth

                auth.ensure_has_permission_with_rt_id(
                    bk_username=self.strategy.update_user,
                    rt_id=rt_query_config.result_table_id,
                    project_id=settings.BK_DATA_PROJECT_ID,
                )
                # 2. 然后再创建异常检测的dataflow
                access_aiops_by_strategy_id.delay(self.id)

    def create_cmdb_level_info(self):
        """
        利用计算平台计算能力，补充CMDB层级信息到原始表（按需开启）

        触发规则：如果未按最细粒度聚合，同时目标target又选择了动态节点，则开启这个逻辑
        """
        # 未开启计算平台接入，则直接返回
        if not settings.IS_ACCESS_BK_DATA:
            return

        for item in list(self.item_data.values()):
            if (
                item.data_source_label != DataSourceLabel.BK_MONITOR_COLLECTOR
                or item.data_type_label != DataTypeLabel.TIME_SERIES
            ):
                continue

            if (
                item.target
                and item.target[0]
                and item.target[0][0].get("field", "") in [TargetFieldType.service_topo, TargetFieldType.host_topo]
            ):
                if item.rt_query_config_id == 0:
                    continue

                rt_query = ResultTableSQLConfig.objects.get(id=item.rt_query_config_id)
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
                            self.id, rt_query.result_table_id
                        )
                    )
                    continue

                rt_query.agg_dimension = list(set(rt_query.agg_dimension + SPLIT_DIMENSIONS))
                rt_query.save()

    def create_result_table_split(self):
        # 判断是否选择的是动态节点
        cmdb_level_list = []
        target = list(self.item_data.values())[0].target
        if (
            target
            and target[0]
            and target[0][0].get("field", "") in [TargetFieldType.service_topo, TargetFieldType.host_topo]
        ):
            cmdb_level_list = list({i["bk_obj_id"] for i in target[0][0]["value"]})

        # 判断数据来源是"监控的时序数据"
        items = Item.objects.filter(strategy_id=self.strategy.id)
        for item in items:
            if (
                not item.rt_query_config_id
                or item.data_type_label != "time_series"
                or item.data_source_label != "bk_monitor"
            ):
                return

        sql_id_list = [item.rt_query_config_id for item in items]
        if 0 in sql_id_list:
            return

        create_list = product(cmdb_level_list, sql_id_list)
        for create_condition in create_list:
            cmdb_level, rt_sql_id = create_condition
            sql_instance = ResultTableSQLConfig.objects.get(id=rt_sql_id)
            # 判断是否去掉了"最小粒度维度"
            # "bk_target_ip" OR "bk_target_service_instance_id"
            if set(NOT_SPLIT_DIMENSIONS) & set(sql_instance.agg_dimension):
                continue

            # 临时去掉主机相关的CMDB字段拆分逻辑, 只有当全局配置为关闭时，而且是system库则拒绝创建
            if not settings.IS_ALLOW_ALL_CMDB_LEVEL and sql_instance.result_table_id.startswith("system."):
                if settings.IS_ACCESS_BK_DATA:
                    # 如果开启了计算平台功能，不运行这里的逻辑即可，不进行报错，后续的逻辑需要继续
                    return
                raise Exception(_("主机性能指标按CMDB动态节点聚合暂不可用(原因：维度未使用云区域ID + IP，目标又选择了CMDB节点)"))

            origin_result_table_id = (
                sql_instance.extend_fields.get("origin_config", {}).get("result_table_id")
                if isinstance(sql_instance.extend_fields, dict)
                else ""
            )
            if not origin_result_table_id:
                origin_result_table_id = sql_instance.result_table_id

            origin_agg_dimension = copy.deepcopy(sql_instance.agg_dimension)
            try:
                result = api.metadata.create_result_table_metric_split(
                    cmdb_level=SPLIT_CMDB_LEVEL_MAP.get(cmdb_level, cmdb_level),
                    table_id=origin_result_table_id,
                    operator=self.strategy.create_user,
                )
                sql_instance.result_table_id = result["table_id"]
            except Exception as e:
                if _("不可对拆分结果表再次拆分") in str(e):
                    continue
                else:
                    raise e

            sql_instance.agg_dimension.extend(SPLIT_DIMENSIONS)
            sql_instance.agg_dimension = list(set(sql_instance.agg_dimension))
            extend_result_table_msg = {
                "origin_config": {
                    "result_table_id": origin_result_table_id,
                    "agg_dimension": list(set(origin_agg_dimension) - set(SPLIT_DIMENSIONS)),
                }
            }
            if sql_instance.extend_fields:
                sql_instance.extend_fields.update(extend_result_table_msg)
            else:
                sql_instance.extend_fields = extend_result_table_msg

            sql_instance.save()

    @classmethod
    def create(cls, strategy_dict):
        item_list = strategy_dict.pop("item_list", [])
        action_list = strategy_dict.pop("action_list", [])
        # 创建strategies表记录
        instance = None
        try:
            strategy_dict.pop("source_type", None)
            strategy = Strategy.objects.create(**strategy_dict)
            instance = cls(strategy_dict["bk_biz_id"], strategy)
            # 创建items表记录
            for item in item_list:
                instance.create_item(item)

            for action in action_list:
                instance.create_action(action)

            instance.create_result_table_split()
            instance.create_cmdb_level_info()
            instance.access_aiops()
        except ValidationError as e:
            # 创建失败，删除该策略所有的关联配置
            if instance:
                instance.delete()

            raise CreateStrategyError({"msg": ",".join(e.detail)})
        except Exception as e:
            # 创建失败，删除该策略所有的关联配置
            if instance:
                instance.delete()

            raise CreateStrategyError({"msg": str(e)})

        return instance

    def update_strategy(self, strategy_dict):
        item_list = strategy_dict.pop("item_list", [])
        action_list = strategy_dict.pop("action_list", [])
        labels = strategy_dict.pop("labels", [])
        # 修改strategies表记录
        self._update_obj_by_dict(self.strategy, strategy_dict)
        # 修改items表记录
        self.save_items(item_list)
        self.save_actions(action_list)
        self.save_labels(labels)

    def update(self, strategy_dict):
        self.conversion_result_table_id = False
        old_strategy_dict = copy.deepcopy(self.strategy_dict)
        try:
            self.update_strategy(strategy_dict)
            self.create_result_table_split()
            self.create_cmdb_level_info()
            self.access_aiops()
        except ValidationError as e:
            self.update_strategy(old_strategy_dict)
            raise UpdateStrategyError({"msg": ",".join(e.detail)})
        except Exception as e:
            # 如果修改失败，回退之前的配置
            self.update_strategy(old_strategy_dict)
            raise UpdateStrategyError({"msg": str(e)})

    def delete(self):
        related_model_list = [
            self.action_notice_mappings,
            self.notice_template_data,
            self.action_data,
            self.detect_algorithm_data,
            self.data_source_data,
            self.item_data,
        ]
        for model_data in related_model_list:
            for obj in list(model_data.values()):
                obj.delete()

        self.strategy.delete()

    @staticmethod
    def handle_advance_condition_method(data_source_dict):
        """
        如果存在高级查询条件，则需要保证监控条件使用的维度必须在监控维度中
        :param data_source_dict: 数据源查询配置
        """
        agg_condition = data_source_dict.get("agg_condition")
        agg_dimension = data_source_dict.get("agg_dimension")
        if agg_condition is None or agg_dimension is None:
            return

        methods = {condition["method"] for condition in agg_condition}
        if methods & set(AdvanceConditionMethod):
            for condition in agg_condition:
                if condition["key"] not in agg_dimension:
                    agg_dimension.append(condition["key"])

    @staticmethod
    def handle_target_dimensions(data_source_dict, target):
        """
        如果target使用静态IP但维度中没有，则进行补全
        """
        is_ip_target = target and target[0] and target[0][0]["field"] == "bk_target_ip"
        if not is_ip_target or "agg_dimension" not in data_source_dict:
            return

        agg_dimension = data_source_dict["agg_dimension"]
        if "bk_target_ip" not in agg_dimension:
            agg_dimension.append("bk_target_ip")
        if "bk_target_cloud_id" not in agg_dimension:
            agg_dimension.append("bk_target_cloud_id")

    def create_item(self, item):
        item.pop("id", None)
        item_dict = {field: item[field] for field in self.ITEM_FIELDS if field in item}
        algorithm_list = item.pop("algorithm_list", [])
        # 获取数据源model

        data_source_model = self.get_data_source_model(item["data_source_label"], item["data_type_label"])

        # 主机重启、进程端口、自定义字符型、进程托管事件特殊处理
        if item["metric_id"] in EVENT_METRIC_ID:
            data_source_model = ResultTableSQLConfig
            self.DATA_SOURCE_FIELDS = self.DATA_SOURCE_MODEL["ResultTableSQLConfig"]["fields"]

        if data_source_model:
            if item.get("rt_query_config"):
                data_source_dict = {
                    field: item["rt_query_config"][field]
                    for field in self.DATA_SOURCE_FIELDS
                    if field in item["rt_query_config"]
                }
            else:
                data_source_dict = {field: item[field] for field in self.DATA_SOURCE_FIELDS if field in item}
            # 清除空维度
            if "agg_dimension" in self.DATA_SOURCE_FIELDS:
                data_source_dict["agg_dimension"] = [
                    dimension for dimension in data_source_dict["agg_dimension"] if dimension
                ]
            self.handle_advance_condition_method(data_source_dict)
            self.handle_target_dimensions(data_source_dict, item_dict.get("target", []))
            self.full_result_table(item, data_source_dict)
            data_source = data_source_model.objects.create(**data_source_dict)
            item_dict.update(rt_query_config_id=data_source.id)
        else:
            item_dict.update(rt_query_config_id=0)

        item_dict.update(strategy_id=self.id)
        item_instance = Item.objects.create(**item_dict)
        for algorithm in algorithm_list:
            algorithm.pop("id", None)
            algorithm.pop("algorithm_id", None)
            obj = DetectAlgorithm.objects.create(strategy_id=self.id, item_id=item_instance.id, **algorithm)
            self.detect_algorithm_data[obj.id] = obj

        # 保存model对象
        self.item_data[item_instance.id] = item_instance
        if data_source_model:
            self.data_source_data[item_instance.id] = data_source

    @staticmethod
    def full_result_table(item, data_source_dict):
        if item["data_type_label"] == DataTypeLabel.EVENT and item["data_source_label"] == DataSourceLabel.CUSTOM:
            event_group_id = data_source_dict["bk_event_group_id"]
            event_group_info = api.metadata.get_event_group(event_group_id=event_group_id)
            data_source_dict["result_table_id"] = event_group_info["table_id"]

    def update_item(self, item_id, item):
        item.pop("id", None)
        if not (item_id and item_id in self.item_data):
            return

        item_dict = {field: item[field] for field in self.ITEM_FIELDS if field in item}
        if item.get("rt_query_config"):
            data_source_dict = {
                field: item["rt_query_config"][field]
                for field in self.DATA_SOURCE_FIELDS
                if field in item["rt_query_config"]
            }
        else:
            data_source_dict = {field: item[field] for field in self.DATA_SOURCE_FIELDS if field in item}
        # 清除空维度
        if "agg_dimension" in self.DATA_SOURCE_FIELDS:
            data_source_dict["agg_dimension"] = [
                dimension for dimension in data_source_dict["agg_dimension"] if dimension
            ]
        self.handle_advance_condition_method(data_source_dict)
        algorithm_list = item.pop("algorithm_list", [])
        self._update_obj_by_dict(self.data_source_data.get(item_id), data_source_dict)
        self._update_obj_by_dict(self.item_data.get(item_id), item_dict)
        self.save_algorithms(item_id=item_id, algorithm_list=algorithm_list)

    def delete_item(self, item_id):
        item_obj = self.item_data.pop(item_id, None)
        if not item_obj:
            return

        detect_algorithm_list = list(self.detect_algorithm_data.values())
        for algorithm in detect_algorithm_list:
            if algorithm.item_id == item_id:
                algorithm.delete()
                self.detect_algorithm_data.pop(algorithm.id, None)

        data_source = self.data_source_data.pop(item_id, None)
        if data_source:
            data_source.delete()

        item_obj.delete()

    def save_items(self, item_list):
        # 记录原有id
        origin_ids = list(self.item_data.keys())
        # 记录传入的id
        updated_ids = []
        for item in item_list:
            item_id = item.pop("id", None)

            if item_id and (item["data_source_label"], item["data_type_label"]) != (
                DataSourceLabel.BK_MONITOR_COLLECTOR,
                DataTypeLabel.EVENT,
            ):
                updated_ids.append(item_id)
                self.update_item(item_id, item)
            else:
                self.create_item(item)

        # 删除多余的item
        for item_id in origin_ids:
            if item_id not in updated_ids:
                self.delete_item(item_id)

    def save_algorithms(self, item_id, algorithm_list):
        origin_ids = [
            algorithm.id for algorithm in list(self.detect_algorithm_data.values()) if algorithm.item_id == item_id
        ]
        updated_ids = []
        for algorithm in algorithm_list:
            algorithm_id = algorithm.pop("id", None)
            # 如果有ID则尝试更新
            if algorithm_id and algorithm_id in origin_ids:
                updated_ids.append(algorithm_id)
                self.update_algorithm(algorithm_id, algorithm)
                continue

            # 如果没有id则创建新的检查算法
            self.create_algorithm(item_id, algorithm)

        # 将传入的算法和已存算法做比较吗，判断出需要删除的算法
        for algorithm_id in origin_ids:
            if algorithm_id not in updated_ids:
                self.delete_algorithm(algorithm_id)

    def create_algorithm(self, item_id, algorithm):
        algorithm.pop("id", None)
        algorithm.pop("algorithm_id", None)
        algorithm.update(strategy_id=self.id, item_id=item_id)
        algorithm_obj = DetectAlgorithm.objects.create(**algorithm)
        self.detect_algorithm_data[algorithm_obj.id] = algorithm_obj

    def update_algorithm(self, algorithm_id, algorithm):
        self._update_obj_by_dict(self.detect_algorithm_data.get(algorithm_id), algorithm)

    def delete_algorithm(self, algorithm_id):
        obj = self.detect_algorithm_data.pop(algorithm_id, None)
        if obj:
            obj.delete()

    def create_action(self, action):
        action.pop("id", None)
        action.pop("action_id", None)
        notice_group_list = action.pop("notice_group_list", [])
        notice_template = action.pop("notice_template", None)
        action.update(strategy_id=self.id)
        action_instance = Action.objects.create(**action)
        for notice_group_id in notice_group_list:
            try:
                NoticeGroup.objects.get(id=notice_group_id)
            except NoticeGroup.DoesNotExist:
                continue

            group_obj = ActionNoticeMapping.objects.create(
                action_id=action_instance.id, notice_group_id=notice_group_id
            )
            self.action_notice_mappings[group_obj.id] = group_obj

        if notice_template:
            notice_template.update(action_id=action_instance.id)
            self.notice_template_data[action_instance.id] = NoticeTemplate.objects.create(**notice_template)

        self.action_data[action_instance.id] = action_instance

    def update_action(self, action_id, action):
        action.pop("id", None)
        if not action_id:
            return

        notice_group_list = action.pop("notice_group_list", [])
        notice_template = action.pop("notice_template", None)
        self._update_obj_by_dict(self.action_data.get(action_id), action)
        if notice_template:
            if self.notice_template_data.get(action_id):
                self._update_obj_by_dict(self.notice_template_data.get(action_id), notice_template)
            else:
                notice_template.update(action_id=action_id)
                self.notice_template_data[action_id] = NoticeTemplate.objects.create(**notice_template)

        self.save_notice_groups(action_id, notice_group_list)

    def save_labels(self, labels):
        pass

    def save_actions(self, action_list):
        origin_ids = list(self.action_data.keys())
        updated_ids = []
        for action in action_list:
            action_id = action.pop("id", None)
            if action_id:
                updated_ids.append(action_id)
                self.update_action(action_id, action)
            else:
                self.create_action(action)

        for action_id in origin_ids:
            if action_id not in updated_ids:
                self.delete_action(action_id)

    def delete_action(self, action_id):
        action = self.action_data.pop(action_id, None)
        if not action:
            return

        notice_template = self.notice_template_data.pop(action_id, None)
        if notice_template:
            notice_template.delete()

        for group in list(self.action_notice_mappings.values()):
            if group.action_id == action_id:
                self.action_notice_mappings.pop(group.id).delete()

        action.delete()

    def save_notice_groups(self, action_id, notice_group_list):
        action_notice_group_list = []
        action_notice_group_id_list = []
        for group in list(self.action_notice_mappings.values()):
            if group.action_id == action_id:
                action_notice_group_list.append(group)
                action_notice_group_id_list.append(group.notice_group_id)

        for group_id in notice_group_list:
            if group_id not in action_notice_group_id_list:
                try:
                    NoticeGroup.objects.get(id=group_id)
                except NoticeGroup.DoesNotExist:
                    continue

                obj = ActionNoticeMapping.objects.create(action_id=action_id, notice_group_id=group_id)
                self.action_notice_mappings[obj.id] = obj

        for group in action_notice_group_list:
            if group.notice_group_id not in notice_group_list:
                self.action_notice_mappings.pop(group.id)
                group.delete()

    def update_specified_field(self, data):
        """
        更新指定指定
        :param data:
        :return:
        """
        strategy_dict = self.strategy_dict
        update_specified_key(strategy_dict, data)
        self.update(strategy_dict)


def update_specified_key(origin_dict, data):
    """递归更新字典"""
    for k in list(origin_dict.keys()):
        if k in data:
            origin_dict[k] = data[k]
        else:
            if isinstance(origin_dict[k], dict):
                update_specified_key(origin_dict[k], data)
            elif isinstance(origin_dict[k], list):
                for item in origin_dict[k]:
                    if isinstance(item, dict):
                        update_specified_key(item, data)
