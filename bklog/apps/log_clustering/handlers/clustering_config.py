# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""
import json
import re

import arrow
from django.utils.translation import ugettext_lazy as _

from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.feature_toggle.plugins.constants import BKDATA_CLUSTERING_TOGGLE
from apps.log_clustering.constants import (
    CLUSTERING_CONFIG_DEFAULT,
    CLUSTERING_CONFIG_EXCLUDE,
    DEFAULT_CLUSTERING_FIELDS,
)
from apps.log_clustering.exceptions import (
    BkdataFieldsException,
    BkdataRegexException,
    ClusteringConfigHasExistException,
    ClusteringConfigNotExistException,
    CollectorEsStorageNotExistException,
    CollectorStorageNotExistException,
)
from apps.log_clustering.handlers.aiops.aiops_model.aiops_model_handler import (
    AiopsModelHandler,
)
from apps.log_clustering.handlers.dataflow.constants import OnlineTaskTrainingArgs
from apps.log_clustering.handlers.dataflow.dataflow_handler import DataFlowHandler
from apps.log_clustering.handlers.pipline_service.constants import OperatorServiceEnum
from apps.log_clustering.models import ClusteringConfig
from apps.log_clustering.tasks.msg import access_clustering
from apps.log_databus.constants import EtlConfig
from apps.log_databus.handlers.collector import CollectorHandler
from apps.log_databus.handlers.collector_scenario import CollectorScenario
from apps.log_databus.models import CollectorConfig
from apps.log_search.handlers.search.search_handlers_esquery import SearchHandler
from apps.log_search.models import LogIndexSet
from apps.models import model_to_dict
from apps.utils.function import map_if
from apps.utils.local import activate_request
from apps.utils.log import logger
from apps.utils.thread import generate_request
from bkm_space.api import SpaceApi
from bkm_space.define import SpaceTypeEnum
from bkm_space.errors import NoRelatedResourceError
from bkm_space.utils import bk_biz_id_to_space_uid


class ClusteringConfigHandler(object):
    class AccessStatusCode:
        PENDING = "PENDING"
        RUNNING = "RUNNING"
        SUCCESS = "SUCCESS"
        FAILED = "FAILED"

    def __init__(self, index_set_id=None, collector_config_id=None):
        self.index_set_id = index_set_id
        self.data = None
        if index_set_id:
            self.data = ClusteringConfig.get_by_index_set_id(index_set_id=self.index_set_id)
        if collector_config_id:
            try:
                self.data = ClusteringConfig.objects.get(collector_config_id=collector_config_id)
            except ClusteringConfig.DoesNotExist:
                raise ClusteringConfigNotExistException()

    def retrieve(self):
        return model_to_dict(self.data, exclude=CLUSTERING_CONFIG_EXCLUDE)

    def start(self):
        from apps.log_clustering.handlers.pipline_service.aiops_service import (
            operator_aiops_service,
        )

        pipeline_id = operator_aiops_service(self.index_set_id)
        return pipeline_id

    def online_start(self):
        from apps.log_clustering.handlers.pipline_service.aiops_service_online import (
            operator_aiops_service_online,
        )

        pipeline_id = operator_aiops_service_online(self.index_set_id)
        return pipeline_id

    def create(self, index_set_id, params):
        clustering_config = ClusteringConfig.get_by_index_set_id(index_set_id=index_set_id, raise_exception=False)

        if clustering_config and clustering_config.task_records:
            # 已接入过聚类的，不允许再创建
            raise ClusteringConfigHasExistException(
                ClusteringConfigHasExistException.MESSAGE.format(index_set_id=index_set_id)
            )

        log_index_set = LogIndexSet.objects.get(index_set_id=index_set_id)
        collector_config_id = log_index_set.collector_config_id
        log_index_set_data, *_ = log_index_set.indexes

        clustering_fields = params["clustering_fields"]

        conf = FeatureToggleObject.toggle(BKDATA_CLUSTERING_TOGGLE).feature_config
        default_conf = conf.get(CLUSTERING_CONFIG_DEFAULT)
        es_storage = ""
        collector_config_name_en = ""

        if collector_config_id:
            # 配置检查
            collector_config = CollectorConfig.objects.filter(collector_config_id=collector_config_id).first()
            collector_config_name_en = collector_config.collector_config_name_en

            collector_clustering_es_storage = conf.get("collector_clustering_es_storage", {})
            if not collector_clustering_es_storage:
                raise CollectorStorageNotExistException(
                    CollectorStorageNotExistException.MESSAGE.format(collector_config_id=collector_config_id)
                )
            es_storage = collector_clustering_es_storage.get("es_storage", "")
            if not es_storage:
                raise CollectorEsStorageNotExistException(
                    CollectorEsStorageNotExistException.MESSAGE.format(collector_config_id=collector_config_id)
                )

            # 校验清洗配置合法性
            all_etl_config = collector_config.get_etl_config()
            self.pre_check_fields(
                fields=all_etl_config["fields"],
                etl_config=collector_config.etl_config,
                clustering_fields=clustering_fields,
            )

        # 非业务类型的项目空间业务 id 为负数，需要通过 Space 的关系拿到其关联的真正的业务ID。然后以这个关联业务ID在计算平台操作, 没有则不允许创建聚类
        related_space_pre_bk_biz_id = params["bk_biz_id"]
        bk_biz_id = self.validate_bk_biz_id(related_space_pre_bk_biz_id)

        # 创建流程
        # 聚类配置优先级：参数传入 -> 数据库默认配置 -> 代码默认配置
        clustering_config = ClusteringConfig.objects.create(
            model_id=conf.get("model_id", ""),  # 模型id 需要判断是否为预测 flow流程
            collector_config_id=collector_config_id,
            collector_config_name_en=collector_config_name_en,
            es_storage=es_storage,
            min_members=params.get("min_members", default_conf.get("min_members", OnlineTaskTrainingArgs.MIN_MEMBERS)),
            max_dist_list=OnlineTaskTrainingArgs.MAX_DIST_LIST,
            predefined_varibles=params.get(
                "predefined_varibles",
                default_conf.get("predefined_varibles", OnlineTaskTrainingArgs.PREDEFINED_VARIBLES),
            ),
            depth=OnlineTaskTrainingArgs.DEPTH,
            delimeter=params.get("delimeter", default_conf.get("delimeter", OnlineTaskTrainingArgs.DELIMETER)),
            max_log_length=params.get(
                "max_log_length", default_conf.get("max_log_length", OnlineTaskTrainingArgs.MAX_LOG_LENGTH)
            ),
            is_case_sensitive=params.get(
                "is_case_sensitive", default_conf.get("is_case_sensitive", OnlineTaskTrainingArgs.IS_CASE_SENSITIVE)
            ),
            clustering_fields=clustering_fields,
            bk_biz_id=bk_biz_id,
            filter_rules=params.get("filter_rules", default_conf.get("filter_rules", [])),
            index_set_id=index_set_id,
            signature_enable=True,
            source_rt_name=log_index_set_data["result_table_id"],
            category_id=log_index_set.category_id,
            related_space_pre_bk_biz_id=related_space_pre_bk_biz_id,  # 查询space关联的真实业务之前的业务id
            new_cls_strategy_enable=params["new_cls_strategy_enable"],
            normal_strategy_enable=params["normal_strategy_enable"],
        )

        access_clustering.delay(index_set_id=index_set_id)
        return model_to_dict(clustering_config, exclude=CLUSTERING_CONFIG_EXCLUDE)

    def update(self, params):
        """
        更新聚类接入
        """
        from apps.log_clustering.handlers.pipline_service.aiops_service_online import (
            UpdateOnlineService,
        )

        params = {
            "index_set_id": self.index_set_id,
            "params": params,
        }

        service = UpdateOnlineService()
        data = service.build_data_context(params)
        pipeline = service.build_pipeline(data, **params)
        service.start_pipeline(pipeline)

        now_time = arrow.now()
        self.data.task_records.append(
            {"operate": OperatorServiceEnum.CREATE, "task_id": pipeline.id, "time": now_time.timestamp}
        )
        self.data.save(update_fields=["task_records"])
        return pipeline.id

    def get_access_status(self, task_id=None):
        """
        接入状态检测
        """
        result = {
            "flow_create": {
                "status": self.AccessStatusCode.SUCCESS,
                "message": _("步骤完成"),
            },
            "flow_run": {
                "status": self.AccessStatusCode.SUCCESS,
                "message": _("步骤完成"),
            },
            "data_check": {
                "status": self.AccessStatusCode.SUCCESS,
                "message": _("步骤完成"),
            },
        }

        clustering_config = ClusteringConfig.get_by_index_set_id(index_set_id=self.index_set_id)

        # 1. 先校验数据写入是否正常
        if clustering_config.clustered_rt:
            # 此处简化流程，只检查模型预测 flow 的输出
            try:
                query_params = {
                    "begin": 0,
                    "size": 1,
                    "original_search": True,
                    "is_desensitize": False,
                }
                search_handler = SearchHandler(self.index_set_id, query_params)
                search_result = search_handler.search()
                if search_result["total"] > 0:
                    return result
                else:
                    result["data_check"].update(status=self.AccessStatusCode.RUNNING, message=_("暂无数据"))
            except Exception as e:
                result["data_check"].update(status=self.AccessStatusCode.RUNNING, message=_("数据获取失败: {}").format(e))
            return result

        # 如若未创建聚类 rt，说明流程还没完成
        result["data_check"].update(status=self.AccessStatusCode.PENDING, message=_("等待执行"))

        # 2. 判断 flow 状态
        if clustering_config.predict_flow_id and clustering_config.log_count_aggregation_flow_id:
            # 此处简化流程，只检查模型预测 flow 的状态即可
            result["flow_run"].update(self.check_dataflow_status(clustering_config.predict_flow_id))

        # 如果 flow 不存在，说明基本流程没走完
        result["flow_run"].update(status=self.AccessStatusCode.PENDING, message=_("等待执行"))

        # 3. 检查数据接入状态
        if not task_id:
            # 如果没有给出任务ID，默认用最新的任务ID
            for record in clustering_config.task_records[::-1]:
                if record["operate"] == OperatorServiceEnum.CREATE:
                    task_id = record["task_id"]
                    break

        # 如果找不到任务结果，说明任务尚未启动
        if not task_id or task_id not in clustering_config.task_details:
            result["flow_create"].update(status=self.AccessStatusCode.PENDING, message=_("等待执行"))
            return result

        # 更新接入任务状态
        result["flow_create"].update(
            task_detail=clustering_config.task_details[task_id],
            status=clustering_config.task_details[task_id][-1]["status"],
            message=clustering_config.task_details[task_id][-1]["message"],
        )

        return result

    def check_dataflow_status(self, flow_id):
        """
        检查 dataflow 状态
        """
        flow_status = ""
        try:
            flow = DataFlowHandler().get_dataflow_info(flow_id=flow_id)
            if flow:
                flow_status = flow["status"]
        except Exception as e:  # pylint:disable=broad-except
            return {"status": self.AccessStatusCode.FAILED, "message": _("dataflow({}) 获取信息失败: {}".format(flow_id, e))}

        flow_status_mapping = {
            "": {"status": self.AccessStatusCode.FAILED, "detail": _("未创建")},
            "no-start": {"status": self.AccessStatusCode.RUNNING, "detail": _("未启动")},
            "running": {"status": self.AccessStatusCode.SUCCESS, "detail": _("状态正常")},
            "starting": {"status": self.AccessStatusCode.FAILED, "detail": _("运行异常")},
            "failure": {"status": self.AccessStatusCode.FAILED, "detail": _("运行失败")},
            "stopping": {"status": self.AccessStatusCode.RUNNING, "detail": _("重启中")},
        }

        return {
            "status": flow_status_mapping[flow_status]["status"],
            "message": _("dataflow({}) {}".format(flow_id, flow_status_mapping[flow_status]["detail"])),
        }

    def preview(self, input_data, min_members, predefined_varibles, delimeter, max_log_length, is_case_sensitive):
        aiops_experiments_debug_result = AiopsModelHandler().aiops_experiments_debug(
            input_data=input_data,
            clustering_field=DEFAULT_CLUSTERING_FIELDS,
            min_members=min_members,
            max_dist_list=OnlineTaskTrainingArgs.MAX_DIST_LIST,
            predefined_varibles=predefined_varibles,
            delimeter=delimeter,
            max_log_length=max_log_length,
            is_case_sensitive=is_case_sensitive,
        )
        return self._deal_preview(aiops_experiments_debug_result)

    @classmethod
    def _deal_preview(cls, aiops_experiments_debug_result):
        result = []
        for predict_output_data in aiops_experiments_debug_result["predict_output_data"]:
            pattern = cls._deal_pattern(json.loads(predict_output_data["pattern"]))
            token_with_regex = cls._deal_token_with_regex(json.loads(predict_output_data["token_with_regex"]))
            result.append({"patterns": pattern, "token_with_regex": token_with_regex})
        return result

    @classmethod
    def _deal_pattern(cls, pattern_result: dict):
        result = []
        for sensitivity, pattern_result in pattern_result.items():
            sensitive_pattern_list = []
            for sensitive_pattern in pattern_result:
                if isinstance(sensitive_pattern, dict):
                    sensitive_pattern_list.append("#{}#".format(sensitive_pattern["name"]))
                    continue
                sensitive_pattern_list.append(sensitive_pattern)
            result.append({"sensitivity": sensitivity, "pattern": " ".join(sensitive_pattern_list)})
        return result

    @classmethod
    def _deal_token_with_regex(cls, token_with_regex_result: list):
        result = {}
        for token_with_regex in token_with_regex_result:
            if isinstance(token_with_regex, dict):
                result[token_with_regex["name"]] = token_with_regex["regex"]
        return result

    def collector_config_reset(self, clustering_config: ClusteringConfig):
        # todo need reset collector_config
        # collector_config = CollectorConfig.objects.get(collector_config_id=clustering_config.collector_config_id)
        pass

    def change_data_stream(self, topic: str, partition: int = 1):
        """
        change_data_stream
        :param topic:
        :param partition:
        :return:
        """
        collector_handler = CollectorHandler(self.data.collector_config_id)
        if not self.data.log_bk_data_id:
            self.data.log_bk_data_id = CollectorScenario.change_data_stream(
                collector_handler.data, mq_topic=topic, mq_partition=partition
            )
            self.data.save()
        # 设置request线程变量
        activate_request(generate_request())

        collector_detail = collector_handler.retrieve(use_request=False)

        # need drop built in field
        collector_detail["fields"] = map_if(collector_detail["fields"], if_func=lambda field: not field["is_built_in"])
        from apps.log_databus.handlers.etl import EtlHandler

        etl_handler = EtlHandler.get_instance(self.data.collector_config_id)
        etl_handler.update_or_create(
            collector_detail["etl_config"],
            collector_detail["table_id"],
            collector_detail["storage_cluster_id"],
            collector_detail["retention"],
            collector_detail.get("allocation_min_days", 0),
            collector_detail["storage_replies"],
            etl_params=collector_detail["etl_params"],
            fields=collector_detail["fields"],
        )

    @staticmethod
    def check_clustering_config_update(
        clustering_config,
        filter_rules,
        min_members,
        predefined_varibles,
        delimeter,
        max_log_length,
        is_case_sensitive,
        clustering_fields,
        signature_enable,
    ):
        """
        判断是否需要进行对应更新操作
        """
        # 此时不需要做任何更新动作
        if not signature_enable:
            return False, False, False, False
        # 此时需要创建service 而不是更新service
        if not clustering_config.signature_enable:
            return False, False, False, True
        change_filter_rules = clustering_config.filter_rules != filter_rules
        change_model_config = model_to_dict(
            clustering_config,
            fields=[
                "min_members",
                "predefined_varibles",
                "delimeter",
                "max_log_length",
                "is_case_sensitive",
            ],
        ) != {
            "min_members": min_members,
            "predefined_varibles": predefined_varibles,
            "delimeter": delimeter,
            "max_log_length": max_log_length,
            "is_case_sensitive": is_case_sensitive,
        }
        change_clustering_fields = clustering_config.clustering_fields != clustering_fields

        return change_filter_rules, change_model_config, change_clustering_fields, False

    @classmethod
    def pre_check_fields(cls, fields, etl_config, clustering_fields):
        """
        判断字段是否符合要求
        """
        for field in fields:
            field_name = field.get("field_name")
            alias_name = field.get("alias_name") or field.get("field_name")
            # 正则需要符合计算平台正则要求
            if etl_config == EtlConfig.BK_LOG_REGEXP and not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9]*", field_name):
                logger.error(_("正则表达式字段名: {}不符合计算平台标准[a-zA-Z][a-zA-Z0-9]*").format(field_name))
                raise BkdataRegexException(BkdataRegexException.MESSAGE.format(field_name=field_name))
            # 存在聚类字段则允许跳出循环
            if alias_name == clustering_fields:
                break
        else:
            if clustering_fields == DEFAULT_CLUSTERING_FIELDS:
                return True
            logger.error(_("不允许删除参与日志聚类字段: {}").format(clustering_fields))
            raise ValueError(BkdataFieldsException(BkdataFieldsException.MESSAGE.format(field=clustering_fields)))

        return True

    @staticmethod
    def validate_bk_biz_id(bk_biz_id: int) -> int:
        """
        注入业务id校验
        :return:
        """

        # 业务id为正数，表示空间类型是bkcc，可以调用cmdb相关接口
        bk_biz_id = int(bk_biz_id)
        if bk_biz_id > 0:
            return bk_biz_id
        # 业务id为负数，需要获取空间关联的真实业务id
        space_uid = bk_biz_id_to_space_uid(bk_biz_id)
        space = SpaceApi.get_related_space(space_uid, SpaceTypeEnum.BKCC.value)
        if space:
            return space.bk_biz_id
        # 无业务关联的空间，不允许创建日志聚类 当前抛出异常
        raise NoRelatedResourceError(_(f"当前业务:{bk_biz_id}通过Space关系查询不到关联的真实业务ID，不允许创建日志聚类").format(bk_biz_id=bk_biz_id))
