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

from django.conf import settings
from jinja2.sandbox import SandboxedEnvironment as Environment
from pypinyin import lazy_pinyin
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
    table_id = table_id.replace("-", "_").replace(".", "_")

    # 处理负数开头和其他情况
    if table_id.startswith("_"):
        table_id = f"bkm_neg_{table_id.lstrip('_')}"
    elif table_id[0].isdigit():
        table_id = f"bkm_{table_id}"
    else:
        table_id = f"bkm_{table_id}"

    # 确保不会出现连续的下划线
    while "__" in table_id:
        table_id = table_id.replace("__", "_")

    # 确保长度不超过40
    return table_id[:40]


def clean_redundant_underscores(table_id: str) -> str:
    """
    清理连续的下划线，确保只保留单个下划线
    """
    while "__" in table_id:
        table_id = table_id.replace("__", "_")
    table_id = table_id.rstrip("_")
    return table_id


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
    table_id = table_id.replace("-", "_").replace(".", "_")

    # 检测并处理中文字符，将其转换为拼音
    chinese_characters = "".join(char for char in table_id if "\u4e00" <= char <= "\u9fff")
    if chinese_characters:
        table_id = "".join("".join(lazy_pinyin(char)) if "\u4e00" <= char <= "\u9fff" else char for char in table_id)

    # 处理负数开头和其他特殊情况
    if table_id.startswith("_"):
        table_id = f"bkm_neg_{table_id.lstrip('_')}"
    else:
        table_id = f"bkm_{table_id}"

    # 计算哈希值, 采用 hash 方式确保 table_id 唯一
    hash_suffix = hashlib.md5(table_id.encode()).hexdigest()[:5]

    # 添加 `_fed` 后缀（如果 strategy 为 `bcs_federal_subset_time_series`）
    suffix = "_fed" if strategy == models.DataLink.BCS_FEDERAL_SUBSET_TIME_SERIES else ""
    base_length = 40 - len(suffix) - 6  # 留出哈希值和下划线的长度

    # 如果长度超过限制，截断并添加哈希值和后缀
    if len(table_id) + len(suffix) > 40:
        table_id = f"{table_id[:base_length]}_{hash_suffix}{suffix}"
    else:
        table_id = f"{table_id}{suffix}"

    table_id = clean_redundant_underscores(table_id)

    return table_id


def parse_and_get_rt_biz_id(table_id: str) -> int:
    """
    解析并获取监控平台结果表的业务ID信息
    @param table_id: 监控平台结果表ID
    @return: 业务ID
    """
    match = re.match(r"^(\d+)", table_id)
    if match:
        # 如果匹配成功，返回数字部分并转换为整数
        return int(match.group(1))
    else:
        return settings.DEFAULT_BKDATA_BIZ_ID


def compose_config(tpl: str, render_params: dict, err_msg_prefix: str | None = "compose config") -> dict:
    """渲染配置模板"""
    content = Environment().from_string(tpl).render(**render_params)
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        logger.error("%s parse data_id config error: %s", err_msg_prefix, e)
        return {}


def get_bkdata_data_id_name(data_name: str) -> str:
    # 剔除不符合的字符
    refine_data_name = re.sub(MATCH_DATA_NAME_PATTERN, "", data_name)
    # 截取长度为45的字符串，同时拼装前缀
    return f"bkm_{refine_data_name[-45:].lower()}"


def compose_bkdata_data_id_name(data_name: str, strategy: str = None) -> str:
    """
    组装bkdata数据源名称，支持中文处理
    @param data_name: 监控平台数据源名称
    @param strategy: 链路策略
    """
    # 先按原正则剔除特殊字符（包括中文）
    refine_data_name = re.sub(MATCH_DATA_NAME_PATTERN, "", data_name)

    # 针对剔除掉的中文字符进行处理
    chinese_characters = "".join(char for char in data_name if "\u4e00" <= char <= "\u9fff")
    if chinese_characters:
        chinese_pinyin = "".join(lazy_pinyin(chinese_characters))  # 转为全拼音
        refine_data_name += chinese_pinyin  # 拼接拼音到 refined_name

    # 替换连续的下划线为单个下划线
    data_id_name = f"bkm_{re.sub(r'_+', '_', refine_data_name)}"

    # 控制长度
    if len(refine_data_name) > 45:
        # 截取长度为45的字符串
        truncated_name = refine_data_name[-39:].lower().strip("_")
        # 计算哈希值
        hash_suffix = hashlib.md5(refine_data_name.encode()).hexdigest()[:5]
        data_id_name = f"bkm_{truncated_name}_{hash_suffix}"

    # 拼装前缀和哈希值
    if strategy == models.DataLink.BCS_FEDERAL_SUBSET_TIME_SERIES:
        data_id_name = "fed_" + data_id_name

    return data_id_name


def get_bkbase_raw_data_id_name(data_source, table_id):
    """
    获取计算平台对应的data_id_name，适配V3迁移V4场景
    @param data_source: 数据源
    @param table_id: 监控平台结果表ID
    """
    try:
        bkbase_data_id = models.AccessVMRecord.objects.filter(result_table_id=table_id).first().bk_base_data_id
        raw_data_name = api.bkdata.get_bkbase_raw_data_with_data_id(bkbase_data_id=bkbase_data_id).get("raw_data_name")
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
        raw_data_name = api.bkdata.get_bkbase_raw_data_with_data_id(bkbase_data_id=bkbase_data_id).get("raw_data_name")
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


def get_data_source_related_info(bk_data_id):
    """
    获取数据源关联信息
    @param bk_data_id: 数据源ID
    @return: 数据源ID、数据源名称、结果表ID、VM结果表ID
    """
    logger.info("get_data_source_related_info: try to get data_source related info for bk_data_id->[%s]", bk_data_id)
    try:
        ds = models.DataSource.objects.get(bk_data_id=bk_data_id)
        dsrt = models.DataSourceResultTable.objects.get(bk_data_id=bk_data_id)
        table_id = dsrt.table_id

        vm_record = models.AccessVMRecord.objects.filter(result_table_id=table_id)

        if vm_record.exists():
            vm_record = vm_record.first()
            vm_result_table_id = vm_record.vm_result_table_id
        else:
            vm_result_table_id = None

        return {
            "bk_data_id": bk_data_id,
            "data_name": ds.data_name,
            "result_table_id": table_id,
            "vm_result_table_id": vm_result_table_id,
        }
    except Exception as e:  # pylint: disable=broad-except
        logger.error(
            "get_data_source_related_info: get data_source related info failed,bk_data_id->[%s] error->[%s]",
            bk_data_id,
            e,
        )
        return {}
