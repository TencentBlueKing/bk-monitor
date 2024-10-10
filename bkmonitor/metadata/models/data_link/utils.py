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

from metadata import models
from metadata.models.data_link.constants import MATCH_DATA_NAME_PATTERN

logger = logging.getLogger("metadata")


def get_bkdata_table_id(table_id: str) -> str:
    """获取计算平台结果表"""
    # 按照 '__default__' 截断，取前半部分
    table_id = table_id.split(".__default__")[0]
    table_id = table_id.lower()

    # 转换中划线和点为下划线
    table_id = table_id.replace('-', '_').replace('.', '_')

    # 处理负数开头和其他情况
    if table_id.startswith('_'):
        table_id = f'bkm_neg_{table_id.lstrip("_")}'
    elif table_id[0].isdigit():
        table_id = f'bkm_{table_id}'
    else:
        table_id = f'bkm_{table_id}'

    # 确保不会出现连续的下划线
    while '__' in table_id:
        table_id = table_id.replace('__', '_')

    # 确保长度不超过40
    return table_id[:40]


def get_bkdata_data_id_name_v3(vm_rt: str) -> str:
    """获取V3链路在计算平台对应的data_id_name"""
    processed_table_id = vm_rt.split("_")[1:]
    result = "_".join(processed_table_id)
    return result


def compose_config(tpl: str, render_params: Dict, err_msg_prefix: Optional[str] = "compose config") -> Dict:
    """渲染配置模板"""
    content = Template(tpl).render(**render_params)
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        logger.error("%s parse data_id config error: %s", err_msg_prefix, e)
        return {}


def get_bkdata_data_id_name(data_name: str) -> str:
    # 剔除不符合的字符
    refine_data_name = re.sub(MATCH_DATA_NAME_PATTERN, '', data_name)
    # 截取长度为45的字符串，同时拼装前缀
    return f"bkm_{refine_data_name[-45:].lower()}"


def is_k8s_metric_data_id(data_name: str) -> bool:
    """判断是否为k8s指标数据源"""
    try:
        obj = models.DataSource.objects.get(data_name=data_name)
    except models.DataSource.DoesNotExist:
        raise ValueError(f"data_name {data_name} not exist")
    data_id = obj.bk_data_id

    return models.BCSClusterInfo.objects.filter(K8sMetricDataID=data_id).exists()
