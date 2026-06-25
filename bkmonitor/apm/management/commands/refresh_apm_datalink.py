"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
import json

from django.conf import settings
from django.core.management import BaseCommand, CommandError

from apm.models import ApmApplication, MetricDataSource
from core.drf_resource import api
from metadata.models import DataSource
from metadata.models.custom_report.time_series import TimeSeriesGroup

logger = logging.getLogger("apm")


class Command(BaseCommand):
    help = "刷新 APM 应用的指标分组维度配置"

    def add_arguments(self, parser):
        parser.add_argument("-d", "--bk_data_id", type=int, help="数据源 ID")
        parser.add_argument("-b", "--bk_biz_id", type=int, help="业务 ID")
        parser.add_argument("-a", "--app_name", type=str, help="APM 应用名称")
        parser.add_argument(
            "--metric_group_dimensions",
            type=str,
            required=True,
            help='自定义 metric_group_dimensions 的 JSON 字符串，如 \'[{"key":"scope_name","default_value":"default"}]\'',
        )

    def handle(self, *args, **options):
        bk_data_id = options.get("bk_data_id")
        bk_biz_id = options.get("bk_biz_id")
        app_name = options.get("app_name")
        metric_group_dimensions_text = options.get("metric_group_dimensions")
        if metric_group_dimensions_text:
            try:
                metric_group_dimensions = json.loads(metric_group_dimensions_text)
            except json.JSONDecodeError as exc:
                raise CommandError(f"metric_group_dimensions JSON 格式错误: {exc}") from exc

            if not isinstance(metric_group_dimensions, list):
                raise CommandError("metric_group_dimensions 必须为 JSON 数组")

        if not bk_data_id and not (bk_biz_id and app_name):
            raise CommandError("必须传入 --bk_data_id，或同时传入 --bk_biz_id 和 --app_name")

        # 1. 获取数据源 ID
        if not bk_data_id:
            # 校验 APM 应用存在
            application = ApmApplication.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
            if not application:
                self.stderr.write(f"APM 应用不存在: bk_biz_id={bk_biz_id}, app_name={app_name}")
                return

            metric_ds = MetricDataSource.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
            if not metric_ds:
                self.stderr.write(f"MetricDataSource 不存在: bk_biz_id={bk_biz_id}, app_name={app_name}")
                return

            # 检查全局开关和白名单（支持业务级灰度：业务ID 整业务通过，业务ID-应用名 单应用通过）
            whitelist = settings.APM_METRIC_GROUP_DIMENSIONS_WHITELIST
            biz_key = str(bk_biz_id)
            app_key = f"{bk_biz_id}-{app_name}"
            if (
                not settings.APM_METRIC_GROUP_DIMENSIONS_ENABLED
                and biz_key not in whitelist
                and app_key not in whitelist
            ):
                self.stderr.write(
                    f"应用 {app_key} 不在 APM_METRIC_GROUP_DIMENSIONS_WHITELIST 白名单中，当前白名单: {whitelist}"
                )
                return

            bk_data_id = metric_ds.bk_data_id

        # 2. 获取 DataSource（用于获取 bk_tenant_id）
        try:
            data_source = DataSource.objects.get(bk_data_id=bk_data_id)
        except DataSource.DoesNotExist:
            self.stderr.write(f"Metadata DataSource 不存在: bk_data_id={bk_data_id}")
            return

        # 3. 获取 TimeSeriesGroup
        ts_group = TimeSeriesGroup.objects.filter(bk_data_id=bk_data_id, is_delete=False).first()
        if not ts_group:
            self.stderr.write(f"TimeSeriesGroup 不存在: bk_data_id={bk_data_id}")
            return

        self.stdout.write(
            f"TimeSeriesGroup: group_id={ts_group.time_series_group_id}, "
            f"table_id={ts_group.table_id}, "
            f"当前 metric_group_dimensions={ts_group.metric_group_dimensions}"
        )

        # 4. 调用 modify API 更新 metric_group_dimensions
        bk_tenant_id = data_source.bk_tenant_id
        try:
            api.metadata.modify_time_series_group(
                bk_tenant_id=bk_tenant_id,
                time_series_group_id=ts_group.time_series_group_id,
                operator="system",
                metric_group_dimensions=metric_group_dimensions,
            )
            self.stdout.write(f"已更新 metric_group_dimensions -> {metric_group_dimensions}")
        except Exception as e:
            self.stderr.write(f"更新失败: {e}")
            raise
