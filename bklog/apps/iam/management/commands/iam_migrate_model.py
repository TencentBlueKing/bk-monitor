from apps.iam.model_sync import get_model_sync_service
from iam_engine.model.django import ModelSyncCommand


class Command(ModelSyncCommand):
    get_service = staticmethod(get_model_sync_service)
