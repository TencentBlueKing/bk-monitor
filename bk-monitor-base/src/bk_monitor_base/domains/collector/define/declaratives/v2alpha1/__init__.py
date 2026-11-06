from bk_monitor_base.infras.declaratives.registry import DefaultResourceRegistry

from .collect import CollectConfig
from .collect_set import CollectSetConfig

DefaultResourceRegistry.register(CollectConfig)
DefaultResourceRegistry.register(CollectSetConfig)
