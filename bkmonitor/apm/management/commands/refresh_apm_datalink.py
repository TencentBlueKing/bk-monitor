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
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from metadata.models import DataSource, Space
from metadata.models.custom_report.time_series import TimeSeriesGroup
from metadata.models.data_link.data_link import DataLink
from metadata.models.data_link.utils import compose_bkdata_data_id_name
from metadata.models.vm.utils import get_vm_cluster_id_name

logger = logging.getLogger("apm")

# APM 场景下的 metric_group_dimensions 固定配置
APM_METRIC_GROUP_DIMENSIONS = [
    {"key": "service_name", "default_value": "unknown_service"},
    {"key": "scope_name", "default_value": "default"},
]


class Command(BaseCommand):
    help = "刷新 APM 应用的 Metric 数据链路配置"

    def add_arguments(self, parser):
        parser.add_argument("-b", "--bk_biz_id", type=int, required=True, help="业务 ID")
        parser.add_argument("-a", "--app_name", type=str, required=True, help="APM 应用名称")
        parser.add_argument(
            "--metric_group_dimensions",
            type=str,
            help='自定义 metric_group_dimensions 的 JSON 字符串，如 \'[{"key":"service_name","default_value":"unknown_service"}]\'',
        )

    def handle(self, *args, **options):
        bk_biz_id = options["bk_biz_id"]
        app_name = options["app_name"]
        metric_group_dimensions_text = options.get("metric_group_dimensions")
        metric_group_dimensions = APM_METRIC_GROUP_DIMENSIONS
        if metric_group_dimensions_text:
            try:
                metric_group_dimensions = json.loads(metric_group_dimensions_text)
            except json.JSONDecodeError as exc:
                raise CommandError(f"metric_group_dimensions JSON 格式错误: {exc}") from exc

            if not isinstance(metric_group_dimensions, list):
                raise CommandError("metric_group_dimensions 必须为 JSON 数组")

        # 1. 检查白名单
        whitelist = settings.APM_METRIC_GROUP_DIMENSIONS_WHITELIST
        app_key = f"{bk_biz_id}-{app_name}"
        if app_key not in whitelist:
            self.stderr.write(
                f"应用 {app_key} 不在 APM_METRIC_GROUP_DIMENSIONS_WHITELIST 白名单中，当前白名单: {whitelist}"
            )
            return

        # 2. 校验 APM 应用存在
        application = ApmApplication.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
        if not application:
            self.stderr.write(f"APM 应用不存在: bk_biz_id={bk_biz_id}, app_name={app_name}")
            return

        # 3. 获取 MetricDataSource
        metric_ds = MetricDataSource.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
        if not metric_ds:
            self.stderr.write(f"MetricDataSource 不存在: bk_biz_id={bk_biz_id}, app_name={app_name}")
            return

        if not metric_ds.result_table_id:
            self.stderr.write("MetricDataSource 的 result_table_id 为空，数据链路尚未初始化")
            return

        self.stdout.write(
            f"MetricDataSource: bk_data_id={metric_ds.bk_data_id}, result_table_id={metric_ds.result_table_id}"
        )

        # 4. 获取 metadata DataSource
        try:
            data_source = DataSource.objects.get(bk_data_id=metric_ds.bk_data_id)
        except DataSource.DoesNotExist:
            self.stderr.write(f"Metadata DataSource 不存在: bk_data_id={metric_ds.bk_data_id}")
            return

        # 5. 更新 TimeSeriesGroup.metric_group_dimensions
        ts_group = TimeSeriesGroup.objects.filter(bk_data_id=metric_ds.bk_data_id, is_delete=False).first()
        if not ts_group:
            self.stderr.write(f"TimeSeriesGroup 不存在: bk_data_id={metric_ds.bk_data_id}")
            return

        self.stdout.write(
            f"TimeSeriesGroup: group_id={ts_group.time_series_group_id}, "
            f"当前 metric_group_dimensions={ts_group.metric_group_dimensions}"
        )
        ts_group.metric_group_dimensions = metric_group_dimensions
        ts_group.save(update_fields=["metric_group_dimensions"])
        self.stdout.write(f"已更新 metric_group_dimensions -> {metric_group_dimensions}")

        # 6. 查找 DataLink 实例
        bkbase_data_name = compose_bkdata_data_id_name(data_source.data_name)
        data_link = DataLink.objects.filter(data_link_name=bkbase_data_name).first()
        if not data_link:
            self.stderr.write(f"DataLink 不存在: data_link_name={bkbase_data_name}")
            return

        self.stdout.write(
            f"DataLink: data_link_name={data_link.data_link_name}, "
            f"strategy={data_link.data_link_strategy}, "
            f"bk_tenant_id={data_link.bk_tenant_id}"
        )

        # 7. 获取 VM 集群名称
        bk_tenant_id = bk_biz_id_to_bk_tenant_id(bk_biz_id)
        space_data = {}
        try:
            space_data = Space.objects.get_space_info_by_biz_id(int(bk_biz_id))
        except Exception as e:
            logger.warning("获取空间信息失败: bk_biz_id=%s, error=%s", bk_biz_id, e)

        vm_cluster = get_vm_cluster_id_name(
            bk_tenant_id=bk_tenant_id,
            space_type=space_data.get("space_type", ""),
            space_id=space_data.get("space_id", ""),
        )
        storage_cluster_name = vm_cluster["cluster_name"]
        self.stdout.write(f"VM 集群: {storage_cluster_name}")

        # 8. 下发配置
        try:
            data_link.apply_data_link(
                bk_biz_id=bk_biz_id,
                data_source=data_source,
                table_id=metric_ds.result_table_id,
                storage_cluster_name=storage_cluster_name,
            )
            self.stdout.write("下发成功")
        except Exception as e:
            self.stderr.write(f"下发失败: {e}")
            raise
