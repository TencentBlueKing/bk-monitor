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
import time
from urllib.parse import urlencode

import arrow
from django.conf import settings

from bkmonitor.data_source import load_data_source
from bkmonitor.documents import AlertDocument
from bkmonitor.models import Event, QueryConfigModel
from bkmonitor.utils import time_tools
from constants.data_source import DataSourceLabel, DataTypeLabel

__all__ = ["get_event_relation_info", "get_alert_relation_info"]

from core.drf_resource import api

logger = logging.getLogger("fta_action.run")


def get_event_relation_info(event: Event):
    """
    获取事件最近的日志
    1. 自定义事件：查询事件关联的最近一条事件信息
    2. 日志关键字：查询符合条件的一条日志信息
    """
    query_config = (
        QueryConfigModel.objects.filter(strategy_id=event.strategy_id)
        .values("data_source_label", "data_type_label", "config")
        .first()
    )

    # 关联日志信息目前固定单指标
    if not query_config or (query_config["data_source_label"], query_config["data_type_label"]) not in (
        (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.LOG),
        (DataSourceLabel.BK_LOG_SEARCH, DataTypeLabel.LOG),
        (DataSourceLabel.BK_LOG_SEARCH, DataTypeLabel.TIME_SERIES),
        (DataSourceLabel.CUSTOM, DataTypeLabel.EVENT),
    ):
        return ""

    query_config = event.origin_config["items"][0]["query_configs"][0]
    data_source_class = load_data_source(query_config["data_source_label"], query_config["data_type_label"])
    data_source = data_source_class.init_by_query_config(query_config, bk_biz_id=event.bk_biz_id)

    data_source.filter_dict.update(
        {
            key: value
            for key, value in event.origin_alarm["data"]["dimensions"].items()
            if key in query_config.get("agg_dimension", [])
        }
    )

    return get_data_source_log(data_source, query_config, int(event.latest_anomaly_record.source_time.timestamp()))


def get_alert_relation_info(alert: AlertDocument):
    """
    获取事件最近的日志
    1. 自定义事件：查询事件关联的最近一条事件信息
    2. 日志关键字：查询符合条件的一条日志信息
    """
    if not alert.strategy:
        return ""

    query_config = (
        QueryConfigModel.objects.filter(strategy_id=alert.strategy["id"])
        .values("data_source_label", "data_type_label", "config")
        .first()
    )

    # 关联日志信息目前固定单指标
    if query_config and (query_config["data_source_label"], query_config["data_type_label"]) in (
        (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.LOG),
        (DataSourceLabel.BK_LOG_SEARCH, DataTypeLabel.LOG),
        (DataSourceLabel.BK_LOG_SEARCH, DataTypeLabel.TIME_SERIES),
        (DataSourceLabel.CUSTOM, DataTypeLabel.EVENT),
    ):
        return get_alert_relation_info_for_log(alert)

    # 日志聚类告警需要提供更详细的信息
    for label in alert.strategy.get("labels") or []:
        # 日志聚类新类告警具有特定标签，格式 "LogClustering/NewClass/{index_set_id}"
        # 根据前缀可识别出来
        if label.startswith("LogClustering/NewClass/"):
            return get_alert_info_for_log_clustering_new_class(alert, label.split("/")[-1])
        # 日志聚类数量告警具有特定标签，格式 "LogClustering/Count/{index_set_id}"
        # 根据前缀可识别出来
        elif label.startswith("LogClustering/Count/"):
            return get_alert_info_for_log_clustering_count(alert, label.split("/")[-1])

    return ""


def get_alert_info_for_log_clustering_count(alert: AlertDocument, index_set_id: str):
    query_config = alert.strategy["items"][0]["query_configs"][0]
    interval = query_config.get("agg_interval", 60)
    start_time = alert.begin_time - 60 * 60
    end_time = max(alert.begin_time + interval, alert.latest_time) + 60 * 60
    group_by = query_config.get("agg_dimension", [])

    try:
        dimensions = alert.origin_alarm["data"]["dimensions"]
        signatures = [dimensions["signature"]]
        sensitivity = dimensions.get("sensitivity", "__dist_05")
    except Exception as e:
        logger.exception("[get_alert_info_for_log_clustering_count] get dimension error: %s", e)
        return ""

    return get_clustering_log(alert, index_set_id, start_time, end_time, sensitivity, signatures, group_by, dimensions)


def get_alert_info_for_log_clustering_new_class(alert: AlertDocument, index_set_id: str):
    """
    get_alert_relation_info_for_log_clustering_new_class
    """
    query_config = alert.strategy["items"][0]["query_configs"][0]
    data_source_class = load_data_source(query_config["data_source_label"], query_config["data_type_label"])
    data_source = data_source_class.init_by_query_config(query_config, bk_biz_id=alert.event.bk_biz_id)
    interval = query_config.get("agg_interval", 60)
    start_time = alert.begin_time
    end_time = max(alert.begin_time + interval, alert.latest_time)
    group_by = query_config.get("agg_dimension", [])
    signatures = []

    try:
        dimensions = alert.origin_alarm["data"]["dimensions"]
        if dimensions.get("signature"):
            signatures = [dimensions["signature"]]
        # 新类敏感度默认取最低档，即最少告警
        sensitivity = dimensions.get("sensitivity", "__dist_09")
    except Exception as e:
        logger.exception("[get_alert_info_for_log_clustering_new_class] get dimension error: %s", e)
        sensitivity = "__dist_09"
        dimensions = {}

    if not signatures:
        signatures = data_source.query_dimensions(
            dimension_field="signature", start_time=start_time * 1000, end_time=end_time * 1000
        )
    return get_clustering_log(alert, index_set_id, start_time, end_time, sensitivity, signatures, group_by, dimensions)


def get_clustering_log(
    alert: AlertDocument, index_set_id: str, start_time, end_time, sensitivity, signatures, group_by, dimensions
):
    start_time_str = time_tools.utc2biz_str(start_time)
    end_time_str = time_tools.utc2biz_str(end_time)
    addition = [{"field": sensitivity, "operator": "=", "value": ",".join(signatures)}]
    addition.extend(
        [
            {"field": dimension_field, "operator": "=", "value": dimension_value}
            for dimension_field, dimension_value in dimensions.items()
            if dimension_field not in ["sensitivity", "signature"]
        ]
    )
    params = {
        "bizId": alert.event.bk_biz_id,
        "addition": json.dumps(addition),
        "start_time": start_time_str,
        "end_time": end_time_str,
    }

    # 拼接查询链接
    bklog_link = f"{settings.BKLOGSEARCH_HOST}#/retrieve/{index_set_id}?{urlencode(params)}"

    # 查询关联日志，最多展示1条
    record = {}
    log_signature = None
    try:
        log_data_source_class = load_data_source(DataSourceLabel.BK_LOG_SEARCH, DataTypeLabel.LOG)
        log_data_source = log_data_source_class.init_by_query_config(
            {
                "index_set_id": index_set_id,
                "result_table_id": "",
                "agg_condition": [{"key": sensitivity, "method": "eq", "value": signatures}],
            }
        )
        logs, log_total = log_data_source.query_log(start_time=start_time * 1000, end_time=end_time * 1000, limit=1)
        if logs:
            record = logs[0]
            for key in record.copy():
                if key.startswith("__dist_"):
                    # 获取pattern
                    if key == sensitivity:
                        log_signature = record[key]
                    # 去掉数据签名相关字段，精简显示内容
                    record.pop(key)

    except Exception as e:
        logger.exception(f"get alert[{alert.id}] log clustering new class log error: {e}")

    record["bklog_link"] = bklog_link

    if log_signature:
        try:
            addition = [{"field": sensitivity, "operator": "=", "value": log_signature}]
            # 增加聚类分组告警维度值作为查询条件
            addition.extend(
                [
                    {"field": dimension_field, "operator": "=", "value": dimension_value}
                    for dimension_field, dimension_value in dimensions.items()
                    if dimension_field not in ["sensitivity", "signature"]
                ]
            )
            pattern_params = {
                "bizId": alert.event.bk_biz_id,
                "addition": addition,
                "start_time": start_time_str,
                "end_time": end_time_str,
                "index_set_id": index_set_id,
                "pattern_level": sensitivity.lstrip("__dist_"),
                "show_new_pattern": False,
            }
            # 增加聚类分组参数
            group_by = [group for group in group_by if group not in ["sensitivity", "signature"]]
            if group_by:
                pattern_params["group_by"] = group_by
                record["group_by"] = group_by

            patterns = api.log_search.search_pattern(pattern_params)
            log_pattern = patterns[0]
            record["owners"] = ",".join(log_pattern["owners"])
            if log_pattern["remark"]:
                remark = log_pattern["remark"][-1]
                record["remark_text"] = remark["remark"]
                record["remark_user"] = remark["username"]
                # 获取备注创建时间字符串
                record["remark_time"] = arrow.get(remark["create_time"] / 1000).to('local').format('YYYY-MM-DD HH:mm')
        except Exception as e:
            logger.exception(f"get alert[{alert.id}] signature[{log_signature}] log clustering new pattern error: {e}")

    content = json.dumps(record, ensure_ascii=False)
    # 截断
    content = content[: settings.EVENT_RELATED_INFO_LENGTH] if settings.EVENT_RELATED_INFO_LENGTH else content
    return content


def get_alert_relation_info_for_log(alert: AlertDocument):
    query_config = alert.strategy["items"][0]["query_configs"][0]
    data_source_class = load_data_source(query_config["data_source_label"], query_config["data_type_label"])
    data_source = data_source_class.init_by_query_config(query_config, bk_biz_id=alert.event.bk_biz_id)

    data_source.filter_dict.update(
        {
            key: value
            for key, value in alert.origin_alarm.get("data", {}).get("dimensions", {}).items()
            if key in query_config.get("agg_dimension", [])
        }
    )
    retry_interval = settings.DELAY_TO_GET_RELATED_INFO_INTERVAL
    try:
        content = get_data_source_log(data_source, query_config, alert.event.time)
        if content:
            return content
        logger.info("alert(%s) related info is empty, try again after %s ms", alert.id, retry_interval)
    except BaseException as error:
        logger.error("alert(%s) related info failed: %s, try again after %s ms", alert.id, str(error), retry_interval)

    # 当第一次获取失败之后，再重新获取一次
    time.sleep(retry_interval / 1000)
    return get_data_source_log(data_source, query_config, alert.event.time)


def get_data_source_log(data_source, query_config, source_time):
    """
    查询时间为事件开始到5个周期后
    :param data_source:
    :param query_config:
    :param source_time:
    :param end_time:
    :return:
    """
    # 查询时间为事件开始到5个周期后
    interval = query_config.get("agg_interval", 60)
    start_time = int(source_time) - 5 * interval
    end_time = int(source_time) + interval
    records, _ = data_source.query_log(start_time=start_time * 1000, end_time=end_time * 1000, limit=1)
    if not records:
        return ""

    record = records[0]
    if query_config["data_source_label"] in [DataSourceLabel.BK_MONITOR_COLLECTOR, DataSourceLabel.CUSTOM]:
        content = record["event"]["content"]
    else:
        content = json.dumps(record, ensure_ascii=False)
    return content[: settings.EVENT_RELATED_INFO_LENGTH] if settings.EVENT_RELATED_INFO_LENGTH else content
