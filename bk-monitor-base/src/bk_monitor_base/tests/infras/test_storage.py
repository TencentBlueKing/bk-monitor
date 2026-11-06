from unittest.mock import Mock, patch

import pytest
from bkstorages.backends.bkrepo import BKRepoStorage
from django.core.files.storage import FileSystemStorage

from bk_monitor_base.config import Config
from bk_monitor_base.config.storage import (
    BkRepoStorageConfig,
    LocalStorageConfig,
    StorageConfig,
    StorageName,
    StorageType,
)
from bk_monitor_base.infras import storage as storage_module


@pytest.fixture(autouse=True)
def clear_storage_cache():
    storage_module._storage_instances.clear()
    yield
    storage_module._storage_instances.clear()


def _build_config(file_storages):
    config = Config()
    config.file_storages = file_storages
    return config


def test_get_storage_falls_back_to_default_local():
    config = _build_config(
        {
            StorageName.DEFAULT: StorageConfig(
                type=StorageType.LOCAL,
                local=LocalStorageConfig(path="media"),
            )
        }
    )

    with patch("bk_monitor_base.infras.storage.get_config", return_value=config):
        storage = storage_module.get_storage(StorageName.JOB)

    assert isinstance(storage, FileSystemStorage)


def test_get_storage_falls_back_to_default_bkrepo():
    config = _build_config(
        {
            StorageName.DEFAULT: StorageConfig(
                type=StorageType.BKREPO,
                bkrepo=BkRepoStorageConfig(
                    bucket="default-bucket",
                    project="default-project",
                    url="http://bkrepo.example.com",
                    username="admin",
                    password="secret",
                ),
            )
        }
    )

    mock_storage = Mock(spec=BKRepoStorage)
    with (
        patch("bk_monitor_base.infras.storage.get_config", return_value=config),
        patch(
            "bk_monitor_base.infras.storage.get_storage_from_config", return_value=mock_storage
        ) as get_storage_from_config,
    ):
        storage = storage_module.get_storage(StorageName.BKMONITOR)

    assert storage is mock_storage
    get_storage_from_config.assert_called_once_with(config.file_storages[StorageName.DEFAULT])


def test_get_bkrepo_storage_falls_back_to_default_bkrepo():
    config = _build_config(
        {
            StorageName.DEFAULT: StorageConfig(
                type=StorageType.BKREPO,
                bkrepo=BkRepoStorageConfig(
                    bucket="default-bucket",
                    project="default-project",
                    url="http://bkrepo.example.com",
                    username="admin",
                    password="secret",
                ),
            )
        }
    )

    mock_storage = Mock(spec=BKRepoStorage)
    with (
        patch("bk_monitor_base.infras.storage.get_config", return_value=config),
        patch("bk_monitor_base.infras.storage.get_storage", return_value=mock_storage) as get_storage,
    ):
        storage = storage_module.get_bkrepo_storage(StorageName.JOB)

    assert storage is mock_storage
    get_storage.assert_called_once_with(StorageName.JOB)


def test_get_bkrepo_storage_raises_value_error_when_default_is_local():
    config = _build_config(
        {
            StorageName.DEFAULT: StorageConfig(
                type=StorageType.LOCAL,
                local=LocalStorageConfig(path="media"),
            )
        }
    )

    with patch("bk_monitor_base.infras.storage.get_config", return_value=config):
        with pytest.raises(ValueError, match="不是蓝鲸仓库存储"):
            storage_module.get_bkrepo_storage(StorageName.BKMONITOR)


def test_get_storage_prefers_specific_storage_over_default():
    config = _build_config(
        {
            StorageName.DEFAULT: StorageConfig(
                type=StorageType.LOCAL,
                local=LocalStorageConfig(path="media"),
            ),
            StorageName.JOB: StorageConfig(
                type=StorageType.BKREPO,
                bkrepo=BkRepoStorageConfig(
                    bucket="job-bucket",
                    project="job-project",
                    url="http://bkrepo.example.com",
                    username="admin",
                    password="secret",
                ),
            ),
        }
    )

    mock_storage = Mock(spec=BKRepoStorage)
    with (
        patch("bk_monitor_base.infras.storage.get_config", return_value=config),
        patch(
            "bk_monitor_base.infras.storage.get_storage_from_config", return_value=mock_storage
        ) as get_storage_from_config,
    ):
        storage = storage_module.get_storage(StorageName.JOB)

    assert storage is mock_storage
    get_storage_from_config.assert_called_once_with(config.file_storages[StorageName.JOB])


def test_handle_file_source_list_to_job_file_source_list_reads_bucket_from_client():
    storage = Mock(spec=BKRepoStorage)
    storage.project_id = "env-project"
    storage.bucket = "env-bucket"
    storage.client = Mock(project="job-project", bucket="job-bucket")

    file_source_list = [{"file_list": ["plugins/test.tgz"]}]

    result = storage_module.handle_file_source_list_to_job_file_source_list(storage, file_source_list)

    assert result == [
        {
            "file_list": ["job-project/job-bucket/plugins/test.tgz"],
            "file_source_code": "job-bucket",
            "file_type": 3,
        }
    ]
