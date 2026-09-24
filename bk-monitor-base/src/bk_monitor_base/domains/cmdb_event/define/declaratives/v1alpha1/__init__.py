from bk_monitor_base.infras.declaratives.registry import DefaultResourceRegistry

from .cmdb_event import CMDBEvent

DefaultResourceRegistry.register(CMDBEvent)
