from typing import final

from django.apps import AppConfig


@final
class UploadedFileConfig(AppConfig):
    name = "bk_monitor_base.domains.uploaded_file"
    verbose_name = "已上传文件"
    default_auto_field = "django.db.models.BigAutoField"
