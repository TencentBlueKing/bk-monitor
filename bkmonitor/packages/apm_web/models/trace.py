# -*- coding: utf-8 -*-
import datetime

from django.db import models

from bkmonitor.utils.db import JsonField
from bkmonitor.utils.model_manager import AbstractRecordModel, ModelManager
from bkmonitor.utils.user import get_global_user


class OperateRecordQuerySet(models.query.QuerySet):
    """
    更新时写入更新时间和更新者
    """

    def update(self, **kwargs):
        kwargs.update(
            {
                "update_time": datetime.datetime.now(),
                "update_user": get_global_user(),
            }
        )
        super().update(**kwargs)
        return self.first()


class TraceComparisonModelManager(ModelManager):
    def get_queryset(self):
        return OperateRecordQuerySet(self.model, using=self._db)

    def get(self, *args, **kwargs):
        if not kwargs.get("is_deleted"):
            kwargs["is_deleted"] = False
        return super().get(*args, **kwargs)

    def filter(self, *args, **kwargs):
        if not kwargs.get("is_deleted"):
            kwargs["is_deleted"] = False
        return super().filter(*args, **kwargs)

    def create(self, *args, **kwargs):
        username = get_global_user()
        kwargs.update({"create_user": username, "update_user": username})
        return super().create(*args, **kwargs)


class TraceComparison(AbstractRecordModel):
    bk_biz_id = models.IntegerField("业务id")
    app_name = models.CharField("应用名称", max_length=50)
    trace_id = models.CharField("trace ID", max_length=32)
    name = models.CharField("参照名称", max_length=16)
    spans = JsonField("span list")

    objects = TraceComparisonModelManager()


class TraceDefaultConfigTemplate(AbstractRecordModel):
    name = models.CharField("配置名称", max_length=255, unique=True)
    bk_biz_id = models.IntegerField("业务id", null=True, blank=True)
    app_name = models.CharField("应用名称", max_length=50, null=True, blank=True)
    trace_config = JsonField("trace 配置", default=dict)
    span_config = JsonField("span 配置", default=dict)


class TraceUserAppDefaultConfig(AbstractRecordModel):
    bk_biz_id = models.IntegerField("业务id")
    app_name = models.CharField("应用名称", max_length=50)
    username = models.CharField("用户名", max_length=64)
    config_template_id = models.IntegerField("配置模板ID", default=0)

    class Meta:
        unique_together = (("bk_biz_id", "app_name", "username"),)


class TraceUserAppCustomConfig(AbstractRecordModel):
    """Tracing 检索页面 trace 视角和 span 视角的自定义配置"""

    bk_biz_id = models.IntegerField("业务id")
    app_name = models.CharField("应用名称", max_length=50)
    username = models.CharField("用户名", max_length=64)
    trace_config = JsonField("trace 自定义配置", default=dict)
    span_config = JsonField("span 自定义配置", default=dict)

    class Meta:
        unique_together = (("bk_biz_id", "app_name", "username"),)
