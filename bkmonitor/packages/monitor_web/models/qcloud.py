"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _lazy

from bkmonitor.utils.db.fields import JsonField
from bkcrypto.contrib.django.fields import SymmetricTextField
from bkmonitor.utils.model_manager import AbstractRecordModel


class CloudProduct(AbstractRecordModel):
    """
    云产品配置模型

    用于存储腾讯云等云厂商的产品基础信息
    """

    namespace = models.CharField(
        max_length=64, unique=True, verbose_name="产品命名空间", help_text="云产品的命名空间，如: QCE/CVM, QCE/CLB"
    )

    product_name = models.CharField(
        max_length=255, verbose_name="产品名称", help_text="云产品的完整名称，如: 云服务器 CVM"
    )

    description = models.TextField(blank=True, default="", verbose_name="产品描述", help_text="云产品的详细描述")

    class Meta:
        verbose_name = "云产品配置"
        verbose_name_plural = "云产品配置"
        db_table = "monitor_cloud_product"
        app_label = "monitor_web"


class CloudProductMetric(AbstractRecordModel):
    """
    云产品指标配置模型

    用于存储云产品的监控指标信息
    """

    namespace = models.CharField(
        max_length=64, verbose_name="产品命名空间", help_text="云产品的命名空间，如: QCE/CVM", db_index=True
    )

    metric_name = models.CharField(
        max_length=64,
        verbose_name="指标名称",
        help_text="监控指标的名称，如: CPUUtilization",
    )

    display_name = models.CharField(max_length=64, verbose_name="显示名称", help_text="指标的显示名称，如: CPU使用率")

    description = models.TextField(blank=True, default="", verbose_name="指标描述", help_text="监控指标的详细描述")

    unit = models.CharField(
        max_length=32, blank=True, default="", verbose_name="单位", help_text="指标的单位，如: %, MB/s"
    )

    dimensions = JsonField(
        default=list, verbose_name="维度列表", help_text="指标的维度信息，如: ['InstanceId', 'RegionId']"
    )

    is_active = models.BooleanField(default=True, verbose_name="是否启用", help_text="是否启用该指标的监控功能")

    class Meta:
        verbose_name = "云产品指标配置"
        verbose_name_plural = "云产品指标配置"
        db_table = "monitor_cloud_product_metric"
        app_label = "monitor_web"


class CloudProductInstanceField(AbstractRecordModel):
    """
    云产品实例字段定义

    仅存储每个云产品(namespace)的实例返回数据中需要展示/过滤的重要字段及其展示名称。
    不落地实例与日志数据，实例查询走实时接口。
    """

    namespace = models.CharField(
        max_length=64,
        verbose_name="产品命名空间",
        help_text="云产品命名空间，如: QCE/CVM",
        db_index=True,
    )

    field_name = models.CharField(
        max_length=64,
        verbose_name="字段名",
        help_text="实例数据中的字段名，如: InstanceId、InstanceName",
    )

    display_name = models.CharField(
        max_length=255,
        verbose_name="展示名称",
        help_text="该字段在前端展示的名称，如: 实例ID、实例名称",
        default="",
        blank=True,
    )

    description = models.TextField(
        verbose_name="字段描述",
        help_text="字段用途、示例等描述信息",
        default="",
        blank=True,
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="是否启用",
        help_text="是否向用户展示该字段",
    )

    class Meta:
        verbose_name = "云产品实例字段"
        verbose_name_plural = "云产品实例字段"
        db_table = "monitor_cloud_product_instance_field"
        app_label = "monitor_web"


class CloudProductTagField(AbstractRecordModel):
    """
    云产品标签字段配置模型

    存储每个云产品的预设标签字段，用于用户筛选实例时的固定标签选项。
    这些标签字段是系统预定义的，用户在配置实例选择时可以基于这些标签进行筛选。
    """

    namespace = models.CharField(
        max_length=64,
        verbose_name="产品命名空间",
        help_text="云产品命名空间，如: QCE/CVM",
        db_index=True,
    )

    tag_name = models.CharField(
        max_length=64,
        verbose_name="Tag名称",
        help_text="Tag的名称，如: env、app、project",
    )

    display_name = models.CharField(
        max_length=255,
        verbose_name="显示名称",
        help_text="Tag在前端展示的名称，如: 环境、应用、项目",
        default="",
        blank=True,
    )

    description = models.TextField(
        verbose_name="Tag描述",
        help_text="Tag的用途和说明",
        default="",
        blank=True,
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="是否启用",
        help_text="是否向用户展示该标签字段",
    )

    class Meta:
        verbose_name = "云产品标签字段配置"
        verbose_name_plural = "云产品标签字段配置"
        db_table = "monitor_cloud_product_tag_field"
        app_label = "monitor_web"


class CloudMonitoringTask(AbstractRecordModel):
    """
    云监控采集任务模型

    用于存储云监控采集任务的配置信息
    """

    # 任务状态选择
    STATUS_CONNECTING = "connecting"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_STOPPED = "stopped"

    STATUS_CHOICES = [
        (STATUS_CONNECTING, _lazy("接入中")),
        (STATUS_SUCCESS, _lazy("成功")),
        (STATUS_FAILED, _lazy("失败")),
        (STATUS_STOPPED, _lazy("已停用")),
    ]

    task_id = models.CharField(
        max_length=64, unique=True, verbose_name="任务ID", help_text="监控任务的唯一标识符", db_index=True
    )

    bk_biz_id = models.IntegerField(verbose_name="业务ID", help_text="蓝鲸业务ID", db_index=True)

    namespace = models.CharField(
        max_length=64, verbose_name="产品命名空间", help_text="云产品的命名空间，如: QCE/CVM", db_index=True
    )

    collect_name = models.CharField(max_length=255, verbose_name="采集名称", help_text="监控采集任务的名称")

    collect_interval = models.CharField(
        max_length=32, verbose_name="采集间隔", help_text="监控数据采集间隔，如: 1m, 5m", default="1m"
    )

    collect_timeout = models.CharField(
        max_length=32, verbose_name="采集超时时间", help_text="单次采集的超时时间，如: 30s, 60s", default="30s"
    )

    # 分字段加密存储凭证
    secret_id = SymmetricTextField(
        verbose_name="SecretId",
        help_text="云账号的 SecretId（加密存储）",
        blank=True,
        default="",
        max_length=256,
    )

    secret_key = SymmetricTextField(
        verbose_name="SecretKey",
        help_text="云账号的 SecretKey（加密存储）",
        blank=True,
        default="",
        max_length=256,
    )

    is_internal = models.BooleanField(default=True, verbose_name="是否内部环境", help_text="采集器是否部署在内部环境")

    is_international = models.BooleanField(default=True, verbose_name="是否国际版", help_text="目标云厂商是否为国际版")

    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default=STATUS_CONNECTING,
        verbose_name="任务状态",
        help_text="监控任务的当前状态",
    )

    latest_datapoint = models.DateTimeField(
        null=True, blank=True, verbose_name="最新数据点时间", help_text="最新收到数据的时间"
    )

    data_id = models.IntegerField(verbose_name="数据ID", null=True, blank=True, help_text="监控数据源的 data_id")

    class Meta:
        verbose_name = "云监控采集任务"
        verbose_name_plural = "云监控采集任务"
        db_table = "monitor_cloud_monitoring_task"
        app_label = "monitor_web"


class CloudMonitoringTaskRegion(AbstractRecordModel):
    """
    云监控采集任务地域配置模型

    单独存储每个任务下的地域配置信息
    """

    # 地域状态选择
    STATUS_CONNECTING = "connecting"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_STOPPED = "stopped"

    STATUS_CHOICES = [
        (STATUS_CONNECTING, _lazy("接入中")),
        (STATUS_SUCCESS, _lazy("成功")),
        (STATUS_FAILED, _lazy("失败")),
        (STATUS_STOPPED, _lazy("已停用")),
    ]

    task_id = models.CharField(max_length=64, verbose_name="任务ID", help_text="关联的监控任务ID", db_index=True)

    region_id = models.IntegerField(verbose_name="地域序号", help_text="地域配置的存储顺序ID")

    region_code = models.CharField(max_length=64, verbose_name="地域代码", help_text="云厂商的地域代码，如: ap-beijing")

    tags_config = JsonField(
        default=list,
        verbose_name="标签配置",
        help_text="实例标签筛选配置，格式: [{'name': 'env', 'values': ['prod'], 'fuzzy': false}]",
    )

    filters_config = JsonField(
        default=list,
        verbose_name="过滤器配置",
        help_text="实例过滤器配置，格式: [{'name': 'instance-state-name', 'values': ['running']}]",
    )

    selected_metrics = JsonField(default=list, verbose_name="选择的指标", help_text="该地域需要采集的监控指标列表")

    dimensions_config = JsonField(
        default=list, verbose_name="维度配置", help_text="自定义维度配置，支持add_dimension等操作"
    )

    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default=STATUS_CONNECTING,
        verbose_name="地域状态",
        help_text="该地域的采集状态",
    )

    last_log_time = models.DateTimeField(
        null=True, blank=True, verbose_name="最后日志时间", help_text="该地域最后的日志记录时间"
    )

    class Meta:
        verbose_name = "云监控采集任务地域配置"
        verbose_name_plural = "云监控采集任务地域配置"
        db_table = "monitor_cloud_monitoring_task_region"
        app_label = "monitor_web"
