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
import re
from typing import Dict, Optional

from jinja2 import Template

from core.drf_resource import api
from metadata.models.data_link import resource
from metadata.models.data_link.constants import (
    DEFAULT_BKDATA_NAMESPACE,
    MATCH_DATA_NAME_PATTERN,
    DataLinkKind,
    DataLinkResourceStatus,
)

logger = logging.getLogger("metadata")


def get_bkdata_table_id(table_id: str) -> str:
    """获取计算平台结果表"""
    # NOTE: 如果以 '__default__'结尾，则取前半部分
    if table_id.endswith("__default__"):
        table_id = table_id.split(".__default__")[0]
    # 转换中划线为下划线，
    name = f"{table_id.replace('-', '_').replace('.', '_').replace('__', '_')[-40:]}"
    # NOTE: 不能以数字，添加一个默认前缀
    return f"bkm_{name}"


def compose_config(tpl: str, render_params: Dict, err_msg_prefix: Optional[str] = "compose config") -> Dict:
    """渲染配置模板"""
    content = Template(tpl).render(**render_params)
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        logger.error("%s parse data_id config error: %s", err_msg_prefix, e)
        return {}


def get_data_id_name_by_data_name(data_name: str) -> str:
    # 剔除不符合的字符
    refine_data_name = re.sub(MATCH_DATA_NAME_PATTERN, '', data_name)
    # 截取长度为45的字符串，同时拼装前缀
    return f"bkm_{refine_data_name[-45:]}"


def apply_data_id(data_name: str) -> bool:
    """下发 data_id 资源"""
    data_id_name = get_data_id_name_by_data_name(data_name)
    data_id_config = resource.DataLinkResourceConfig.compose_data_id_config(data_id_name)
    if not data_id_config:
        return False
    # 调用接口创建 data_id 资源
    api.bkdata.apply_data_link(data_id_config)
    return True


def get_data_id(data_name: str, namespace: Optional[str] = DEFAULT_BKDATA_NAMESPACE) -> Dict:
    """获取数据源对应的 data_id"""
    data_id_name = get_data_id_name_by_data_name(data_name)
    data_id_config = api.bkdata.get_data_link(kind=DataLinkKind.DATAID.value, namespace=namespace, name=data_id_name)
    # 解析数据获取到数据源ID
    phase = data_id_config.get("status", {}).get("phase")
    # 如果状态不是处于正常的终态，则返回 None
    if phase == DataLinkResourceStatus.OK.value:
        return {"status": phase, "data_id": data_id_config.get("metadata", {}).get("annotations", {}).get("data_id")}

    return {"status": phase, "data_id": None}
