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

from apm.constants import ACTIVE_PROFILING_DEPLOYMENT_DEPLOYING
from bkmonitor.utils.model_manager import AbstractRecordModel
from constants.common import DEFAULT_TENANT_ID


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

    bk_biz_id = models.IntegerField("业务 ID", db_index=True)
    name = models.CharField("任务名称", max_length=128)
    collection_method = models.CharField("采集方式", max_length=32)
    collection_type = models.CharField("采集类型", max_length=32)
    deployment_status = models.CharField("部署状态", max_length=32, default=ACTIVE_PROFILING_DEPLOYMENT_DEPLOYING)
    # 一个计划一个订阅，覆盖计划的全部目标主机；0 表示订阅还没建成
    subscription_id = models.IntegerField("节点管理订阅 ID", default=0)

    target_config = models.JSONField("目标主机配置", default=dict)
    process_selector = models.JSONField("进程选择器", default=dict)
    schedule = models.JSONField("调度配置", default=dict)
    collector_config = models.JSONField("采集参数", default=dict)
    resource_guard_config = models.JSONField("资源保护参数", default=dict)

    class Meta:
        verbose_name = "主动 Profiling 计划"
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
        self.deployment_status = ACTIVE_PROFILING_DEPLOYMENT_DEPLOYING
        self.save()

    @classmethod
    def _config_from(cls, validated_data):
        # Golang 不传 process_selector，落库时补空值
        return {field: validated_data.get(field, {}) for field in cls.CONFIG_FIELDS}


class ActiveProfilingExecution(models.Model):
    """主动 Profiling 的一次执行，可能覆盖多台主机。
    由 BMW 预计算与 SaaS 写入，BMW 按同一结构直接写库，数据库列上没有 Django 默认值，写入方要显式填写全部非空列"""

    bk_tenant_id = models.CharField("租户 ID", max_length=64, default=DEFAULT_TENANT_ID)
    bk_biz_id = models.IntegerField("业务 ID")
    schedule_type = models.CharField("执行方式", max_length=16)
    # 计划执行为计划 ID，立即执行为本行 id；改造前上报的立即执行没有 task_id，写 0，不用 NULL 以免唯一索引失效
    task_id = models.IntegerField("任务 ID", default=0)
    scheduled_at = models.BigIntegerField("执行计划时间")
    task_name = models.CharField("任务名称", max_length=128)
    creator = models.CharField("创建人", max_length=128)
    collection_method = models.CharField("采集方式", max_length=32)
    collection_type = models.CharField("采集类型", max_length=32)
    execution_status = models.CharField("执行状态", max_length=32)
    status_summary = models.JSONField("主机状态计数", default=dict)
    target_count = models.IntegerField("主机数", default=0)
    # 全部主机都还是占位行时没有开始时间
    started_at = models.BigIntegerField("开始时间", null=True)
    finished_at = models.BigIntegerField("结束时间", null=True)
    config = models.JSONField("执行配置", default=dict)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "主动 Profiling 执行"
        unique_together = ("bk_tenant_id", "bk_biz_id", "task_id", "scheduled_at")
        # 末尾补上排序列，任务历史按 scheduled_at、task_id 同向倒序时直接沿索引读，不用对整个时间范围排序
        index_together = [
            ["bk_tenant_id", "bk_biz_id", "scheduled_at", "task_id"],
            ["bk_tenant_id", "bk_biz_id", "execution_status", "scheduled_at", "task_id"],
        ]

    @classmethod
    def get_execution(cls, bk_tenant_id, bk_biz_id, scheduled_at, task_id=None):
        """按执行定位键查找。前端不给立即执行传 task_id，按立即执行与计划时间定位，
        同一业务同一毫秒提交两次立即执行时可能定位到另一次，按极小概率接受"""
        queryset = cls.objects.filter(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, scheduled_at=scheduled_at)
        if task_id is None:
            queryset = queryset.filter(schedule_type="immediate")
        else:
            queryset = queryset.filter(task_id=task_id)
        execution = queryset.first()
        if execution is None:
            raise ValueError(_("执行记录不存在"))
        return execution


class ActiveProfilingHostExecution(models.Model):
    """主动 Profiling 一次执行中的一台主机，没有外键，冗余所属执行的业务与计划时间，供已采数据直接分页"""

    execution_id = models.IntegerField("执行 ID")
    bk_biz_id = models.IntegerField("业务 ID")
    scheduled_at = models.BigIntegerField("执行计划时间")
    bk_host_id = models.IntegerField("主机 ID")
    ip = models.CharField("执行时 IP", max_length=64, default="")
    status = models.CharField("主机执行状态", max_length=32)
    # 还没有任何 Event 的占位行没有开始时间
    started_at = models.BigIntegerField("开始时间", null=True)
    finished_at = models.BigIntegerField("结束时间", null=True)
    # 取 finished 的 error_type，前端按类型给出展示文案；成功、超时、取消与旧版采集端为空串
    error_type = models.CharField("失败类型", max_length=32, default="")
    # 取 finished 的 message：失败与部分成功时为原因，成功时为空串，接口展示为采集成功
    message = models.TextField("执行信息", default="")
    process_names = models.TextField("进程名", default="")
    process_pids = models.TextField("进程 PID", default="")
    processes = models.JSONField("采集进程", default=list)
    # 当前生效 Event 的上报时间，用于判断后到的同阶段 Event 是否更新；占位行为 0
    event_time = models.BigIntegerField("生效 Event 时间")
    unknown_at = models.BigIntegerField("转为 unknown 的时间", null=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "主动 Profiling 主机执行"
        unique_together = ("execution_id", "bk_host_id")
        # 末尾补上排序列，已采数据按 scheduled_at、execution_id、bk_host_id 同向倒序时直接沿索引读
        index_together = [["bk_biz_id", "scheduled_at", "execution_id", "bk_host_id"]]
