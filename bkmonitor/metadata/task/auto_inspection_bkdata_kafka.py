# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import logging

from django.conf import settings

from metadata import models
from metadata.resources import CheckOrCreateKafkaStorageResource

logger = logging.getLogger("metadata")

NEED_CHECK_PLUGIN_TYPE = [
    "exporter",
    "script",
    "jmx",
    "datadog",
    "pushgateway",
    "process",
    "snmp",
]


def auto_inspect_bk_data_kafka_storage():
    table_ids = []

    logger.info("start inspection kafka and bk_data storage")
    # 1. 根据插件type查找出对应的result_table
    for plugin_type in NEED_CHECK_PLUGIN_TYPE:
        result_table_queryset = models.ResultTable.objects.filter(
            table_id__startswith="%s" % plugin_type, is_deleted=False
        )
        table_ids.extend(result_table_queryset.values_list("table_id", flat=True))

    if settings.IS_ACCESS_BK_DATA:
        # 2. 获取ids之后，通过CheckOrCreateKafkaStorageResource查看是否存在对应的kafka，如果不存在则直接创建
        logger.info("start check kafka storage")
        CheckOrCreateKafkaStorageResource().perform_request(validated_request_data={"table_ids": table_ids})
        for table_id in table_ids:
            logger.info("start create bk_data storage: table_id({})".format(table_id))
            try:
                models.storage.BkDataStorage.create_table(table_id, is_sync_db=True, is_access_now=True)
                models.ResultTable.objects.get(table_id=table_id).refresh_etl_config()
            except Exception as e:
                msg = "create bk_data storage error:%s" % e
                logger.exception(msg)
    logger.info("end inspection")


def access_with_tables(tables):
    if not settings.IS_ACCESS_BK_DATA:
        return
    if not hasattr(tables, "__iter__"):
        tables = [tables]
    logger.info("start check kafka storage")
    CheckOrCreateKafkaStorageResource().perform_request(validated_request_data={"table_ids": tables})
    for table_id in tables:
        logger.info("start create bk_data storage: table_id({})".format(table_id))
        try:
            models.storage.BkDataStorage.create_table(table_id, is_sync_db=True, is_access_now=True)
            models.ResultTable.objects.get(table_id=table_id).refresh_etl_config()
        except Exception as e:
            msg = "create bk_data storage error:%s" % e
            logger.exception(msg)
    logger.info("end inspection")
