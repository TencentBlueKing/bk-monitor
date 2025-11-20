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

import copy
import json
from typing import Any

from django.conf import settings
from django.utils.module_loading import import_string
from django.utils.translation import gettext as _

from apps.api import NodeApi, TransferApi
from apps.exceptions import ApiResultError
from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.feature_toggle.plugins.constants import MINI_CLUSTERING_CONFIG
from apps.log_clustering.constants import PatternEnum
from apps.log_clustering.models import ClusteringConfig
from apps.log_databus.constants import EtlConfig
from apps.log_databus.exceptions import (
    BaseCollectorConfigException,
    DataLinkConfigPartitionException,
)
from apps.log_databus.handlers.collector_scenario.utils import build_es_option_type
from apps.log_databus.handlers.storage import StorageHandler
from apps.log_databus.models import CollectorConfig, DataLinkConfig
from apps.log_search.constants import CollectorScenarioEnum
from apps.utils.function import ignored
from apps.utils.log import logger


class CollectorScenario:
    """
    采集场景：行日志、段日志、window event, Redis慢日志, syslog日志
    1. 根据采集场景加载具体实现的类
    2.
    """

    @classmethod
    def get_instance(cls, collector_scenario_id=None):
        mapping = {
            CollectorScenarioEnum.ROW.value: "RowCollectorScenario",
            CollectorScenarioEnum.SECTION.value: "SectionCollectorScenario",
            CollectorScenarioEnum.WIN_EVENT.value: "WinEventLogScenario",
            CollectorScenarioEnum.CUSTOM.value: "CustomCollectorScenario",
            CollectorScenarioEnum.REDIS_SLOWLOG.value: "RedisSlowLogCollectorScenario",
            CollectorScenarioEnum.SYSLOG.value: "SysLogScenario",
            CollectorScenarioEnum.KAFKA.value: "KafkaScenario",
        }
        try:
            collector_scenario = import_string(
                f"apps.log_databus.handlers.collector_scenario.{collector_scenario_id}.{mapping.get(collector_scenario_id)}"
            )
            return collector_scenario()
        except ImportError as error:
            raise NotImplementedError(
                _("{collector_scenario_id}场景对应的采集器功能暂未实现, error: {error}").format(
                    collector_scenario_id=collector_scenario_id, error=error
                )
            )

    def get_subscription_steps(self, data_id, params, collector_config_id=None, data_link_id=None):
        """
        根据采集场景返回节点管理插件下发步骤
        1. 获取配置模板信息
        2. 如果模板未发布，则配置并发布模板
        """
        raise NotImplementedError()

    @classmethod
    def parse_steps(cls, steps):
        """
        解析订阅配置中的步骤
        """
        raise NotImplementedError()

    @classmethod
    def get_built_in_config(cls, es_version="5.X", etl_config=EtlConfig.BK_LOG_TEXT):
        """
        获取采集器内置配置
        """
        raise NotImplementedError()

    @staticmethod
    def get_unique_field_list(field_list: list, target_fields: list, sort_fields: list):
        """
        获取唯一字段列表
        :param field_list: 字段列表
        :param target_fields: 定位字段
        :param sort_fields: 排序字段
        """
        if target_fields:
            field_list.extend(target_fields)
        if sort_fields:
            field_list.extend(sort_fields)
        return sorted(set(field_list))

    @staticmethod
    def delete_data_id(bk_data_id, data_name):
        """
        删除data_id
        """
        params = {"data_id": bk_data_id, "data_name": data_name, "option": {"is_log_data": True}, "is_enable": False}
        TransferApi.modify_data_id(params)
        logger.info(f"[delete_data_id] bk_data_id=>{bk_data_id}, params=>{params}")
        return True

    @staticmethod
    def update_or_create_data_id(
        bk_data_id=None,
        data_link_id=None,
        data_name=None,
        description=None,
        encoding=None,
        option: dict = None,
        mq_config: dict = None,
        bk_biz_id=None,
    ):
        """
        创建或更新数据源
        :param bk_data_id: 数据源ID
        :param data_link_id: 数据链路ID
        :param data_name: 数据源名称
        :param description: 描述
        :param encoding: 字符集编码
        :param mq_config: mq配置
        :param bk_biz_id: 业务id
        :param option: 附加参数 {"topic": "xxxx", "partition": 1}
        :return: bk_data_id
        """
        default_option = {
            "encoding": "UTF-8" if encoding is None else encoding,
            "is_log_data": True,
            "allow_metrics_missing": True,
        }

        with ignored(ApiResultError):
            bk_data_id = TransferApi.get_data_id({"data_name": data_name, "no_request": True})["bk_data_id"]

        if not bk_data_id:
            # 创建数据源，创建时一定是BK_LOG_TEXT这种直接入库的方式，后面进行字段提取时再根据情况变更清洗方式
            if not data_name:
                raise BaseCollectorConfigException(_("创建采集项时名称不能为空"))
            if not mq_config:
                mq_config = {}

            params = {
                "data_name": data_name,
                "etl_config": "bk_flat_batch",
                "data_description": description,
                "source_label": "bk_monitor",
                "type_label": "log",
                "mq_config": mq_config,
                "option": default_option,
                "bk_biz_id": bk_biz_id,
            }
            if data_link_id:
                data_link = DataLinkConfig.objects.filter(data_link_id=data_link_id).first()
                if not data_link:
                    raise DataLinkConfigPartitionException
                else:
                    params.update(
                        {
                            "transfer_cluster_id": data_link.transfer_cluster_id,
                            "mq_cluster": data_link.kafka_cluster_id,
                        }
                    )

            bk_data_id = TransferApi.create_data_id(params)["bk_data_id"]
            logger.info(f"[create_data_id] bk_data_id=>{bk_data_id}, params=>{params}")
        else:
            params = {"data_id": bk_data_id, "option": default_option}

            if data_name:
                params["data_name"] = data_name

            if description:
                params["data_description"] = description

            if option:
                params["option"] = dict(params["option"], **option)

            # 聚类小型化链路配置更新
            clustering_config = ClusteringConfig.objects.filter(log_bk_data_id=bk_data_id).first()
            if clustering_config and clustering_config.use_mini_link and clustering_config.signature_enable:
                params["option"].update(
                    {
                        "is_log_cluster": True,
                        "log_cluster_config": CollectorScenario.gen_clustering_datasource_options(clustering_config),
                    }
                )
                params["etl_config"] = "bk_flat_batch_cluster"
            else:
                params["option"].update({"is_log_cluster": False})
                params["etl_config"] = "bk_flat_batch"

            # 更新数据源
            TransferApi.modify_data_id(params)
            logger.info(f"[update_data_id] bk_data_id=>{bk_data_id}, params=>{params}")
        return bk_data_id

    @staticmethod
    def gen_clustering_datasource_options(clustering_config: ClusteringConfig) -> dict:
        """
        生成聚类数据源配置
        :param clustering_config: 聚类配置
        :return: dict
        """
        feature_config = {}
        if feature_obj := FeatureToggleObject.toggle(MINI_CLUSTERING_CONFIG):
            feature_config = feature_obj.feature_config

        log_filter = []
        for rule in clustering_config.filter_rules:
            value = rule["value"] if isinstance(rule["value"], list) else [rule["value"]]
            if rule["op"] == "=":
                op = "eq"
            elif rule["op"] == "!=":
                op = "neq"
            elif rule["op"] == "contains":
                op = "include"
            elif rule["op"] == "not contains":
                op = "exclude"
            else:
                continue
            log_filter.append(
                {
                    "key": rule["fields_name"],
                    "value": value,
                    "method": op,
                    "condition": rule.get("logic_operator", "and"),
                }
            )

        options = {
            "log_cluster": {
                "address": feature_config.get("predict_cluster_address", {}).get(
                    clustering_config.predict_cluster
                ),  # TODO: 需要根据集群名称转换
                # TODO: 以下配置需要把它放到每个 ClusteringConfig 中作为动态配置
                "timeout": feature_config.get("timeout", "1m"),
                "batch_size": feature_config.get("batch_size", 2000),
                "poll_interval": feature_config.get("poll_interval", "1000-5000"),
                "retry": feature_config.get("retry", 1),
                "retry_interval": feature_config.get("retry_interval", "200ms"),
                "clustering_field": clustering_config.clustering_fields,
            },
            "log_filter": log_filter,
            "backend_fields": {
                "raw_es": {
                    "drop_dimensions": ["pattern", "is_new"],
                },
                "pattern_es": {
                    "keep_dimensions": ["pattern", "signature", "time", "dtEventTimeStamp"],
                    "keep_metrics": [clustering_config.clustering_fields],
                    "group_keys": ["signature"],
                },
            },
            "predict_cluster": clustering_config.predict_cluster,
            "predict_args": {
                "min_members": clustering_config.min_members,
                "max_dist_list": clustering_config.max_dist_list,
                "st_list": clustering_config.st_list,
                "predefined_varibles": clustering_config.predefined_varibles,
                "delimeter": clustering_config.delimeter,
                "max_log_length": clustering_config.max_log_length,
                "is_case_sensitive": clustering_config.is_case_sensitive,
                "depth": clustering_config.depth,
                "max_child": clustering_config.max_child,
            },
        }
        return options

    def update_or_create_subscription(self, collector_config: CollectorConfig, params: dict):
        """
        创建或更新订阅事件
        :param collector_config: 采集项配置
        :param params: 配置参数，用于获取订阅步骤，不同的场景略有不同
        :return: subscription_id 订阅ID
        """
        if isinstance(collector_config.collector_config_overlay, dict):
            params["collector_config_overlay"] = collector_config.collector_config_overlay
        steps = self.get_subscription_steps(
            collector_config.bk_data_id, params, collector_config.collector_config_id, collector_config.data_link_id
        )

        subscription_params = {
            "scope": {
                "bk_biz_id": collector_config.bk_biz_id,
                "node_type": collector_config.target_node_type,
                "object_type": collector_config.target_object_type,
                "nodes": collector_config.target_nodes,
            },
            "steps": steps,
        }
        if not collector_config.subscription_id:
            # 创建订阅配置
            collector_config.subscription_id = NodeApi.create_subscription(subscription_params)["subscription_id"]
        else:
            # 修改订阅配置
            subscription_params["subscription_id"] = collector_config.subscription_id
            NodeApi.update_subscription_info(subscription_params)
        return collector_config.subscription_id

    def _deal_text_public_params(self, local_params, params, collector_config_id=None):
        need_define_params = [
            "clean_inactive",
            "harvester_limit",
            "scan_frequency",
            "close_inactive",
        ]
        local_params.update(
            {
                "paths": params.get("paths", []),
                "exclude_files": params.get("exclude_files", []),
                "encoding": params["encoding"],
                "tail_files": params["tail_files"],
                "ignore_older": params["ignore_older"],
                "max_bytes": params["max_bytes"],
                "package_count": settings.COLLECTOR_ROW_PACKAGE_COUNT,
                "delimiter": params.get("conditions", {}).get("separator") or "",
            }
        )
        local_params.update({param: params.get(param) for param in need_define_params if params.get(param) is not None})

        if params.get("collector_config_overlay"):
            local_params.update(params["collector_config_overlay"])
        local_params = self._add_labels(local_params, params, collector_config_id)
        local_params = self._add_ext_meta(local_params, params)
        return local_params

    @staticmethod
    def get_edge_transport_output_params(data_link_id: int = None):
        if not data_link_id:
            return
        data_link = DataLinkConfig.objects.filter(data_link_id=data_link_id).first()

        if not data_link:
            # 如果找不到链路配置，则不处理
            return

        if not data_link.is_edge_transport:
            # 如果不是边缘存查链路，则不处理
            return

        kafka_cluster_info = StorageHandler(data_link.kafka_cluster_id).get_cluster_info_by_id()
        cluster_config = kafka_cluster_info["cluster_config"]

        host = cluster_config.get("extranet_domain_name") or cluster_config["domain_name"]
        port = cluster_config.get("extranet_port") or cluster_config["port"]

        kafka_output_params = {
            "hosts": [f"{host}:{port}"],  # noqa: IP_CHECK_ERROR_CODE
            "topic": "0bkmonitor_%{[dataid]}0",
            "version": cluster_config.get("version") or "0.10.2.1",  # noqa: IP_CHECK_ERROR_CODE
        }

        if kafka_cluster_info["auth_info"]["username"]:
            kafka_output_params.update(
                {
                    "username": kafka_cluster_info["auth_info"]["username"],
                    "password": kafka_cluster_info["auth_info"]["password"],
                }
            )

        if cluster_config["is_ssl_verify"]:
            kafka_output_params.update(
                {
                    "ssl.enabled": True,
                    "ssl.verification_mode": cluster_config.get("ssl_verification_mode", "none"),
                }
            )

            if cluster_config.get("ssl_certificate_authorities"):
                kafka_output_params["ssl.certificate_authorities"] = cluster_config["ssl_certificate_authorities"]

            if cluster_config.get("ssl_certificate"):
                kafka_output_params["ssl.certificate"] = cluster_config["ssl_certificate"]

            if cluster_config.get("ssl_certificate_key"):
                kafka_output_params["ssl.key"] = cluster_config["ssl_certificate_key"]

        custom_params = data_link.deploy_options.get("kafka")
        if custom_params:
            # 如果DB中有特殊配置，则直接覆盖
            kafka_output_params.update(custom_params)
        return kafka_output_params

    @staticmethod
    def _deal_edge_transport_params(local_params, data_link_id: int = None):
        kafka_output_params = CollectorScenario.get_edge_transport_output_params(data_link_id)
        if not kafka_output_params:
            return local_params

        # outputs format
        # {"type": "output.kafka", "params": {"hosts": ["127.0.0.1:9092"], "topic": "0bkmonitor_%{[dataid]}0"}}

        local_params["output"] = {
            "type": "output.kafka",
            "params": json.dumps(kafka_output_params),
        }
        return local_params

    @staticmethod
    def _add_labels(local_params: dict[str, Any], params: dict[str, Any], collector_config_id: int = None):
        """
        补充采集器模板里的labels, 采集器里的labels格式为: List[Dict[str, Dict[str, Any]]]
        params里的取值是: extra_template_labels, 格式为: List[Dict[str, Dict[str, Any]]]
        即 接口参数 extra_template_labels -> 采集器 labels
        此处针对collector_config_id进行了特殊处理
        因为在创建采集项时，生成的collector_config_id未知，所以需要在内部流程透传
        """
        extra_template_labels: list[dict[str, dict[str, Any]]] = params.get("extra_template_labels", [])
        if not extra_template_labels:
            return local_params
        local_params["labels"] = {}
        for extra_template_label in extra_template_labels:
            if extra_template_label["key"] == "$body" and collector_config_id:
                extra_template_label["value"].update({"bk_collect_config_id": collector_config_id})
            local_params["labels"][extra_template_label["key"]] = extra_template_label["value"]
        return local_params

    @staticmethod
    def _add_ext_meta(local_params: dict[str, Any], params: dict[str, Any]):
        """
        补充采集器里的元数据ext_meta
        params里的取值是extra_labels(容器日志历史遗留字段), 格式为: List[Dict[str, str]]
        即 接口参数 extra_labels -> 采集器 ext_meta
        采集器内的ext_meta的格式为: Dict[str, str], 所以传给采集器的ext_meta需要做一次转换
        """
        ext_meta = params.get("extra_labels", [])
        if not ext_meta:
            return local_params
        local_params["ext_meta"] = {em["key"]: em["value"] for em in ext_meta}
        return local_params

    @staticmethod
    def _handle_collector_config_overlay(local_params: dict[str, Any], params: dict[str, Any]):
        """
        处理自定义采集器配置字段
        """
        if params.get("collector_config_overlay"):
            local_params.update(params["collector_config_overlay"])

        return local_params

    @staticmethod
    def log_clustering_fields(es_version: str = "5.x"):
        return [
            {
                "field_name": f"__dist_{pattern_level}",
                "field_type": "string",
                "tag": "dimension",
                "alias_name": f"dist_{pattern_level}",
                "description": _("聚类数字签名{pattern_level}").format(pattern_level=pattern_level),
                "option": build_es_option_type("keyword", es_version),
                "is_built_in": False,
                "is_time": False,
                "is_analyzed": False,
                "is_dimension": False,
                "is_delete": False,
            }
            for pattern_level in PatternEnum.get_dict_choices().keys()
        ]

    @staticmethod
    def fields_insert_field_index(source_fields, dst_fields) -> list:
        """
        给dst_field添加field_index并且组成新的field_index返回回去
        @param source_fields list 包含field_index的原始数据
        @param dst_fields list 不包含field_index的目标数据
        """
        field_index = 0
        for field in source_fields:
            source_field_index = field.get("field_index")
            if source_field_index and source_field_index > field_index:
                field_index = source_field_index

        result_fields = copy.deepcopy(source_fields)
        for field in dst_fields:
            field_index += 1
            field["field_index"] = field_index
            result_fields.append(field)

        return result_fields
