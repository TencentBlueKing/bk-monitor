"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import time
from enum import Enum

from celery import shared_task
from django.conf import settings
from django.db.models import Q
from django.utils.functional import cached_property
from django.utils.translation import gettext as _

from bkmonitor.utils.common_utils import get_local_ip
from bkmonitor.utils.custom_report_tools import custom_report_tool
from bkmonitor.utils.time_tools import strftime_local
from bkmonitor.utils.tenant import set_local_tenant_id
from common.log import logger
from rum_web.models.application import Application


class RUMEvent(Enum):
    """RUM 应用事件类型"""

    APP_CREATE = "app_create"
    APP_UPDATE = "app_update"

    @cached_property
    def event_name(self):
        return {
            "app_create": _("新RUM应用创建"),
            "app_update": _("RUM应用更新"),
        }.get(self.value)

    def event_template(self):
        body_template = {
            "app_create": _(
                "\n有新 RUM 应用创建，请关注！"
                "\n应用名称：{app_name},"
                "\n应用别名：{app_alias}, "
                "\n业务 ID：{bk_biz_id}, "
                "\n业务名称：{bk_biz_name}, "
                "\n创建者：{operator}，"
                "\n创建时间：{operate_time}"
            ),
            "app_update": _(
                "\n有 RUM 应用更新，请关注！"
                "\n应用名称：{app_name},"
                "\n应用别名：{app_alias}, "
                "\n业务 ID：{bk_biz_id}, "
                "\n业务名称：{bk_biz_name}, "
                "\n更新者：{operator}，"
                "\n更新时间：{operate_time}"
            ),
        }.get(self.value)
        return body_template


def build_event_body(app: Application, bk_biz_id: int, rum_event: RUMEvent):
    bk_biz_name = ""
    operator = app.create_user if rum_event is RUMEvent.APP_CREATE else app.update_user

    event_body_map = {"event_name": _("监控平台{}").format(rum_event.event_name)}

    from bkm_space.api import SpaceApi

    space = SpaceApi.get_space_detail(bk_biz_id=bk_biz_id)
    if space is not None:
        bk_biz_name = space.space_name

    event_body_map["target"] = get_local_ip()
    event_body_map["timestamp"] = int(round(time.time() * 1000))
    event_body_map["dimension"] = {"bk_biz_id": bk_biz_id, "bk_biz_name": bk_biz_name}

    event_body_params = {
        "app_name": app.app_name,
        "app_alias": app.app_alias,
        "bk_biz_id": bk_biz_id,
        "bk_biz_name": bk_biz_name,
        "operator": operator,
        "operate_time": strftime_local(app.create_time)
        if rum_event is RUMEvent.APP_CREATE
        else strftime_local(app.update_time),
    }
    content = rum_event.event_template().format(**event_body_params)
    event_body_map["event"] = {"content": content}
    return [event_body_map]


@shared_task(ignore_result=True)
def report_rum_application_event(bk_biz_id, application_id, rum_event: RUMEvent):
    """
    RUM 应用事件上报
    """
    logger.info(f"[report_rum_application_event] task start, bk_biz_id({bk_biz_id}), application_id({application_id})")

    application = Application.objects.get(application_id=application_id)
    data = build_event_body(application, bk_biz_id, rum_event)
    config_info = settings.RUM_CUSTOM_EVENT_REPORT_CONFIG
    data_id = config_info.get("data_id", "")
    token = config_info.get("token", "")
    if config_info and token:
        custom_report_tool(data_id).send_data_by_http(data, token)
    else:
        logger.info("[report_rum_application_event] config is empty, do nothing")

    logger.info(
        f"[report_rum_application_event] task finished, bk_biz_id({bk_biz_id}), application_id({application_id})"
    )


@shared_task(ignore_result=True)
def application_create_check():
    """每分钟检查异步创建的应用是否已完成数据源创建，对齐 apm_web.application_create_check"""
    apps = Application.objects.filter(Q(span_result_table_id="") | Q(metric_result_table_id=""))
    logger.info(f"[RumCreateCheck] found {len(apps)} apps pending datasource sync")
    for app in apps:
        try:
            app.sync_datasource()
        except Exception as e:
            logger.exception(f"[RumCreateCheck] sync app({app.application_id}) failed: {e}")


@shared_task(ignore_result=True)
def refresh_application():
    logger.info("[REFRESH_APPLICATION] task start")

    for application in Application.objects.filter(is_enabled=True):
        set_local_tenant_id(application.bk_tenant_id)
        try:
            # 刷新数据状态
            application.set_data_status()
        except Exception as e:  # noqa
            logger.warning(
                f"[REFRESH_APPLICATION] refresh data failed: {application.bk_biz_id}{application.app_name}, error: {e}"
            )

    logger.info("[REFRESH_APPLICATION] task finished")
