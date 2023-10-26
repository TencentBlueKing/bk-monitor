# -*- coding: utf-8 -*-

from django.db import models


class IPChooserConfig(models.Model):
    """用户配置"""

    username = models.CharField("用户名", max_length=255)
    config = models.JSONField("配置", null=True, blank=True)
