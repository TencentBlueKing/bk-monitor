from bk_monitor_base.infras.declaratives.logger import logger

from .constants import ModelFieldDefinition
from .es_resource import CMDBEventDocument, CommonDocument, DocumentController, GeneralDocument, ResourceEventDocument
from .event import EventModel
from .resource import ResourceManager, ResourceModel, ResourceModelController


def init_es_resource_index(sender, *args, **kwargs):
    print("es resource index init start ...")
    for obj in [ResourceEventDocument, CMDBEventDocument, GeneralDocument]:
        try:
            obj.setup()
        except Exception as e:
            logger.info(f"{obj} index init failed, error: {e}")
    print("es resource index init end ...")


__all__ = [
    "ResourceModel",
    "ResourceModelController",
    "ResourceManager",
    "EventModel",
    "ModelFieldDefinition",
    "DocumentController",
    "CommonDocument",
    "ResourceEventDocument",
    "CMDBEventDocument",
    "GeneralDocument",
    "init_es_resource_index",
]
