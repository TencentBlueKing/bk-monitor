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
import hashlib
import json
import logging
import re
from typing import Dict, Optional

from django.conf import settings
from jinja2 import Template
from tenacity import retry, stop_after_attempt, wait_exponential

from core.drf_resource import api
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


def compose_bkdata_table_id(table_id: str, strategy: str = None) -> str:
    """
    获取计算平台结果表ID, 计算平台元数据长度限制为40，不可超出
    @param table_id: 监控平台结果表ID
    @param strategy: 链路策略
    """
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

    # 计算哈希值, 采用 hash 方式确保 table_id 唯一
    hash_suffix = hashlib.md5(table_id.encode()).hexdigest()[:5]

    # 添加 `_fed` 后缀（如果 strategy 为 `bcs_federal_subset_time_series`）
    if strategy == 'bcs_federal_subset_time_series':
        table_id = table_id + '_fed'

    # 如果长度超过 40，截断并确保末尾包含 `_fed` 后缀
    if len(table_id) > 40:
        if strategy == 'bcs_federal_subset_time_series':
            table_id = f'{table_id[:33]}_{hash_suffix}_fed'
        else:
            table_id = f'{table_id[:34]}_{hash_suffix}'

    return table_id


def parse_and_get_rt_biz_id(table_id: str) -> int:
    """
    解析并获取监控平台结果表的业务ID信息
    @param table_id: 监控平台结果表ID
    @return: 业务ID
    """
    match = re.match(r'^(\d+)', table_id)
    if match:
        # 如果匹配成功，返回数字部分并转换为整数
        return int(match.group(1))
    else:
        return settings.DEFAULT_BKDATA_BIZ_ID


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


def compose_bkdata_data_id_name(data_name: str, strategy: str = None) -> str:
    """
    组装bkdata数据源名称
    @param data_name: 监控平台数据源名称
    @param strategy: 链路策略
    """
    # 剔除不符合的字符
    refine_data_name = re.sub(MATCH_DATA_NAME_PATTERN, '', data_name)
    # 替换连续的下划线为单个下划线
    data_id_name = f"bkm_{re.sub(r'_+', '_', refine_data_name)}"

    # 控制长度
    if len(refine_data_name) > 45:
        # 截取长度为45的字符串
        truncated_name = refine_data_name[-39:].lower().strip('_')
        # 计算哈希值
        hash_suffix = hashlib.md5(refine_data_name.encode()).hexdigest()[:5]
        data_id_name = f"bkm_{truncated_name}_{hash_suffix}"
    # 拼装前缀和哈希值
    if strategy == models.DataLink.BCS_FEDERAL_SUBSET_TIME_SERIES:
        data_id_name = 'fed_' + data_id_name
    return data_id_name


def get_bkbase_raw_data_id_name(data_source, table_id):
    """
    获取计算平台对应的data_id_name，适配V3迁移V4场景
    @param data_source: 数据源
    @param table_id: 监控平台结果表ID
    """
    try:
        bkbase_data_id = models.AccessVMRecord.objects.get(result_table_id=table_id).bk_base_data_id
        raw_data_name = api.bkdata.get_bkbase_raw_data_with_data_id(bkbase_data_id=bkbase_data_id).get('raw_data_name')
    except Exception as e:  # pylint: disable=broad-except
        logger.info(
            "get_bkbase_raw_data_id_name: data_source->[%s] table_id->[%s] error->[%s],use new rule to "
            "generate data_id_name",
            data_source,
            table_id,
            e,
        )
        raw_data_name = compose_bkdata_data_id_name(data_source.data_name)

    logger.info(
        "get_bkbase_raw_data_id_name: data_source->[%s] table_id->[%s] raw_data_name->[%s]",
        data_source,
        table_id,
        raw_data_name,
    )

    return raw_data_name


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=1, max=10))
def get_bkbase_raw_data_name_for_v3_datalink(bkbase_data_id):
    """
    获取计算平台对应的data_id_name，适配V3迁移V4场景，具备重试能力
    @param bkbase_data_id: 计算平台数据源ID
    """
    try:
        raw_data_name = api.bkdata.get_bkbase_raw_data_with_data_id(bkbase_data_id=bkbase_data_id).get('raw_data_name')
        return raw_data_name
    except Exception as e:  # pylint: disable=broad-except
        logger.info("get_bkbase_raw_data_name_for_v3_datalink: bkbase_data_id->[%s] error->[%s]", bkbase_data_id, e)
        raise e


def is_k8s_metric_data_id(data_name: str) -> bool:
    """判断是否为k8s指标数据源"""
    try:
        obj = models.DataSource.objects.get(data_name=data_name)
    except models.DataSource.DoesNotExist:
        raise ValueError(f"data_name {data_name} not exist")
    data_id = obj.bk_data_id

    return models.BCSClusterInfo.objects.filter(K8sMetricDataID=data_id).exists()
