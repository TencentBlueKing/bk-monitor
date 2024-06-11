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
import json
import logging
from typing import Dict, List

import requests

from metadata import models
from metadata.models.constants import EsSourceType
from metadata.models.space.constants import (
    DATA_LABEL_TO_RESULT_TABLE_CHANNEL,
    DATA_LABEL_TO_RESULT_TABLE_KEY,
    RESULT_TABLE_DETAIL_CHANNEL,
    RESULT_TABLE_DETAIL_KEY,
    SPACE_REDIS_KEY,
    SPACE_TO_RESULT_TABLE_CHANNEL,
    SPACE_TO_RESULT_TABLE_KEY,
    SpaceTypes,
)
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis
from metadata.utils.redis_tools import RedisTools

logger = logging.getLogger("metadata")


def get_space_config_from_redis(space_uid: str, table_id: str) -> Dict:
    """从 redis 中获取空间配置信息"""
    key = f"{SPACE_REDIS_KEY}:{space_uid}"
    data = RedisTools.hget(key, table_id)
    if not data:
        logger.error("space_uid: %s, table_id: %s not found space config", space_uid, table_id)
        return {}
    # Byte 转换格式，返回数据
    return json.loads(data.decode("utf-8"))


def get_kihan_prom_field_list(domain: str) -> List:
    # NOTE: 因为是临时接口，访问的域名配置到 apigw，通过header 传递进来
    url = f"{domain}/api/v1/targets/metadata"
    params = {"match_target": "{namespace='pg'}"}
    metrics = requests.get(url, params=params).json()
    # 去重
    return list({i["metric"] for i in metrics["data"]})


def push_and_publish_es_space_router(space_type: str, space_id: str, table_id: str):
    """推送并发布es空间路由"""
    client = SpaceTableIDRedis()
    if space_type == SpaceTypes.BKCC.value:
        values = client._push_bkcc_space_table_ids(space_type, space_id, can_push_data=False)
    elif space_type == SpaceTypes.BKCI.value:
        values = client._push_bkci_space_table_ids(space_type, space_id, can_push_data=False)
    elif space_type == SpaceTypes.BKSAAS.value:
        values = client._push_bksaas_space_table_ids(space_type, space_id, table_id, can_push_data=False)
    else:
        logger.error("not found space_type: %s, space_id: %s", space_type, space_id)
        raise ValueError("not found space type")

    # 推送并发布
    space_uid = f"{space_type}__{space_id}"
    RedisTools.hmset_to_redis(SPACE_TO_RESULT_TABLE_KEY, {space_uid: json.dumps(values)})
    RedisTools.publish(SPACE_TO_RESULT_TABLE_CHANNEL, [space_uid])

    logger.info("push and publish es space router success, space_type: %s, space_id: %s", space_type, space_id)


def push_and_publish_es_aliases(data_label: str):
    """推送并发布es别名"""
    if not data_label:
        return
    # 为避免覆盖，重新获取一遍数据
    table_id_list = list(models.ResultTable.objects.filter(data_label=data_label).values_list("table_id", flat=True))
    RedisTools.hmset_to_redis(DATA_LABEL_TO_RESULT_TABLE_KEY, {data_label: json.dumps(table_id_list)})
    RedisTools.publish(DATA_LABEL_TO_RESULT_TABLE_CHANNEL, [data_label])

    logger.info("push and publish es alias, alias: %s", data_label)


def push_and_publish_es_table_id(table_id: str, index_set: str, source_type: str, cluster_id: str):
    """推送并发布es结果表

    - 自有: 追加时间戳和read后缀
    - 数据平台: 追加时间戳
    - 第三方: 不追加任何，直接按照规则处理
    """
    table_id_db = ""
    # 针对内建的索引，如果没有设置索引集，则按照结果表获取查询规则
    if source_type == EsSourceType.LOG.value:
        _index_list = index_set.split(",") if index_set else [table_id]
        table_id_db = ",".join([f"{index.replace('.', '_')}_*_read" for index in _index_list])
    elif source_type == EsSourceType.BKDATA.value:
        _index_list = index_set.split(",")
        table_id_db = ",".join([f"{index}_*" for index in _index_list])
    else:
        table_id_db = index_set

    if not table_id_db:
        logger.error("compose table_id_db failed, index_set: %s", index_set)
        return

    RedisTools.hmset_to_redis(
        RESULT_TABLE_DETAIL_KEY,
        {table_id: json.dumps({"storage_id": cluster_id, "db": table_id_db, "measurement": ""})},
    )
    RedisTools.publish(RESULT_TABLE_DETAIL_CHANNEL, [table_id])

    logger.info(
        "push and publish es table_id detail, table_id: %s, index_set: %s, source_type: %s, cluster_id: %s",
        table_id,
        index_set,
        source_type,
        cluster_id,
    )
