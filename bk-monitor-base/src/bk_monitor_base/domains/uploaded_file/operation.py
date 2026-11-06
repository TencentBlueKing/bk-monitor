from datetime import datetime
from typing import ClassVar

from django.core.files.base import ContentFile, File
from pydantic import BaseModel, ConfigDict, Field

from bk_monitor_base.domains.uploaded_file.models import FileModel
from bk_monitor_base.infras.types import FILE_OR_CONTENT_TYPE


class FileInfo(BaseModel):
    """文件信息模型

    包含文件的元数据和文件对象本身。
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(arbitrary_types_allowed=True)

    id: int = Field(title="文件ID")
    file: File = Field(title="文件对象")
    filename: str = Field(title="文件名")
    usage: str = Field(title="用途")
    token: str = Field(title="文件token")
    md5: str = Field(title="文件MD5")
    description: str = Field(title="文件描述")
    created_by: str = Field(title="创建人")
    created_at: datetime = Field(title="创建时间")


def get_file(bk_tenant_id: str, file_token: str) -> FileInfo:
    """获取文件

    Args:
        bk_tenant_id: 租户ID
        file_token: 文件token
    Returns:
        FileInfo: 文件信息对象，包含文件对象和元数据
    """
    file_model = FileModel.objects.get(bk_tenant_id=bk_tenant_id, token=file_token)
    return FileInfo(
        id=file_model.pk,
        file=file_model.file.file,
        filename=file_model.original_filename,
        usage=file_model.usage,
        token=file_model.token,
        md5=file_model.md5,
        description=file_model.description,
        created_by=file_model.created_by,
        created_at=file_model.created_at,
    )


def save_file(
    bk_tenant_id: str,
    usage: str,
    created_by: str,
    file_or_content: FILE_OR_CONTENT_TYPE,
    filename: str | None = None,
    description: str = "",
) -> FileInfo:
    """保存文件

    Args:
        bk_tenant_id: 租户ID
        usage: 用途
        created_by: 创建人
        file_or_content: 文件对象或内容
        filename: 文件名 (必需，如果文件对象没有name属性)
    Returns:
        FileInfo: 已保存文件的信息
    Raises:
        ValueError: 如果filename为空且文件对象没有name属性
    """
    if isinstance(file_or_content, str | bytes):
        content = file_or_content if isinstance(file_or_content, bytes) else file_or_content.encode("utf-8")
        file_object = ContentFile(content)
    else:
        if filename is None and getattr(file_or_content, "name", None):
            filename = str(file_or_content.name)

        if isinstance(file_or_content, File):
            file_object = file_or_content
        else:
            file_object = File(file_or_content)

    if not filename:
        raise ValueError("Filename must be provided when saving raw content or when file object has no name.")

    file_model = FileModel(
        bk_tenant_id=bk_tenant_id,
        usage=usage,
        original_filename=filename,
        created_by=created_by,
        description=description,
    )
    file_model.file.save(filename, file_object)
    file_model.save()
    return FileInfo(
        id=file_model.pk,
        file=file_model.file.file,
        filename=file_model.original_filename,
        usage=file_model.usage,
        token=file_model.token,
        md5=file_model.md5,
        description=file_model.description,
        created_by=file_model.created_by,
        created_at=file_model.created_at,
    )
