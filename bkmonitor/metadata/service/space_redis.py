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

from metadata.models.space.constants import SPACE_REDIS_KEY
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
