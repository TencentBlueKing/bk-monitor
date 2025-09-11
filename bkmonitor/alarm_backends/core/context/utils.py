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
import functools
import json
import logging
import time

from alarm_backends.core.cache.cmdb.business import BusinessManager
from alarm_backends.core.cache.key import NOTICE_MAPPING_KEY
from constants.action import NoticeWay
from core.drf_resource import api
from core.prometheus import metrics

logger = logging.getLogger("fta_action.run")


def get_business_roles(bk_biz_id):
    """
    获取业务角色
    :param bk_biz_id: 业务ID
    :return: dic: CMDB里的所有业务角色组
    """
    business = BusinessManager.get(bk_biz_id)
    if not business:
        return {}
    # 人员字段一定是列表，但列表字段不一定是人员，此处只做了简单的判断
    # 标准的判断方式是调用接口 api.cmdb.get_object_attribute 获取人员字段，但这样会产生一次额外请求，影响性能
    # 由于在配置侧已经限制了配置的人员字段，正常来说这里不会读取到非人员的字段。所以这里的加载方式也不会有问题
    return {
        key: value
        for key, value in business.__dict__.items()
        if isinstance(value, list) and key not in ["operator", "bk_bak_operator"]
    }


def collect_info_dumps(collect_info):
    """
    汇总信息转为字符串，方便日志检索
    :param collect_info: 汇总信息
    :return: str
    """
    return ";".join(["{}:{}".format(key, collect_info[key]) for key in collect_info])


def get_target_dimension_keys(agg_dimensions, scenario):
    """
    目标维度名称
    :param scenario: 监控对象
    :param agg_dimensions: 聚合维度
    :return: 目标维度
    """
    target_dimensions = []

    # 去除目标维度
    if scenario in ["os", "host_process"]:
        if "bk_target_ip" in agg_dimensions:
            target_dimensions.extend(["bk_target_ip", "bk_target_cloud_id"])
        elif "ip" in agg_dimensions:
            target_dimensions.extend(["ip", "bk_cloud_id"])
        else:
            target_dimensions.extend(["bk_obj_id", "bk_inst_id"])
    elif scenario in ["service_module", "component", "service_process"]:
        if "bk_target_service_instance_id" in agg_dimensions:
            target_dimensions.append("bk_target_service_instance_id")
        else:
            target_dimensions.extend(["bk_obj_id", "bk_inst_id"])

    return target_dimensions


def get_display_dimensions(event, strategy):
    """
    获取维度信息
    """
    agg_dimensions = strategy["item_list"][0]["rt_query_config"].get("agg_dimension", [])
    target_dimension_keys = get_target_dimension_keys(agg_dimensions, strategy["scenario"])
    display_dimensions = {
        "{}={}".format(value["display_name"], value["display_value"])
        for key, value in list(event.origin_alarm["dimension_translation"].items())
        if key not in target_dimension_keys and key in agg_dimensions
    }
    return display_dimensions


def get_display_targets(event, strategy):
    agg_dimensions = strategy["item_list"][0]["rt_query_config"].get("agg_dimension", [])
    target_dimension_keys = get_target_dimension_keys(agg_dimensions, strategy["scenario"])
    display_targets = []
    dimensions = event.origin_alarm["dimension_translation"]

    if "ip" in target_dimension_keys or "bk_target_ip" in target_dimension_keys:
        ip = dimensions.get("bk_target_ip") or dimensions.get("ip")
        if ip:
            display_targets.append(ip["display_value"])
    elif "bk_target_service_instance_id" in target_dimension_keys:
        service_instance_id = dimensions.get("bk_target_service_instance_id")
        if service_instance_id:
            display_targets.append(service_instance_id["display_value"])
    elif "bk_obj_id" in target_dimension_keys and "bk_inst_id" in target_dimension_keys:
        bk_obj_id = dimensions.get("bk_obj_id")
        bk_inst_id = dimensions.get("bk_inst_id")
        if bk_obj_id and bk_inst_id:
            display_targets.append("{}-{}".format(bk_obj_id["display_value"], bk_inst_id["display_value"]))

    return display_targets


def get_notice_display_mapping(notice_way):
    """
    接口获取通知显示内容
    :return:
    """
    notice_mapping_key = NOTICE_MAPPING_KEY.get_key()
    notice_display_mapping = NOTICE_MAPPING_KEY.client.get(notice_mapping_key)
    if not notice_display_mapping:
        try:
            notice_display_mapping = {msg["type"]: msg["label"] for msg in api.cmsi.get_msg_type()}
            NOTICE_MAPPING_KEY.client.set(notice_mapping_key, json.dumps(notice_display_mapping))
        except BaseException as error:
            logger.exception("get msg type error: %s", str(error))
            notice_display_mapping = NoticeWay.NOTICE_WAY_MAPPING
    else:
        notice_display_mapping = json.loads(notice_display_mapping)

    return str(notice_display_mapping.get(notice_way) or NoticeWay.NOTICE_WAY_MAPPING.get(notice_way, notice_way))


def context_field_timer(func):

    """
    处理套餐上下文字段指标计时
    处理方式：记录字段耗时，对于异常情况记录异常类名，并统一返回 None
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        result, exception = None, None
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
        except Exception as e:
            exception = e

        metrics.ALARM_CONTEXT_GET_FIELD_TIME.labels(
            field=func.__name__,
            exception=exception.__class__.__name__ if exception else "None",
        ).observe(time.time() - start_time)
        metrics.report_all()

        return result

    return wrapper
