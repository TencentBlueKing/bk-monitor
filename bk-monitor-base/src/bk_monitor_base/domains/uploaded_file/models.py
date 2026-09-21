import hashlib
import os
import secrets
import time
import uuid
from typing import Any, final

from django.db import models
from typing_extensions import override

from bk_monitor_base.config.storage import StorageName
from bk_monitor_base.infras.storage import get_storage_func


def generate_upload_path(instance: "FileModel", filename: str) -> str:
    """
    生成上传文件的存储路径
    格式: storage/{usage}/{date}/{uuid}{ext}
    """
    # 获取文件扩展名
    ext = os.path.splitext(filename)[1]
    # 生成 UUID+时间戳 文件名
    new_filename = f"{uuid.uuid4().hex}_{int(time.time())}{ext}"
    # 组合路径
    return os.path.join("storage", instance.usage, new_filename)


def generate_token() -> str:
    """生成安全的随机字符串（32字节 = 64个十六进制字符）"""
    return secrets.token_hex(32)


def calculate_file_md5(file_field: Any) -> str:
    """计算文件内容的 MD5，并尽量恢复原有文件指针位置。"""
    if not file_field:
        return ""

    file_obj = file_field.file
    current_position = None
    if hasattr(file_obj, "tell"):
        try:
            current_position = file_obj.tell()
        except (OSError, ValueError):
            current_position = None

    if hasattr(file_obj, "seek"):
        try:
            file_obj.seek(0)
        except (OSError, ValueError):
            pass

    md5_hash = hashlib.md5()
    for chunk in file_obj.chunks() if hasattr(file_obj, "chunks") else iter(lambda: file_obj.read(8192), b""):
        if not chunk:
            continue
        if isinstance(chunk, str):
            chunk = chunk.encode("utf-8")
        md5_hash.update(chunk)

    if current_position is not None and hasattr(file_obj, "seek"):
        try:
            file_obj.seek(current_position)
        except (OSError, ValueError):
            pass

    return md5_hash.hexdigest()


@final
class FileModel(models.Model):
    """
    用户上传文件模型
    """

    bk_tenant_id = models.CharField(verbose_name="租户ID", max_length=64)

    # 实际存储的文件
    file = models.FileField(
        verbose_name="文件内容",
        upload_to=generate_upload_path,
        storage=get_storage_func(StorageName.DEFAULT),
    )
    token = models.CharField(verbose_name="文件token", max_length=128, default=generate_token)
    # 原始文件名
    original_filename = models.CharField(verbose_name="原始文件名", max_length=255)
    # 用途/分类 (例如: logo, document, avatar)
    usage = models.CharField(verbose_name="用途", max_length=64, db_index=True)
    md5 = models.CharField(verbose_name="文件MD5", max_length=32, blank=True, default="")
    description = models.TextField(verbose_name="文件描述", blank=True, default="")
    # 创建信息
    created_by = models.CharField(verbose_name="创建用户", max_length=255)
    created_at = models.DateTimeField(verbose_name="创建时间", auto_now_add=True)

    @final
    class Meta:
        db_table = "uploaded_file"
        verbose_name = "用户上传文件"
        verbose_name_plural = "用户上传文件"
        ordering = ["-created_at"]

    @override
    def __str__(self) -> str:
        return f"{self.original_filename} ({self.usage})"

    @override
    def save(self, *args: Any, **kwargs: Any) -> None:
        # 如果是首次保存且没有 original_filename，尝试从 file 获取
        if not self.pk and not self.original_filename and self.file and getattr(self.file, "name", None):
            self.original_filename = self.file.name

        # 确保 original_filename 不为空
        if not self.original_filename:
            raise ValueError("original_filename cannot be empty or None")

        if self.file:
            self.md5 = calculate_file_md5(self.file)

        super().save(*args, **kwargs)
