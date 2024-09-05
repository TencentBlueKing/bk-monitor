# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import time
from enum import Enum

from celery.schedules import crontab
from celery.task import periodic_task, task
from django.conf import settings
from django.utils.functional import cached_property
from django.utils.translation import gettext as _

from apm_web.handlers.service_handler import ServiceHandler
from apm_web.meta.plugin.plugin import LOG_TRACE
from apm_web.models import Application
from apm_web.profile.file_handler import ProfilingFileHandler
from apm_web.serializers import ApplicationCacheSerializer
from bkmonitor.utils.common_utils import get_local_ip
from bkmonitor.utils.custom_report_tools import custom_report_tool
from bkmonitor.utils.time_tools import strftime_local
from common.log import logger
from core.drf_resource import api


class APMEvent(Enum):
    APP_CREATE = "app_create"
    APP_UPDATE = "app_update"

    @cached_property
    def event_name(self):
        return {"app_create": _("新APM应用创建"), "app_update": _("APM应用更新")}.get(self.value)

    def event_template(self, data_sources: dict = None):
        data_sources_template = _("开启了以下datasource上报: {}").format(
            ", ".join([key for key, enabled in data_sources.items() if enabled]) or "None"
        )
        body_template = {
            "app_create": _(
                "有新APM应用创建，请关注！应用名称：{app_name}, 应用别名：{app_alias}, "
                "业务ID：{bk_biz_id}, 业务名称：{bk_biz_name}, 创建者：{operator}，创建时间：{operate_time}"
            ),
            "app_update": _(
                "有APM应用更新，请关注！应用名称：{app_name}, 应用别名：{app_alias}, "
                "业务ID：{bk_biz_id}, 业务名称：{bk_biz_name}, 更新者：{operator}，更新时间：{operate_time}"
            ),
        }.get(self.value)
        return body_template + "\n" + data_sources_template


def build_event_body(app: Application, bk_biz_id: int, apm_event: APMEvent, data_sources: dict = None):
    event_body_map = {"event_name": _("监控平台{}").format(apm_event.event_name)}
    response_biz_data = api.cmdb.get_business(bk_biz_ids=[bk_biz_id])
    if response_biz_data:
        biz_data = response_biz_data[0]
        bk_biz_name = biz_data.bk_biz_name
    else:
        bk_biz_name = ""

    event_body_map["target"] = get_local_ip()
    event_body_map["timestamp"] = int(round(time.time() * 1000))
    event_body_map["dimension"] = {"bk_biz_id": bk_biz_id, "bk_biz_name": bk_biz_name}
    event_body_params = {
        "app_name": app.app_name,
        "app_alias": app.app_alias,
        "bk_biz_id": bk_biz_id,
        "bk_biz_name": bk_biz_name,
        "operator": app.create_user if apm_event is APMEvent.APP_CREATE else app.update_user,
        "operate_time": strftime_local(app.create_time)
        if apm_event is APMEvent.APP_CREATE
        else strftime_local(app.update_time),
    }
    content = apm_event.event_template(data_sources).format(**event_body_params)
    event_body_map["event"] = {"content": content}
    return [event_body_map]


@task(ignore_result=True)
def update_application_config(application_id):
    Application.objects.get(application_id=application_id).refresh_config()


@task(ignore_result=True)
def refresh_application_data_status():
    for application in Application.objects.filter(is_enabled=True):
        _refresh_application_data_status.delay(application.application_id)


@task(ignore_result=True)
def _refresh_application_data_status(application_id):
    Application.objects.get(application_id=application_id).set_data_status()


@task(ignore_result=True)
def refresh_application():
    logger.info("[REFRESH_APPLICATION] task start")

    # 刷新数据状态
    for application in Application.objects.filter(is_enabled=True):
        application.set_data_status()

    logger.info("[REFRESH_APPLICATION] task finished")


@task(ignore_result=True)
def report_apm_application_event(bk_biz_id, application_id, apm_event: APMEvent, data_sources: dict = None):
    logger.info(f"[report_apm_application_event] task start, bk_biz_id({bk_biz_id}), application_id({application_id})")

    application = Application.objects.get(application_id=application_id)
    data = build_event_body(application, bk_biz_id, apm_event, data_sources)
    config_info = settings.APM_CUSTOM_EVENT_REPORT_CONFIG
    data_id = config_info.get("data_id", "")
    token = config_info.get("token", "")
    if config_info and token:
        custom_report_tool(data_id).send_data_by_http(data, token)
    else:
        logger.info("[report_apm_application_event] config is empty, do nothing")

    logger.info(
        f"[report_apm_application_event] task finished, bk_biz_id({bk_biz_id}), application_id({application_id})"
    )


@periodic_task(run_every=crontab(minute="*/30"))
def refresh_log_trace_config():
    # 30分钟刷新一次
    applications = Application.objects.filter().values("application_id", "plugin_config")
    for application in applications:
        if application.plugin_id == LOG_TRACE:
            application.set_plugin_config(application["plugin_config"], application["application_id"])


@task(ignore_result=True)
def refresh_apm_application_metric():
    logger.info("[refresh_apm_application_metric] task start")

    # 刷新 APM 应用列表页, 应用指标数据
    queryset = Application.objects.filter(is_enabled=True)

    applications = ApplicationCacheSerializer(queryset, many=True).data

    ServiceHandler.refresh_application_cache_data(applications)

    logger.info("[refresh_apm_application_metric] task finished")


@task(ignore_result=True)
def profile_file_upload_and_parse(key: str, profile_id: str, bk_biz_id: int, service_name: str):
    """
    :param key : 文件完整路径
    :param str profile_id: profile_id
    :param int bk_biz_id: 业务id
    :param str service_name: 服务名称
    """
    logger.info(f"[profile_file_upload_and_parse] task start, bk_biz_id({bk_biz_id}),  profile_id({profile_id})")

    ProfilingFileHandler().parse_file(
        key=key,
        profile_id=profile_id,
        bk_biz_id=bk_biz_id,
        service_name=service_name,
    )

    logger.info(f"[profile_file_upload_and_parse] task finished, bk_biz_id({bk_biz_id}), profile_id({profile_id})")
