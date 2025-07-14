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
from collections import defaultdict

import requests
from django.conf import settings
from django.db.models import Q

from metadata import models
from metadata.models.space.constants import (
    DATA_LABEL_TO_RESULT_TABLE_CHANNEL,
    DATA_LABEL_TO_RESULT_TABLE_KEY,
    RESULT_TABLE_DETAIL_CHANNEL,
    RESULT_TABLE_DETAIL_KEY,
    SPACE_REDIS_KEY,
)
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis
from metadata.models.space.utils import reformat_table_id
from metadata.utils.redis_tools import RedisTools

logger = logging.getLogger("metadata")


def get_space_config_from_redis(space_uid: str, table_id: str) -> dict:
    """从 redis 中获取空间配置信息"""
    key = f"{SPACE_REDIS_KEY}:{space_uid}"
    data = RedisTools.hget(key, table_id)
    if not data:
        logger.error("space_uid: %s, table_id: %s not found space config", space_uid, table_id)
        return {}
    # Byte 转换格式，返回数据
    return json.loads(data.decode("utf-8"))


def get_kihan_prom_field_list(domain: str) -> list:
    # NOTE: 因为是临时接口，访问的域名配置到 apigw，通过header 传递进来
    url = f"{domain}/api/v1/targets/metadata"
    params = {"match_target": "{namespace='pg'}"}
    metrics = requests.get(url, params=params).json()
    # 去重
    return list({i["metric"] for i in metrics["data"]})


def push_and_publish_log_space_router(space_type: str, space_id: str):
    """推送并发布es空间路由"""
    client = SpaceTableIDRedis()
    client.push_space_table_ids(space_type=space_type, space_id=space_id, is_publish=True)
    logger.info("push and publish es space router success, space_type: %s, space_id: %s", space_type, space_id)


def push_and_publish_es_aliases(bk_tenant_id: str, data_label: str):
    """推送并发布es别名"""

    # 拆分data_label，去重
    data_label_list: list[str] = list(set([dl for dl in data_label.split(",") if dl]))
    if not data_label_list:
        return

    # 组装查询条件
    data_label_qs: Q = Q(data_label__contains=data_label_list[0])
    for data_label in data_label_list[1:]:
        data_label_qs |= Q(data_label__contains=data_label)

    # 查询结果表
    result_tables = models.ResultTable.objects.filter(
        data_label_qs, bk_tenant_id=bk_tenant_id, is_deleted=False, is_enable=True
    )

    data_label_to_table_ids: dict[str, list[str]] = defaultdict(list)
    for result_table in result_tables:
        # 拆分data_label
        for dl in result_table.data_label.split(","):
            if not dl or dl not in data_label_list:
                continue
            data_label_to_table_ids[dl].append(reformat_table_id(result_table.table_id))

    # 多租户模式下，在data_label前拼接bk_tenant_id
    if settings.ENABLE_MULTI_TENANT_MODE:
        redis_values = {
            f"{dl}|{bk_tenant_id}": json.dumps(table_ids) for dl, table_ids in data_label_to_table_ids.items()
        }
    else:
        redis_values = {dl: json.dumps(table_ids) for dl, table_ids in data_label_to_table_ids.items()}

    RedisTools.hmset_to_redis(DATA_LABEL_TO_RESULT_TABLE_KEY, redis_values)
    RedisTools.publish(DATA_LABEL_TO_RESULT_TABLE_CHANNEL, list(redis_values.keys()))

    logger.info("push and publish es alias, alias: %s", data_label)


def push_and_publish_es_table_id(
    bk_tenant_id: str, table_id: str, index_set: str, source_type: str, cluster_id: int, options: list | None = None
):
    """推送并发布es结果表

    下面的处理方式，交由调用接口端，通过 `option` 进行处理
    - 自有: 追加时间戳和read后缀
    - 数据平台: 追加时间戳
    - 第三方: 不追加任何，直接按照规则处理
    """
    logger.info(
        "push_and_publish_es_table_id: table_id->[%s], index_set->[%s], source_type->[%s]",
        table_id,
        index_set,
        source_type,
    )
    # 组装values，包含 options 字段
    values = {
        "source_type": source_type,
        "storage_id": cluster_id,
        "db": index_set,
        "measurement": "__default__",
        "storage_type": models.ESStorage.STORAGE_TYPE,
        "options": {},
    }
    if options:
        _options = {}
        for option in options:
            try:
                _options[option["name"]] = (
                    option["value"]
                    if option["value_type"] == models.ResultTableOption.TYPE_STRING
                    else json.loads(option["value"])
                )
            except Exception:  # pylint: disable=broad-except
                _options[option["name"]] = {}
        values["options"] = _options

    try:
        logger.info("push_and_publish_es_table_id: table_id->[%s] try to compose storage cluster records", table_id)
        storage_record = models.StorageClusterRecord.compose_table_id_storage_cluster_records(table_id)
    except Exception as e:  # pylint: disable=broad-except
        logger.warning("get table_id storage cluster record failed, table_id: %s, error: %s", table_id, e)
        storage_record = []

    values["storage_cluster_records"] = storage_record

    logger.info("push_and_publish_es_table_id: table_id->[%s] try to hmset to redis with value->[%s]", table_id, values)

    # 若开启多租户模式,则在table_id前拼接bk_tenant_id
    if settings.ENABLE_MULTI_TENANT_MODE:
        redis_value = {f"{table_id}|{bk_tenant_id}": json.dumps(values)}
    else:
        redis_value = {table_id: json.dumps(values)}

    RedisTools.hmset_to_redis(
        RESULT_TABLE_DETAIL_KEY,
        redis_value,
    )
    logger.info(
        "push_and_publish_es_table_id: table_id->[%s] try to publish to channel->[%s]",
        table_id,
        RESULT_TABLE_DETAIL_CHANNEL,
    )
    RedisTools.publish(RESULT_TABLE_DETAIL_CHANNEL, list(redis_value.keys()))

    logger.info(
        "push and publish es table_id detail, table_id: %s, index_set: %s, source_type: %s, cluster_id: %s",
        table_id,
        index_set,
        source_type,
        cluster_id,
    )


def push_and_publish_doris_table_id_detail(
    bk_tenant_id: str,
    table_id: str,
):
    """
    推送并发布doris结果表路由
    """
    logger.info("push_and_publish_doris_table_id_detail: table_id->[%s]", table_id)

    try:
        result_table = models.ResultTable.objects.get(table_id=table_id, bk_tenant_id=bk_tenant_id)
        doris_storage = models.DorisStorage.objects.get(table_id=table_id, bk_tenant_id=bk_tenant_id)
    except Exception as e:
        logger.error(
            "push_and_publish_doris_table_id_detail: table_id->[%s] get result table or doris storage "
            "failed, error: [%s]",
            table_id,
            e,
        )
        raise ValueError(f"get result table or doris storage failed, table_id:{table_id}")

    values = {
        "db": doris_storage.bkbase_table_id,
        "measurement": models.ClusterInfo.TYPE_DORIS,
        "storage_type": "bk_sql",
        "data_label": result_table.data_label,
    }

    # 若开启多租户模式,则在table_id前拼接bk_tenant_id
    if settings.ENABLE_MULTI_TENANT_MODE:
        redis_value = {f"{bk_tenant_id}|{table_id}": json.dumps(values)}
    else:
        redis_value = {table_id: json.dumps(values)}

    RedisTools.hmset_to_redis(
        RESULT_TABLE_DETAIL_KEY,
        redis_value,
    )
    RedisTools.publish(RESULT_TABLE_DETAIL_CHANNEL, list(redis_value.keys()))
    logger.info("push and publish doris table_id detail successfully, table_id->[%s]", table_id)
