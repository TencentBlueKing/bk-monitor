from django.conf import settings

from bk_monitor_base.infras.declaratives.controller.constants import ControllerTaskEngine


class EngineRegistry:
    _registry = {}

    @classmethod
    def register(cls, engine_type, engine_class):
        cls._registry[engine_type] = engine_class

    @classmethod
    def get_engine_class(cls, engine_type: str):
        engine_class = cls._registry.get(engine_type)
        if not engine_class:
            raise ValueError(f"Unsupported TASK_ENGINE: {engine_type}")
        return engine_class


class TaskFactory:
    def __init__(self, engine=None):
        if engine:
            self.engine = engine
        elif hasattr(settings, "TASK_ENGINE"):
            self.engine = settings.TASK_ENGINE
        else:
            self.engine = ControllerTaskEngine.CELERY

    def get_task_handler(self):
        engine_class = EngineRegistry.get_engine_class(self.engine)
        return engine_class()
