# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""
import copy
import json
import logging
import time

import arrow
from blueapps.contrib.celery_tools.periodic import periodic_task
from blueapps.core.celery.celery import app
from celery.schedules import crontab
from django.conf import settings

from apps.feature_toggle.models import FeatureToggle
from apps.log_measure.constants import COLLECTOR_IMPORT_PATHS, LOG_MEASURE_METRIC_TOGGLE
from apps.log_measure.models import MetricDataHistory
from apps.log_measure.utils.metric import MetricUtils
from apps.utils.task import high_priority_periodic_task
from bk_monitor.handler.monitor import BKMonitor
from bk_monitor.utils.collector import MetricCollector
from bk_monitor.utils.metric import (
    REGISTERED_METRICS,
    build_metric_id,
    clear_registered_metrics,
)
from config.domains import MONITOR_APIGATEWAY_ROOT

logger = logging.getLogger("app")


@periodic_task(run_every=crontab(minute="*/1"))
def bk_monitor_report():
    # todo 由于与菜单修改有相关性 暂时先改成跟原本monitor开关做联动
    if settings.FEATURE_TOGGLE["monitor_report"] == "off":
        return

    # 这里是为了兼容调度器由于beat与worker时间差异导致的微小调度异常
    time.sleep(2)
    bk_monitor_client = BKMonitor(
        app_id=settings.APP_CODE,
        app_token=settings.SECRET_KEY,
        monitor_host=MONITOR_APIGATEWAY_ROOT,
        report_host=f"{settings.BKMONITOR_CUSTOM_PROXY_IP}/",
        bk_username="admin",
        bk_biz_id=settings.BLUEKING_BK_BIZ_ID,
    )
    custom_metric_instance = bk_monitor_client.custom_metric()

    # 获取运营数据采集模块开关
    feature_toggle_obj, __ = FeatureToggle.objects.get_or_create(
        name=LOG_MEASURE_METRIC_TOGGLE,
        defaults={
            "status": "on",
            "is_viewed": False,
            # 初始化值默认为空列表
            "feature_config": {"import_paths": []},
            "biz_id_white_list": [],
            "biz_id_black_list": [],
        },
    )
    # 如果为空列表，则默认全部执行
    import_paths = feature_toggle_obj.feature_config.get("import_paths", []) or COLLECTOR_IMPORT_PATHS
    if feature_toggle_obj.status == "on" and import_paths:
        custom_metric_instance.report(collector_import_paths=import_paths)

    # 此处是为了释放对应util资源 非必须
    MetricUtils.del_instance()

    # 清理注册表里的内容，下一次运行的时候重新注册
    clear_registered_metrics()


@high_priority_periodic_task(run_every=crontab(minute="*/1"))
def bk_monitor_collect():
    # todo 由于与菜单修改有相关性 暂时先改成跟原本monitor开关做联动
    if settings.FEATURE_TOGGLE["monitor_report"] == "off":
        return
    # 获取运营数据上报模块开关
    feature_toggle_obj, __ = FeatureToggle.objects.get_or_create(
        name=LOG_MEASURE_METRIC_TOGGLE,
        defaults={
            "status": "on",
            "is_viewed": False,
            # 初始化值默认为空列表
            "feature_config": {"import_paths": []},
            "biz_id_white_list": [],
            "biz_id_black_list": [],
        },
    )
    if not feature_toggle_obj.status == "on":
        return

    # 这里是为了兼容调度器由于beat与worker时间差异导致的微小调度异常
    time.sleep(2)
    time_now = arrow.now()
    time_now_minute = 60 * time_now.hour + time_now.minute
    # 如果为空列表，则默认全部执行
    import_paths = feature_toggle_obj.feature_config.get("import_paths", []) or COLLECTOR_IMPORT_PATHS
    MetricCollector(collector_import_paths=import_paths)
    execute_metrics = copy.deepcopy(REGISTERED_METRICS)
    for metric_id, metric in execute_metrics.items():
        if not time_now_minute % metric["time_filter"]:
            collect_params = {
                "namespaces": [metric["namespace"]],
                "data_names": [metric["data_name"]],
                "sub_types": [metric["sub_type"]] if metric["sub_type"] else None,
            }
            logger.info("[statistics_data] metric->{} receive collection task.".format(metric_id))
            collect_metrics.delay(
                import_paths, collect_params["namespaces"], collect_params["data_names"], collect_params["sub_types"]
            )
    # 清理注册表里的内容，下一次运行的时候重新注册
    clear_registered_metrics()


@app.task(ignore_result=True)
def collect_metrics(
    collector_import_paths: list, namespaces: list = None, data_names: list = None, sub_types: list = None
):
    """
    将已通过 register_metric 注册的对应metric收集存入数据库
    Attributes:
        collector_import_paths: list 动态引用文件列表
        namespaces: 允许上报namespace列表
    """
    metric_groups = MetricCollector(collector_import_paths=collector_import_paths).collect(
        namespaces=namespaces, data_names=data_names, sub_types=sub_types
    )
    try:
        for group in metric_groups:
            metric_id = build_metric_id(
                data_name=group["data_name"],
                namespace=group["namespace"],
                prefix=group["prefix"],
                sub_type=group["sub_type"],
            )
            metric_data = [i.__dict__ for i in group["metrics"]]
            MetricDataHistory.objects.update_or_create(
                metric_id=metric_id,
                defaults={
                    "metric_data": json.dumps(metric_data),
                    "updated_at": MetricUtils.get_instance().report_ts,
                },
            )
            logger.info(f"[statistics_data] save metric_data[{metric_id}] successfully")

        # 此处是为了释放对应util资源 非必须
        MetricUtils.del_instance()

        # 清理注册表里的内容，下一次运行的时候重新注册
        clear_registered_metrics()

    except Exception as ex:  # pylint:disable=broad-except
        logger.exception(f"[statistics_data] Failed to save metric_data, msg: {ex}")
