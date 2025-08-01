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

import arrow
from django.conf import settings
from django.db import transaction
from django.utils.module_loading import import_string
from django.utils.translation import gettext as _

from apps.api import TransferApi
from apps.constants import UserOperationActionEnum, UserOperationTypeEnum
from apps.decorators import user_operation_record
from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.feature_toggle.plugins.constants import FEATURE_COLLECTOR_ITSM
from apps.log_clustering.handlers.clustering_config import ClusteringConfigHandler
from apps.log_clustering.tasks.flow import update_clustering_clean
from apps.log_databus.constants import (
    ETL_PARAMS,
    REGISTERED_SYSTEM_DEFAULT,
    EtlConfig,
    ETLProcessorChoices,
)
from apps.log_databus.exceptions import (
    CollectorActiveException,
    CollectorConfigNotExistException,
    CollectorResultTableIDDuplicateException,
    EtlParseTimeFormatException,
    EtlStorageUsedException,
)
from apps.log_databus.handlers.collector_scenario import CollectorScenario
from apps.log_databus.handlers.collector_scenario.custom_define import get_custom
from apps.log_databus.handlers.etl_storage import EtlStorage
from apps.log_databus.handlers.storage import StorageHandler
from apps.log_databus.models import (
    CollectorConfig,
    ItsmEtlConfig,
    StorageCapacity,
    StorageUsed,
)
from apps.log_search.constants import (
    ISO_8601_TIME_FORMAT_NAME,
    CollectorScenarioEnum,
    FieldDateFormatEnum,
)
from apps.log_search.handlers.index_set import IndexSetHandler
from apps.log_search.models import Scenario
from apps.models import model_to_dict
from apps.utils.db import array_group
from apps.utils.local import get_request_username
from apps.utils.log import logger
from bkm_space.utils import bk_biz_id_to_space_uid


class EtlHandler:
    def __init__(self, collector_config_id=None, etl_processor=ETLProcessorChoices.TRANSFER.value):
        super().__init__()
        self.collector_config_id = collector_config_id
        self.data = None
        self.etl_processor = etl_processor
        if collector_config_id:
            self.data = self._get_collect_config(collector_config_id)
            self.etl_processor = self.data.etl_processor

    @staticmethod
    def _get_collect_config(collector_config_id):
        try:
            collect_config: CollectorConfig = CollectorConfig.objects.get(collector_config_id=collector_config_id)
            return collect_config
        except CollectorConfig.DoesNotExist:
            raise CollectorConfigNotExistException()

    @classmethod
    def get_instance(cls, collector_config_id=None, etl_processor=ETLProcessorChoices.TRANSFER.value):
        if collector_config_id:
            collect_config = cls._get_collect_config(collector_config_id)
            etl_processor = collect_config.etl_processor
        # 处理器映射关系
        mapping = {
            ETLProcessorChoices.BKBASE.value: "BKBaseEtlHandler",
            ETLProcessorChoices.TRANSFER.value: "TransferEtlHandler",
        }
        # 获取处理器
        try:
            etl_handler = import_string(f"apps.log_databus.handlers.etl.{etl_processor}.{mapping.get(etl_processor)}")
            return etl_handler(collector_config_id=collector_config_id, etl_processor=etl_processor)
        except ImportError as error:
            raise NotImplementedError(f"EtlHandler of {etl_processor} not implement, error: {error}")

    def check_es_storage_capacity(self, cluster_info, storage_cluster_id):
        if self.data.table_id:
            return
        es_storage_capacity = int(settings.ES_STORAGE_CAPACITY)
        register_system = cluster_info["cluster_config"].get("registered_system")
        if es_storage_capacity > 0 and register_system == REGISTERED_SYSTEM_DEFAULT:
            biz_storage = StorageCapacity.objects.filter(bk_biz_id=self.data.bk_biz_id).first()
            biz_storage_used = StorageUsed.objects.filter(
                bk_biz_id=self.data.bk_biz_id, storage_cluster_id=storage_cluster_id
            ).first()

            if biz_storage and biz_storage_used:
                storage = biz_storage.storage_capacity
                storage_used = biz_storage_used.storage_used
                if storage > 0:
                    if storage_used >= storage:
                        raise EtlStorageUsedException()

    def itsm_pre_hook(self, data, collect_config_id):
        if not FeatureToggleObject.switch(name=FEATURE_COLLECTOR_ITSM):
            return data, True

        collect_config = CollectorConfig.objects.get(collector_config_id=collect_config_id)
        if data["need_assessment"]:
            from apps.log_databus.handlers.itsm import ItsmHandler

            itsm_handler = ItsmHandler()
            sn = itsm_handler.create_ticket(
                {
                    "title": collect_config.generate_itsm_title(),
                    "bk_biz_id": collect_config.bk_biz_id,
                    "approvals": ",".join(data["assessment_config"]["approvals"]),
                    "log_assessment": data["assessment_config"]["log_assessment"],
                    "collector_detail": itsm_handler.generate_collector_detail_itsm_form(collect_config),
                }
            )
            collect_config.set_itsm_applying(sn)
            if data["assessment_config"]["need_approval"]:
                ItsmEtlConfig.objects.create(ticket_sn=sn, request_param=data)
                return itsm_handler.collect_itsm_status(collect_config_id), False
            collect_config.set_itsm_success()
        return data, True

    def update_or_create(
        self,
        etl_config,
        table_id,
        storage_cluster_id,
        retention,
        allocation_min_days,
        storage_replies,
        view_roles=None,
        etl_params=None,
        fields=None,
        username="",
        alias_settings=None,
    ):
        # 停止状态下不能编辑
        if self.data and not self.data.is_active:
            raise CollectorActiveException()

        # 存储集群信息
        cluster_info = StorageHandler(storage_cluster_id).get_cluster_info_by_id()
        self.check_es_storage_capacity(cluster_info, storage_cluster_id)
        is_add = False if self.data.table_id else True

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

        # 判断是否已存在同result_table_id
        if CollectorConfig(table_id=table_id).get_result_table_by_id():
            logger.error(f"result_table_id {table_id} already exists")
            raise CollectorResultTableIDDuplicateException(
                CollectorResultTableIDDuplicateException.MESSAGE.format(result_table_id=table_id)
            )

        # 1. meta-创建/修改结果表
        etl_storage = EtlStorage.get_instance(etl_config=etl_config)
        result_table_info = etl_storage.update_or_create_result_table(
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
            alias_settings=alias_settings,
        )

        if not view_roles:
            view_roles = []

        # 2. 创建索引集
        index_set = self._update_or_create_index_set(etl_config, storage_cluster_id, view_roles, username=username)

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
            },
        }
        user_operation_record.delay(operation_record)
        if self.data.collector_scenario_id == CollectorScenarioEnum.CUSTOM.value:
            custom_config = get_custom(self.data.custom_type)
            custom_config.after_etl_hook(self.data)

        return {
            "collector_config_id": self.data.collector_config_id,
            "collector_config_name": self.data.collector_config_name,
            "etl_config": etl_config,
            "index_set_id": index_set["index_set_id"],
            "scenario_id": index_set["scenario_id"],
            "storage_cluster_id": storage_cluster_id,
            "retention": retention,
            "table_id": result_table_info["table_id"],
        }

    @staticmethod
    def etl_preview(etl_config, etl_params, data):
        etl_storage = EtlStorage.get_instance(etl_config=etl_config)
        fields = etl_storage.etl_preview(data, etl_params)
        return {"fields": fields}

    def etl_time(self, time_format, time_zone, data):
        """
        时间解析
        """
        fmts = array_group(FieldDateFormatEnum.get_choices_list_dict(), "id", True)
        fmt = fmts.get(time_format)

        if fmt.get("is_custom"):
            # 自定义格式跳过校验
            return {"epoch_millis": f"{int(arrow.now().timestamp())}000"}

        if fmt["name"] in [ISO_8601_TIME_FORMAT_NAME, "ISO8601"]:
            try:
                epoch_second = int(
                    arrow.get(
                        data,
                        tzinfo=f"GMT{time_zone}",
                    ).timestamp()
                )
            except Exception:  # pylint: disable=broad-except
                raise EtlParseTimeFormatException()
        else:
            if len(data) != len(fmt["description"]) and len(data) != len(fmt["name"]):
                raise EtlParseTimeFormatException()

            if time_format in ["epoch_second", "epoch_millis", "epoch_micros"]:
                epoch_second = str(data)[0:10]
            else:
                try:
                    epoch_second = int(arrow.get(data, fmt["name"], tzinfo=f"GMT{time_zone}").timestamp())
                except Exception:  # pylint: disable=broad-except
                    raise EtlParseTimeFormatException()
        return {"epoch_millis": f"{epoch_second}000"}

    @transaction.atomic()
    def _update_or_create_index_set(
        self,
        etl_config,
        storage_cluster_id,
        view_roles=None,
        username="",
        sort_fields=None,
        target_fields=None,
    ):
        """
        创建索引集
        """
        # view_roles的来源
        indexes = [
            {
                "bk_biz_id": self.data.bk_biz_id,
                "result_table_id": self.data.table_id,
                "result_table_name": self.data.collector_config_name,
                "time_field": "dtEventTimeStamp",
            }
        ]
        index_set_name = _("[采集项]") + self.data.collector_config_name

        if self.data.index_set_id:
            index_set_handler = IndexSetHandler(index_set_id=self.data.index_set_id)
            if not view_roles:
                view_roles = index_set_handler.data.view_roles
            index_set = index_set_handler.update(
                index_set_name=index_set_name,
                storage_cluster_id=storage_cluster_id,
                view_roles=view_roles,
                category_id=self.data.category_id,
                indexes=indexes,
                username=username,
                sort_fields=sort_fields,
                target_fields=target_fields,
            )
        else:
            if not view_roles:
                view_roles = []
            index_set = IndexSetHandler.create(
                index_set_name=index_set_name,
                space_uid=bk_biz_id_to_space_uid(self.data.bk_biz_id),
                storage_cluster_id=storage_cluster_id,
                scenario_id=Scenario.LOG,
                view_roles=view_roles,
                indexes=indexes,
                category_id=self.data.category_id,
                collector_config_id=self.collector_config_id,
                username=username,
                sort_fields=sort_fields,
                target_fields=target_fields,
            )
            self.data.index_set_id = index_set.index_set_id
        self.data.etl_config = etl_config
        self.data.save()

        return model_to_dict(index_set)

    def close_clean(self):
        storage = TransferApi.get_result_table_storage(
            params={"result_table_list": self.data.table_id, "storage_type": "elasticsearch"}
        )[self.data.table_id]
        storage_cluster_id = storage["cluster_config"]["cluster_id"]
        retention = storage["storage_config"].get("retention")
        allocation_min_days = storage["storage_config"].get("warm_phase_days")
        storage_replies = storage["storage_config"]["index_settings"]["number_of_replicas"]
        _, table_id = self.data.table_id.split(".")
        self.update_or_create(
            etl_config=EtlConfig.BK_LOG_TEXT,
            table_id=table_id,
            storage_cluster_id=storage_cluster_id,
            retention=retention,
            allocation_min_days=allocation_min_days,
            storage_replies=storage_replies,
            etl_params=ETL_PARAMS,
            fields=[],
        )
        return {"collector_config_id": self.collector_config_id}
