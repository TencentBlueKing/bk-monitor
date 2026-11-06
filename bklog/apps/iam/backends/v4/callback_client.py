"""BKLog credential and configuration-store injection for the shared callback."""

from apps.iam.mode import get_mode_provider
from iam_engine.v4.callback import V4CallbackIAM
from iam_engine.v4.config import V4Options


def build_callback_client(bk_tenant_id):
    return V4CallbackIAM(
        options_loader=lambda tenant: V4Options.from_settings(bk_tenant_id=tenant, for_resource_callback=True),
        mode_loader=lambda: get_mode_provider().get_mode(),
        bk_tenant_id=bk_tenant_id,
    )
