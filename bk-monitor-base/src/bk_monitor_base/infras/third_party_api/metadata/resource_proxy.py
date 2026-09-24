"""
在开启 enable_base_compatible_switch 时，metadata.resources 接管 metadata API。
"""

from typing import Any

from .api import (  # noqa
    CreateDataSourceParams,
    CreateTimeSeriesGroupParams,
    GetDataSourceResult,
    ModifyDataSourceParams,
    ModifyTimeSeriesGroupParams,
)

_metadata_api_cache: dict[str, Any] = {}


def __getattr__(name: str) -> Any:
    """
    模块级 __getattr__ 实现延迟导入，避免循环引用。
    这种方式可以避免在模块加载时就导入 MetadataAPI，只在真正访问属性时才导入。
    """

    # 先检查缓存
    if name in _metadata_api_cache:
        return _metadata_api_cache[name]

    # 延迟导入 MetadataAPI，避免循环引用
    from bk_monitor_base.metadata.resources.resources import MetadataAPI

    if hasattr(MetadataAPI, name) and not name.startswith("_"):
        resource = getattr(MetadataAPI, name)
        _metadata_api_cache[name] = resource
        return resource

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
