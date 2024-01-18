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
"""
prometheus metric格式数据的检测
"""


import copy
import functools
import logging

import requests
from prometheus_client.parser import text_string_to_metric_families

from alarm_backends.service.selfmonitor.healthz.checker.checker import (
    CHECKER_FAILED,
    CHECKER_OK,
    CHECKER_WARN,
    CheckerRegister,
)
from alarm_backends.service.selfmonitor.healthz.checker.utils import resolve_domain
from bkmonitor.utils.call_cache import CallCache

logger = logging.getLogger("self_monitor")
register = CheckerRegister.prometheus
METRIC_VALUE_CACHE = {}


def get_metrics(url):
    """
    从指定url获取到指标信息，并转化成python对象
    :param url:
    :return:
    """
    metrics = {}
    try:
        response = requests.get(url)
    except Exception as e:
        return {
            "error": str(e),
            "metric": metrics,
        }

    if response.status_code == 200:
        for family in text_string_to_metric_families(response.text):
            for sample in family.samples:
                metrics.setdefault(sample.name, []).append(sample)

        return {
            "error": "",
            "metric": metrics,
        }
    else:
        return {
            "error": "{} {}".format(response.status_code, response.reason),
            "metric": metrics,
        }


def generate_check_info(name, status=CHECKER_OK, message="", value=""):
    return {
        "name": name,
        "status": status,
        "message": message,
        "value": value,
    }


get_metrics_cache = CallCache(get_metrics, timeout=10)


@register.status()
def connect_status(manager, result, domain, port):
    sub_info_list = []
    # 解析host获取ip列表
    ips = resolve_domain(domain)
    # 遍历ips,对每一个ip拼接url进行请求
    for ip in ips:
        url = "http://{}:{}/metrics".format(ip.strip(), port.strip())
        metrics_info = get_metrics_cache(url)
        status_check_info = functools.partial(generate_check_info, name=str({"ip": ip}))
        if metrics_info.get("error"):
            sub_info_list.append(status_check_info(status=CHECKER_FAILED, message=metrics_info["error"]))
        else:
            sub_info_list.append(status_check_info(status=CHECKER_OK, value="ok"))

    return result.update(value=sub_info_list)


def data_check(func):
    @functools.wraps(func)
    def wrapper(manager, result, domain, port, **kwargs):
        sub_info_list = []
        # 解析域名得到IP列表
        ips = resolve_domain(domain)
        for ip in ips:
            url = "http://{}:{}/metrics".format(ip.strip(), port.strip())
            metrics_info = get_metrics_cache(url)
            metric_check_info = functools.partial(generate_check_info, name=str({"ip": ip}))
            # 检查获取数据是否正常数据
            if metrics_info.get("error"):
                sub_info_list.append(metric_check_info(status=CHECKER_FAILED, message=metrics_info["error"]))
                continue

            metric_list = metrics_info["metric"].get(kwargs["metric_name"], [])
            # 当未找到所需的指标时，对指标是否允许不存在进行判断
            if not metric_list and not kwargs.get("allow_null"):
                sub_info_list.append(metric_check_info(status=CHECKER_WARN, message="Metric Not Exist"))
                continue

            # 将返回值根据数据是否异常状态进行汇总
            check_result = func(result, metric_list=metric_list, ip=ip, **kwargs)
            sub_info_list.extend(check_result)

        return result.update(value=sub_info_list)

    return wrapper


@register.counter()
@data_check
def prometheus_counter_processor(result, metric_list, ip, *args, **kwargs):
    sub_info_list = []
    # 从缓存中获取上一次的数据
    cache_key = "{}|{}".format(ip, kwargs["metric_name"])
    cache = copy.deepcopy(METRIC_VALUE_CACHE.get(cache_key, []))
    METRIC_VALUE_CACHE[cache_key] = metric_list
    for metric in metric_list:
        # 从上一次的数据中查找出维度相同的指标
        old_metric = [x for x in cache if x.labels == metric.labels]
        # 计算差值
        old_value = metric.value
        if len(old_metric) > 0:
            old_value = old_metric[0].value

        contrast_value = metric.value - old_value
        # 将差值不为0的指标视为异常指标
        labels = copy.deepcopy(metric.labels)
        labels.update({"ip": ip})
        metric_check_info = functools.partial(generate_check_info, name=str(labels), value=contrast_value)
        if contrast_value != 0:
            sub_info_list.append(metric_check_info(status=CHECKER_WARN if kwargs.get("forbid_grow") else CHECKER_OK))
        else:
            sub_info_list.append(metric_check_info(status=CHECKER_OK))

    return sub_info_list


@register.gauge()
@data_check
def prometheus_gauge_processor(result, metric_list, *args, **kwargs):
    checker_value = kwargs.get("checker_value")
    sub_info_list = []
    for metric in metric_list:
        if kwargs.get("ip"):
            metric.labels.update({"ip": kwargs["ip"]})

        sub_info_list.append(
            generate_check_info(
                name=str(metric.labels),
                status=CHECKER_WARN if checker_value and metric.value != checker_value else CHECKER_OK,
                value=metric.value,
            )
        )

    return sub_info_list
