"""
Django 的 settings 文件，用于配置 Django 项目的设置。

本文件由 DjangoConfig 动态生成。
"""

from bk_monitor_base.config.django import DjangoConfig

_config = DjangoConfig()

# 将 _config 的所有大写属性导入为模块变量
for key in dir(_config):
    if key.isupper():
        globals()[key] = getattr(_config, key)

if _config.use_django_cache_redis:
    globals()["CACHES"]["default"] = globals()["CACHES"]["redis"]
