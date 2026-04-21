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

from django.db import models
from django.db.transaction import atomic
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from bkmonitor.utils.model_manager import AbstractRecordModel
from constants.common import DEFAULT_TENANT_ID
from rum.constants import DATABASE_CONNECTION_NAME
from rum.models.datasource import MetricDataSource, RumDataSource


class RumApplication(AbstractRecordModel):
    """RUM 应用模型"""

    bk_biz_id = models.IntegerField("业务id")
    app_name = models.CharField("应用名称", max_length=50)
    app_alias = models.CharField("应用别名", max_length=128)
    description = models.CharField("应用描述", max_length=255, default="")
    type = models.CharField("前端类型", max_length=32, default="web")
    token = models.CharField("前端接入 Token", max_length=64, default="")
    is_enabled = models.BooleanField("是否启用", default=True)
    bk_tenant_id = models.CharField("租户ID", max_length=64, default=DEFAULT_TENANT_ID)

    class Meta:
        unique_together = ("app_name", "bk_biz_id")

    def start_rum(self):
        """开启应用（整体启动：RUM 数据源 + Metric 数据源）"""
        RumDataSource.start(bk_biz_id=self.bk_biz_id, app_name=self.app_name)
        MetricDataSource.start(bk_biz_id=self.bk_biz_id, app_name=self.app_name)
        self.is_enabled = True
        self.save(update_fields=["is_enabled"])

    def stop_rum(self):
        """关闭应用（整体停止：Metric 数据源 + RUM 数据源）"""
        MetricDataSource.stop(bk_biz_id=self.bk_biz_id, app_name=self.app_name)
        RumDataSource.stop(bk_biz_id=self.bk_biz_id, app_name=self.app_name)
        self.is_enabled = False
        self.save(update_fields=["is_enabled"])

    def start_metric(self):
        """开启 Metric 数据源（单独操作，不影响 is_enabled）"""
        MetricDataSource.start(bk_biz_id=self.bk_biz_id, app_name=self.app_name)

    def stop_metric(self):
        """关闭 Metric 数据源（单独操作，不影响 is_enabled）"""
        MetricDataSource.stop(bk_biz_id=self.bk_biz_id, app_name=self.app_name)

    @classmethod
    def get_application(cls, bk_biz_id, app_name):
        try:
            return RumApplication.objects.get(bk_biz_id=bk_biz_id, app_name=app_name)
        except RumApplication.DoesNotExist:
            raise ValueError(_("应用不存在"))

    @classmethod
    def check_application(cls, bk_biz_id, app_name):
        """检查应用是否已经存在"""
        if cls.origin_objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first():
            raise ValueError(f"应用: {app_name} 已被创建，请尝试更换应用名称")

    @classmethod
    @atomic(using=DATABASE_CONNECTION_NAME)
    def create_application(cls, bk_tenant_id, bk_biz_id, app_name, app_alias, description, es_storage_config):
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
        from rum.task.tasks import create_application_async

        create_application_async.apply_async(args=(application.id, es_storage_config), countdown=3)

        return {
            "bk_biz_id": bk_biz_id,
            "app_name": app_name,
            "application_id": application.id,
            "datasource_option": es_storage_config,
        }

    def apply_datasource(self, es_storage_config):
        """
        创建/更新应用的数据源 (支持重复执行)
        RUM 只有两种数据源: rum_datasource (原始日志) 和 metric_datasource (指标)
        """
        try:
            # RUM 原始数据源
            RumDataSource.apply_datasource(
                bk_biz_id=self.bk_biz_id,
                app_name=self.app_name,
                option=True,
                **es_storage_config,
            )
        except Exception as e:
            raise e

        try:
            # Metric 数据源
            MetricDataSource.apply_datasource(
                bk_biz_id=self.bk_biz_id,
                app_name=self.app_name,
                option=True,
            )
        except Exception as e:
            raise e

    @cached_property
    def rum_datasource(self):
        return RumDataSource.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name).first()

    @cached_property
    def metric_datasource(self):
        return MetricDataSource.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name).first()

    def get_bk_data_token(self):
        """获取上报 token，优先使用 model 里的 token"""
        if self.token:
            return self.token
