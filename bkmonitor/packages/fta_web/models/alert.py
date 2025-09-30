# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import time
from contextlib import contextmanager

from django.db import models
from django.utils.translation import gettext_lazy as _

from bkmonitor.utils.common_utils import count_md5
from bkmonitor.utils.db import JsonField
from bkmonitor.utils.model_manager import AbstractRecordModel


class SearchType:
    ALERT = "alert"
    EVENT = "event"
    ACTION = "action"
    INCIDENT = "incident"


SEARCH_TYPE_CHOICES = (
    (SearchType.ALERT, _("告警")),
    (SearchType.EVENT, _("事件")),
    (SearchType.ACTION, _("处理动作")),
    (SearchType.INCIDENT, _("故障")),
)


# 检索历史保留数量
HISTORY_RESERVED_COUNT = 100


class SearchHistory(AbstractRecordModel):
    """
    检索历史
    """

    search_type = models.CharField("检索类型", choices=SEARCH_TYPE_CHOICES, max_length=32, default=SearchType.ALERT)
    params = JsonField("检索条件")
    duration = models.FloatField("检索耗时", null=True)

    class Meta:
        verbose_name = "检索历史"
        verbose_name_plural = "检索历史"

    @classmethod
    @contextmanager
    def record(cls, search_type, params, enabled: bool = True):
        """
        记录执行时间的上下文管理器
        :param search_type: 检索类型
        :param params: 检索条件
        :param enabled: 是否保存历史

        使用示例
        >>> with SearchHistory.record(SearchType.ALERT, {"xx": "yy"}, enabled=True):
        >>>     a = 1  # do sth
        """
        start = time.time()
        yield
        duration = time.time() - start
        if not enabled:
            return
        history = cls.objects.create(
            search_type=search_type,
            params=params,
            duration=duration,
        )
        # 只保留最近N条历史
        ids = list(
            cls.objects.filter(create_user=history.create_user, search_type=history.search_type)
            .order_by("-create_time")
            .values_list("id", flat=True)[HISTORY_RESERVED_COUNT:]
        )
        cls.objects.filter(id__in=ids).delete()


class SearchFavorite(AbstractRecordModel):
    """
    检索收藏
    """

    name = models.CharField("收藏名称", max_length=64)

    search_type = models.CharField("检索类型", choices=SEARCH_TYPE_CHOICES, max_length=32, default=SearchType.ALERT)
    params = JsonField("检索条件")

    class Meta:
        verbose_name = "检索收藏"
        verbose_name_plural = "检索收藏"
        ordering = ("-update_time",)


class AlertExperience(AbstractRecordModel):
    """
    (已废弃) 处理经验表
    """

    bk_biz_id = models.IntegerField(verbose_name="业务ID", default=0)
    # 指标，时序类：使用表名 + 字段名，事件类：使用事件类型标识
    metric = models.CharField(max_length=128, verbose_name="指标ID", default="", blank=True)
    # 若指标不存在，则使用告警名称，两者保存其一即可
    alert_name = models.CharField(max_length=128, verbose_name="告警名称", default="", blank=True)
    description = models.TextField(verbose_name="处理建议")

    class Meta:
        unique_together = ("bk_biz_id", "metric", "alert_name")


class AlertSuggestion(AbstractRecordModel):
    """
    告警处理建议
    """

    class Type:
        METRIC = "metric"
        DIMENSION = "dimension"

    TYPE_CHOICES = (
        (Type.METRIC, _("指标")),
        (Type.DIMENSION, _("维度")),
    )

    id = models.CharField(verbose_name="ID", max_length=64, primary_key=True)
    bk_biz_id = models.IntegerField(verbose_name="业务ID", default=0, db_index=True)
    type = models.CharField(max_length=32, verbose_name="经验类型", choices=TYPE_CHOICES)

    # 指标，时序类：使用表名 + 字段名，事件类：使用事件类型标识
    metric = models.JSONField(verbose_name="指标ID", default=list)
    # 若指标不存在，则使用告警名称，两者保存其一即可
    alert_name = models.TextField(verbose_name="告警名称", default="", blank=True)
    # 过滤条件
    conditions = models.JSONField(verbose_name="匹配条件", default=list)
    description = models.TextField(verbose_name="处理建议")

    @classmethod
    def generate_id(cls, bk_biz_id, type, metric, alert_name, conditions):
        """
        生成主键ID
        """
        return count_md5(
            [
                bk_biz_id,
                type,
                metric,
                alert_name,
                conditions,
            ]
        )

    class Meta:
        verbose_name = "告警处理建议"
        verbose_name_plural = "告警处理建议"


class AlertFeedback(AbstractRecordModel):
    """
    告警反馈
    """

    alert_id = models.CharField("告警ID", max_length=64, db_index=True)
    is_anomaly = models.BooleanField("是否异常")
    description = models.TextField("反馈信息", blank=True)

    class Meta:
        verbose_name = "告警反馈"
        verbose_name_plural = "告警反馈"


class MetricRecommendationFeedback(AbstractRecordModel):
    """
    指标推荐反馈
    """

    class FeedBackChoices:
        GOOD = "good"
        BAD = "bad"

    FEEDBACK_CHOICES = ((FeedBackChoices.GOOD, _("点赞")), (FeedBackChoices.BAD, _("点踩")))

    alert_metric_id = models.CharField("告警指标ID", max_length=128)
    recommendation_metric_hash = models.CharField("推荐指标哈希", max_length=32)
    feedback = models.CharField("反馈行为", choices=FEEDBACK_CHOICES, max_length=16)
    bk_biz_id = models.IntegerField("业务ID")
    recommendation_metric = models.TextField("推荐指标文本")

    class Meta:
        verbose_name = "指标推荐反馈"
        unique_together = (("alert_metric_id", "recommendation_metric_hash", "bk_biz_id", "create_user"),)

    @classmethod
    def generate_recommendation_metric_hash(cls, recommendation_metric):
        """生成被推荐指标hash值

        :param recommendation_metric: 被推荐指标
        :return: 被推荐指标hash值
        """
        return count_md5(recommendation_metric)
