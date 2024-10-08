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

# TODO 需要优化一下，将后台定时任务移到公共代码中
# 这里需要使用告警后台的celery应用，因为后台只有告警后台的worker实例
import datetime
import logging
import time

import jinja2
from django.conf import settings
from django.db.models import Q
from opentelemetry import trace
from opentelemetry.trace import StatusCode

from alarm_backends.core.cache import key
from alarm_backends.core.lock.service_lock import service_lock
from alarm_backends.service.scheduler.app import app
from apm.core.application_config import ApplicationConfig
from apm.core.cluster_config import ClusterConfig
from apm.core.discover.base import TopoHandler
from apm.core.discover.precalculation.consul_handler import ConsulHandler
from apm.core.discover.precalculation.storage import PrecalculateStorage
from apm.core.discover.profile.base import DiscoverHandler as ProfileDiscoverHandler

# from apm.core.handlers.application_hepler import ApplicationHelper
from apm.core.handlers.bk_data.tail_sampling import TailSamplingFlow
from apm.core.handlers.bk_data.virtual_metric import VirtualMetricFlow
from apm.core.platform_config import PlatformConfig
from apm.models import (
    ApmApplication,
    EbpfApplicationConfig,
    MetricDataSource,
    ProfileDataSource,
)
from constants.apm import BkCollectorComp
from core.errors.alarm_backends import LockError

logger = logging.getLogger("apm")

tracer = trace.get_tracer(__name__)


@app.task(ignore_result=True, queue="celery_cron")
def handler(bk_biz_id, app_name):
    start = time.time()
    topo_handler = TopoHandler(bk_biz_id, app_name)
    if topo_handler.is_valid():
        topo_handler.discover()
    logger.info(f"[topo_discover_cron] end. app_name: {app_name} cost: {time.time() - start}")


def topo_discover_cron():
    # 10分钟刷新一次
    interval = 10
    slug = datetime.datetime.now().minute % interval
    ebpf_application_ids = [e["application_id"] for e in EbpfApplicationConfig.objects.all().values("application_id")]
    to_be_refreshed = list(
        ApmApplication.objects.filter(Q(is_enabled=True) & ~Q(id__in=ebpf_application_ids)).values_list(
            "bk_biz_id", "app_name", "id"
        )
    )
    for index, application in enumerate(to_be_refreshed):
        bk_biz_id, app_name, app_id = application
        try:
            with service_lock(key.APM_TOPO_DISCOVER_LOCK, app_id=app_id):
                if index % interval == slug:
                    logger.info(f"[topo_discover_cron] start. app_name: {app_name}, app_id: {app_id}")
                    handler.delay(bk_biz_id, app_name)
        except LockError:
            logger.info(f"skipped: [topo_discover_cron] already running. app_name: {app_name}, app_id: {app_id}")
            continue


def refresh_apm_config():
    # 30分钟刷新一次
    interval = 30
    to_be_refreshed = list(ApmApplication.objects.filter(is_enabled=True).values_list("bk_biz_id", "app_name"))
    slug = datetime.datetime.now().minute % interval
    for index, application in enumerate(to_be_refreshed):
        bk_biz_id, app_name = application
        if index % interval == slug:
            logger.info(f"[refresh_apm_config]: publish application [{bk_biz_id}]({app_name})")
            refresh_apm_application_config.delay(bk_biz_id, app_name)


def refresh_apm_platform_config():
    PlatformConfig.refresh()


@app.task(ignore_result=True, queue="celery_cron")
def refresh_apm_application_config(bk_biz_id, app_name):
    _app = ApmApplication.objects.get(bk_biz_id=bk_biz_id, app_name=app_name)
    ApplicationConfig(_app).refresh()


@app.task(ignore_result=True, queue="celery_cron")
def create_virtual_metric(bk_biz_id, app_name):
    """创建APM应用在计算平台的虚拟指标计算Flow"""
    logger.info(f"[create_virtual_metric] start create virtual metric, bk_biz_id: {bk_biz_id} app_name: {app_name}")
    metric = MetricDataSource.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
    if not metric:
        logger.info(f"[create_virtual_metric] bk_biz_id: {bk_biz_id} app_name: {app_name} metric table not found, skip")
        return

    # 空间下应用不创建虚拟指标
    if int(metric.bk_biz_id) > 0 and settings.IS_ACCESS_BK_DATA:
        VirtualMetricFlow(metric).update_or_create()


@app.task(ignore_result=True, queue="celery_cron")
def create_or_update_tail_sampling(trace_datasource, data):
    """创建/更新尾部采样Flow"""
    TailSamplingFlow(trace_datasource, data).start()


@app.task(ignore_result=True, queue="celery_cron")
def check_pre_calculate_fields_update():
    logger.info(f"[check_pre_calculate_fields_update] start {datetime.datetime.now()}")
    PrecalculateStorage.handle_fields_update()
    logger.info(f"[check_pre_calculate_fields_update] end {datetime.datetime.now()}")


@app.task(ignore_result=True, queue="celery_cron")
def check_apm_consul_config():
    """遍历应用检查consul配置是否需要更新"""
    logger.info(f"[check_apm_consul_config] start {datetime.datetime.now()}")
    ConsulHandler.check_update()
    logger.info(f"[check_apm_consul_config] end {datetime.datetime.now()}")


@app.task(ignore_result=True, queue="celery_cron")
def profile_handler(bk_biz_id: int, app_name: str):
    logger.info(f"[profile_handler] ({bk_biz_id}){app_name} start at {datetime.datetime.now()}")
    try:
        ProfileDiscoverHandler(bk_biz_id, app_name).discover()
    except Exception as e:  # noqa
        logger.error(f"[profile_handler] occur exception of {bk_biz_id}-{app_name}: {e}")
    logger.info(f"[profile_handler] ({bk_biz_id}){app_name} end at {datetime.datetime.now()}")


def profile_discover_cron():
    """定时发现profile服务"""
    logger.info(f"[profile_discover_cron] start at {datetime.datetime.now()}")
    apps = [
        (i["bk_biz_id"], i["app_name"])
        for i in ApmApplication.objects.filter(is_enabled=True).values("bk_biz_id", "app_name")
    ]
    apps = [i for i in ProfileDataSource.objects.all() if (i.bk_biz_id, i.app_name) in apps]

    for item in apps:
        logger.info(f"[profile_discover_cron] start handle. ({item.bk_biz_id}){item.app_name}")
        profile_handler(item.bk_biz_id, item.app_name)
        logger.info(f"[profile_discover_cron] finished handle. ({item.bk_biz_id}){item.app_name}")

    logger.info(f"[profile_discover_cron] end at {datetime.datetime.now()}")


def post_deploy_bk_collector():
    """
    集群部署 bk-collector 后的后置操作，包括：
    1. 创建默认应用
    2. 下发平台配置
    """
    logger.info(f"[post-deploy-bk_collector] start at {datetime.datetime.now()}")

    # 已安装 bk-collector 的集群 id 列表 由 apm_ebpf 模块发现
    cluster_mapping = ClusterConfig.get_cluster_mapping()
    logger.info(f"[post-deploy-bk_collector] find {len(cluster_mapping)} clusters")

    for cluster_id, cc_bk_biz_ids in cluster_mapping.items():
        with tracer.start_as_current_span(f"cluster-id: {cluster_id}", attributes={"bk_biz_ids": cc_bk_biz_ids}) as s:
            try:
                platform_config_tpl = ClusterConfig.platform_config_tpl(cluster_id)
                if platform_config_tpl is None:
                    # 如果集群中不存在 bk-collector 的平台配置模版，则不下发
                    continue

                # bk_biz_id = cc_bk_biz_ids[0]
                # if len(cc_bk_biz_ids) != 1:
                #     logger.warning(
                #         f"[post-deploy-bk_collector] cluster_id: {cluster_id} record multiple bk_biz_id!",
                #     )

                # Step1: 创建默认应用
                # default_application = ApplicationHelper.create_default_application(bk_biz_id)

                # Step2: 往集群的 bk-collector 下发配置
                platform_config_context = PlatformConfig.get_platform_config()
                tpl = jinja2.Template(platform_config_tpl)
                platform_config = tpl.render(platform_config_context)
                ClusterConfig.deploy_platform_config(cluster_id, platform_config)

                # s.add_event("default_application", attributes={"id": default_application.id})
                s.add_event("platform_secret", attributes={"name": BkCollectorComp.SECRET_PLATFORM_NAME})
                s.set_status(StatusCode.OK)
                logger.info(
                    f"[post-deploy-bk_collector] successfully deploy platform config in cluster: {cluster_id}",
                )
            except Exception as e:  # noqa
                # 仅记录异常
                s.record_exception(exception=e)
                logger.error(f"[post-deploy-bk_collector] check cluster: {cluster_id} failed, error: {e}")
