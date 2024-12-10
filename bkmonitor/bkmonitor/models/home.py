from django.db import models
from django.utils.translation import ugettext_lazy as _lazy


class FunctionAccessRecord(models.Model):
    """
    功能访问记录
    """

    username = models.CharField(max_length=64, verbose_name="用户名")
    function = models.CharField(max_length=64, verbose_name="功能类型")
    function_instance = models.CharField(max_length=64, verbose_name="功能实例")
    access_time = models.DateTimeField(auto_now=True, verbose_name="访问时间")

    class Meta:
        db_table = "function_access_record"
        unique_together = ("username", "function", "function_instance")
        index_together = ("username", "function")
        verbose_name = _lazy("功能访问记录")
        verbose_name_plural = _lazy("功能访问记录")
        ordering = ["-access_time"]


class HomeAlarmGraphConfig(models.Model):
    """
    首页告警图配置
    """

    username = models.CharField(max_length=64, verbose_name="用户名", db_index=True)
    index = models.IntegerField(verbose_name="排序")
    bk_biz_id = models.IntegerField(verbose_name="业务ID")
    config = models.JSONField(verbose_name="配置", default=list)

    class Meta:
        db_table = "home_alarm_graph_config"
        verbose_name = _lazy("首页告警图配置")
        verbose_name_plural = _lazy("首页告警图配置")
