"""测试 uploaded_file.old_models 模块。"""

import importlib
import sys
from types import SimpleNamespace

import pytest
from django.core.files.base import ContentFile
from pytest_mock import MockerFixture

from bk_monitor_base.domains.uploaded_file.models import FileModel
from bk_monitor_base.infras.storage import get_storage_func
from bk_monitor_base.config.storage import StorageName


def _create_fake_old_files(*old_files: object, max_pk: int):
    """构造带 aggregate 能力的旧模型查询结果。"""

    class FakeOldFiles(list):
        def aggregate(self, **kwargs):
            return {"max_pk": max_pk}

    return FakeOldFiles(old_files)


def _load_old_models_module(mocker: MockerFixture):
    """在替换旧存储配置后延迟导入 old_models 模块。"""
    module_name = "bk_monitor_base.domains.uploaded_file.old_models"
    if module_name in sys.modules:
        return sys.modules[module_name]

    default_storage_func = get_storage_func(StorageName.DEFAULT)
    mocker.patch(
        "bk_monitor_base.infras.storage.get_storage_func",
        side_effect=lambda storage_name: default_storage_func,
    )

    return importlib.import_module(module_name)


@pytest.mark.django_db(databases=["default"])
class TestSetNewModelPkStartCursor:
    """测试新模型主键起始游标设置逻辑。"""

    def test_set_new_model_pk_start_cursor_uses_double_old_max(self, mocker: MockerFixture):
        """当旧表最大主键较大时，应将新表自动主键抬到其两倍。"""
        old_models_module = _load_old_models_module(mocker)
        old_files = _create_fake_old_files(max_pk=6000)

        old_models_module.set_new_model_pk_start_cursor(old_files)

        file_model = FileModel(
            bk_tenant_id="test_tenant",
            usage="logo",
            original_filename="new.txt",
            created_by="tester",
        )
        file_model.file.save("new.txt", ContentFile(b"new file"), save=False)
        file_model.save()

        assert file_model.pk == 12000


@pytest.mark.django_db(databases=["default"])
class TestMigrateUploadedFileInfoToNewModel:
    """测试旧上传文件模型迁移到新模型。"""

    def test_migrate_uploaded_file_info_to_new_model_is_idempotent(self, mocker: MockerFixture):
        """重复迁移相同旧文件时，应复用同一条新记录且保持主键一致。"""
        old_models_module = _load_old_models_module(mocker)
        old_file = SimpleNamespace(
            pk=123,
            original_filename="legacy.txt",
            actual_filename="legacy.txt",
            create_user="legacy_user",
            file_data=SimpleNamespace(file=ContentFile(b"legacy content")),
        )
        old_files = _create_fake_old_files(old_file, max_pk=6000)

        mocker.patch(
            "bk_monitor_base.domains.uploaded_file.old_models.UploadedFileInfo.objects.all",
            return_value=old_files,
        )

        first_result = old_models_module.migrate_uploaded_file_info_to_new_model(
            bk_tenant_id="test_tenant",
            usage="metric_plugin",
        )
        second_result = old_models_module.migrate_uploaded_file_info_to_new_model(
            bk_tenant_id="test_tenant",
            usage="metric_plugin",
        )

        file_model = FileModel.objects.get(pk=123)
        assert first_result == second_result
        assert first_result[123] == file_model.token
        assert file_model.created_by == "legacy_user"
        assert file_model.description == "migrate_from_uploaded_file_info: 123"
        assert FileModel.objects.filter(pk=123).count() == 1
