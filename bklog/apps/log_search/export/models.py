"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.log_search.constants import (
    ExportJobStatus,
    ExportPartStatus,
    ExportPlanStatus,
    ExportStage,
)


class ExportJob(models.Model):
    """
    一条用户可见的逻辑导出任务。

    一期只支持单索引集、时间维度分片：任务被规划成若干个左闭右开的时间区间（ExportPart），
    每个分片独立执行、独立压缩上传，最终由 Manifest 汇总。
    """

    space_uid = models.CharField(_("空间标识"), max_length=256)
    created_by = models.CharField(_("创建者"), max_length=64)
    source_app_code = models.CharField(_("来源系统"), max_length=32, blank=True, default="")
    is_external = models.BooleanField(_("外部版任务"), default=False)
    index_set_id = models.IntegerField(_("索引集ID"))
    bk_biz_id = models.IntegerField(_("业务ID"), null=True, blank=True)
    search_params = models.JSONField(_("冻结查询参数"))
    base_dict = models.JSONField(_("冻结查询体"))
    policy = models.JSONField(_("任务策略快照"), default=dict)
    start_time = models.BigIntegerField(_("起始时间（毫秒，闭区间）"))
    end_time = models.BigIntegerField(_("结束时间（毫秒，开区间）"))
    status = models.CharField(
        _("状态"), max_length=16, choices=ExportJobStatus.CHOICES, default=ExportJobStatus.PENDING
    )
    estimated_total = models.PositiveBigIntegerField(_("预计总条数"), null=True, blank=True)
    # 叶子分片 actual_rows 的聚合快照，分片变更时整体重算
    actual_total = models.PositiveBigIntegerField(_("已导出条数"), default=0)
    # 当前生效的计划版本。当前只有 0 -> 1：规划成功后任务进入 READY 就不允许再规划，
    # 规划失败重试刻意复用同一版本号，因此版本递进依赖后续的"重新规划"入口。
    plan_version = models.PositiveIntegerField(_("当前生效计划版本"), default=0)
    requested_parallelism = models.PositiveSmallIntegerField(_("期望并行上限"), default=4)
    manifest_object_key = models.CharField(_("清单对象名"), max_length=1024, blank=True, default="")
    manifest_bytes = models.PositiveBigIntegerField(_("清单字节数"), null=True, blank=True)
    # 清单文件自身的 sha256，下载方可以据此校验清单没有被截断或篡改
    manifest_checksum = models.CharField(_("清单SHA256"), max_length=64, blank=True, default="")
    error_code = models.CharField(_("错误分类"), max_length=64, blank=True, default="")
    error_detail = models.TextField(_("错误详情"), blank=True, default="")
    planning_started_at = models.DateTimeField(_("规划开始时间"), null=True, blank=True)
    planning_attempts = models.PositiveIntegerField(_("规划尝试次数"), default=0)
    last_dispatched_at = models.DateTimeField(_("最近投递时间"), null=True, blank=True)
    started_at = models.DateTimeField(_("开始执行时间"), null=True, blank=True)
    completed_at = models.DateTimeField(_("完成时间"), null=True, blank=True)
    expires_at = models.DateTimeField(_("产物过期时间"), null=True, blank=True)
    created_at = models.DateTimeField(_("创建时间"), auto_now_add=True)
    updated_at = models.DateTimeField(_("更新时间"), auto_now=True)

    class Meta:
        db_table = "log_export_job"
        verbose_name = _("分片导出任务")
        verbose_name_plural = _("43_分片导出任务")
        indexes = [
            models.Index(fields=["created_by", "status", "created_at"], name="export_job_user_status"),
            models.Index(fields=["space_uid", "created_at", "id"], name="export_job_space_history"),
            models.Index(fields=["status", "last_dispatched_at"], name="export_job_dispatch"),
        ]


class ExportPlan(models.Model):
    """一个计划版本的规划输入与产出快照；版本只由成功落库的计划递增。"""

    job = models.ForeignKey(ExportJob, on_delete=models.CASCADE, related_name="plans")
    plan_version = models.PositiveIntegerField(_("计划版本"))
    status = models.CharField(
        _("规划状态"), max_length=16, choices=ExportPlanStatus.CHOICES, default=ExportPlanStatus.PLANNING
    )
    target_rows = models.PositiveBigIntegerField(_("目标条数"), null=True, blank=True)
    target_bytes = models.PositiveBigIntegerField(_("目标字节数"), null=True, blank=True)
    total_rows = models.PositiveBigIntegerField(_("统计总条数"), null=True, blank=True)
    avg_row_bytes = models.PositiveBigIntegerField(_("平均单条字节数"), null=True, blank=True)
    initial_interval_ms = models.PositiveBigIntegerField(_("初始统计桶（毫秒）"), null=True, blank=True)
    planned_parts = models.PositiveIntegerField(_("预计分片数"), null=True, blank=True)
    started_at = models.DateTimeField(_("规划开始时间"), null=True, blank=True)
    finished_at = models.DateTimeField(_("规划结束时间"), null=True, blank=True)
    created_at = models.DateTimeField(_("创建时间"), auto_now_add=True)
    updated_at = models.DateTimeField(_("更新时间"), auto_now=True)

    class Meta:
        db_table = "log_export_plan"
        verbose_name = _("分片导出计划")
        verbose_name_plural = _("45_分片导出计划")
        unique_together = (("job", "plan_version"),)


class ExportPart(models.Model):
    """规划产出的一个固定时间区间，是调度、重试和产物管理的最小单位。"""

    job = models.ForeignKey(ExportJob, on_delete=models.CASCADE, related_name="parts")
    part_no = models.PositiveIntegerField(_("分片序号"))
    plan_version = models.PositiveIntegerField(_("所属计划版本"), default=0)
    # 细分血缘：父分片转为 SPLIT 后不再产出产物
    parent_part = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children", verbose_name=_("父分片")
    )
    start_time = models.BigIntegerField(_("起始时间（毫秒，闭区间）"))
    end_time = models.BigIntegerField(_("结束时间（毫秒，开区间）"))
    # 已经递归到时间字段最小精度仍然超量，一期直接按原样执行并在清单中标记
    oversized = models.BooleanField(_("已到最小时间精度仍超量"), default=False)
    estimated_rows = models.PositiveBigIntegerField(_("预计条数"), null=True, blank=True)
    estimated_bytes = models.PositiveBigIntegerField(_("预计字节数"), null=True, blank=True)
    actual_rows = models.PositiveBigIntegerField(_("实际条数"), null=True, blank=True)
    actual_bytes = models.PositiveBigIntegerField(_("实际JSONL字节数"), null=True, blank=True)
    compressed_bytes = models.PositiveBigIntegerField(_("压缩后字节数"), null=True, blank=True)
    status = models.CharField(
        _("状态"), max_length=16, choices=ExportPartStatus.CHOICES, default=ExportPartStatus.WAITING
    )
    stage = models.CharField(_("阶段"), max_length=16, choices=ExportStage.CHOICES, blank=True, default="")
    attempts = models.PositiveIntegerField(_("执行次数"), default=0)
    task_id = models.CharField(_("Celery任务ID"), max_length=255, blank=True, default="")
    object_key = models.CharField(_("产物对象名"), max_length=1024, blank=True, default="")
    checksum = models.CharField(_("产物SHA256"), max_length=64, blank=True, default="")
    started_at = models.DateTimeField(_("本次执行开始时间"), null=True, blank=True)
    finished_at = models.DateTimeField(_("本次执行结束时间"), null=True, blank=True)
    error_code = models.CharField(_("错误分类"), max_length=64, blank=True, default="")
    error_detail = models.TextField(_("错误详情"), blank=True, default="")
    created_at = models.DateTimeField(_("创建时间"), auto_now_add=True)
    updated_at = models.DateTimeField(_("更新时间"), auto_now=True)

    class Meta:
        db_table = "log_export_part"
        verbose_name = _("分片导出子任务")
        verbose_name_plural = _("44_分片导出子任务")
        unique_together = (("job", "plan_version", "part_no"),)
        indexes = [
            models.Index(fields=["job", "status"], name="export_part_job_status"),
            models.Index(fields=["status", "updated_at"], name="export_part_recover"),
        ]
