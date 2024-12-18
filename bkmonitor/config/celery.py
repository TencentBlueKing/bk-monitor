# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import os

from celery import Celery, platforms
from celery.schedules import crontab
from django.conf import settings

from config.tools.rabbitmq import get_rabbitmq_settings

# http://docs.celeryproject.org/en/latest/userguide/daemonizing.html#running-the-worker-with-superuser-privileges-root
# for root start celery

platforms.C_FORCE_ROOT = True

# set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

app = Celery("proj")

*_, celery_broker_url = get_rabbitmq_settings(settings.APP_CODE)


class Config:
    broker_url = celery_broker_url
    result_backend = "django_celery_results.backends:DatabaseBackend"
    beat_scheduler = "monitor.schedulers.MonitorDatabaseScheduler"

    task_serializer = "pickle"
    result_serializer = "pickle"
    accept_content = ["pickle"]

    timezone = "Asia/Shanghai"

    schedule = {
        "monitor_web.tasks.update_config_instance_count": {
            "task": "monitor_web.tasks.update_config_instance_count",
            "schedule": crontab(minute=0),
            "enabled": False,
        },
        "monitor_web.tasks.update_external_approval_status": {
            "task": "monitor_web.tasks.update_external_approval_status",
            "schedule": crontab(minute="*/10"),
            "enabled": True,
        },
        "monitor_web.tasks.update_metric_list": {
            "task": "monitor_web.tasks.update_metric_list",
            "schedule": crontab(),
            "enabled": True,
            "options": {"queue": "celery_resource"},
        },
        "monitor_web.tasks.access_pending_aiops_strategy": {
            "task": "monitor_web.tasks.access_pending_aiops_strategy",
            "schedule": crontab(minute="*/5"),
            "enabled": True,
        },
        "monitor_web.tasks.update_uptime_check_task_status": {
            "task": "monitor_web.tasks.update_uptime_check_task_status",
            "schedule": crontab(minute="*/10"),
            "enabled": True,
        },
        "monitor_web.tasks.maintain_aiops_strategies": {
            "task": "monitor_web.tasks.maintain_aiops_strategies",
            "schedule": crontab(minute="*/10"),
            "enabled": False,
        },
        "fta_web.tasks.update_home_statistics": {
            "task": "fta_web.tasks.update_home_statistics",
            "schedule": crontab(minute="*/5"),
            "enabled": True,
        },
        "monitor_web.tasks.update_report_receivers": {
            "task": "monitor_web.tasks.update_report_receivers",
            "schedule": crontab(minute=27, hour=2),
            "enabled": True,
        },
        "apm_web.tasks.refresh_application": {
            "task": "apm_web.tasks.refresh_application",
            "schedule": crontab(minute="*/10"),
            "enabled": True,
        },
        "apm_web.tasks.refresh_apm_application_metric": {
            "task": "apm_web.tasks.refresh_apm_application_metric",
            "schedule": crontab(minute="*/10"),
            "enabled": True,
        },
        "apm_web.tasks.application_create_check": {
            "task": "apm_web.tasks.application_create_check",
            "schedule": crontab(minute="*/1"),
            "enabled": True,
        },
        "apm_web.tasks.cache_application_scope_name": {
            "task": "apm_web.tasks.cache_application_scope_name",
            "schedule": crontab(minute="*/60"),
            "enabled": True,
        },
        "monitor_web.tasks.refresh_dashboard_strategy_snapshot": {
            "task": "monitor_web.tasks.refresh_dashboard_strategy_snapshot",
            "schedule": crontab(minute="*/60"),
            "enabled": True,
            "options": {"queue": "celery_resource"},
        },
        "monitor_web.tasks.update_statistics_data": {
            "task": "monitor_web.tasks.update_statistics_data",
            "schedule": crontab(),
            "enabled": True,
        },
        "monitor_web.tasks.clean_bkrepo_temp_file": {
            "task": "monitor_web.tasks.clean_bkrepo_temp_file",
            "schedule": crontab(hour="*/1"),
            "enabled": True,
            "options": {"queue": "celery_resource"},
        },
        "monitor_web.tasks.update_metric_json_from_ts_group": {
            "task": "monitor_web.tasks.update_metric_json_from_ts_group",
            "schedule": crontab(minute="*/50"),
            "enabled": True,
        },
        "monitor_web.tasks.update_target_detail": {
            "task": "monitor_web.tasks.update_target_detail",
            "schedule": crontab(minute="*/15"),
            "enabled": True,
        },
    }


# Using a string here means the worker don't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object(Config)

# Load task modules from all registered Django app configs.
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
