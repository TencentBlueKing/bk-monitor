# -*- coding: utf-8 -*-
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
import hashlib
import json

import arrow
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.log_clustering.constants import (
    LogColShowTypeEnum,
    PatternEnum,
    RegexRuleTypeEnum,
    StrategiesType,
    SubscriptionTypeEnum,
    YearOnYearChangeEnum,
    YearOnYearEnum,
)
from apps.log_clustering.exceptions import ClusteringConfigNotExistException
from apps.models import SoftDeleteModel


class SampleSet(SoftDeleteModel):
    sample_set_id = models.IntegerField(_("样本集ID"), db_index=True)
    sample_set_name = models.CharField(_("样本集名称"), db_index=True, max_length=128)


class AiopsModel(SoftDeleteModel):
    model_id = models.CharField(_("模型ID"), db_index=True, max_length=128)
    model_name = models.CharField(_("模型名称"), db_index=True, max_length=128)


class AiopsModelExperiment(SoftDeleteModel):
    model_id = models.CharField(_("模型ID"), db_index=True, max_length=128)
    # experiment_id后续可能会变化，如需要进一步使用，需要手动维护
    experiment_id = models.IntegerField(_("实验id"), db_index=True)
    experiment_alias = models.CharField(_("实验名称"), db_index=True, max_length=128)
    status = models.CharField(_("实验状态"), null=True, blank=True, max_length=128)
    basic_model_id = models.CharField(_("最新模型实例id"), null=True, blank=True, max_length=128)
    node_id_list = models.JSONField(_("节点列表"), null=True, blank=True)

    @classmethod
    def get_experiment(cls, model_name: str, experiment_alias: str):
        model_id = AiopsModel.objects.get(model_name=model_name).model_id
        return AiopsModelExperiment.objects.filter(model_id=model_id, experiment_alias=experiment_alias).first()


class AiopsSignatureAndPattern(SoftDeleteModel):
    model_id = models.CharField(_("模型ID"), max_length=128)
    signature = models.CharField(_("数据指纹"), max_length=256)
    pattern = models.TextField("pattern")
    origin_pattern = models.TextField(_("原始pattern"), default="")
    label = models.TextField(_("标签"), default="")
    remark = models.JSONField(_("备注信息"), default=list, null=True, blank=True)
    owners = models.JSONField(_("负责人"), default=list, null=True, blank=True)

    class Meta:
        index_together = ["model_id", "signature"]


class ClusteringRemark(SoftDeleteModel):
    bk_biz_id = models.IntegerField(_("业务id"))
    signature = models.CharField(_("数据指纹"), max_length=256)
    origin_pattern = models.TextField(_("原始pattern"), default="")
    groups = models.JSONField(_("分组信息 kv格式"), default=dict, null=True, blank=True)
    group_hash = models.CharField(_("分组hash"), max_length=256)
    remark = models.JSONField(_("备注信息"), default=list, null=True, blank=True)
    owners = models.JSONField(_("负责人"), default=list, null=True, blank=True)

    class Meta:
        index_together = ["signature", "group_hash"]

    @classmethod
    def convert_groups_to_groups_hash(cls, groups: dict) -> str:
        """
        对 groups 字段进行 hash
        """
        sorted_groups = sorted(groups.items(), key=lambda x: x[0])
        return hashlib.md5(json.dumps(sorted_groups).encode("utf-8")).hexdigest()


class ClusteringConfig(SoftDeleteModel):
    group_fields = models.JSONField(_("分组字段"), default=list, null=True, blank=True)
    collector_config_id = models.IntegerField(_("采集项id"), null=True, blank=True)
    collector_config_name_en = models.CharField(_("采集项英文名"), max_length=255, null=True, blank=True)
    index_set_id = models.IntegerField(_("索引集id"), db_index=True)
    sample_set_id = models.IntegerField(_("样本集id"), null=True, blank=True)
    model_id = models.CharField(_("模型id"), max_length=128, null=True, blank=True)
    min_members = models.IntegerField(_("最小日志数量"))
    max_dist_list = models.CharField(_("敏感度"), max_length=128)
    predefined_varibles = models.TextField(_("预先定义的正则表达式"))
    delimeter = models.TextField(_("分词符"))
    max_log_length = models.IntegerField(_("最大日志长度"))
    is_case_sensitive = models.IntegerField(_("是否大小写忽略"), default=0)
    depth = models.IntegerField(_("搜索树深度"), default=5)
    max_child = models.IntegerField(_("搜索树最大子节点数"), default=100)
    clustering_fields = models.CharField(_("聚合字段"), max_length=128)
    filter_rules = models.JSONField(_("过滤规则"), null=True, blank=True)
    bk_biz_id = models.IntegerField(_("业务id"))
    related_space_pre_bk_biz_id = models.IntegerField(_("关联空间业务id之前的业务id"), null=True, blank=True)
    pre_treat_flow = models.JSONField(_("预处理flow配置"), null=True, blank=True)
    new_cls_pattern_rt = models.CharField(_("新类结果表id"), max_length=255, default="", null=True, blank=True)
    new_cls_index_set_id = models.IntegerField(_("新聚类类索引集id"), null=True, blank=True)
    bkdata_data_id = models.IntegerField(_("计算平台接入dataid"), null=True, blank=True)
    bkdata_etl_result_table_id = models.CharField(_("计算平台清洗结果表"), max_length=255, null=True, blank=True)
    bkdata_etl_processing_id = models.CharField(_("计算平台清洗id"), max_length=255, null=True, blank=True)
    log_bk_data_id = models.IntegerField(_("入库数据源"), null=True, blank=True)
    signature_enable = models.BooleanField(_("数据指纹开关"), default=False)
    pre_treat_flow_id = models.IntegerField(_("预处理flowid"), null=True, blank=True)
    after_treat_flow = models.JSONField(_("after_treat_flow配置"), null=True, blank=True)
    after_treat_flow_id = models.IntegerField(_("模型应用flowid"), null=True, blank=True)
    source_rt_name = models.CharField(_("源rt名"), max_length=255, null=True, blank=True)
    category_id = models.CharField(_("数据分类"), max_length=64, null=True, blank=True, default=None)
    python_backend = models.JSONField(_("模型训练配置"), null=True, blank=True)
    es_storage = models.CharField(_("es 集群"), max_length=64, null=True, blank=True, default=None)
    modify_flow = models.JSONField(_("修改after_treat_flow调用的配置"), null=True, blank=True)
    options = models.JSONField(_("额外配置"), null=True, blank=True)
    task_records = models.JSONField(_("任务记录"), default=list)
    # task_details 任务详情格式 list of dict as below
    # {
    #     "node_id": node_id,  # 节点id
    #     "node_name": node_name,  # 节点名称
    #     "status": status,  # 状态
    #     "message": message,  # 任务信息
    #     "exc_info": exc_info,  # 异常信息
    #     "create_at": now,  # 创建时间
    #     "update_at": now,  # 更新时间
    # }
    task_details = models.JSONField(_("任务详情"), default=dict)
    model_output_rt = models.CharField(_("模型输出结果表"), max_length=255, default="", null=True, blank=True)
    clustered_rt = models.CharField(_("聚类结果表"), max_length=255, default="", null=True, blank=True)
    signature_pattern_rt = models.CharField(_("Pattern 结果表"), max_length=255, default="", null=True, blank=True)
    predict_flow = models.JSONField(_("predict_flow配置"), null=True, blank=True)
    predict_flow_id = models.IntegerField(_("预测flow_id"), null=True, blank=True)
    online_task_id = models.IntegerField(_("在线任务id"), null=True, blank=True)
    log_count_aggregation_flow = models.JSONField(_("日志数量聚合flow配置"), null=True, blank=True)
    log_count_aggregation_flow_id = models.IntegerField(_("日志数量聚合flow_id"), null=True, blank=True)
    new_cls_strategy_enable = models.BooleanField(_("是否开启新类告警"), default=False)
    new_cls_strategy_output = models.CharField(_("日志新类告警输出结果表"), max_length=255, default="", null=True, blank=True)
    normal_strategy_enable = models.BooleanField(_("是否开启数量突增告警"), default=False)
    normal_strategy_output = models.CharField(_("日志数量告警输出结果表"), max_length=255, default="", null=True, blank=True)
    access_finished = models.BooleanField(_("是否接入完成"), default=True)

    regex_rule_type = models.CharField(
        _("规则类型"),
        max_length=64,
        choices=RegexRuleTypeEnum.get_choices(),
        default=RegexRuleTypeEnum.CUSTOMIZE.value,
    )
    regex_template_id = models.IntegerField(_("模板ID"), default=0)

    @classmethod
    def get_by_index_set_id(cls, index_set_id: int, raise_exception: bool = True) -> "ClusteringConfig":
        try:
            return ClusteringConfig.objects.get(index_set_id=index_set_id)
        except ClusteringConfig.DoesNotExist:
            try:
                return ClusteringConfig.objects.get(new_cls_index_set_id=index_set_id)
            except ClusteringConfig.DoesNotExist:
                if raise_exception:
                    raise ClusteringConfigNotExistException()
                else:
                    return None

    @classmethod
    def get_by_flow_id(cls, flow_id: int, raise_exception: bool = True):
        try:
            return ClusteringConfig.objects.get(
                Q(pre_treat_flow_id=flow_id) | Q(after_treat_flow_id=flow_id) | Q(predict_flow_id=flow_id)
            )
        except ClusteringConfig.DoesNotExist:
            if raise_exception:
                raise ClusteringConfigNotExistException()

    @classmethod
    def update_task_details(cls, index_set_id, pipline_id, node_id, node_name, status, message="", exc_info=""):
        """
        更新任务详情
        """
        conf = cls.get_by_index_set_id(index_set_id, raise_exception=False)
        if not conf:
            return

        conf.task_details = conf.task_details or {}
        conf.task_details.setdefault(pipline_id, [])

        now = arrow.now().format("YYYY-MM-DD HH:mm:ss")

        # 查找当前节点，如果已经存在则更新，
        for step in conf.task_details[pipline_id]:
            if step["node_id"] == node_id:
                step.update(status=status, message=message, exc_info=exc_info, update_at=now)
                break
        else:
            conf.task_details[pipline_id].append(
                {
                    "node_id": node_id,
                    "node_name": node_name,
                    "status": status,
                    "message": message,
                    "exc_info": exc_info,
                    "create_at": now,
                    "update_at": now,
                }
            )

        conf.save(update_fields=["task_details"])


class SignatureStrategySettings(SoftDeleteModel):
    signature = models.CharField(_("数据指纹"), max_length=256, db_index=True, blank=True)
    index_set_id = models.IntegerField(_("索引集id"), db_index=True)
    strategy_id = models.IntegerField(_("监控策略id"), null=True, blank=True)
    enabled = models.BooleanField(_("是否启用"), default=True)
    bk_biz_id = models.IntegerField(_("业务id"))
    pattern_level = models.CharField(_("聚类级别"), max_length=64, null=True, blank=True)
    strategy_type = models.CharField(
        _("策略类型"), max_length=64, null=True, blank=True, default=StrategiesType.NORMAL_STRATEGY
    )

    @classmethod
    def get_monitor_config(cls, signature, index_set_id, pattern_level):
        signature_strategy_settings = SignatureStrategySettings.objects.filter(
            signature=signature, index_set_id=index_set_id, pattern_level=pattern_level
        ).first()
        if not signature_strategy_settings:
            return {
                "is_active": False,
                "strategy_id": None,
            }
        return {"is_active": True, "strategy_id": signature_strategy_settings.strategy_id}


class NoticeGroup(SoftDeleteModel):
    index_set_id = models.IntegerField(_("索引集id"), db_index=True)
    notice_group_id = models.IntegerField(_("通知人组id"))
    bk_biz_id = models.IntegerField(_("业务id"), null=True, blank=True)


class ClusteringSubscription(SoftDeleteModel):
    """
    # frequency 频率&发送范围存储格式示例
    {
        "type": 1,
        "day_list": [],
        "run_time": "10",
        "week_list": [1, 2, 3, 4, 5, 6, 7],
        "data_range": {
            "number": 30,
            "time_level": "minutes"
        }
    }
    """

    subscription_type = models.CharField(
        _("订阅类型"),
        max_length=64,
        choices=SubscriptionTypeEnum.get_choices(),
        default=SubscriptionTypeEnum.WECHAT.value,
    )
    space_uid = models.CharField(_("空间ID"), db_index=True, max_length=256)
    index_set_id = models.IntegerField(_("索引集id"), db_index=True)
    title = models.TextField(_("标题"))
    receivers = models.JSONField(_("接收人"))
    managers = models.JSONField(_("管理员"))
    frequency = models.JSONField(_("发送频率"))
    pattern_level = models.CharField(
        _("敏感度"), choices=PatternEnum.get_choices(), max_length=64, default=PatternEnum.LEVEL_05.value
    )
    log_display_count = models.IntegerField(_("日志条数"), default=5)
    log_col_show_type = models.CharField(
        _("日志列显示"), choices=LogColShowTypeEnum.get_choices(), max_length=64, default=LogColShowTypeEnum.PATTERN.value
    )
    group_by = models.JSONField(_("统计维度"), default=[], null=True, blank=True)
    year_on_year_hour = models.IntegerField(
        _("同比"), choices=YearOnYearEnum.get_choices(), default=YearOnYearEnum.NOT.value
    )
    year_on_year_change = models.CharField(
        _("同比变化"), choices=YearOnYearChangeEnum.get_choices(), default=YearOnYearChangeEnum.ALL.value, max_length=64
    )
    query_string = models.TextField(_("查询语句"), default="*", null=True, blank=True)
    addition = models.JSONField(_("查询条件"), default=[], null=True, blank=True)
    host_scopes = models.JSONField(_("主机范围"), default={}, null=True, blank=True)
    is_show_new_pattern = models.BooleanField(_("是否只要新类"), default=True)
    is_enabled = models.BooleanField(_("是否启用"), default=True)
    last_run_at = models.DateTimeField(_("最后运行时间"), blank=True, null=True)

    created_at = models.DateTimeField(_("创建时间"), auto_now_add=True)
    updated_at = models.DateTimeField(_("更新时间"), auto_now=True)

    class Meta:
        verbose_name = _("日志聚类订阅")
        verbose_name_plural = _("日志聚类订阅")


class RegexTemplate(models.Model):
    space_uid = models.CharField(_("空间唯一标识"), db_index=True, max_length=256)
    template_name = models.CharField(_("模板名称"), db_index=True, max_length=256)
    predefined_varibles = models.TextField(_("模板的正则表达式"))

    class Meta:
        verbose_name = _("聚类正则模板")
        verbose_name_plural = _("聚类正则模板")
