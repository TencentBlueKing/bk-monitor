from bk_monitor_base.infras.declaratives.registry import DefaultResourceRegistry

from .collect import CollectConfig
from .collect_set import CollectSetConfig
from .collect_task import CollectTask

DefaultResourceRegistry.register(CollectConfig)
DefaultResourceRegistry.register(CollectTask)
DefaultResourceRegistry.register(CollectSetConfig)
