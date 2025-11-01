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
from apps.log_clustering.models import ClusteringConfig
from apps.log_clustering.tasks.flow import update_clustering_clean
from apps.log_databus.exceptions import CollectorActiveException
from apps.log_databus.handlers.collector import CollectorHandler
from apps.log_databus.handlers.collector_scenario import CollectorScenario
from apps.log_databus.handlers.collector_scenario.custom_define import get_custom
from apps.log_databus.handlers.collector_scenario.utils import build_es_option_type
from apps.log_databus.handlers.etl import EtlHandler
from apps.log_databus.handlers.etl_storage import EtlStorage
from apps.log_databus.handlers.storage import StorageHandler
from apps.log_search.constants import CollectorScenarioEnum
from apps.log_search.models import LogIndexSet
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
        total_shards_per_node=None,
        *args,
        **kwargs,
    ):
        etl_params = etl_params or {}
        user_fields = copy.deepcopy(fields)
        # 停止状态下不能编辑
        if self.data and not self.data.is_active:
            raise CollectorActiveException()

        # 存储集群信息
        cluster_info = StorageHandler(storage_cluster_id).get_cluster_info_by_id()
        self.check_es_storage_capacity(cluster_info, storage_cluster_id)
        is_add = False if self.data.table_id else True

        if self.data.is_clustering:
            clustering_config = ClusteringConfig.objects.get(collector_config_id=self.data.collector_config_id)

            update_clustering_clean.delay(
                collector_config_id=self.data.collector_config_id,
                fields=fields,
                etl_config=etl_config,
                etl_params=etl_params,
            )

            if clustering_config.bkdata_data_id and clustering_config.bkdata_data_id != self.data.bk_data_id:
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

            if clustering_config.use_mini_link:
                fields = CollectorScenario.fields_insert_field_index(
                    source_fields=fields,
                    dst_fields=[
                        {
                            "field_name": "signature",
                            "field_type": "string",
                            "tag": "dimension",
                            "alias_name": "signature",
                            "description": "signature",
                            "option": build_es_option_type("keyword", cluster_info["cluster_config"]["version"]),
                            "is_built_in": True,
                            "is_time": False,
                            "is_analyzed": False,
                            "is_dimension": True,
                            "is_delete": False,
                        }
                    ],
                )

                # 接入聚类小型化必须要创建 pattern 结果表
                EtlStorage.update_or_create_pattern_result_table(
                    instance=self.data,
                    table_id=clustering_config.signature_pattern_rt,
                    storage_cluster_id=storage_cluster_id,
                    allocation_min_days=allocation_min_days,
                    storage_replies=storage_replies,
                    es_version=cluster_info["cluster_config"]["version"],
                    hot_warm_config=cluster_info["cluster_config"].get("custom_option", {}).get("hot_warm_config"),
                    es_shards=es_shards,
                    total_shards_per_node=total_shards_per_node,
                )

        index_set_obj = LogIndexSet.objects.filter(index_set_id=self.data.index_set_id).first()
        if sort_fields is None and index_set_obj:
            sort_fields = index_set_obj.sort_fields
        if sort_fields is None and index_set_obj:
            target_fields = index_set_obj.target_fields

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
            sort_fields=sort_fields,
            target_fields=target_fields,
            total_shards_per_node=total_shards_per_node,
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

        CollectorHandler(collector_config_id=self.collector_config_id).create_clean_stash(
            {
                "clean_type": etl_config,
                "etl_params": etl_params,
                "etl_fields": user_fields,
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

    def patch_update(
        self,
        storage_cluster_id=None,
        retention=None,
        allocation_min_days=None,
        storage_replies=None,
        es_shards=None,
    ):
        from apps.log_databus.handlers.collector import CollectorHandler

        handler = CollectorHandler(self.collector_config_id)
        collect_config = handler.retrieve()
        clean_stash = handler.get_clean_stash()

        etl_params = clean_stash["etl_params"] if clean_stash else collect_config["etl_params"]
        etl_fields = (
            clean_stash["etl_fields"]
            if clean_stash
            else [field for field in collect_config["fields"] if not field["is_built_in"]]
        )

        storage_cluster_id = (
            storage_cluster_id if storage_cluster_id is not None else collect_config["storage_cluster_id"]
        )
        retention = retention if retention is not None else collect_config["retention"]
        allocation_min_days = (
            allocation_min_days if allocation_min_days is not None else collect_config["allocation_min_days"]
        )
        storage_replies = storage_replies if storage_replies is not None else collect_config["storage_replies"]
        es_shards = es_shards if es_shards is not None else collect_config["storage_shards_nums"]

        if storage_cluster_id:
            cluster_info = StorageHandler(storage_cluster_id).get_cluster_info_by_id()
            hot_warm_enabled = (
                cluster_info["cluster_config"].get("custom_option", {}).get("hot_warm_config", {}).get("is_enabled")
            )
        else:
            hot_warm_enabled = False

        etl_params = {
            "table_id": self.data.collector_config_name_en,
            "storage_cluster_id": storage_cluster_id,
            "retention": retention,
            "allocation_min_days": allocation_min_days if hot_warm_enabled else 0,
            "storage_replies": storage_replies,
            "es_shards": es_shards,
            "etl_params": etl_params,
            "etl_config": collect_config["etl_config"],
            "fields": etl_fields,
        }

        return self.update_or_create(**etl_params)
