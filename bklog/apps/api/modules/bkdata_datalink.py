"""Read-only BKBase V4 data-link control-plane APIs."""

from django.conf import settings

from apps.api.base import DataAPI
from apps.api.modules.utils import add_esb_info_before_request_for_bkdata_user


class _BkDataDataLinkApi:
    def __init__(self):
        root = f"{settings.PAAS_API_HOST}/api/bk-base/{settings.ENVIRONMENT}/v4/"
        resource_path = (
            "tenants/{tenant}/namespaces/{namespace}/{kind}/{name}/"
            if settings.ENABLE_MULTI_TENANT_MODE
            else "namespaces/{namespace}/{kind}/{name}/"
        )
        self.metadata = DataAPI(
            method="GET",
            url=root + "meta/datalink/metadata/",
            module="BKBase V4",
            description="Read data-link metadata",
            before_request=add_esb_info_before_request_for_bkdata_user,
        )
        self.resource = DataAPI(
            method="GET",
            url=root + resource_path,
            module="BKBase V4",
            description="Read a data-link resource",
            before_request=add_esb_info_before_request_for_bkdata_user,
            url_keys=["tenant", "namespace", "kind", "name"]
            if settings.ENABLE_MULTI_TENANT_MODE
            else ["namespace", "kind", "name"],
        )


BkDataDataLinkApi = _BkDataDataLinkApi()
