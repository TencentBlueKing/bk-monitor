"""Monitor SaaS credential injection for the shared V4 callback mechanism."""

from config.tools.iam_credentials import get_saas_setting

from bkmonitor.iam.mode import get_mode_provider
from iam_engine.v4.callback import V4CallbackIAM
from iam_engine.v4.config import V4Options


def build_callback_client(bk_tenant_id):
    def load_options(tenant):
        return V4Options.from_settings(
            bk_tenant_id=tenant,
            for_resource_callback=True,
            global_credentials=(get_saas_setting("SAAS_APP_CODE"), get_saas_setting("SAAS_SECRET_KEY")),
        )

    return V4CallbackIAM(
        options_loader=load_options,
        mode_loader=lambda: get_mode_provider().get_mode(),
        bk_tenant_id=bk_tenant_id,
    )
