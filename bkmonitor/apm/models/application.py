"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import uuid

from django.conf import settings
from django.db import models
from django.db.transaction import atomic
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from apm.constants import DATABASE_CONNECTION_NAME
from apm.models.datasource import (
    LogDataSource,
    MetricDataSource,
    ProfileDataSource,
    TraceDataSource,
)
from apm.utils.report_event import EventReportHelper
from bkmonitor.utils.cipher import (
    transform_data_id_to_token,
    transform_data_id_to_v1_token,
)
from bkmonitor.utils.model_manager import AbstractRecordModel
from constants.apm import TelemetryDataType
from constants.common import DEFAULT_TENANT_ID


class ApmApplication(AbstractRecordModel):
    bk_biz_id = models.IntegerField("业务id")
    app_name = models.CharField("应用名称", max_length=50)
    app_alias = models.CharField("应用别名", max_length=128)
    description = models.CharField("应用描述", max_length=255)

    token = models.CharField("应用 Token", max_length=256, default="")

    is_enabled = models.BooleanField("是否启用", default=True)

    # 数据源开关
    is_enabled_log = models.BooleanField("是否开启 Logs 功能", default=False)
    is_enabled_trace = models.BooleanField("是否开启 Traces 功能", default=True)
    is_enabled_metric = models.BooleanField("是否开启 Metrics 功能", default=True)
    is_enabled_profiling = models.BooleanField("是否开启 Profiling 功能", default=False)
    # 租户id
    bk_tenant_id = models.CharField("租户ID", max_length=64, default=DEFAULT_TENANT_ID)

    class Meta:
        unique_together = ("app_name", "bk_biz_id")

    def start_trace(self):
        """开启 Trace 数据源"""
        TraceDataSource.start(bk_biz_id=self.bk_biz_id, app_name=self.app_name)
        self.is_enabled = True
        self.is_enabled_trace = True
        self.save(update_fields=["is_enabled", "is_enabled_trace"])

    def start_metric(self):
        """开启 Metric 数据源"""
        MetricDataSource.start(bk_biz_id=self.bk_biz_id, app_name=self.app_name)
        self.is_enabled = True
        self.is_enabled_metric = True
        self.save(update_fields=["is_enabled", "is_enabled_metric"])

    def start_profiling(self):
        """开启 Profiling 数据源"""
        profile_datasource = ProfileDataSource.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name).first()
        if not profile_datasource:
            # 没有则同步创建
            try:
                # Profile
                ProfileDataSource.apply_datasource(bk_biz_id=self.bk_biz_id, app_name=self.app_name, option=True)
            except Exception as e:  # noqa
                self.send_datasource_apply_alert(TelemetryDataType.PROFILING.value)
                raise e

        ProfileDataSource.start(self.bk_biz_id, self.app_name)
        self.is_enabled = True
        self.is_enabled_profiling = True
        self.save(update_fields=["is_enabled", "is_enabled_profiling"])

    def start_log(self):
        """开启 Log 数据源"""
        log_datasource = LogDataSource.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name).first()
        if not log_datasource:
            # 没有则同步创建
            from apm.core.handlers.application_hepler import ApplicationHelper

            datasource_options = ApplicationHelper.get_default_storage_config(self.bk_biz_id, self.app_name)
            try:
                # Log
                LogDataSource.apply_datasource(
                    bk_biz_id=self.bk_biz_id,
                    app_name=self.app_name,
                    option=True,
                    **datasource_options,
                )
            except Exception as e:  # noqa
                self.send_datasource_apply_alert(TelemetryDataType.LOG.value)
                raise e

        LogDataSource.start(self.bk_biz_id, self.app_name)
        self.is_enabled = True
        self.is_enabled_log = True
        self.save(update_fields=["is_enabled", "is_enabled_log"])

    def stop_trace(self):
        TraceDataSource.stop(bk_biz_id=self.bk_biz_id, app_name=self.app_name)
        self.is_enabled_trace = False
        self.save(update_fields=["is_enabled_trace"])

    def stop_profiling(self):
        ProfileDataSource.stop(bk_biz_id=self.bk_biz_id, app_name=self.app_name)
        self.is_enabled_profiling = False
        self.save(update_fields=["is_enabled_profiling"])

    def stop_metric(self):
        MetricDataSource.stop(bk_biz_id=self.bk_biz_id, app_name=self.app_name)
        self.is_enabled_metric = False
        self.save(update_fields=["is_enabled_metric"])

    def stop_log(self):
        LogDataSource.stop(bk_biz_id=self.bk_biz_id, app_name=self.app_name)
        self.is_enabled_log = False
        self.save(update_fields=["is_enabled_log"])

    @classmethod
    def get_application(cls, bk_biz_id, app_name):
        try:
            return ApmApplication.objects.get(bk_biz_id=bk_biz_id, app_name=app_name)
        except ApmApplication.DoesNotExist:
            raise ValueError(_("应用不存在"))

    def apply_datasource(self, trace_storage_config, log_storage_config, options=None):
        """
        创建/更新应用的数据源 (支持重复执行)
        适用以下场景:
        1. 新建应用
        2. 更新应用数据源
        """
        if not options:
            # 如果没有 options 则从应用的字段中取功能开关
            options = {
                "is_enabled_trace": self.is_enabled_trace,
                "is_enabled_log": self.is_enabled_log,
                "is_enabled_metric": self.is_enabled_metric,
                "is_enabled_profiling": self.is_enabled_profiling,
            }

        # 更新字段
        ApmApplication.objects.filter(id=self.id).update(**options)

        try:
            if trace_storage_config:
                # Trace
                TraceDataSource.apply_datasource(
                    bk_biz_id=self.bk_biz_id,
                    app_name=self.app_name,
                    option=options["is_enabled_trace"],
                    **trace_storage_config,
                )
        except Exception as e:  # noqa
            self.send_datasource_apply_alert(TelemetryDataType.TRACE.value)
            raise e

        try:
            # Metric
            MetricDataSource.apply_datasource(
                bk_biz_id=self.bk_biz_id, app_name=self.app_name, option=options["is_enabled_metric"]
            )
        except Exception as e:  # noqa
            self.send_datasource_apply_alert(TelemetryDataType.METRIC.value)
            raise e

        try:
            if log_storage_config:
                # Log
                LogDataSource.apply_datasource(
                    bk_biz_id=self.bk_biz_id,
                    app_name=self.app_name,
                    option=options["is_enabled_log"],
                    **log_storage_config,
                )
        except Exception as e:  # noqa
            self.send_datasource_apply_alert(TelemetryDataType.LOG.value)
            raise e

        try:
            # Profile
            ProfileDataSource.apply_datasource(
                bk_biz_id=self.bk_biz_id,
                app_name=self.app_name,
                option=options["is_enabled_profiling"],
            )
        except Exception as e:  # noqa
            self.send_datasource_apply_alert(TelemetryDataType.PROFILING.value)
            raise e

        # 虚拟指标
        if self.bk_biz_id in settings.APM_CREATE_VIRTUAL_METRIC_ENABLED_BK_BIZ_ID:
            from apm.task.tasks import create_virtual_metric

            create_virtual_metric.delay(self.bk_biz_id, self.app_name)

    def send_datasource_apply_alert(self, data_type):
        EventReportHelper.report(
            f"[!!!] 应用: [{self.bk_biz_id}]{self.app_name} 创建/更新 {data_type} 数据源失败", application=self
        )

    @classmethod
    def check_application(cls, bk_biz_id, app_name):
        """检查应用是否已经存在"""
        # 只检查名称是否重名
        if cls.origin_objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first():
            raise ValueError(f"应用: {app_name} 已被创建，请尝试更换应用名称")

    @classmethod
    @atomic(using=DATABASE_CONNECTION_NAME)
    def create_application(
        cls, bk_tenant_id, bk_biz_id, app_name, app_alias, description, es_storage_config, options: dict | None = None
    ):
        cls.check_application(bk_biz_id, app_name)

        # step1: 创建应用
        application = cls.objects.create(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            app_name=app_name,
            app_alias=app_alias,
            token=uuid.uuid4().hex,  # 长度 32，(16 个随机字符的 16 进制表示)
            description=description,
        )

        # step2: 异步创建数据源
        from apm.task.tasks import create_application_async

        create_application_async.apply_async(args=(application.id, es_storage_config, options), countdown=3)

        return {
            "bk_biz_id": bk_biz_id,
            "app_name": app_name,
            "application_id": application.id,
            "datasource_option": es_storage_config,
        }

    @cached_property
    def trace_datasource(self) -> TraceDataSource:
        return TraceDataSource.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name).first()

    @cached_property
    def metric_datasource(self):
        return MetricDataSource.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name).first()

    @cached_property
    def profile_datasource(self):
        return ProfileDataSource.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name).first()

    @cached_property
    def log_datasource(self):
        return LogDataSource.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name).first()

    def get_bk_data_token(self):
        # 1. 优先使用 model 里的 token
        if self.token:
            return self.token

        # 2. 兼容逻辑，保留下面的 token 生成逻辑(历史已创建的应用，使用的是动态生成的 token)
        params = {
            "bk_biz_id": self.bk_biz_id,
            "app_name": self.app_name,
        }
        if self.trace_datasource:
            params["trace_data_id"] = self.trace_datasource.bk_data_id
        if self.metric_datasource:
            params["metric_data_id"] = self.metric_datasource.bk_data_id
        if self.log_datasource:
            params["log_data_id"] = self.log_datasource.bk_data_id
        if self.profile_datasource:
            params["profile_data_id"] = self.profile_datasource.bk_data_id
            # 一开始没有预留 profile 的位置，所以如果开启了 profile，需要走单独的函数生成 token
            return transform_data_id_to_v1_token(**params)
        return transform_data_id_to_token(**params)


class RootEndpoint(models.Model):
    id = models.BigAutoField(primary_key=True)
    bk_biz_id = models.IntegerField("业务id")
    app_name = models.CharField("应用名称", max_length=50)
    endpoint_name = models.CharField("接口", max_length=2048)
    service_name = models.CharField("服务名称", max_length=2048)
    category_id = models.CharField("分类名称", max_length=128)
    created_at = models.DateTimeField("创建时间", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("更新时间", blank=True, null=True, auto_now=True, db_index=True)

    class Meta:
        index_together = [["bk_biz_id", "app_name"]]


class Endpoint(models.Model):
    id = models.BigAutoField(primary_key=True)
    bk_biz_id = models.IntegerField("业务id")
    app_name = models.CharField("应用名称", max_length=50)
    endpoint_name = models.CharField("接口", max_length=2048)
    service_name = models.CharField("服务名称", max_length=2048)
    category_id = models.CharField("分类名称", max_length=128)
    category_kind_key = models.CharField("分类类型key", max_length=255)
    category_kind_value = models.CharField("分类类型值", max_length=255)
    span_kind = models.IntegerField("跟踪类型", default=0)
    extra_data = models.TextField(null=True, verbose_name="额外数据")
    created_at = models.DateTimeField("创建时间", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("更新时间", blank=True, null=True, auto_now=True, db_index=True)

    class Meta:
        index_together = [["bk_biz_id", "app_name"]]


class EbpfApplicationConfig(models.Model):
    bk_biz_id = models.IntegerField(verbose_name="业务id")
    application_id = models.IntegerField("应用Id")

    class Meta:
        verbose_name = "ebpf应用配置"


class BcsClusterDefaultApplicationRelation(models.Model):
    bk_biz_id = models.IntegerField("业务 ID")
    app_name = models.CharField("应用名称", max_length=50)

    cluster_id = models.CharField("集群 ID", max_length=128)

    class Meta:
        verbose_name = "BCS 集群中默认上报 APM 应用关联配置"

    @property
    def application(self):
        return ApmApplication.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name).first()
