# pyright: reportUnknownVariableType=false
import os
from collections.abc import Callable
from functools import partial
from typing import Any, cast

from bkstorages.backends.bkrepo import BKRepoStorage
from django.core.files.storage import FileSystemStorage, Storage

from bk_monitor_base.config import get_config
from bk_monitor_base.config.storage import StorageConfig, StorageName, StorageType
from bk_monitor_base.infras.path_formatter import PathFormatter, PathStyle

# 默认的django存储实例
_storage_instances: dict[str, Storage] = {}


def _get_storage_config(storage_name: StorageName) -> StorageConfig:
    """获取存储配置，专用配置缺失时回退到 DEFAULT。"""
    file_storages = get_config().file_storages
    storage_config = file_storages.get(storage_name)
    if storage_config is None and storage_name != StorageName.DEFAULT:
        storage_config = file_storages.get(StorageName.DEFAULT)
    if storage_config is None:
        raise KeyError(storage_name)
    return storage_config


def handle_file_source_list_to_job_file_source_list(
    storage: BKRepoStorage, file_source_list: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    # 获取文件源
    bucket = storage.client.bucket
    project = storage.client.project
    file_source_with_source_info_list: list[dict[str, Any]] = []
    for file_source in file_source_list:
        # 作业平台要求制品库分发的路径带上 project/bucket 前缀
        file_list_raw = [
            os.path.join(str(project), str(bucket), file_path) for file_path in file_source.get("file_list", [])
        ]
        # 转换为 posix 路径格式
        file_list = [PathFormatter.format_path(file_path, style=PathStyle.POSIX) for file_path in file_list_raw]

        file_source_with_source_info_list.append(
            {
                "file_list": file_list,
                "file_source_code": bucket,  # TODO: 必须保证job的文件源里标识是bucket名称,后续自动创建文件源
                "file_type": 3,  # 制品库文件
            }
        )

    return file_source_with_source_info_list


def get_storage_from_config(storage_config: StorageConfig) -> Storage:
    """将存储配置转换为存储实例

    Args:
        storage_config: 存储配置
    Returns:
        Storage: 存储实例
    Raises:
        ValueError: 如果存储配置不能为空
    """
    match storage_config.type:
        case StorageType.BKREPO:
            if storage_config.bkrepo is None:
                raise ValueError("蓝鲸仓库存储配置不能为空")
            return BKRepoStorage(
                bucket=storage_config.bkrepo.bucket,
                project_id=storage_config.bkrepo.project,
                endpoint_url=storage_config.bkrepo.url,
                username=storage_config.bkrepo.username,
                password=storage_config.bkrepo.password,
            )
        case StorageType.LOCAL:
            if storage_config.local is None:
                raise ValueError("本地存储配置不能为空")
            return FileSystemStorage(location=storage_config.local.path)


def get_storage_func(storage_name: StorageName) -> Callable[[], Storage]:
    """获取存储实例的函数(用于django的filefield中storage参数)

    Args:
        storage_name: 存储名称
    Returns:
        Callable[[], Storage]: 存储实例的函数
    """

    return partial(get_storage, storage_name)


def get_bkrepo_storage(storage_name: StorageName) -> BKRepoStorage:
    """获取蓝鲸仓库存储实例

    Args:
        storage_name: 存储名称
    Returns:
        BKRepoStorage: 蓝鲸仓库存储实例
    """
    storage_config = _get_storage_config(storage_name)
    if storage_config.type != StorageType.BKREPO:
        raise ValueError(f"存储{storage_name}不是蓝鲸仓库存储")

    storage = get_storage(storage_name)
    return cast(BKRepoStorage, storage)


def get_storage(storage_name: StorageName) -> Storage:
    """获取默认的存储django实例

    Args:
        storage_name: 存储名称
    Returns:
        Storage: 存储实例
    """
    global _storage_instances
    if storage_name in _storage_instances:
        return _storage_instances[storage_name]

    storage_config = _get_storage_config(storage_name)
    storage_instance = get_storage_from_config(storage_config)
    _storage_instances[storage_name] = storage_instance
    return storage_instance
