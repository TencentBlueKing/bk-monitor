# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import json
import logging
import os

from django.conf import settings
from django.template import Context
from django.utils.safestring import mark_safe

from bkmonitor.dataflow.utils.multivariate_anomaly.host.constant import (
    AGG_METRICS_SQL_EXPR,
    AGG_TRANS_METRICS_SQL_EXPR,
    MERGE_SQL_EXPR,
)
from core.drf_resource import api

logger = logging.getLogger("utils")


def load_flow_json(file_name):
    """从文件名中加载json数据

    :param file_name: 文件名
    :raises Exception: 文件不存在
    :return: 经json.load解析的文件内容
    """
    flow_json_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), file_name)
    if not os.path.exists(flow_json_file_path):
        raise Exception("flow info file not exists")
    with open(flow_json_file_path) as f:
        return json.load(f)


def check_and_access_system_tables(sources):
    """检查系统表, 并将未接入的结果表接入

    :param sources: json.load数据, 内容请查看bkmonitor/dataflow/utils/multivariate_anomaly/host/sources.json
    :raises Exception: 接入失败错误
    """
    for source in sources:
        rt = source["result_table_id"]
        bk_data_result_table_id = source["bk_data_result_table_id"]

        # 该接口如果查询不到对应结果表则返回空字典，所以此处字典不为空则认为已接入
        result = api.bkdata.get_result_table(result_table_id=bk_data_result_table_id)

        if result:
            continue

        # 将表接入到计算平台
        try:
            api.metadata.access_bk_data_by_result_table(table_id=rt, is_access_now=True)
        except Exception as e:  # noqa
            err_msg = "access({}) to bkdata failed: {}".format(rt, e)
            raise Exception(err_msg)
        else:
            logger.info("access({}) to bkdata success.".format(rt))


def build_metric_alias(metric, result_table_id):
    """构建指标在计算平台的别名
        由于从对应结果表中查询的只有指标名
        为了符合监控的指标名, 需要附带上结果表使用.拼接, 但由于不支持使用.作为字段，所以使用双下划线(__)代替
    :param metric: 指标名
    :param result_table_id: 指标所在结果表
    :return: 指标在计算平台的别名
    """
    return ".".join([result_table_id, metric]).replace(".", "__")


def build_agg_sql(metrics, result_table_id, from_rt_id):
    """构建聚合sql

    :param metrics: 指标名列表
    :param result_table_id: 指标所在的监控结果表
    :param from_rt_id: sql from的表
    :return: 聚合sql
    """
    metric_alias_list = [build_metric_alias(metric, result_table_id) for metric in metrics]
    return AGG_METRICS_SQL_EXPR.render(
        Context({"metric_infos": zip(metrics, metric_alias_list), "output_table_name": from_rt_id})
    )


def build_agg_trans_sql(metrics, result_table_id, from_rt_id):
    """构建聚合清洗sql

    :param metrics: 指标名列表
    :param result_table_id: 指标所在的监控结果表
    :param from_rt_id: sql from的表
    :return: 聚合清洗sql
    """
    metric_alias_list = [build_metric_alias(metric, result_table_id) for metric in metrics]
    return AGG_TRANS_METRICS_SQL_EXPR.render(
        Context(
            {
                "metrics": metric_alias_list,
                "metrics_strs": mark_safe(",".join(map(lambda x: "'{}'".format(x), metric_alias_list))),
                "output_table_name": from_rt_id,
            }
        )
    )


def build_merge_sql(from_rt_id):
    """构建所有输入合并的sql

    :param from_rt_id: sql from的表
    :return: 合并的sql
    """
    return MERGE_SQL_EXPR.render(Context({"output_table_name": from_rt_id}))


def build_merge_table_name():
    """返回对应环境合流节点的表名

    :return: 对应环境合流节点的表名
    """
    return f"{settings.BK_DATA_RT_ID_PREFIX}_system_metric_merge"


def build_result_table_name():
    """返回对应环境flow最后结果表的表名

    :return: 对应环境flow最后结果表的表名
    """
    return settings.BK_DATA_MULTIVARIATE_HOST_RT_ID
