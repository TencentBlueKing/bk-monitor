import json
import logging
from collections import defaultdict
from typing import Any

import requests
from django.db.models import Q

from bk_monitor_base.metadata import models
from bk_monitor_base.metadata.config import settings
from bk_monitor_base.metadata.models.space.constants import (
    DATA_LABEL_TO_RESULT_TABLE_CHANNEL,
    DATA_LABEL_TO_RESULT_TABLE_KEY,
    SPACE_REDIS_KEY,
)
from bk_monitor_base.metadata.models.space.utils import reformat_table_id
from bk_monitor_base.metadata.utils.redis_tools import RedisTools

logger = logging.getLogger("metadata")


def get_space_config_from_redis(space_uid: str, table_id: str) -> dict[str, Any]:
    """从 redis 中获取空间配置信息"""
    key = f"{SPACE_REDIS_KEY}:{space_uid}"
    data = RedisTools.hget(key, table_id)
    if not data:
        logger.error("space_uid: %s, table_id: %s not found space config", space_uid, table_id)
        return {}
    # Byte 转换格式，返回数据
    return json.loads(data.decode("utf-8"))


def get_kihan_prom_field_list(domain: str) -> list[str]:
    # NOTE: 因为是临时接口，访问的域名配置到 apigw，通过header 传递进来
    url = f"{domain}/api/v1/targets/metadata"
    params = {"match_target": "{namespace='pg'}"}
    metrics = requests.get(url, params=params).json()
    # 去重
    return list({i["metric"] for i in metrics["data"]})


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
    if settings.blueking.enable_multi_tenancy:
        redis_values = {
            f"{dl}|{bk_tenant_id}": json.dumps(table_ids) for dl, table_ids in data_label_to_table_ids.items()
        }
    else:
        redis_values = {dl: json.dumps(table_ids) for dl, table_ids in data_label_to_table_ids.items()}

    RedisTools.hmset_to_redis(DATA_LABEL_TO_RESULT_TABLE_KEY, redis_values)
    RedisTools.publish(DATA_LABEL_TO_RESULT_TABLE_CHANNEL, list(redis_values.keys()))

    logger.info("push and publish es alias, alias: %s", data_label)
