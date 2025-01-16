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
import copy
import json

from django.utils.translation import gettext_lazy as _

import settings
from apps.api import (
    BkDataAccessApi,
    BkDataAuthApi,
    BkDataDatabusApi,
    BkDataMetaApi,
    BkDataResourceCenterApi,
)
from apps.log_clustering.handlers.aiops.base import BaseAiopsHandler
from apps.log_clustering.models import ClusteringConfig
from apps.log_databus.constants import BKDATA_ES_TYPE_MAP, PARSE_FAILURE_FIELD
from apps.log_databus.handlers.collector_scenario import CollectorScenario
from apps.log_databus.handlers.etl_storage import EtlStorage
from apps.log_databus.models import CollectorConfig
from apps.utils.log import logger
from bkm_space.api import SpaceApi
from bkm_space.define import SpaceTypeEnum
from bkm_space.errors import NoRelatedResourceError
from bkm_space.utils import bk_biz_id_to_space_uid


class DataAccessHandler(BaseAiopsHandler):
    def __init__(self, raw_data_id: int = None):
        super(DataAccessHandler, self).__init__()
        self.raw_data_id = raw_data_id

    def get_deploy_plan(self):
        return BkDataDatabusApi.get_config_db_list(params={"raw_data_id": self.raw_data_id})

    @classmethod
    def get_fields(cls, result_table_id: str):
        return BkDataMetaApi.result_tables.fields({"result_table_id": result_table_id})

    def create_bkdata_access(self, collector_config_id):
        collector_config = CollectorConfig.objects.get(collector_config_id=collector_config_id)
        clustering_config = ClusteringConfig.objects.get(collector_config_id=collector_config_id)

        if clustering_config.bkdata_data_id:
            logger.info("bkdata access has exists")
            return

        kafka_config = collector_config.get_result_table_kafka_config()

        # 计算平台要求，raw_data_name不能超过50个字符
        raw_data_name = "{}_{}".format("bk_log", collector_config.collector_config_name_en)[:50]
        params = {
            "bk_username": self.conf.get("bk_username"),
            "data_scenario": "queue",
            "bk_biz_id": self.conf.get("bk_biz_id"),
            "description": "",
            "access_raw_data": {
                "raw_data_name": raw_data_name,
                "maintainer": self.conf.get("bk_username"),
                "raw_data_alias": collector_config.collector_config_name,
                "data_source": "kafka",
                "data_encoding": "UTF-8",
                "sensitivity": "private",
                "description": _("接入配置 ({description})").format(description=collector_config.description),
                "tags": [],
                "data_source_tags": ["src_kafka"],
            },
            "access_conf_info": {
                "collection_model": {"collection_type": "incr", "start_at": 1, "period": "-1"},
                "resource": {
                    "type": "kafka",
                    "scope": [
                        {
                            "master": f"{self._get_kafka_broker_url(kafka_config['cluster_config']['domain_name'])}"
                            f":{kafka_config['cluster_config']['port']}",
                            "group": f"{self.conf.get('kafka_consumer_group_prefix', 'bkmonitorv3_transfer')}"
                            f"{kafka_config['storage_config']['topic']}",
                            "topic": kafka_config["storage_config"]["topic"],
                            "tasks": kafka_config["storage_config"]["partition"],
                            "use_sasl": kafka_config["cluster_config"]["is_ssl_verify"],
                            "security_protocol": "SASL_PLAINTEXT",
                            "sasl_mechanism": "SCRAM-SHA-512",
                            "user": kafka_config["auth_info"]["password"],
                            "password": kafka_config["auth_info"]["username"],
                            "auto_offset_reset": "latest",
                        }
                    ],
                },
            },
        }
        result = BkDataAccessApi.deploy_plan_post(params)
        logger.info(f"access to bkdata, result: {result}")
        clustering_config.bkdata_data_id = result["raw_data_id"]
        clustering_config.save()

    def _get_kafka_broker_url(self, broker):
        if "consul" in broker and settings.DEFAULT_KAFKA_HOST:
            return settings.DEFAULT_KAFKA_HOST
        return broker

    def validate_bk_biz_id(self, bk_biz_id: int) -> int:
        """
        采集项业务id校验
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
        # 无业务关联的空间，不允许创建清洗任务
        raise NoRelatedResourceError(_(f"当前业务:{bk_biz_id}通过Space关系查询不到关联的真实业务ID，不允许创建清洗任务").format(bk_biz_id=bk_biz_id))

    def sync_bkdata_etl(self, collector_config_id):
        clustering_config = ClusteringConfig.objects.get(collector_config_id=collector_config_id)
        bk_data_id = clustering_config.bkdata_data_id
        result = self.create_or_update_bkdata_etl(
            collector_config_id, bk_data_id, clustering_config.bkdata_etl_processing_id
        )
        if not clustering_config.bkdata_etl_processing_id:
            clustering_config.bkdata_etl_processing_id = result["processing_id"]
            clustering_config.bkdata_etl_result_table_id = result["result_table_id"]
            clustering_config.save()
            # 新建rt后需要启动清洗任务，并且从尾部开始消费
            self.start_bkdata_clean(result["result_table_id"], from_tail=True)
        else:
            # 更新rt之后需要重启清洗任务
            self.stop_bkdata_clean(clustering_config.bkdata_etl_result_table_id)
            self.start_bkdata_clean(clustering_config.bkdata_etl_result_table_id)

    def create_or_update_bkdata_etl(self, collector_config_id, bk_data_id=None, bkdata_etl_processing_id=None):
        collector_config = CollectorConfig.objects.get(collector_config_id=collector_config_id)

        bk_data_id = bk_data_id or collector_config.bk_data_id

        etl_config = collector_config.get_etl_config()

        fields = etl_config["fields"]
        etl_params = etl_config["etl_params"]

        etl_storage = EtlStorage.get_instance(etl_config=collector_config.etl_config)

        # 把path的字段信息从fields中分离
        fields, path_fields = etl_storage.separate_fields_config(fields)

        # 获取清洗配置
        collector_scenario = CollectorScenario.get_instance(
            collector_scenario_id=collector_config.collector_scenario_id
        )
        built_in_config = collector_scenario.get_built_in_config(etl_config=collector_config.etl_config)
        fields_config = etl_storage.get_result_table_config(fields, etl_params, copy.deepcopy(built_in_config)).get(
            "field_list", []
        )

        bkdata_json_config = etl_storage.get_bkdata_etl_config(fields, etl_params, built_in_config)

        # 根据路径正则,加入路径清洗配置
        separator_configs = etl_params.get("separator_configs", [])
        if separator_configs:
            etl_path_regexp = separator_configs[0].get("separator_regexp", "")
            path_fields_config = etl_storage.get_path_field_configs(etl_path_regexp, fields_config)
            fields_config.extend(path_fields_config)
            etl_storage.add_path_configs(path_fields, etl_path_regexp, bkdata_json_config)

        # 固定有time字段
        fields_config.append({"alias_name": "time", "field_name": "time", "option": {"es_type": "long"}})

        # 结果表统一添加 bklog 前缀，避免同名冲突
        result_table_name = f"bklog_{collector_config.collector_config_name_en}"

        # 当用户使用了自定义字段作为时间字段，则会产生同名字段，需要去重
        fields_names = set()
        dedupe_fields_config = []
        for field in fields_config:
            # 剔除解析失败字段
            if field.get("field_name") == PARSE_FAILURE_FIELD:
                continue
            field_name = field.get("alias_name") if field.get("alias_name") else field.get("field_name")
            if field_name not in fields_names:
                dedupe_fields_config.append(field)
                fields_names.add(field_name)

        if bk_data_id == collector_config.bk_data_id:
            bk_biz_id = self.validate_bk_biz_id(collector_config.bk_biz_id)
        else:
            # 旧版聚类链路，清洗走公共业务
            bk_biz_id = self.conf.get("bk_biz_id")

        params = {
            "raw_data_id": bk_data_id,
            "result_table_name": result_table_name[-50:],
            "result_table_name_alias": collector_config.collector_config_name_en,
            "clean_config_name": collector_config.collector_config_name,
            "description": collector_config.description or collector_config.collector_config_name,
            "bk_biz_id": bk_biz_id,
            "fields": [
                {
                    "field_name": field.get("alias_name") if field.get("alias_name") else field.get("field_name"),
                    "field_type": BKDATA_ES_TYPE_MAP.get(field.get("option").get("es_type"), "string"),
                    "field_alias": field.get("description") if field.get("description") else field.get("field_name"),
                    "is_dimension": field.get("tag", "dimension") == "dimension",
                    "field_index": index,
                }
                for index, field in enumerate(dedupe_fields_config, 1)
            ],
            "json_config": json.dumps(bkdata_json_config),
            "bk_username": self.conf.get("bk_username"),
            "operator": self.conf.get("bk_username"),
            "no_request": True,
        }

        if bkdata_etl_processing_id:
            params.update({"processing_id": bkdata_etl_processing_id})
            result = BkDataDatabusApi.databus_cleans_put(params, request_cookies=False)
            return result

        return BkDataDatabusApi.databus_cleans_post(params)

    def stop_bkdata_clean(self, bkdata_result_table_id):
        return BkDataDatabusApi.delete_tasks(
            params={
                "result_table_id": bkdata_result_table_id,
                "bk_username": self.conf.get("bk_username"),
                "operator": self.conf.get("bk_username"),
                "no_request": True,
            }
        )

    def start_bkdata_clean(self, bkdata_result_table_id, from_tail=False):
        params = {
            "result_table_id": bkdata_result_table_id,
            "storages": ["kafka"],
            "bk_username": self.conf.get("bk_username"),
            "operator": self.conf.get("bk_username"),
            "no_request": True,
        }
        if from_tail:
            params["consume_position"] = "tail"
        return BkDataDatabusApi.post_tasks(params=params)

    def add_cluster_group(self, result_table_id):
        storage_config = BkDataMetaApi.result_tables.storages({"result_table_id": result_table_id})
        cluster_resource_groups = BkDataResourceCenterApi.cluster_query_digest(
            params={
                "resource_type": "storage",
                "service_type": "es",
                "cluster_name": storage_config["es"]["storage_cluster"]["cluster_name"],
            }
        )
        cluster_resource_group, *_ = cluster_resource_groups
        BkDataAuthApi.add_cluster_group(
            params={
                "project_id": self.conf.get("project_id"),
                "cluster_group_id": cluster_resource_group["resource_group_id"],
            }
        )

        return storage_config["es"]["storage_cluster"]["cluster_name"]
