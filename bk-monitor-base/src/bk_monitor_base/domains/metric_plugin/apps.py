# pyright: reportUnknownMemberType=false
# pyright: reportUnusedImport=false

from typing import final

from django.apps import AppConfig
from typing_extensions import override

from bk_monitor_base.infras.declaratives.controller.constants import ControllerTaskEngine


@final
class MetricPluginConfig(AppConfig):
    name = "bk_monitor_base.domains.metric_plugin"
    verbose_name = "指标插件"
    default_auto_field = "django.db.models.BigAutoField"

    @override
    def ready(self) -> None:
        """注册异步任务处理引擎"""
        # must be imported to register task handlers
        from bk_monitor_base.domains.metric_plugin.installer.task import DeployAsyncHandler  # noqa: F401
        from bk_monitor_base.domains.metric_plugin.manager.job.task import JobDebugAsyncHandler  # noqa: F401

        # register task engine
        from bk_monitor_base.infras.declaratives.controller.task_manager.tasks.async_task_define import CeleryEngine
        from bk_monitor_base.infras.declaratives.controller.task_manager.tasks.task_factory import EngineRegistry

        EngineRegistry.register(ControllerTaskEngine.CELERY, CeleryEngine)
