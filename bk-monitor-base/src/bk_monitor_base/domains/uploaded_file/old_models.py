import hashlib
import json
import logging
import os
import subprocess
from typing import Any, final

from django.core.files.base import ContentFile
from django.db import models
from django.db.models import Max
from typing_extensions import override

from bk_monitor_base.config.storage import StorageName
from bk_monitor_base.infras.constant import OLD_MONITOR_SAAS_DB_NAME
from bk_monitor_base.infras.db_models.manger import OldModelManager
from bk_monitor_base.infras.storage import get_storage_func

logger = logging.getLogger(__name__)
MIGRATION_DESCRIPTION_PREFIX = "migrate_from_uploaded_file_info"


def generate_upload_path(instance: "UploadedFileInfo", filename: str) -> str:  # pyright: ignore[reportUnusedParameter]
    return os.path.join(instance.relative_path, instance.actual_filename)


@final
class UploadedFileInfo(models.Model):
    """上传文件信息"""

    original_filename = models.CharField("原始文件名", max_length=255)
    actual_filename = models.CharField("文件名", max_length=255)
    relative_path = models.TextField("文件相对路径")
    file_data = models.FileField(
        "文件内容", upload_to=generate_upload_path, storage=get_storage_func(StorageName.BKMONITOR)
    )
    file_md5 = models.CharField("文件内容MD5", max_length=50)
    is_dir = models.BooleanField("是否为目录", default=False)

    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    create_user = models.CharField("创建人", max_length=32, blank=True, default="")
    update_time = models.DateTimeField("修改时间", auto_now=True)
    update_user = models.CharField("修改人", max_length=32, blank=True, default="")
    is_deleted = models.BooleanField("是否删除", default=False)

    objects = OldModelManager(default_db_name=OLD_MONITOR_SAAS_DB_NAME)

    @final
    class Meta:
        db_table = "monitor_web_uploadedfileinfo"
        managed = False

    def generate_file_md5(self):
        if self.file_data:
            return hashlib.md5(self.file_data.file.read()).hexdigest()

    @property
    def file_type(self):
        file_command = ["file", "-b", self.file_data.path]
        try:
            stdout, _ = subprocess.Popen(file_command, stdout=subprocess.PIPE).communicate()
        except Exception as e:
            logger.exception(f"不存在的文件，获取文件类型失败：{e}")
            return ""
        return stdout

    @override
    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.file_md5:
            self.file_md5 = self.generate_file_md5()

        return super().save(*args, **kwargs)


def migrate_uploaded_file_info_to_new_model(
    bk_tenant_id: str, usage: str, file_ids: list[int] | None = None
) -> dict[int, str]:
    """
    将旧模型数据迁移到新模型

    Args:
        bk_tenant_id: 租户ID
        usage: 文件用途
        file_ids: 旧文件ID列表

    Returns:
        旧文件ID到新文件token的映射字典
    """
    from .models import FileModel

    file_id_to_token_map: dict[int, str] = {}
    old_files = UploadedFileInfo.objects.filter(id__in=file_ids) if file_ids else UploadedFileInfo.objects.all()
    set_new_model_pk_start_cursor(old_files)

    for old_file in old_files:
        description = f"{MIGRATION_DESCRIPTION_PREFIX}: {old_file.pk}"

        existing_file = FileModel.objects.filter(pk=old_file.pk).first()
        if existing_file:
            if existing_file.description != description:
                raise ValueError(f"新模型主键 {old_file.pk} 已被非迁移文件占用，无法保持旧新ID对应关系")
            file_id_to_token_map[old_file.pk] = existing_file.token
            continue

        new_file = FileModel(
            pk=old_file.pk,
            original_filename=old_file.original_filename,
            usage=usage,
            created_by=old_file.create_user or "system",
            bk_tenant_id=bk_tenant_id,
            description=description,
        )
        new_file.file.save(old_file.actual_filename, old_file.file_data.file, save=False)
        new_file.save(force_insert=True)
        file_id_to_token_map[old_file.pk] = new_file.token

    return file_id_to_token_map


def set_new_model_pk_start_cursor(old_files: models.QuerySet[UploadedFileInfo] | Any) -> None:
    """确保新模型后续自动分配的主键落在高位区间。"""
    from .models import FileModel

    old_max_pk = old_files.aggregate(max_pk=Max("pk"))["max_pk"] or 0
    target_pk_start = max(10000, old_max_pk * 2)
    current_max_pk = FileModel.objects.aggregate(max_pk=Max("pk"))["max_pk"] or 0
    placeholder_pk = target_pk_start - 1
    if current_max_pk >= placeholder_pk:
        return

    placeholder = FileModel(
        pk=placeholder_pk,
        bk_tenant_id="system",
        usage="migration_placeholder",
        original_filename="migration_placeholder",
        created_by="system",
        description="migration_placeholder",
    )
    placeholder.file.save("migration_placeholder.txt", ContentFile(b""), save=False)
    placeholder.save(force_insert=True)
    placeholder.delete()


def export_uploaded_file_info(file_ids: list[int] | None = None) -> str:
    """导出上传文件信息"""
    files = UploadedFileInfo.objects.filter(id__in=file_ids).values(
        "id", "original_filename", "actual_filename", "relative_path", "file_data", "file_md5", "is_dir"
    )
    return json.dumps(list(files))


def import_uploaded_file_info(data: str) -> bool:
    """导入上传文件信息"""

    files = json.loads(data)
    for file in files:
        UploadedFileInfo.objects.create(**file)
    return True
