"""Monitor registers native SDK providers on the shared V4 callback dispatcher."""

from django.conf import settings

from bkmonitor.iam.backends.v4.callback_client import build_callback_client
from bkmonitor.iam.backends.v4.codec import MonitorV4Codec
from bkmonitor.iam.handlers.catalog import get_resource_provider
from iam_engine.v4.callback import V4ResourceApiDispatcher
from iam_engine.v4.config import resolve_effective_v4_system_id
from iam_engine.v4.resource import V4ResourceProvider


def build_resource_dispatcher():
    dispatcher = V4ResourceApiDispatcher(
        build_callback_client(settings.BK_APP_TENANT_ID), resolve_effective_v4_system_id()
    )
    codec = MonitorV4Codec()
    for resource_type in ("space", "apm_application", "grafana_dashboard", "rum_application"):
        dispatcher.register(resource_type, V4ResourceProvider(get_resource_provider(resource_type), resource_type, codec))
    return dispatcher
