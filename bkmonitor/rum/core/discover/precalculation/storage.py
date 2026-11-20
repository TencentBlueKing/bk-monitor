"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

"""

import datetime
import json
import logging
import traceback
from typing import Any

from django.conf import settings
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from apm.core.discover.precalculation.storage import RendezvousHash  # noqa: F401  复用 APM 实现的 hash
from apm.utils.base import rt_id_to_index
from bkmonitor.utils.common_utils import count_md5
from bkmonitor.utils.user import get_global_user
from constants.common import DEFAULT_TENANT_ID
from constants.data_source import DataSourceLabel, DataTypeLabel
from constants.result_table import RT_RESERVED_WORD_EXACT
from core.drf_resource import api, resource
from metadata.models import ESStorage
from rum.models import DataLink
from rum.core.handlers.application_helper import RumApplicationHelper

from rum.core.discover.precalculation.constants import (
    RUM_PRECALCULATE_RESULT_TABLE_OPTION,
    RumGlobalTablePrefix,
    RumPrecalculateStorageConfig,
)

logger = logging.getLogger("apm")

# DataLink 的全局配置级别
GLOBAL_CONFIG_BK_BIZ_ID = 0


class RumPrecalculateStorage:
    # 全局默认分表数量（与 APM 一致）
    DEFAULT_STORAGE_DISPERSED_COUNT = 5

    """RUM 预计算存储（session / view 两套）

    使用方式：
        storage = RumPrecalculateStorage(bk_biz_id=2, app_name="my_app", table_kind="session")
        storage.save_index_name         # 写入 alias，例如 write_20260914_rum_global_session_precalculate_auto_1
        storage.origin_index_name       # 原始索引名
        storage.result_table_id         # 完整 RT ID
        storage.storage_cluster_id      # 实际落库的 ES 集群 ID
        storage.save(docs)              # 走 ES bulk API 写入
    """

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

    def __init__(self, bk_biz_id: int, app_name: str, table_kind: str, need_client: bool = True):
        if table_kind not in ("session", "view"):
            raise ValueError(_("RUM 预计算 table_kind 必须是 session 或 view，收到: {}").format(table_kind))
        self.bk_biz_id = bk_biz_id
        self.app_name = app_name
        self.table_kind = table_kind

        self.hash_ring, self.node_mapping, self.id_mapping = self.list_nodes(bk_biz_id, table_kind, need_client)
        (
            self.search_index_name,
            self.save_index_name,
            self.client,
            self.storage_cluster_id,
            self.origin_index_name,
            self.result_table_id,
        ) = self.select_and_get_storage_client()
        self.is_valid = self.storage_cluster_id is not None

    @classmethod
    def get_route_key(cls, bk_biz_id: int, app_name: str) -> str:
        """RUM 没有共享 trace data_id 概念，直接按 (bk_biz_id, app_name) 路由。"""
        return f"{bk_biz_id}:{app_name}"

    def select_and_get_storage_client(self):
        if not self.hash_ring:
            return None, None, None, None, None, None

        node: str = self.hash_ring.select_node(self.get_route_key(self.bk_biz_id, self.app_name))
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

    @classmethod
    def get_datalink_or_none(cls, bk_biz_id: int, table_kind: str) -> DataLink | None:
        datalink: DataLink | None = DataLink.get_data_link(bk_biz_id)
        # 不存在则创建；已存在则追加当前 table_kind 缺失的配置（_create_default 内部已做幂等判断）
        try:
            datalink = cls._create_default(bk_biz_id, table_kind, datalink)
            if not datalink:
                return None
        except Exception as e:  # noqa
            logger.exception(f"[PreCalculate] create default storage failed, {e} detail: {traceback.format_exc()}")
            return None
        return datalink

    @classmethod
    def fetch_cluster_simple_infos(cls, bk_biz_id: int, table_kind: str) -> list[dict[str, Any]]:
        """业务下所有 RUM 预计算分表的 (table_name, cluster_id) 列表。"""
        datalink = cls.get_datalink_or_none(bk_biz_id, table_kind)
        if not datalink:
            return []
        cluster_infos: list[dict[str, Any]] = datalink.pre_calculate_config.get("cluster") or []
        if not cluster_infos:
            logger.warning("[RumPrecalculateStorage] empty pre_calculate clusters, bk_biz_id -> %s", bk_biz_id)
            return []
        return [
            {"table_name": ci["table_name"], "cluster_id": ci["cluster_id"]}
            for ci in cluster_infos
            if table_kind in ci["table_name"]
        ]

    @classmethod
    def fetch_result_table_ids(cls, bk_biz_id: int, table_kind: str) -> list[str]:
        return [ci["table_name"] for ci in cls.fetch_cluster_simple_infos(bk_biz_id, table_kind)]

    @classmethod
    def list_nodes(
        cls, bk_biz_id: int, table_kind: str, need_client: bool
    ):
        """构造 hash_ring + node/cluster mapping。"""
        cluster_infos = cls.fetch_cluster_simple_infos(bk_biz_id, table_kind)
        if not cluster_infos:
            return None, None, None

        table_ids: list[str] = [ci["table_name"] for ci in cluster_infos]
        table_storage_mapping = {
            _storage.table_id: _storage for _storage in ESStorage.objects.filter(table_id__in=table_ids)
        }

        nodes: list[str] = []
        id_mapping: dict[str, int] = {}
        node_mapping: dict[str, Any] = {}

        for ci in cluster_infos:
            table_name: str = ci["table_name"]
            cluster_id: int = ci["cluster_id"]
            key: str = f"{cluster_id}-{table_name}"

            if table_name not in table_storage_mapping:
                try:
                    storage = cls.create_storage_table(
                        bk_biz_id=bk_biz_id, storage_id=cluster_id, table_name=table_name, table_kind=table_kind
                    )
                except Exception as e:  # noqa: BLE001
                    logger.exception(
                        "[RumPrecalculateStorage] create storage table failed, table_name -> %s, cluster_id -> %s, error: %s",
                        table_name,
                        cluster_id,
                        e,
                    )
                    continue
            else:
                storage = table_storage_mapping[table_name]

            if need_client:
                try:
                    client = storage.get_client()
                except Exception as e:  # noqa: BLE001
                    logger.exception(
                        "[RumPrecalculateStorage] get storage client failed, storage_cluster_id -> %s, error: %s",
                        storage.storage_cluster_id,
                        e,
                    )
                    continue
            else:
                client = None

            nodes.append(key)
            node_mapping[key] = client
            id_mapping[key] = storage.storage_cluster_id

        if not nodes or not node_mapping or not id_mapping:
            logger.warning(
                "[RumPrecalculateStorage] find storage config(bk_biz_id: %s, table_kind: %s) but completely get failed",
                bk_biz_id,
                table_kind,
            )
            return None, None, None

        return RendezvousHash(nodes), node_mapping, id_mapping

    @classmethod
    def _create_default(cls, bk_biz_id: int, table_kind: str, datalink) -> DataLink | None:
        """当预计算配置不存在时 基于默认存储创建索引"""
        default_storage_id = RumApplicationHelper.get_default_cluster_id(bk_biz_id)
        if not default_storage_id:
            logger.warning("[PreCalculate] not found default storage, skip create config")
            return None

        pre_calculate_config = {"cluster": []}

        table_prefix = RumGlobalTablePrefix.PRECALCULATE_SESSION if table_kind == "session" else RumGlobalTablePrefix.PRECALCULATE_VIEW

        for i in range(cls.DEFAULT_STORAGE_DISPERSED_COUNT):
            pre_calculate_config["cluster"].append(
                {
                    "cluster_id": default_storage_id,
                    "table_name": f"{table_prefix}_auto_{i + 1}",
                }
            )
        if datalink:
            # 确保当前 table_kind 的配置追加到 cluster 列表
            if datalink.pre_calculate_config is None:
                datalink.pre_calculate_config = {"cluster": []}
            existing_table_names = {c["table_name"] for c in datalink.pre_calculate_config.get("cluster", [])}
            for item in pre_calculate_config["cluster"]:
                if item["table_name"] not in existing_table_names:
                    datalink.pre_calculate_config["cluster"].append(item)
            datalink.save()
            return datalink

        return DataLink.create_global(pre_calculate_config=pre_calculate_config)



    @classmethod
    def create_data_id(cls, bk_biz_id: int, table_name: str, bk_tenant_id: str | None = None):
        from metadata.models import DataSource

        existing = DataSource.objects.filter(data_name=table_name).first()
        if existing:
            logger.info("[RumPrecalculateStorage] dataId already exists -> %s", existing.bk_data_id)
            return existing.bk_data_id

        try:
            instance = api.metadata.create_data_id(
                {
                    "bk_biz_id": bk_biz_id,
                    "data_name": table_name,
                    "operator": get_global_user(bk_tenant_id=bk_tenant_id),
                    "data_description": "rum_precalculate",
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
            logger.info("[RumPrecalculateStorage] create dataId success -> %s", instance)
            return instance["bk_data_id"]
        except Exception as e:  # noqa: BLE001
            raise ValueError(_("创建 dataId 失败: {}").format(e))

    @classmethod
    def create_storage_table(
        cls,
        bk_biz_id: int,
        storage_id: int,
        table_name: str,
        table_kind: str,
        bk_tenant_id: str | None = None,
    ):
        existing_storage = ESStorage.objects.filter(table_id=table_name).first()
        if existing_storage:
            logger.info("[RumPrecalculateStorage] storage table already exists -> %s", table_name)
            return existing_storage

        bk_data_id = cls.create_data_id(bk_biz_id=bk_biz_id, table_name=table_name, bk_tenant_id=bk_tenant_id)
        try:
            resource.metadata.create_result_table(
                {
                    "bk_data_id": bk_data_id,
                    "table_id": table_name,
                    "bk_tenant_id": bk_tenant_id or DEFAULT_TENANT_ID,
                    "operator": get_global_user(bk_tenant_id=bk_tenant_id),
                    "is_enable": True,
                    "table_name_zh": f"RUM预计算结果表: {table_name}",
                    "is_custom_table": True,
                    "schema_type": "free",
                    "default_storage": "elasticsearch",
                    "default_storage_config": {
                        "cluster_id": storage_id,
                        "storage_cluster_id": storage_id,
                        # UnifyQuery 查询索引
                        "index_set": table_name.replace(".", "_"),
                        "slice_size": settings.RUM_APP_DEFAULT_ES_SLICE_LIMIT,
                        "retention": settings.RUM_APP_DEFAULT_ES_RETENTION,
                        "slice_gap": 60 * 24,
                        "date_format": "%Y%m%d",
                        "mapping_settings": cls.MAPPING_SETTINGS,
                        "index_settings": {
                            "number_of_shards": settings.RUM_APP_DEFAULT_ES_SHARDS,
                            "number_of_replicas": settings.RUM_APP_DEFAULT_ES_REPLICAS,
                        },
                    },
                    "field_list": [
                        f for f in RumPrecalculateStorageConfig.get_table_schema(table_kind)
                        if f["field_name"].upper() not in RT_RESERVED_WORD_EXACT
                    ],
                    "is_time_field_only": True,
                    "label": "application_check",
                    "option": RUM_PRECALCULATE_RESULT_TABLE_OPTION,
                    "time_option": {
                        "es_type": "date",
                        "es_format": "epoch_millis",
                        "time_format": "yyyy-MM-dd HH:mm:ss",
                        "time_zone": 0,
                    },
                }
            )
        except ValueError as e:
            if "已经存在" not in str(e):
                raise
            logger.info("[RumPrecalculateStorage] result table already exists in metadata, creating ESStorage record -> %s", table_name)
            # RT 已在 metadata 存在，但 ESStorage 本地记录缺失，补充完整字段
            storage = ESStorage.objects.create(
                table_id=table_name,
                storage_cluster_id=storage_id,
                bk_tenant_id=DEFAULT_TENANT_ID,
                index_settings=json.dumps({
                    "number_of_shards": settings.RUM_APP_DEFAULT_ES_SHARDS,
                    "number_of_replicas": settings.RUM_APP_DEFAULT_ES_REPLICAS,
                }),
                mapping_settings=json.dumps(cls.MAPPING_SETTINGS),
                retention=settings.RUM_APP_DEFAULT_ES_RETENTION,
                slice_gap=60 * 24,
                date_format="%Y%m%d",
                time_zone=0,
            )
            logger.info("[RumPrecalculateStorage] ESStorage record created for existing RT -> %s", table_name)
            return storage
        logger.info("[RumPrecalculateStorage] create result table success -> %s", table_name)
        return ESStorage.objects.filter(table_id=table_name)[0]

    @cached_property
    def helpers(self):
        """不同 ES 版本的 bulk helpers（沿用 APM 的实现，未显式 import 复用 helpers_common）。"""
        if not self.client:
            return None

        from elasticsearch import helpers as helpers_common
        from elasticsearch5 import helpers as helpers_5
        from elasticsearch6 import helpers as helpers_6

        version = self.client.info().get("version", {}).get("number", "")
        if version.startswith("6."):
            return helpers_6
        if version.startswith("5."):
            return helpers_5
        return helpers_common

    def save(self, data):
        if not self.client:
            logger.warning(
                "[RumPrecalculateStorage] %s:%s storage not ready, skip",
                self.bk_biz_id,
                self.app_name,
            )
            return
        self.helpers.bulk(self.client, data, index=self.save_index_name)
        logger.info("[RumPrecalculateStorage] save %d docs success", len(data))

    @classmethod
    def get_index_write_alias(cls, index_name: str) -> str:
        return f"write_{datetime.datetime.now().strftime('%Y%m%d')}_{index_name}"

    @classmethod
    def handle_fields_update(cls, table_kind: str):
        """遍历所有 DataLink 预计算配置，比对字段 / 集群，发现差异则调 modify_result_table 更新。"""
        if table_kind not in ("session", "view"):
            raise ValueError(_("table_kind 必须是 session 或 view"))

        for datalink in DataLink.objects.filter(bk_biz_id__gt=GLOBAL_CONFIG_BK_BIZ_ID):
            cluster_config = (datalink.pre_calculate_config or {}).get("cluster") or []
            for ci in cluster_config:
                table_name: str = ci["table_name"]
                cluster_id: int = ci["cluster_id"]

                # 仅处理当前 table_kind 对应的表（session/view 配置已合并到同一个 cluster 列表）
                if table_kind not in table_name:
                    continue

                storage = ESStorage.objects.filter(table_id=table_name).first()
                if not storage:
                    logger.info(
                        "[RumPrecalculateStorage-CHECK_UPDATE] storage: %s not created, skip",
                        table_name,
                    )
                    continue

                try:
                    info = resource.metadata.query_result_table_source(table_id=table_name)
                    pre_res = cls._exact_unique_data(
                        info["field_list"],
                        RumPrecalculateStorageConfig.RESULT_TABLE_FIELD_MAPPING,
                        key_field="field_name",
                        remove_field="time",
                    )
                    cur_res = cls._exact_unique_data(
                        RumPrecalculateStorageConfig.get_table_schema(table_kind),
                        RumPrecalculateStorageConfig.CHECK_UPDATE_FIELDS,
                        "field_name",
                    )

                    if (
                        count_md5(json.dumps(cur_res, sort_keys=True))
                        != count_md5(json.dumps(pre_res, sort_keys=True))
                    ) or (storage.storage_cluster_id != cluster_id):
                        logger.info("[RumPrecalculateStorage-CHECK_UPDATE] FIELD OR STORAGE UPDATE: %s", table_name)
                        cls.update_result_table(table_name=table_name, storage_cluster_id=cluster_id, table_kind=table_kind)
                    else:
                        logger.info(
                            "[RumPrecalculateStorage-CHECK_UPDATE] result table: %s not changed, skip",
                            table_name,
                        )
                except Exception as e:  # noqa: BLE001
                    logger.warning(
                        "[RumPrecalculateStorage-CHECK_UPDATE] handle rt: %s fields update failed: %s",
                        table_name,
                        e,
                    )

    @classmethod
    def _exact_unique_data(cls, data: list[dict], mapping_or_fields, key_field: str, remove_field: str | None = None) -> dict:
        res: dict[str, dict] = {}
        for i in data:
            item: dict = {}
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
    def update_result_table(cls, table_name: str, storage_cluster_id: int, table_kind: str):
        resource.metadata.modify_result_table(
            {
                "table_id": table_name,
                "bk_tenant_id": DEFAULT_TENANT_ID,
                "operator": get_global_user(),
                "label": "application_check",
                "field_list": [
                    f for f in RumPrecalculateStorageConfig.get_table_schema(table_kind)
                    if f["field_name"].upper() not in RT_RESERVED_WORD_EXACT
                ],
                "external_storage": {
                    "elasticsearch": {
                        "cluster_id": storage_cluster_id,
                        "storage_cluster_id": storage_cluster_id,
                        "slice_size": settings.RUM_APP_DEFAULT_ES_SLICE_LIMIT,
                        "retention": settings.RUM_APP_DEFAULT_ES_RETENTION,
                        "slice_gap": 60 * 24,
                        "date_format": "%Y%m%d",
                        "mapping_settings": cls.MAPPING_SETTINGS,
                        "index_settings": {
                            "number_of_shards": settings.RUM_APP_DEFAULT_ES_SHARDS,
                            "number_of_replicas": settings.RUM_APP_DEFAULT_ES_REPLICAS,
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
        )
        logger.info("[RumPrecalculateStorage] update result table %s success", table_name)
