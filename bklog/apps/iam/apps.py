from django.apps import AppConfig


class IamConfig(AppConfig):
    """IAM 应用配置。启动时校验进程级鉴权模式，非法环境变量直接拒绝启动。"""

    default = True
    name = "apps.iam"
    verbose_name = "IAM"

    def ready(self):
        from apps.iam.mode import validate_configured_permission_mode

        validate_configured_permission_mode()
