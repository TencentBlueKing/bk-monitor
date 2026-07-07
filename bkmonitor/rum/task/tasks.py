"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import traceback

from opentelemetry.trace import get_current_span

from alarm_backends.service.scheduler.app import app
from common.log import logger
from rum.models import RumAppConfig, RumApplication
from rum.core.application_config import RumApplicationConfig


@app.task(ignore_result=True, queue="celery_cron")
def create_application_async(application_id, es_storage_config, cur_retry_times=0):
    """
    异步创建 RUM 应用数据源
    """
    try:
        application = RumApplication.objects.get(id=application_id)
    except RumApplication.DoesNotExist:
        logger.error(f"[create_application_async] RumApplication(id={application_id}) not found")
        return

    try:
        application.apply_datasource(es_storage_config)
        logger.info(
            f"[create_application_async] application: {application.bk_biz_id}-{application.app_name} "
            f"datasource created successfully"
        )
    except Exception as e:
        logger.error(f"[create_application_async] app_id:{application_id} error: {e}\n{traceback.format_exc()}")
        next_retry_times = cur_retry_times + 1
        if next_retry_times <= 2:
            create_application_async.apply_async(
                args=(application_id, es_storage_config, next_retry_times),
                countdown=next_retry_times * 60,
            )
        return

    RumApplicationConfig.refresh_k8s([application])


@app.task(ignore_result=True, queue="celery_cron")
def delete_application_async(bk_biz_id, app_name, operator=None):
    """
    异步删除 RUM 应用
    """
    application = RumApplication.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
    if not application:
        logger.info(f"[DeleteRumApplication] application: {bk_biz_id}-{app_name} not found")
        return

    # QPS 清理：将 qps 配置设为 -1（RUM 的 QPS/Apdex 统一在 RumAppConfig 中）
    try:
        qps_configs = RumAppConfig.get_configs_by_category(bk_biz_id, app_name, "qps")
        if qps_configs:
            RumAppConfig.refresh_config(
                bk_biz_id=bk_biz_id,
                app_name=app_name,
                scope_type=RumAppConfig.APPLICATION_LEVEL,
                scope_key="",
                refresh_configs=[{"config_type": "qps:default", "config_value": -1}],
            )
    except Exception as e:
        logger.warning(f"[DeleteRumApplication] clear qps config failed: {e}")

    refresh_rum_application_config(bk_biz_id, app_name)

    try:
        application.stop_rum()
        logger.info(f"[DeleteRumApplication] operator: {operator} deleted application: ({bk_biz_id}){app_name}")
    except Exception as e:
        logger.exception(
            f"[DeleteRumApplication] stop app: {bk_biz_id}-{app_name} failed {e}\n{traceback.format_exc()}"
        )
        get_current_span().record_exception(e)

    application.delete()


def refresh_rum_config_to_k8s():
    """
    刷新所有 RUM 应用的 K8s 配置（获取全部数据进行批量调度）
    """
    # 获取所有启用的应用
    applications = list(RumApplication.objects.filter(is_enabled=True))
    if not applications:
        return

    try:
        RumApplicationConfig.refresh_k8s(applications)
        logger.info(f"[refresh_rum_config_to_k8s]: batch publish k8s config for {len(applications)} applications")
    except Exception as e:  # pylint: disable=broad-except
        logger.exception(f"[RefreshRumApplicationK8sConfigFailed] Err => {str(e)}; Applications => {applications}")


@app.task(ignore_result=True, queue="celery_cron")
def refresh_rum_application_config(bk_biz_id, app_name):
    _app = RumApplication.objects.get(bk_biz_id=bk_biz_id, app_name=app_name)
    RumApplicationConfig.refresh_k8s([_app])
