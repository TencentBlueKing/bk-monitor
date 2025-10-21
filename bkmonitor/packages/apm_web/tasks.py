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
import time
from datetime import datetime, timedelta
from enum import Enum

from celery import shared_task
from django.conf import settings
from django.core.cache import caches, cache
from django.db.models import Q
from django.utils.functional import cached_property
from django.utils.translation import gettext as _

from apm_web.constants import ApmCacheKey
from apm_web.handlers.metric_group import MetricHelper
from apm_web.handlers.service_handler import ServiceHandler
from apm_web.models import Application
from apm_web.profile.file_handler import ProfilingFileHandler
from apm_web.serializers import ApplicationCacheSerializer
from apm_web.strategy.builtin.registry import BuiltinStrategyTemplateRegistry
from apm_web.strategy.handler import StrategyTemplateHandler
from monitor.models import GlobalConfig
from bkmonitor.utils.common_utils import compress_and_serialize, get_local_ip, deserialize_and_decompress
from bkmonitor.utils.custom_report_tools import custom_report_tool
from bkmonitor.utils.tenant import set_local_tenant_id
from bkmonitor.utils.time_tools import strftime_local
from common.log import logger
from constants.apm import TelemetryDataType
from core.drf_resource import api


class APMEvent(Enum):
    APP_CREATE = "app_create"
    APP_UPDATE = "app_update"

    @cached_property
    def event_name(self):
        return {"app_create": _("新APM应用创建"), "app_update": _("APM应用更新")}.get(self.value)

    def event_template(self, data_sources: dict = None, updated_telemetry_types: list = None):
        data_sources_template = _("变更的数据源: ")
        if updated_telemetry_types:
            data_sources_template += "、".join(updated_telemetry_types)

        content = _("应用当前整体状态为: ")
        if data_sources:
            for key, value in data_sources.items():
                value = "enabled" if value else "disabled"
                content += _("\n - {}: {};").format(key, value)
        body_template = {
            "app_create": _(
                "\n有新 APM 应用创建，请关注！"
                "\n应用名称：{app_name},"
                "\n应用别名：{app_alias}, "
                "\n业务 ID：{bk_biz_id}, "
                "\n业务名称：{bk_biz_name}, "
                "\n创建者：{operator}，"
                "\n创建时间：{operate_time}"
            ),
            "app_update": _(
                "\n有 APM 应用更新，请关注！"
                "\n应用名称：{app_name},"
                "\n应用别名：{app_alias}, "
                "\n业务 ID：{bk_biz_id}, "
                "\n业务名称：{bk_biz_name}, "
                "\n更新者：{operator}，"
                "\n更新时间：{operate_time}"
            ),
        }.get(self.value)
        if updated_telemetry_types:
            return body_template + "\n" + data_sources_template + "\n" + content
        else:
            return body_template + "\n" + content


def build_event_body(
    app: Application,
    bk_biz_id: int,
    apm_event: APMEvent,
    data_sources: dict = None,
    updated_telemetry_types: list = None,
):
    bk_biz_name = ""
    operator = (app.create_user if apm_event is APMEvent.APP_CREATE else app.update_user,)
    event_body_map = {"event_name": _("监控平台{}").format(apm_event.event_name)}

    from bkm_space.api import SpaceApi
    from bkm_space.define import SpaceTypeEnum

    space = SpaceApi.get_space_detail(bk_biz_id=bk_biz_id)
    if space is not None:
        bk_biz_name = space.space_name
        if space.space_type_id == SpaceTypeEnum.BKSAAS.value:
            # 对于 PAAS 平台创建的 APM 应用，临时通过通知组<<应用成员>>来获取用户
            SAAS_NOTICE_GROUP_NAME = "应用成员"
            from bkmonitor.models import UserGroup

            operators = []
            qs = UserGroup.objects.filter(bk_biz_id=bk_biz_id, name=SAAS_NOTICE_GROUP_NAME)
            if qs.exists():
                for dr in qs.first().duty_arranges:
                    operators.extend([user["id"] for user in dr.users if user["type"] == "user"])

            if operators:
                operator = ",".join(operators)

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
        if apm_event is APMEvent.APP_CREATE
        else strftime_local(app.update_time),
    }
    content = apm_event.event_template(data_sources, updated_telemetry_types).format(**event_body_params)
    event_body_map["event"] = {"content": content}
    return [event_body_map]


@shared_task(ignore_result=True)
def update_application_config(bk_biz_id, app_name, config):
    api.apm_api.release_app_config({"bk_biz_id": bk_biz_id, "app_name": app_name, **config})


@shared_task(ignore_result=True)
def refresh_application():
    logger.info("[REFRESH_APPLICATION] task start")

    for application in Application.objects.filter(is_enabled=True):
        set_local_tenant_id(application.bk_tenant_id)
        try:
            # 刷新数据状态
            application.set_data_status()
            # 刷新服务数量和数据状态
            application.set_service_count_and_data_status()
        except Exception as e:  # noqa
            logger.warning(
                f"[REFRESH_APPLICATION] refresh data failed: {application.bk_biz_id}{application.app_name}, error: {e}"
            )

    logger.info("[REFRESH_APPLICATION] task finished")


@shared_task(ignore_result=True)
def report_apm_application_event(
    bk_biz_id, application_id, apm_event: APMEvent, data_sources: dict = None, updated_telemetry_types: list = None
):
    logger.info(f"[report_apm_application_event] task start, bk_biz_id({bk_biz_id}), application_id({application_id})")

    application = Application.objects.get(application_id=application_id)
    data = build_event_body(application, bk_biz_id, apm_event, data_sources, updated_telemetry_types)
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


@shared_task(ignore_result=True)
def refresh_apm_application_metric():
    logger.info("[refresh_apm_application_metric] task start")

    # 刷新 APM 应用列表页, 应用指标数据
    queryset = Application.objects.filter(
        ~Q(metric_result_table_id=""), metric_result_table_id__isnull=False, is_enabled=True
    )

    applications = ApplicationCacheSerializer(queryset, many=True).data

    ServiceHandler.refresh_application_cache_data(applications)

    logger.info("[refresh_apm_application_metric] task finished")


@shared_task(ignore_result=True)
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


@shared_task(ignore_result=True)
def application_create_check():
    """
    每分钟检查异步创建的应用是否已经创建完成
    如果创建完成 则同步数据至 apm_web 表
    如果创建失败 则发送通知 + 清理数据
    """

    # 获取所有没有 traceDatasource && metricDatasource 的应用(证明是未进行 saas 数据源同步的应用)
    # 因创建失败是偶尔事件并且会发送通知所以这里可以一直尝试同步
    apps = Application.objects.filter(Q(trace_result_table_id="") | Q(metric_result_table_id=""))
    logger.info(f"[CreateCheck] found {len(apps)} app were created and not datasource")
    for app in apps:
        app.sync_datasource()


@shared_task(ignore_result=True)
def cache_application_scope_name():
    """
    1. 每次获取 5 分钟内的数据
    2. 和已有的缓存数据做一个整合
    """
    logger.info("[CACHE_APPLICATION_SCOPE_NAME] task start")
    if "redis" not in caches:
        logger.info("[CACHE_APPLICATION_SCOPE_NAME] no redis cache, task stopped")
        return

    cache_agent = caches["redis"]
    for application in Application.objects.filter(is_enabled=True, is_enabled_metric=True):
        try:
            bk_biz_id = application.bk_biz_id
            application_id = application.application_id
            result_table_id = application.fetch_datasource_info(
                TelemetryDataType.METRIC.value, attr_name="result_table_id"
            )
            if result_table_id is None:
                continue

            monitor_info = MetricHelper.get_monitor_info(bk_biz_id, result_table_id)
            if monitor_info and isinstance(monitor_info, dict):
                cache_key = ApmCacheKey.APP_SCOPE_NAME_KEY.format(bk_biz_id=bk_biz_id, application_id=application_id)
                cached_data = cache_agent.get(cache_key)
                old_monitor_info = deserialize_and_decompress(cached_data) if cached_data else {}
                merged_monitor_info = MetricHelper.merge_monitor_info(monitor_info, old_monitor_info)
                cache_agent.set(cache_key, compress_and_serialize(merged_monitor_info))
                cache_agent.expire(cache_key, 60 * 60 * 24)
        except Exception as e:  # noqa
            logger.warning(
                f"[REFRESH_APPLICATION] refresh data failed: {application.bk_biz_id}{application.app_name}, error: {e}"
            )

    logger.info("[CACHE_APPLICATION_SCOPE_NAME] task finished")


@shared_task(ignore_result=True)
def refresh_apm_app_state_snapshot():
    all_data_status = {}
    for application in Application.objects.filter(is_enabled=True).values(
        "application_id",
        "bk_biz_id",
        "app_name",
        "app_alias",
        "trace_data_status",
        "metric_data_status",
        "log_data_status",
        "profiling_data_status",
    ):
        data_status = {
            "bk_biz_id": application["bk_biz_id"],
            "app_name": application["app_name"],
            "app_alias": application["app_alias"],
            TelemetryDataType.TRACE.value: application["trace_data_status"],
            TelemetryDataType.METRIC.value: application["metric_data_status"],
            TelemetryDataType.LOG.value: application["log_data_status"],
            TelemetryDataType.PROFILING.value: application["profiling_data_status"],
        }
        all_data_status[application["application_id"]] = data_status
    key = ApmCacheKey.APP_APPLICATION_STATUS_KEY.format(date=(datetime.now() - timedelta(days=1)).strftime("%Y%m%d"))
    cache.set(key, json.dumps(all_data_status), 7 * 24 * 60 * 60)


@shared_task(ignore_result=True)
def auto_register_apm_builtin_strategy_template():
    logger.info("[AUTO_REGISTER_APM_BUILTIN_STRATEGY_TEMPLATE] task start")

    config_obj, _ = GlobalConfig.objects.get_or_create(key="apm_register_builtin_strategy_template_version")
    current_map: dict[str, str] = config_obj.value if isinstance(config_obj.value, dict) else {}
    applied_map: dict[str, str] = {}
    for app in Application.objects.filter(is_enabled=True):
        map_key = f"{app.bk_biz_id}-{app.app_name}"
        current = current_map.get(map_key, "-")
        try:
            current_version, current_system_str = current.rsplit("-", 1) if "-" in current else ("", "")
            current_systems: list[str] = current_system_str.split("|") if current_system_str else []
            applied_map[map_key] = current
            registry = BuiltinStrategyTemplateRegistry(app)
            if not registry.is_need_register(current_version, current_systems):
                continue
            registry.register()
            applied_map[map_key] = (
                f"{BuiltinStrategyTemplateRegistry.BUILTIN_STRATEGY_TEMPLATE_VERSION}-{'|'.join(registry.systems)}"
            )
        except Exception as e:
            logger.exception(
                f"[AUTO_REGISTER_APM_BUILTIN_STRATEGY_TEMPLATE] apply failed: "
                f"bk_biz_id={app.bk_biz_id}, app_name={app.app_name}, "
                f"current={current}, "
                f"expect_version={BuiltinStrategyTemplateRegistry.BUILTIN_STRATEGY_TEMPLATE_VERSION}, "
                f"error_info => {e}"
            )

    config_obj.value = applied_map
    config_obj.save()

    logger.info("[AUTO_REGISTER_APM_BUILTIN_STRATEGY_TEMPLATE] task finished")


@shared_task(ignore_result=True)
def auto_apply_strategy_template():
    logger.info("[AUTO_APPLY_STRATEGY_TEMPLATE] task start")

    for application in Application.objects.filter(is_enabled=True).values("bk_biz_id", "app_name"):
        bk_biz_id: int = application["bk_biz_id"]
        app_name: str = application["app_name"]

        try:
            StrategyTemplateHandler.handle_auto_apply(bk_biz_id, app_name)
        except Exception as e:
            logger.exception(
                f"[AUTO_APPLY_STRATEGY_TEMPLATE] auto apply strategy template failed: "
                f"bk_biz_id={bk_biz_id}, app_name={app_name}, error_info => {e}"
            )

    logger.info("[AUTO_APPLY_STRATEGY_TEMPLATE] task finished")
