"""
ORM 配置
"""

from collections.abc import Mapping, MutableMapping
from enum import Enum
from typing import Any, ClassVar, cast

from pydantic import ConfigDict, Field
from pydantic_settings import SettingsConfigDict

from .base import BaseConfigModel, BaseConfigSettings

_INSTALLED_APPS: list[str] = [
    "modeltranslation",
    "bk_monitor_base.domains.uploaded_file",
    "bk_monitor_base.domains.space",
    "bk_monitor_base.domains.metric_plugin",
    "bk_monitor_base.domains.strategy",
    "bk_monitor_base.domains.object_model",
    "bk_monitor_base.domains.uptime_check",
    "bk_monitor_base.domains.dynamic_group",
    "bk_monitor_base.metadata",
]


class DatabaseEngine(str, Enum):
    """
    数据库引擎枚举
    """

    sqlite = "django.db.backends.sqlite3"
    mysql = "django.db.backends.mysql"
    postgresql = "django.db.backends.postgresql"


class Database(BaseConfigModel):
    """
    数据库配置
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(populate_by_name=True, extra="ignore")

    engine: str = Field(default=DatabaseEngine.mysql.value, alias="ENGINE", description="数据库引擎")
    name: str = Field(default="bk-monitor-base", alias="NAME", description="数据库名称")
    user: str = Field(default="root", alias="USER", description="数据库用户名")
    password: str = Field(default="", alias="PASSWORD", description="数据库密码")
    host: str = Field(default="127.0.0.1", alias="HOST", description="数据库主机")
    port: str = Field(default="3306", alias="PORT", description="数据库端口")
    options: dict[str, Any] = Field(default_factory=dict, alias="OPTIONS", description="数据库配置项")
    timezone: str | None = Field(default=None, alias="TIME_ZONE", description="数据库时区")
    test: dict[str, Any] = Field(default_factory=dict, alias="TEST", description="测试配置")


class CacheEngine(str, Enum):
    """
    缓存引擎枚举
    """

    db = "django.core.cache.backends.db.DatabaseCache"
    dumpy = "django.core.cache.backends.dummy.DummyCache"
    locmem = "django.core.cache.backends.locmem.LocMemCache"
    redis = "django.core.cache.backends.redis.RedisCache"
    django_redis = "django_redis.cache.RedisCache"


class Caches(BaseConfigSettings):
    """
    缓存配置
    """

    backend: str = Field(default=CacheEngine.locmem.value, alias="BACKEND", description="缓存引擎")
    location: str = Field(default="", alias="LOCATION", description="缓存LOCATION")
    options: dict[str, Any] = Field(default_factory=dict, alias="OPTIONS", description="缓存配置项")


class DjangoConfig(BaseConfigSettings):
    """
    Django 配置
    """

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(populate_by_name=True, extra="ignore")

    use_tz: bool = Field(default=True, alias="USE_TZ", description="是否使用时区")
    time_zone: str = Field(default="Asia/Shanghai", alias="TIME_ZONE", description="数据库时区")
    media_root: str = Field(default="media", alias="MEDIA_ROOT", description="媒体文件根目录")
    databases: dict[str, Database] = Field(default_factory=lambda: {"default": Database()}, alias="DATABASES")
    installed_apps: list[str] = Field(default_factory=lambda: _INSTALLED_APPS, alias="INSTALLED_APPS")
    default_auto_field: str = Field(default="django.db.models.BigAutoField", alias="DEFAULT_AUTO_FIELD")
    languages: list[tuple[str, str]] = Field(default=[("en", "English"), ("zh-hans", "简体中文")], alias="LANGUAGES")
    language_code: str = Field(default="zh-hans", alias="LANGUAGE_CODE")
    use_django_cache_redis: bool = Field(
        default=False, alias="USE_DJANGO_CACHE_REDIS", description="是否使用Django Redis缓存"
    )
    caches: dict[str, Caches] = Field(default_factory=lambda: {"default": Caches()}, alias="CACHES")
    migration_modules: dict[str, str | None] = Field(default_factory=dict, alias="MIGRATION_MODULES")


def merge_django_settings(
    target_settings: MutableMapping[str, Any], base_settings: Mapping[str, Any] | None = None
) -> None:
    """将 bk-monitor-base 的 Django 配置融合到主项目 settings 中（主项目优先）。

    仅处理以下配置项：
    - `INSTALLED_APPS`: 主项目在前，去重追加底座配置。
    - `DATABASES`: 按数据库别名合并，主项目同名 key 不覆盖。
    - `DATABASE_ROUTERS`: 主项目在前，去重追加底座配置。

    说明：
    - 其他 Django 配置项不做融合，避免底座配置“意外接管”主项目行为。
    - 该函数适合在主项目 `settings.py` 里，在加载完环境/角色/本地配置后执行：
      `merge_django_settings(globals())`。

    Args:
        target_settings: 主项目 settings 字典（通常传 `globals()` 或 `locals()`）。
            - 该参数会被**原地修改**（in-place），以便 Django 后续导入到的是融合后的配置。
            - 期望包含（可选）`INSTALLED_APPS`/`DATABASES`/`STORAGES` 等键。
        base_settings: 底座 settings 字典（可选）。
            - 当不传时，将从 `bk_monitor_base.config.get_config().django` 读取底座配置并
              `model_dump(by_alias=True)` 得到一个形如 Django settings 的字典。
            - 期望键名为 Django settings 的大写形式（例如 `INSTALLED_APPS`）。

    Examples:
        在主项目 settings 文件末尾调用（推荐：角色/环境/local_settings 加载后）：:

            from bk_monitor_base.config.django import merge_django_settings
            merge_django_settings(globals())
    """

    if base_settings is None:
        # 延迟导入避免循环依赖（bk_monitor_base.config.all -> DjangoConfig）
        from bk_monitor_base.config import get_config

        base_settings = get_config().django.model_dump(by_alias=True)

    _merge_installed_apps(target_settings, base_settings.get("INSTALLED_APPS"))
    _merge_mapping_by_key(target_settings, "DATABASES", base_settings.get("DATABASES"))
    _merge_mapping_by_key(target_settings, "MIGRATION_MODULES", base_settings.get("MIGRATION_MODULES"))


def _merge_installed_apps(target_settings: MutableMapping[str, Any], base_value: Any) -> None:
    """融合 INSTALLED_APPS（主项目优先，去重追加底座）。

    Args:
        target_settings: 主项目 settings 字典（原地修改 `INSTALLED_APPS`）。
        base_value: 底座侧 `INSTALLED_APPS`，允许为 `list[str] | tuple[str, ...]`，
            非序列类型将被忽略。
    """

    if not base_value:
        return

    if not isinstance(base_value, list | tuple):
        return

    base_apps: list[str] = []
    for item in cast(list[Any] | tuple[Any, ...], base_value):
        if isinstance(item, str):
            base_apps.append(item)
    if not base_apps:  # pragma: no cover - 防御性分支
        return

    main_value = target_settings.get("INSTALLED_APPS")
    if isinstance(main_value, list | tuple):
        main_apps: list[str] = []
        for item in cast(list[Any] | tuple[Any, ...], main_value):
            if isinstance(item, str):
                main_apps.append(item)
    else:
        main_apps = []

    seen = set(main_apps)
    merged: list[str] = list(main_apps)
    for app in base_apps:
        if app not in seen:
            merged.append(app)
            seen.add(app)

    # 尽量保持主项目原有类型（tuple/list）
    if isinstance(main_value, tuple):
        target_settings["INSTALLED_APPS"] = tuple(merged)
    else:
        target_settings["INSTALLED_APPS"] = merged


def _merge_mapping_by_key(target_settings: MutableMapping[str, Any], key: str, base_value: Any) -> None:
    """按一级 key 融合 dict 配置（主项目优先，仅补齐缺失项）。

    用于处理 `DATABASES` / `STORAGES` 等“一级 key 为别名”的 Django 配置。

    Args:
        target_settings: 主项目 settings 字典（原地修改 `key` 对应的映射）。
        key: Django settings 键名，例如 `DATABASES` / `STORAGES`。
        base_value: 底座侧配置映射。仅当其为 `Mapping` 时才会参与融合；
            且仅补齐主项目缺失的一级 key（主项目同名 key 不覆盖）。
    """

    if not base_value or not isinstance(base_value, Mapping):
        return

    base_map: dict[str, Any] = {}
    typed_base_value = cast(Mapping[Any, Any], base_value)
    for base_key, base_item in typed_base_value.items():
        if isinstance(base_key, str):
            base_map[base_key] = base_item
    if not base_map:
        return

    main_value = target_settings.get(key)
    if main_value is None:
        # 主项目未配置，直接补齐
        target_settings[key] = dict(base_map)
        return

    if isinstance(main_value, dict):
        main_map: MutableMapping[str, Any] = cast(dict[str, Any], main_value)
    elif isinstance(main_value, MutableMapping):
        # 兜底：主项目可能使用了自定义 mapping 类型
        main_map = cast(MutableMapping[str, Any], main_value)
    else:
        # 主项目存在但不是 dict，保持主项目为准
        return

    for sub_key, sub_value in base_map.items():
        main_map.setdefault(sub_key, sub_value)
