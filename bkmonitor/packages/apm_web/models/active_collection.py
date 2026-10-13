"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from apm_web.profile.active_collection.constants import (
    COLLECTION_METHOD_CHOICES,
    COLLECTION_TYPE_CHOICES,
    DEPLOYMENT_STATUS_CHOICES,
    DEPLOYMENT_STATUS_DEPLOYING,
)
from bkmonitor.utils.model_manager import AbstractRecordModel


class ActiveProfilingTask(AbstractRecordModel):
    """主动 Profiling 的指定时间/周期计划，立即执行不落表"""

    # 提交与编辑共用的配置字段，顺序与协议文档一致
    CONFIG_FIELDS = (
        "name",
        "collection_method",
        "collection_type",
        "target_config",
        "process_selector",
        "schedule",
        "collector_config",
        "resource_guard_config",
    )

    bk_biz_id = models.IntegerField(verbose_name=_("业务 ID"), db_index=True)
    name = models.CharField(verbose_name=_("任务名称"), max_length=128)
    collection_method = models.CharField(verbose_name=_("采集方式"), max_length=32, choices=COLLECTION_METHOD_CHOICES)
    collection_type = models.CharField(verbose_name=_("采集类型"), max_length=32, choices=COLLECTION_TYPE_CHOICES)
    deployment_status = models.CharField(
        verbose_name=_("部署状态"),
        max_length=32,
        choices=DEPLOYMENT_STATUS_CHOICES,
        default=DEPLOYMENT_STATUS_DEPLOYING,
    )
    # 一个计划一个订阅，覆盖计划的全部目标主机；0 表示订阅还没建成
    subscription_id = models.IntegerField(verbose_name=_("节点管理订阅 ID"), default=0)

    target_config = models.JSONField(verbose_name=_("目标主机配置"), default=dict)
    process_selector = models.JSONField(verbose_name=_("进程选择器"), default=dict)
    schedule = models.JSONField(verbose_name=_("调度配置"), default=dict)
    collector_config = models.JSONField(verbose_name=_("采集参数"), default=dict)
    resource_guard_config = models.JSONField(verbose_name=_("资源保护参数"), default=dict)

    class Meta:
        index_together = [["bk_biz_id", "is_deleted"]]

    @classmethod
    def get_task(cls, bk_biz_id, task_id):
        task = cls.objects.filter(bk_biz_id=bk_biz_id, id=task_id).first()
        if not task:
            raise ValueError(_("计划不存在"))
        return task

    @classmethod
    def check_duplicated_name(cls, bk_biz_id, name, exclude_id=None):
        """任务名在业务内唯一。objects 走 RecordModelManager，已过滤 is_deleted，软删后名称可复用"""
        queryset = cls.objects.filter(bk_biz_id=bk_biz_id, name=name)
        if exclude_id is not None:
            queryset = queryset.exclude(id=exclude_id)
        if queryset.exists():
            raise ValueError(_("任务名称: {} 已存在").format(name))

    @classmethod
    def create_task(cls, bk_biz_id, validated_data):
        cls.check_duplicated_name(bk_biz_id, validated_data["name"])
        return cls.objects.create(bk_biz_id=bk_biz_id, **cls._config_from(validated_data))

    def update_config(self, validated_data):
        self.check_duplicated_name(self.bk_biz_id, validated_data["name"], exclude_id=self.id)
        for field, value in self._config_from(validated_data).items():
            setattr(self, field, value)
        self.deployment_status = DEPLOYMENT_STATUS_DEPLOYING
        self.save()

    @classmethod
    def _config_from(cls, validated_data):
        # Golang 不传 process_selector，落库时补空值
        return {field: validated_data.get(field, {}) for field in cls.CONFIG_FIELDS}
