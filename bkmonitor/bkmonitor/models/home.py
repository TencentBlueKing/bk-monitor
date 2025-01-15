from django.db import models
from django.utils.translation import gettext_lazy as _lazy


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
