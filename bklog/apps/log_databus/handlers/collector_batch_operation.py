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
import copy

from django.db import transaction
from django.utils.translation import ugettext as _

from apps.api import NodeApi
from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.feature_toggle.plugins.constants import FEATURE_COLLECTOR_ITSM
from apps.log_databus.constants import (
    CollectorBatchOperationType,
    ContainerCollectStatus,
)
from apps.log_databus.exceptions import CollectorConfigNotExistException
from apps.log_databus.handlers.collector import CollectorHandler
from apps.log_databus.handlers.collector_scenario import CollectorScenario
from apps.log_databus.handlers.collector_scenario.utils import (
    deal_collector_scenario_param,
)
from apps.log_databus.handlers.etl import EtlHandler
from apps.log_databus.handlers.etl_storage import EtlStorage
from apps.log_databus.handlers.storage import StorageHandler
from apps.log_databus.models import CollectorConfig, ContainerCollectorConfig
from apps.log_databus.tasks.collector import create_container_release
from apps.log_search.models import LogIndexSet


class CollectorBatchHandler(object):
    def __init__(self, collector_ids=None):
        self.collector_ids = collector_ids
        self.collectors = CollectorConfig.objects.filter(collector_config_id__in=self.collector_ids)
        if not self.collectors:
            raise CollectorConfigNotExistException()

    def batch_operation(self, params):
        operation = params["operation_type"]
        if operation == CollectorBatchOperationType.STOP.value:
            result = self.stop()
        elif operation == CollectorBatchOperationType.START.value:
            result = self.start()
        elif operation == CollectorBatchOperationType.MODIFY_STORAGE.value:
            result = self.modify_storage(params["operation_params"])
        elif operation == CollectorBatchOperationType.QUERY_STORAGE.value:
            result = self.query_storage()
        return result

    @transaction.atomic
    def stop(self):
        index_set_ids = self.collectors.values_list("index_set_id")
        if index_set_ids:
            LogIndexSet.objects.filter(index_set_id__in=index_set_ids).update(is_active=False)

        collector_config_list = []
        container_config_list = []
        for collector in self.collectors:
            if collector.is_container_environment:
                container_configs = ContainerCollectorConfig.objects.filter(
                    collector_config_id=collector.collector_config_id
                )
                for container_config in container_configs:
                    from apps.log_databus.tasks.collector import (
                        delete_container_release,
                    )

                    name = self.generate_bklog_config_name(collector, container_config.id)
                    container_config.status = ContainerCollectStatus.PENDING.value
                    container_config_list.append(container_config)

                    delete_container_release.delay(
                        bcs_cluster_id=collector.bcs_cluster_id,
                        container_config_id=container_config.id,
                        config_name=name,
                        delete_config=False,
                    )
            if collector.subscription_id:
                # 停止节点管理订阅功能
                NodeApi.switch_subscription({"subscription_id": collector.subscription_id, "action": "disable"})
            if collector.table_id:
                etl_storage = EtlStorage.get_instance(collector.etl_config)
                etl_storage.switch_result_table(collector_config=collector, is_enable=False)

            if collector.subscription_id:
                self._run_subscription_task(collector, "STOP")
            collector.is_active = False
            collector_config_list.append(collector)
        if collector_config_list:
            CollectorConfig.objects.bulk_update(
                collector_config_list,
                ["task_id_list", "is_active"],
            )
        if container_config_list:
            ContainerCollectorConfig.objects.bulk_update(
                container_config_list,
                ["status"],
            )
        return _(f"执行stop操作成功")

    @transaction.atomic
    def start(self):
        index_set_ids = []
        collector_config_list = []
        container_config_list = []
        for collector in self.collectors:
            if (
                not collector.is_custom_scenario
                and collector.itsm_has_appling()
                and FeatureToggleObject.switch(name=FEATURE_COLLECTOR_ITSM)
            ):
                continue
            if collector.is_container_environment:
                container_configs = ContainerCollectorConfig.objects.filter(
                    collector_config_id=collector.collector_config_id
                )
                for container_config in container_configs:
                    if container_config.yaml_config_enabled and container_config.raw_config:
                        # 如果开启了yaml模式且有原始配置，则优先使用
                        request_params = copy.deepcopy(container_config.raw_config)
                        request_params["dataId"] = container_config.bk_data_id
                    else:
                        deal_collector_scenario_param(container_config.params)
                        request_params = CollectorHandler.collector_container_config_to_raw_config(
                            collector,
                            container_config,
                        )

                    # 如果是边缘存查配置，还需要追加 output 配置
                    data_link_id = CollectorConfig.objects.get(
                        collector_config_id=container_config.collector_config_id
                    ).data_link_id
                    edge_transport_params = CollectorScenario.get_edge_transport_output_params(data_link_id)
                    if edge_transport_params:
                        ext_options = request_params.get("extOptions") or {}
                        ext_options["output.kafka"] = edge_transport_params
                        request_params["extOptions"] = ext_options

                    name = self.generate_bklog_config_name(container_config, container_config.id)

                    container_config.status = ContainerCollectStatus.PENDING.value
                    container_config.status_detail = _("等待配置下发")
                    container_config_list.append(container_config)

                    create_container_release.delay(
                        bcs_cluster_id=container_config.bcs_cluster_id,
                        container_config_id=container_config.id,
                        config_name=name,
                        config_params=request_params,
                    )
            # 启动节点管理订阅功能
            if collector.subscription_id:
                NodeApi.switch_subscription({"subscription_id": collector.subscription_id, "action": "enable"})
            # 存在RT则启用RT
            if collector.table_id:
                etl_storage = EtlStorage.get_instance(collector.etl_config)
                etl_storage.switch_result_table(collector_config=collector, is_enable=True)
            if collector.subscription_id:
                self._run_subscription_task(collector)

            index_set_ids.append(collector.index_set_id)
            collector.is_active = True
            collector_config_list.append(collector)

        if collector_config_list:
            CollectorConfig.objects.bulk_update(
                collector_config_list,
                ["task_id_list", "is_active"],
            )
        if index_set_ids:
            LogIndexSet.objects.filter(index_set_id__in=index_set_ids).update(is_active=True)
        if container_config_list:
            ContainerCollectorConfig.objects.bulk_update(
                container_config_list,
                ["status", "status_detail"],
            )

        return _(f"执行start操作成功")

    @transaction.atomic
    def modify_storage(self, operation_params):
        retention = operation_params["retention"]
        storage_replies = operation_params["storage_replies"]
        es_shards = operation_params["es_shards"]
        allocation_min_days = operation_params["allocation_min_days"]

        success_collector_ids = []
        results = []
        for collector in self.collectors:
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
                results.append(
                    f"[Skipped] collector_config_id->[{collector.collector_config_id}], "
                    f"Collector->[{collector.collector_config_name_en}] is not active"
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
                    success_collector_ids.append(collector.collector_config_id)
                except Exception as e:
                    results.append(
                        f"[Failed] collector_config_id->[{collector.collector_config_id}], "
                        f"Collector->[{collector.collector_config_name_en}] is failed, reason: {e}"
                    )

        return {"collector_ids": success_collector_ids, "exception_records": results}

    def query_storage(self):
        results = []
        storage_data = []
        total_store_size = 0
        for collector in self.collectors:
            try:
                indices_info = CollectorHandler(collector.collector_config_id).indices_info()
            except Exception as e:
                results.append(
                    f"[Skipped] collector_config_id->[{collector.collector_config_id}], "
                    f"Collector->[{collector.collector_config_name_en}], reason: {e}"
                )
                continue
            total = sum(int(idx["store.size"]) for idx in indices_info)
            storage_data.append(
                {
                    "id": collector.collector_config_id,
                    "name": collector.collector_config_name,
                    "bk_biz_id": collector.bk_biz_id,
                    "store_size": f"{total / 1024 ** 3:.2f}GB",
                }
            )
            total_store_size += total

        return {
            "storage_data": storage_data,
            "total_store_size": f"{total_store_size / 1024 ** 3:.2f}GB",
        }

    @staticmethod
    def generate_bklog_config_name(collector, container_config_id) -> str:
        return "{}-{}-{}".format(
            collector.collector_config_name_en.lower(),
            collector.bk_biz_id,
            container_config_id,
        ).replace("_", "-")

    @staticmethod
    def _run_subscription_task(collector, action=None):
        collector_scenario = CollectorScenario.get_instance(collector_scenario_id=collector.collector_scenario_id)
        params = {"subscription_id": collector.subscription_id}
        if action:
            params.update({"actions": {collector_scenario.PLUGIN_NAME: action}})
        task_id = str(NodeApi.run_subscription_task(params)["task_id"])
        collector.task_id_list = [str(task_id)]
