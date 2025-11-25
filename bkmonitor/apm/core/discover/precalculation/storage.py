"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - Resource SDK (BlueKing - Resource SDK) available.
Copyright (C) 2017-2025 Tencent,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import datetime
import hashlib
import json
import logging
import traceback
from typing import Any

from django.conf import settings
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from elasticsearch import helpers as helpers_common
from elasticsearch5 import helpers as helpers_5
from elasticsearch6 import helpers as helpers_6
from elasticsearch7 import helpers as helpers_7

from apm.core.handlers.application_hepler import ApplicationHelper
from apm.models import DataLink
from apm.utils.base import rt_id_to_index
from bkmonitor.utils.common_utils import count_md5
from bkmonitor.utils.user import get_global_user
from constants.apm import PRECALCULATE_RESULT_TABLE_OPTION, PreCalculateSpecificField, PrecalculateStorageConfig
from constants.common import DEFAULT_TENANT_ID
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import api, resource
from metadata.models import ESStorage

logger = logging.getLogger("apm")


class RendezvousHash:
    def __init__(self, nodes):
        self.nodes = nodes

    def select_node(self, bk_biz_id, app_name):
        max_weight = None
        max_node = None
        key = f"{bk_biz_id}:{app_name}"
        for node in self.nodes:
            combined = f"{node}:{key}"
            hash_val = hashlib.sha1(combined.encode()).hexdigest()
            weight = int(hash_val, 16)

            if max_weight is None or weight > max_weight:
                max_weight = weight
                max_node = node

        return max_node


class PrecalculateStorage:
    """预计算存储类"""

    MAPPING_SETTINGS = {
        "dynamic_templates": [
            {
                "strings_as_keywords": {
                    "match_mapping_type": "string",
                    "mapping": {"norms": "false", "type": "keyword"},
                }
            }
        ]
    }
    # 创建默认存储时默认分表数量
    DEFAULT_STORAGE_DISPERSED_COUNT = 5

    CHECK_UPDATE_FIELDS = ["field_name", "field_type", "tag", "option"]

    # Modify(/Create)ResultTable和QueryResultTable接口返回的字段命名差异
    RESULT_TABLE_FIELD_MAPPING = {"field_name": "field_name", "type": "field_type", "tag": "tag", "option": "option"}

    def __init__(self, bk_biz_id: int, app_name: str, need_client: bool = True):
        self.bk_biz_id = bk_biz_id
        self.app_name = app_name
        self.hash_ring, self.node_mapping, self.id_mapping = self.list_nodes(bk_biz_id, need_client)
        (
            self.search_index_name,
            self.save_index_name,
            self.client,
            self.storage_cluster_id,
            self.origin_index_name,
            self.result_table_id,
        ) = self.select_and_get_storage_client()

        self.is_valid = self.storage_cluster_id is not None

    def select_and_get_storage_client(self):
        if not self.hash_ring:
            return None, None, None, None, None

        node: str = self.hash_ring.select_node(self.bk_biz_id, self.app_name)
        result_table_id: str = node.split("-", 1)[-1]
        origin_index_name: str = rt_id_to_index(result_table_id)

        return (
            f"{origin_index_name}*",
            self.get_index_write_alias(origin_index_name),
            self.node_mapping[node],
            self.id_mapping[node],
            origin_index_name,
            result_table_id,
        )

    @cached_property
    def helpers(self):
        if not self.client:
            return None

        version = self.client.info().get("version", {}).get("number", "")
        helpers = helpers_common
        if version.startswith("6."):
            helpers = helpers_6
        elif version.startswith("5."):
            helpers = helpers_5
        elif version.startswith("7."):
            helpers = helpers_7

        return helpers

    def save(self, data):
        if not self.client:
            logger.warning(f"[PrecalculateStorage] {self.bk_biz_id}: {self.app_name} storage not ready, skip")
            return

        self.helpers.bulk(self.client, data, index=self.save_index_name)
        logger.info(f"[PrecalculateStorage] save {len(data)} success")

    @classmethod
    def _create_default(cls, bk_biz_id, datalink):
        """当预计算配置不存在时 基于默认存储创建索引"""

        default_storage_id = ApplicationHelper.get_default_cluster_id(bk_biz_id)
        if not default_storage_id:
            logger.warning("[PreCalculate] not found default storage, skip create config")
            return None

        pre_calculate_config = {"cluster": []}

        prefix = "apm_global.precalculate_storage_auto_{index}"

        for i in range(cls.DEFAULT_STORAGE_DISPERSED_COUNT):
            pre_calculate_config["cluster"].append(
                {"cluster_id": default_storage_id, "table_name": prefix.format(index=i + 1)}
            )

        if datalink:
            datalink.pre_calculate_config = pre_calculate_config
            datalink.save()
            return datalink

        return DataLink.create_global(pre_calculate_config=pre_calculate_config)

    @classmethod
    def get_datalink_or_none(cls, bk_biz_id: int) -> DataLink | None:
        datalink: DataLink | None = DataLink.get_data_link(bk_biz_id)
        # 不存在则创建
        if not datalink or not datalink.pre_calculate_config:
            try:
                datalink = cls._create_default(bk_biz_id, datalink)
                if not datalink:
                    return None
            except Exception as e:  # noqa
                logger.exception(f"[PreCalculate] create default storage failed, {e} detail: {traceback.format_exc()}")
                return None
        return datalink

    @classmethod
    def fetch_cluster_simple_infos(cls, bk_biz_id) -> list[dict[str, int | str]]:
        datalink: DataLink | None = cls.get_datalink_or_none(bk_biz_id)
        if datalink is None:
            return []

        cluster_infos: list[dict[str, Any]] = datalink.pre_calculate_config.get("cluster") or []
        if not cluster_infos:
            logger.warning("[PreCalculate] empty pre_calculate clusters, bk_biz_id -> %s", bk_biz_id)
            return []

        return [
            {"table_name": cluster_info["table_name"], "cluster_id": cluster_info["cluster_id"]}
            for cluster_info in cluster_infos
        ]

    @classmethod
    def fetch_result_table_ids(cls, bk_biz_id: int) -> list[str]:
        cluster_infos: list[dict[str, Any]] = cls.fetch_cluster_simple_infos(bk_biz_id)
        return [cluster_info["table_name"] for cluster_info in cluster_infos]

    @classmethod
    def list_nodes(
        cls, bk_biz_id: int, need_client: bool
    ) -> tuple[RendezvousHash | None, dict[str, Any] | None, dict[str, int] | None]:
        cluster_infos: list[dict[str, Any]] = cls.fetch_cluster_simple_infos(bk_biz_id)
        if not cluster_infos:
            return None, None, None

        table_ids: list[str] = [cluster_info["table_name"] for cluster_info in cluster_infos]
        table_storage_mapping = {
            _storage.table_id: _storage for _storage in ESStorage.objects.filter(table_id__in=table_ids)
        }

        nodes: list[str] = []
        id_mapping: dict[str, int] = {}
        node_mapping: dict[str, Any] = {}

        for cluster_info in cluster_infos:
            table_name: str = cluster_info["table_name"]
            cluster_id: int = cluster_info["cluster_id"]
            key: str = f"{cluster_id}-{table_name}"

            if table_name not in table_storage_mapping:
                try:
                    storage = cls.create_storage_table(
                        bk_biz_id=bk_biz_id, storage_id=cluster_id, table_name=table_name
                    )
                except Exception as e:  # noqa
                    logger.exception(
                        "[PreCalculate] create storage table failed but ignore: table_name -> %s, cluster_id -> %s",
                        table_name,
                        cluster_id,
                    )
                    continue
            else:
                storage: ESStorage = table_storage_mapping[table_name]

            if need_client:
                try:
                    client = storage.get_client()
                except Exception as e:  # noqa
                    logger.exception(
                        "[PreCalculate] get storage client failed but ignore: storage_cluster_id -> %s",
                        storage.storage_cluster_id,
                    )
                    continue
            else:
                client = None

            nodes.append(key)
            node_mapping[key] = client
            id_mapping[key] = storage.storage_cluster_id

        if not nodes or not node_mapping or not id_mapping:
            logger.warning(
                "[PreCalculate] find storage config(bk_biz_id: %s), but completely get failed, preStorage not work",
                bk_biz_id,
            )
            return None, None, None

        return RendezvousHash(nodes), node_mapping, id_mapping

    @classmethod
    def get_index_write_alias(cls, index_name):
        return f"write_{datetime.datetime.now().strftime('%Y%m%d')}_{index_name}"

    @classmethod
    def create_storage_table(cls, bk_biz_id: int, storage_id: int, table_name: str):
        bk_data_id = cls.create_data_id(bk_biz_id=bk_biz_id, table_name=table_name)
        resource.metadata.create_result_table(
            {
                "bk_data_id": bk_data_id,
                "table_id": table_name,
                "bk_tenant_id": DEFAULT_TENANT_ID,
                "operator": get_global_user(),
                "is_enable": True,
                "table_name_zh": f"APM预计算结果表: {table_name}",
                "is_custom_table": True,
                "schema_type": "free",
                # 默认情况下，预计算表需要按业务 ID 进行隔离查询。
                "bk_biz_id_alias": PreCalculateSpecificField.BIZ_ID.value,
                "default_storage": "elasticsearch",
                "default_storage_config": {
                    "cluster_id": storage_id,
                    "storage_cluster_id": storage_id,
                    # 指定 UnifyQuery 查询索引。
                    "index_set": table_name.replace(".", "_"),
                    "slice_size": settings.APM_APP_PRE_CALCULATE_STORAGE_SLICE_SIZE,
                    "retention": settings.APM_APP_PRE_CALCULATE_STORAGE_RETENTION,
                    "slice_gap": 60 * 24,
                    "date_format": "%Y%m%d",
                    "mapping_settings": cls.MAPPING_SETTINGS,
                    "index_settings": {
                        "number_of_shards": settings.APM_APP_PRE_CALCULATE_STORAGE_SHARDS,
                        "number_of_replicas": 0,
                    },
                },
                "field_list": PrecalculateStorageConfig.TABLE_SCHEMA,
                "is_time_field_only": True,
                "label": "application_check",
                "option": PRECALCULATE_RESULT_TABLE_OPTION,
                "time_option": {
                    "es_type": "date",
                    "es_format": "epoch_millis",
                    "time_format": "yyyy-MM-dd HH:mm:ss",
                    "time_zone": 0,
                },
            }
        )
        logger.info(f"[PrecalculateStorage] create result table success -> {table_name}")

        return ESStorage.objects.filter(table_id=table_name)[0]

    @classmethod
    def create_data_id(cls, bk_biz_id: int, table_name: str):
        try:
            instance = api.metadata.create_data_id(
                {
                    "bk_biz_id": bk_biz_id,
                    "data_name": table_name,
                    "operator": get_global_user(),
                    "data_description": "apm_cross_trace_info",
                    "etl_config": "bk_flat_batch",
                    "type_label": DataTypeLabel.LOG,
                    "source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
                    "option": {
                        "encoding": "UTF-8",
                        "is_log_data": True,
                        "allow_metrics_missing": True,
                    },
                }
            )
            logger.info(f"[PrecalculateStorage] create dataId success -> {instance}")
            return instance["bk_data_id"]
        except Exception as e:  # noqa
            raise ValueError(_("创建dataId失败"))

    @classmethod
    def handle_fields_update(cls):
        """
        检查预计算表字段是否有更新/集群变动 如果有则更新
        """
        for i in DataLink.objects.all():
            cluster_config = i.pre_calculate_config.get("cluster")
            if not cluster_config:
                logger.info(f"[PreCalculateStorage-CHECK_UPDATE] not found config in dataLinkId: {i.pk}")
                continue

            for j in cluster_config:
                instance = ESStorage.objects.filter(table_id=j["table_name"]).first()
                if not instance:
                    logger.info(f"[PreCalculateStorage-CHECK_UPDATE] storage: {j['table_name']} not created, skip")
                    continue

                try:
                    info = resource.metadata.query_result_table_source(table_id=j["table_name"])
                    pre_res = cls._exact_unique_data(
                        info["field_list"], cls.RESULT_TABLE_FIELD_MAPPING, key_field="field_name", remove_field="time"
                    )
                    cur_res = cls._exact_unique_data(
                        PrecalculateStorageConfig.TABLE_SCHEMA, cls.CHECK_UPDATE_FIELDS, "field_name"
                    )

                    # 如果字段有更新 或者 存储集群变动 则更新
                    if (
                        count_md5(json.dumps(cur_res, sort_keys=True)) != count_md5(json.dumps(pre_res, sort_keys=True))
                    ) or (instance.storage_cluster_id != j["cluster_id"]):
                        logger.info("[PreCalculateStorage-CHECK_UPDATE] FIELD OR STORAGE UPDATE!")
                        cls.update_result_table(j["table_name"], j["cluster_id"])
                    else:
                        logger.info(
                            f"[PreCalculateStorage-CHECK_UPDATE] "
                            f"result table: {j['table_name']} not changed, skip update"
                        )
                except Exception as e:  # noqa
                    logger.warning(
                        f"[PreCalculateStorage-CHECK_UPDATE] handle rt: {j['table_name']} fields update failed: {e}"
                    )

    @classmethod
    def _exact_unique_data(cls, data, mapping_or_fields, key_field, remove_field=None):
        res = {}

        for i in data:
            item = {}

            if isinstance(mapping_or_fields, list):
                for j in mapping_or_fields:
                    item[j] = i.get(j)
            else:
                for k, v in mapping_or_fields.items():
                    item[v] = i.get(k)

            res[i[key_field]] = item

        if remove_field:
            res.pop(remove_field, None)

        return res

    @classmethod
    def update_result_table(cls, table_name, storage_cluster_id):
        """更新所有DataLink的预计算存储配置"""
        params = {
            "table_id": table_name,
            "bk_tenant_id": DEFAULT_TENANT_ID,
            "operator": get_global_user(),
            "label": "application_check",
            "field_list": PrecalculateStorageConfig.TABLE_SCHEMA,
            "external_storage": {
                "elasticsearch": {
                    "cluster_id": storage_cluster_id,
                    "storage_cluster_id": storage_cluster_id,
                    "slice_size": settings.APM_APP_PRE_CALCULATE_STORAGE_SLICE_SIZE,
                    "retention": settings.APM_APP_PRE_CALCULATE_STORAGE_RETENTION,
                    "slice_gap": 60 * 24,
                    "date_format": "%Y%m%d",
                    "mapping_settings": cls.MAPPING_SETTINGS,
                    "index_settings": {
                        "number_of_shards": settings.APM_APP_PRE_CALCULATE_STORAGE_SHARDS,
                        "number_of_replicas": 0,
                    },
                }
            },
            "is_time_field_only": True,
            "time_option": {
                "es_type": "date",
                "es_format": "epoch_millis",
                "time_format": "yyyy-MM-dd HH:mm:ss",
                "time_zone": 0,
            },
        }

        resource.metadata.modify_result_table(params)
        logger.info(f"[PrecalculateStorage] update result table {table_name} success! ")
