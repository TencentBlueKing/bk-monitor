# -*- coding: utf-8 -*-

from django.db import models
from django.utils.translation import gettext_lazy as _


class SearchModuleUserConfig(models.Model):
    """用户配置"""

    username = models.CharField(_("用户名"), max_length=255)
    config = models.JSONField(_("配置"), null=True, blank=True)
