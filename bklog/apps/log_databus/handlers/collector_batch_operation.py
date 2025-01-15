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
"""
from apps.log_databus.constants import CollectorBatchOperationType
from apps.log_databus.exceptions import CollectorConfigNotExistException
from apps.log_databus.handlers.collector import CollectorHandler
from apps.log_databus.handlers.etl import EtlHandler
from apps.log_databus.handlers.storage import StorageHandler
from apps.log_databus.models import CollectorConfig


class CollectorBatchHandler(object):
    def __init__(self, collector_ids, operation):
        self.collector_ids = collector_ids
        self.operation = operation
        self.collectors = CollectorConfig.objects.filter(collector_config_id__in=self.collector_ids)
        if not self.collectors:
            raise CollectorConfigNotExistException()

    def batch_operation(self, params):
        """
        根据operation执行不同的操作逻辑
        """
        if self.operation == CollectorBatchOperationType.MODIFY_STORAGE.value:
            retention = params["operation_params"].get("retention", -1)
            storage_replies = params["operation_params"].get("storage_replies", -1)
            es_shards = params["operation_params"].get("es_shards", -1)
            allocation_min_days = params["operation_params"].get("allocation_min_days", -1)
            result = self.modify_storage(retention, storage_replies, es_shards, allocation_min_days)
        elif self.operation == CollectorBatchOperationType.QUERY_STORAGE.value:
            result = self.query_storage()
        else:
            result = self.stop_or_start()
        return result

    def stop_or_start(self):
        """
        停用或启动采集项
        """
        results = []
        for collector in self.collectors:
            collector_info = {
                "id": collector.collector_config_id,
                "name": collector.collector_config_name,
                "status": "SUCCESS",
                "description": f"{self.operation} operation executed successfully",
            }
            try:
                handler = CollectorHandler(collector_config_id=collector.collector_config_id)
                if self.operation == CollectorBatchOperationType.STOP.value:
                    handler.stop()
                else:
                    handler.start()

            except Exception as e:
                collector_info.update(
                    {
                        "status": "FAILED",
                        "description": f"Failed to execute {self.operation} operation, reason: {e}",
                    }
                )
            results.append(collector_info)
        return results

    def modify_storage(self, retention, storage_replies, es_shards, allocation_min_days):
        """
        修改存储配置
        :param retention: 过期时间
        :param storage_replies: 副本数
        :param es_shards: 分片数
        :param allocation_min_days: 热数据天数
        """
        results = []
        for collector in self.collectors:
            collector_info = {
                "id": collector.collector_config_id,
                "name": collector.collector_config_name,
                "status": "SUCCESS",
                "description": f"{self.operation} operation executed successfully",
            }
            handler = CollectorHandler(collector.collector_config_id)
            collect_config = handler.retrieve()
            clean_stash = handler.get_clean_stash()

            etl_params = clean_stash["etl_params"] if clean_stash else collect_config["etl_params"]
            etl_fields = (
                clean_stash["etl_fields"]
                if clean_stash
                else [field for field in collect_config["fields"] if not field["is_built_in"]]
            )
            storage_cluster_id = collect_config["storage_cluster_id"]
            if storage_cluster_id > 0:
                cluster_info = StorageHandler(storage_cluster_id).get_cluster_info_by_id()
                hot_warm_enabled = (
                    cluster_info["cluster_config"].get("custom_option", {}).get("hot_warm_config", {}).get("is_enabled")
                )
            else:
                hot_warm_enabled = True

            if not collect_config["is_active"]:
                collector_info.update(
                    {
                        "status": "FAILED",
                        "description": f"Failed to execute {self.operation} operation, "
                        f"reason: The collector is not active",
                    }
                )
            else:
                etl_params = {
                    "table_id": collector.collector_config_name_en,
                    "storage_cluster_id": storage_cluster_id,
                    "retention": retention if retention > 0 else collect_config["retention"],
                    "allocation_min_days": allocation_min_days if hot_warm_enabled else 0,
                    "storage_replies": storage_replies if storage_replies >= 0 else collect_config["storage_replies"],
                    "es_shards": es_shards if es_shards > 0 else collect_config["storage_shards_nums"],
                    "etl_params": etl_params,
                    "etl_config": collect_config["etl_config"],
                    "fields": etl_fields,
                }
                try:
                    etl_handler = EtlHandler.get_instance(collector.collector_config_id)
                    etl_handler.update_or_create(**etl_params)
                except Exception as e:
                    collector_info.update(
                        {
                            "status": "FAILED",
                            "description": f"Failed to execute {self.operation} operation, reason: {e}",
                        }
                    )
            results.append(collector_info)

        return results

    def query_storage(self):
        """
        查询存储
        """
        storage_data = []
        total_store_size = 0
        for collector in self.collectors:
            collector_info = {
                "id": collector.collector_config_id,
                "name": collector.collector_config_name,
                "bk_biz_id": collector.bk_biz_id,
                "status": "SUCCESS",
                "store_size": 0,
                "description": f"{self.operation} success",
            }
            try:
                indices_info = CollectorHandler(collector.collector_config_id).indices_info()
                total = sum(int(idx["store.size"]) for idx in indices_info)
                total_store_size += total
                collector_info.update({"store_size": total})
            except Exception as e:
                collector_info.update(
                    {
                        "status": "FAILED",
                        "description": f"{self.operation} failed, reason: {e}",
                    }
                )

            storage_data.append(collector_info)

        return {
            "storage_data": storage_data,
            "total_store_size": total_store_size,
        }
