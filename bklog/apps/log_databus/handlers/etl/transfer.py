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

from django.conf import settings

from apps.constants import UserOperationActionEnum, UserOperationTypeEnum
from apps.decorators import user_operation_record
from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.log_clustering.handlers.clustering_config import ClusteringConfigHandler
from apps.log_clustering.tasks.flow import update_clustering_clean
from apps.log_databus.exceptions import CollectorActiveException
from apps.log_databus.handlers.collector import CollectorHandler
from apps.log_databus.handlers.collector_scenario import CollectorScenario
from apps.log_databus.handlers.collector_scenario.custom_define import get_custom
from apps.log_databus.handlers.etl import EtlHandler
from apps.log_databus.handlers.etl_storage import EtlStorage
from apps.log_databus.handlers.storage import StorageHandler
from apps.log_search.constants import CollectorScenarioEnum
from apps.log_search.models import LogIndexSet
from apps.utils.codecs import unicode_str_encode
from apps.utils.local import get_request_username


class TransferEtlHandler(EtlHandler):
    def update_or_create(
        self,
        etl_config,
        table_id,
        storage_cluster_id,
        retention,
        allocation_min_days,
        storage_replies,
        es_shards=settings.ES_SHARDS,
        view_roles=None,
        etl_params=None,
        fields=None,
        sort_fields=None,
        target_fields=None,
        username="",
        alias_settings=None,
        *args,
        **kwargs,
    ):
        etl_params = etl_params or {}
        # 停止状态下不能编辑
        if self.data and not self.data.is_active:
            raise CollectorActiveException()

        # 存储集群信息
        cluster_info = StorageHandler(storage_cluster_id).get_cluster_info_by_id()
        self.check_es_storage_capacity(cluster_info, storage_cluster_id)
        is_add = False if self.data.table_id else True

        if FeatureToggleObject.switch("etl_record_parse_failure", self.data.bk_biz_id):
            # 增加清洗结果字段记录
            etl_params["record_parse_failure"] = True

        if self.data.is_clustering:
            handler = ClusteringConfigHandler(collector_config_id=self.data.collector_config_id)
            update_clustering_clean.delay(
                collector_config_id=self.data.collector_config_id,
                fields=fields,
                etl_config=etl_config,
                etl_params=etl_params,
            )

            if handler.data.bkdata_data_id and handler.data.bkdata_data_id != self.data.bk_data_id:
                # 旧版聚类链路，由于入库链路不是独立的，需要更新 transfer 的结果表配置；新版则无需更新
                etl_params["etl_flat"] = True
                etl_params["separator_node_action"] = ""
                log_clustering_fields = CollectorScenario.log_clustering_fields(
                    cluster_info["cluster_config"]["version"]
                )
                fields = CollectorScenario.fields_insert_field_index(
                    source_fields=fields, dst_fields=log_clustering_fields
                )

                # 涉及到字段映射的，需要把前缀去掉，比如 bk_separator_object.abc => abc
                for field in fields:
                    if "option" in field and "real_path" in field["option"]:
                        field["option"]["real_path"] = field["option"]["real_path"].replace(
                            f"{EtlStorage.separator_node_name}.", ""
                        )

        # 暂时去掉这个效验逻辑，底下的逻辑都是幂等的，可以继续也必须继续往下走
        # # 判断是否已存在同result_table_id
        # if is_add and CollectorConfig(table_id=table_id).get_result_table_by_id():
        #     logger.error(f"result_table_id {table_id} already exists")
        #     raise CollectorResultTableIDDuplicateException(
        #         CollectorResultTableIDDuplicateException.MESSAGE.format(result_table_id=table_id)
        #     )

        # 1. meta-创建/修改结果表
        etl_storage = EtlStorage.get_instance(etl_config=etl_config)
        etl_storage.update_or_create_result_table(
            self.data,
            table_id=table_id,
            storage_cluster_id=storage_cluster_id,
            retention=retention,
            allocation_min_days=allocation_min_days,
            storage_replies=storage_replies,
            fields=fields,
            etl_params=etl_params,
            es_version=cluster_info["cluster_config"]["version"],
            hot_warm_config=cluster_info["cluster_config"].get("custom_option", {}).get("hot_warm_config"),
            es_shards=es_shards,
            alias_settings=alias_settings,
        )

        if not view_roles:
            view_roles = []

        # 2. 创建索引集
        index_set = self._update_or_create_index_set(
            etl_config,
            storage_cluster_id,
            view_roles,
            username=username,
            sort_fields=sort_fields,
            target_fields=target_fields,
        )

        # 3. 更新完结果表之后, 如果存在fields的snapshot, 清理一次
        LogIndexSet.objects.filter(index_set_id=index_set["index_set_id"]).update(fields_snapshot={})

        # add user_operation_record
        operation_record = {
            "username": username or get_request_username(),
            "biz_id": self.data.bk_biz_id,
            "record_type": UserOperationTypeEnum.ETL,
            "record_object_id": self.data.collector_config_id,
            "action": UserOperationActionEnum.CREATE if is_add else UserOperationActionEnum.UPDATE,
            "params": {
                "etl_config": etl_config,
                "table_id": table_id,
                "storage_cluster_id": storage_cluster_id,
                "retention": retention,
                "allocation_min_days": allocation_min_days,
                "view_roles": view_roles,
                "etl_params": etl_params,
                "fields": fields,
                "es_shards": es_shards,
            },
        }
        user_operation_record.delay(operation_record)
        if self.data.collector_scenario_id == CollectorScenarioEnum.CUSTOM.value:
            custom_config = get_custom(self.data.custom_type)
            custom_config.after_etl_hook(self.data)

        # create_clean_stash 直接集成到该接口，避免修改结果表失败导致 stash 数据不一致
        # 在前面序列化器校验时，对字符做了转义，这里需要转回来
        origin_etl_params = copy.deepcopy(etl_params)
        if origin_etl_params.get("original_text_tokenize_on_chars"):
            origin_etl_params["original_text_tokenize_on_chars"] = unicode_str_encode(
                origin_etl_params["original_text_tokenize_on_chars"]
            )

        origin_fields = copy.deepcopy(fields)
        for field in origin_fields:
            if field.get("tokenize_on_chars"):
                field["tokenize_on_chars"] = unicode_str_encode(field["tokenize_on_chars"])

        CollectorHandler(collector_config_id=self.collector_config_id).create_clean_stash(
            {
                "clean_type": etl_config,
                "etl_params": origin_etl_params,
                "etl_fields": origin_fields,
                "bk_biz_id": self.data.bk_biz_id,
            }
        )

        return {
            "collector_config_id": self.data.collector_config_id,
            "collector_config_name": self.data.collector_config_name,
            "etl_config": etl_config,
            "index_set_id": index_set["index_set_id"],
            "scenario_id": index_set["scenario_id"],
            "storage_cluster_id": storage_cluster_id,
            "retention": retention,
            "es_shards": es_shards,
        }
