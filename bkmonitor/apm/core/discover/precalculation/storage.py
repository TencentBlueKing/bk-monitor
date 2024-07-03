# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - Resource SDK (BlueKing - Resource SDK) available.
Copyright (C) 2022 THL A29 Limited,
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
import os
import traceback

from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from elasticsearch import helpers as helpers_common
from elasticsearch5 import helpers as helpers_5
from elasticsearch6 import helpers as heplers_6

from apm.core.handlers.application_hepler import ApplicationHelper
from apm.models import DataLink
from bkmonitor.utils.common_utils import count_md5
from bkmonitor.utils.user import get_global_user
from constants.apm import PreCalculateSpecificField
from constants.data_source import DataSourceLabel, DataTypeLabel
from constants.result_table import ResultTableField
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
            combined = f'{node}:{key}'
            hash_val = hashlib.sha1(combined.encode()).hexdigest()
            weight = int(hash_val, 16)

            if max_weight is None or weight > max_weight:
                max_weight = weight
                max_node = node

        return max_node


class PrecalculateStorage:
    """预计算存储类"""

    TABLE_SCHEMA = [
        {
            "field_name": PreCalculateSpecificField.BIZ_ID.value,
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "keyword"},
            "is_config_by_user": True,
            "description": "Bk Biz Id",
        },
        {
            "field_name": PreCalculateSpecificField.BIZ_NAME.value,
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "keyword"},
            "is_config_by_user": True,
            "description": "Bk Biz Name",
        },
        {
            "field_name": PreCalculateSpecificField.APP_ID.value,
            "field_type": ResultTableField.FIELD_TYPE_INT,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "integer"},
            "is_config_by_user": True,
            "description": "App Id",
        },
        {
            "field_name": PreCalculateSpecificField.APP_NAME.value,
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "keyword"},
            "is_config_by_user": True,
            "description": "App Name",
        },
        {
            "field_name": PreCalculateSpecificField.TRACE_ID.value,
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "keyword"},
            "is_config_by_user": True,
            "description": "Trace ID",
        },
        {
            "field_name": PreCalculateSpecificField.HIERARCHY_COUNT.value,
            "field_type": ResultTableField.FIELD_TYPE_INT,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "integer"},
            "is_config_by_user": True,
            "description": "Hierarchy Count",
        },
        {
            "field_name": PreCalculateSpecificField.SERVICE_COUNT.value,
            "field_type": ResultTableField.FIELD_TYPE_INT,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "integer"},
            "is_config_by_user": True,
            "description": "Service Count",
        },
        {
            "field_name": PreCalculateSpecificField.SPAN_COUNT.value,
            "field_type": ResultTableField.FIELD_TYPE_INT,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "integer"},
            "is_config_by_user": True,
            "description": "Span Count",
        },
        {
            "field_name": PreCalculateSpecificField.MIN_START_TIME.value,
            "field_type": ResultTableField.FIELD_TYPE_LONG,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "long"},
            "is_config_by_user": True,
            "description": "Min Start Time",
        },
        {
            "field_name": PreCalculateSpecificField.MAX_END_TIME.value,
            "field_type": ResultTableField.FIELD_TYPE_LONG,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "long"},
            "is_config_by_user": True,
            "description": "Max End Time",
        },
        {
            "field_name": PreCalculateSpecificField.TRACE_DURATION.value,
            "field_type": ResultTableField.FIELD_TYPE_LONG,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "long"},
            "is_config_by_user": True,
            "description": "Trace Duration",
        },
        {
            "field_name": PreCalculateSpecificField.SPAN_MAX_DURATION.value,
            "field_type": ResultTableField.FIELD_TYPE_LONG,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "long"},
            "is_config_by_user": True,
            "description": "Span Max Duration",
        },
        {
            "field_name": PreCalculateSpecificField.SPAN_MIN_DURATION.value,
            "field_type": ResultTableField.FIELD_TYPE_LONG,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "long"},
            "is_config_by_user": True,
            "description": "Span Min Duration",
        },
        {
            "field_name": PreCalculateSpecificField.ROOT_SERVICE.value,
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "keyword"},
            "is_config_by_user": True,
            "description": "Entry Service",
        },
        {
            "field_name": PreCalculateSpecificField.ROOT_SERVICE_SPAN_ID.value,
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "keyword"},
            "is_config_by_user": True,
            "description": "Root Service Span Id",
        },
        {
            "field_name": PreCalculateSpecificField.ROOT_SERVICE_SPAN_NAME.value,
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "keyword"},
            "is_config_by_user": True,
            "description": "Root Service Span Name",
        },
        {
            "field_name": PreCalculateSpecificField.ROOT_SERVICE_STATUS_CODE.value,
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "keyword"},
            "is_config_by_user": True,
            "description": "Root Service Status Code",
        },
        {
            "field_name": PreCalculateSpecificField.ROOT_SERVICE_CATEGORY.value,
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "keyword"},
            "is_config_by_user": True,
            "description": "Root Service Category",
        },
        {
            "field_name": PreCalculateSpecificField.ROOT_SERVICE_KIND.value,
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "keyword"},
            "is_config_by_user": True,
            "description": "Root Service Kind",
        },
        {
            "field_name": PreCalculateSpecificField.ROOT_SPAN_ID.value,
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "keyword"},
            "is_config_by_user": True,
            "description": "Root Span Id",
        },
        {
            "field_name": PreCalculateSpecificField.ROOT_SPAN_NAME.value,
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "keyword"},
            "is_config_by_user": True,
            "description": "Root Span Name",
        },
        {
            "field_name": PreCalculateSpecificField.ROOT_SPAN_SERVICE.value,
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "keyword"},
            "is_config_by_user": True,
            "description": "Root Span Service",
        },
        {
            "field_name": PreCalculateSpecificField.ROOT_SPAN_KIND.value,
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "keyword"},
            "is_config_by_user": True,
            "description": "Root Span Kind",
        },
        {
            "field_name": PreCalculateSpecificField.ERROR.value,
            "field_type": ResultTableField.FIELD_TYPE_BOOLEAN,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "boolean"},
            "is_config_by_user": True,
            "description": "error",
        },
        {
            "field_name": PreCalculateSpecificField.ERROR_COUNT.value,
            "field_type": ResultTableField.FIELD_TYPE_INT,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "integer"},
            "is_config_by_user": True,
            "description": "Error Count",
        },
        {
            "field_name": PreCalculateSpecificField.CATEGORY_STATISTICS.value,
            "field_type": ResultTableField.FIELD_TYPE_OBJECT,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "object", "es_dynamic": True},
            "is_config_by_user": True,
            "description": "Span分类统计",
        },
        {
            "field_name": PreCalculateSpecificField.KIND_STATISTICS.value,
            "field_type": ResultTableField.FIELD_TYPE_OBJECT,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "object", "es_dynamic": True},
            "is_config_by_user": True,
            "description": "Span类型统计",
        },
        {
            "field_name": PreCalculateSpecificField.COLLECTIONS.value,
            "field_type": ResultTableField.FIELD_TYPE_OBJECT,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "object", "es_dynamic": True},
            "is_config_by_user": True,
            "description": "常见标准字段数据",
        },
    ]

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

    def __init__(self, bk_biz_id, app_name):
        self.bk_biz_id = bk_biz_id
        self.app_name = app_name
        self.hash_ring, self.node_mapping, self.id_mapping = self.list_nodes(bk_biz_id)
        (
            self.search_index_name,
            self.save_index_name,
            self.client,
            self.storage_cluster_id,
            self.origin_index_name,
        ) = self.select_and_get_storage_client()
        self.helpers = self.get_es_helpers()
        self.is_valid = bool(self.client)

    def select_and_get_storage_client(self):
        if not self.hash_ring:
            return None, None, None, None, None

        node = self.hash_ring.select_node(self.bk_biz_id, self.app_name)
        table_name = node.split('-', 1)[-1].replace('.', '_')

        return (
            f"{table_name}*",
            self.get_index_write_alias(table_name),
            self.node_mapping[node],
            self.id_mapping[node],
            table_name,
        )

    @classmethod
    def _create_default(cls, bk_biz_id, datalink):
        """当预计算配置不存在时 基于默认存储创建索引"""

        default_storage_id = ApplicationHelper.get_default_cluster_id(bk_biz_id)
        if not default_storage_id:
            logger.warning(f"[PreCalculate] not found default storage, skip create config")
            return None

        pre_calculate_config = {"cluster": []}

        prefix = f"apm_global.precalculate_storage_auto_{{index}}"

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
    def list_nodes(cls, bk_biz_id):
        datalink = DataLink.get_data_link(bk_biz_id)
        if not datalink or not datalink.pre_calculate_config:
            try:
                datalink = cls._create_default(bk_biz_id, datalink)
                if not datalink:
                    return None, None, None
            except Exception as e:  # noqa
                logger.exception(f"[PreCalculate] create default storage failed, {e} detail: {traceback.format_exc()}")
                return None, None, None

        cluster_config = datalink.pre_calculate_config.get("cluster")
        if not cluster_config:
            return None, None, None

        nodes = []
        node_mapping = {}
        id_mapping = {}
        for i in cluster_config:
            key = f"{i['cluster_id']}-{i['table_name']}"
            instance = ESStorage.objects.filter(table_id=i["table_name"]).first()

            if not instance:
                try:
                    instance = cls.create_storage_table(i["cluster_id"], i["table_name"])
                    client = instance.get_client()
                except Exception as e:  # noqa
                    logger.exception(
                        f"[PreCalculate] create storage table failed. "
                        f"except to create: {i['table_name']} in storageId: {i['cluster_id']}, ignore. \n"
                        f"{traceback.format_exc()}"
                    )
                    continue
            else:
                try:
                    client = instance.get_client()
                except Exception as e:  # noqa
                    logger.exception(
                        f"[PreCalculate] get storage client failed. "
                        f"except to get storageId: {instance.storage_cluster_id} client, ignore. \n"
                        f"{traceback.format_exc()}"
                    )
                    continue

            if client:
                nodes.append(key)
                node_mapping[key] = client
                id_mapping[key] = instance.storage_cluster_id

        if not nodes or not node_mapping or not id_mapping:
            logger.warning(
                f"[PreCalculate] find storage config(dataId: {datalink.id}), "
                f"but completely get failed, preStorage not work"
            )
            return None, None, None

        return RendezvousHash(nodes), node_mapping, id_mapping

    def get_index_write_alias(self, index_name):
        return f"write_{datetime.datetime.now().strftime('%Y%m%d')}_{index_name}"

    @classmethod
    def create_storage_table(cls, storage_id, table_name):
        bk_data_id = cls.create_data_id(table_name)
        resource.metadata.create_result_table(
            {
                "bk_data_id": bk_data_id,
                "table_id": table_name,
                "operator": get_global_user(),
                "is_enable": True,
                "table_name_zh": f"APM预计算结果表: {table_name}",
                "is_custom_table": True,
                "schema_type": "free",
                "default_storage": "elasticsearch",
                "default_storage_config": {
                    "cluster_id": storage_id,
                    "storage_cluster_id": storage_id,
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
                "field_list": cls.TABLE_SCHEMA,
                "is_time_field_only": True,
                "label": "application_check",
                "option": {},
                "time_option": {
                    "es_type": "date",
                    "es_format": "epoch_millis",
                    "time_format": "yyyy-MM-dd HH:mm:ss",
                    "time_zone": 0,
                },
            }
        )
        logger.info(f"[PrecalculateStorage] create result table success -> {table_name}")

        return ESStorage.objects.filter(table_id=table_name).first()

    @classmethod
    def create_data_id(cls, table_name):
        try:
            instance = api.metadata.create_data_id(
                {
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

    def get_es_helpers(self):
        if not self.client:
            return None

        version = self.client.info().get("version", {}).get("number", "")
        helpers = helpers_common
        if version.startswith("6."):
            helpers = heplers_6
        elif version.startswith("5."):
            helpers = helpers_5

        return helpers

    def save(self, data):
        if not self.client:
            logger.warning(f"[PrecalculateStorage] {self.bk_biz_id}: {self.app_name} storage not ready, skip")
            return

        self.helpers.bulk(self.client, data, index=self.save_index_name)
        logger.info(f"[PrecalculateStorage] save {len(data)} success")

    @classmethod
    def get_search_mapping(cls, bk_biz_id):
        def can_combine(index_names):
            """只有索引名称长度一致并且只有最后一个字符不相同 才合并名称"""

            def is_same_length(strings):
                length = len(strings[0])
                for string in strings:
                    if len(string) != length:
                        return False
                return True

            def is_last_char_diff(strings):
                for i in range(len(strings) - 1):
                    diff_count = 0
                    for j in range(len(strings[0])):
                        if strings[i][j] != strings[i + 1][j]:
                            diff_count += 1
                    if diff_count != 1:
                        return False
                return True

            if not index_names:
                return False

            if is_same_length(index_names) and is_last_char_diff(index_names):
                return True
            else:
                return False

        _, node_mapping, _ = cls.list_nodes(bk_biz_id)
        res = {}

        cluster_mapping = {}
        for k, v in node_mapping.items():
            parts = k.split("-", 1)
            cluster_id = parts[0]
            index_name = parts[-1].replace('.', '_')
            if cluster_id in cluster_mapping:
                cluster_mapping[cluster_id]["tables"].append(index_name)
            else:
                cluster_mapping[cluster_id] = {"client": v, "tables": [index_name]}

        for cluster, index_info in cluster_mapping.items():
            is_combine = can_combine(index_info["tables"])
            if not is_combine:
                logger.info(f"[PreCalculate] table_name not have common prefix, will not combine indexes")
                for t in index_info["tables"]:
                    res[f"{t}*"] = index_info["client"]
            else:
                prefix = os.path.commonprefix(index_info["tables"])
                res[f"{prefix}*"] = index_info["client"]

        return res

    @classmethod
    def handle_fields_update(cls):
        """
        检查预计算表字段是否有更新/集群变动 如果有则更新
        """
        for i in DataLink.objects.all():
            cluster_config = i.pre_calculate_config.get("cluster")
            if not cluster_config:
                logger.info(f"[PreCalculateStorage-CHECK_UPDATE] not found config in dataLinkId: {i.id}")
                continue

            for j in cluster_config:
                instance = ESStorage.objects.filter(table_id=j['table_name']).first()
                if not instance:
                    logger.info(f"[PreCalculateStorage-CHECK_UPDATE] storage: {j['table_name']} not created, skip")
                    continue

                try:
                    info = resource.metadata.query_result_table_source(table_id=j["table_name"])
                    pre_res = cls._exact_unique_data(
                        info["field_list"], cls.RESULT_TABLE_FIELD_MAPPING, key_field="field_name", remove_field="time"
                    )
                    cur_res = cls._exact_unique_data(cls.TABLE_SCHEMA, cls.CHECK_UPDATE_FIELDS, "field_name")

                    # 如果字段有更新 或者 存储集群变动 则更新
                    if (
                        count_md5(json.dumps(cur_res, sort_keys=True)) != count_md5(json.dumps(pre_res, sort_keys=True))
                    ) or (instance.storage_cluster_id != j["cluster_id"]):
                        logger.info(f"[PreCalculateStorage-CHECK_UPDATE] FIELD OR STORAGE UPDATE!")
                        cls.update_result_table(j["table_name"], j["cluster_id"])
                    else:
                        logger.info(
                            f"[PreCalculateStorage-CHECK_UPDATE] "
                            f"result table: {j['table_name']} not changed, skip update"
                        )
                except Exception as e:  # noqa
                    logger.warning(
                        f"[PreCalculateStorage-CHECK_UPDATE] " f"handle rt: {j['table_name']} fields update failed: {e}"
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
            "operator": get_global_user(),
            "label": "application_check",
            "field_list": cls.TABLE_SCHEMA,
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
