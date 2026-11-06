"""BKLog registers native SDK providers on the shared V4 callback dispatcher."""

from django.conf import settings

from apps.iam.backends.v4.callback_client import build_callback_client
from apps.iam.backends.v4.codec import BklogNameCodec
from apps.iam.views.resources import (
    CollectionResourceProvider,
    EsSourceResourceProvider,
    IndicesResourceProvider,
    SpaceResourceProvider,
)
from iam_engine.v4.callback import V4ResourceApiDispatcher
from iam_engine.v4.config import resolve_effective_v4_system_id
from iam_engine.v4.resource import V4ResourceProvider


def build_resource_dispatcher():
    dispatcher = V4ResourceApiDispatcher(
        build_callback_client(settings.BK_APP_TENANT_ID), resolve_effective_v4_system_id()
    )
    codec = BklogNameCodec()
    for resource_type, provider in (
        ("space", SpaceResourceProvider()),
        ("collection", CollectionResourceProvider()),
        ("es_source", EsSourceResourceProvider()),
        ("indices", IndicesResourceProvider()),
    ):
        dispatcher.register(resource_type, V4ResourceProvider(provider, resource_type, codec))
    return dispatcher
