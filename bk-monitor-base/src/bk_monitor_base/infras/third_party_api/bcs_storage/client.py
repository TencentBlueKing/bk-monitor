import logging
from abc import ABC
from typing import Any, ClassVar

import requests
from typing_extensions import override

from bk_monitor_base.config import Config, get_config
from bk_monitor_base.infras.third_party_api.api_client import BkApiClient, UserParams

logger = logging.getLogger(__name__)

config = get_config()


class BCSStorageClient(BkApiClient, ABC):
    abstract_class: ClassVar[bool] = True

    module_name: ClassVar[str] = "bcs_storage"
    esb_base_url: ClassVar[str] = ""
    apigw_base_url: ClassVar[str] = "bcsapi/v4/storage/k8s/dynamic/all_resources/clusters"

    def __init__(
        self,
        *,
        bk_app_code: str | None = None,
        bk_app_secret: str | None = None,
        bk_api_url: str | None = None,
        config: Config | None = None,
    ) -> None:
        super().__init__(
            bk_app_code=bk_app_code,
            bk_app_secret=bk_app_secret,
            bk_api_url=bk_api_url,
            config=config,
        )
        if not config:
            config = get_config()
        self.bk_api_url = f"{config.metadata.bcs_api_gateway_schema}://{config.metadata.bcs_api_gateway_host}:{config.metadata.bcs_api_gateway_port}"

    @override
    def get_headers(self, bk_tenant_id: str, user_params: UserParams) -> dict[str, str]:
        headers = super().get_headers(bk_tenant_id, user_params)
        headers["Authorization"] = f"Bearer {get_config().metadata.bcs_api_gateway_token}"
        return headers

    @override
    def handle_response(self, response: requests.Response) -> list[dict[str, Any]]:
        """
        处理响应结果，返回数据部分
        """
        result: list[dict[str, Any]] = []
        data_list = super().handle_response(response).get("data", [])
        for item in data_list:
            try:
                result.append(item.get("data", {}))
            except Exception as e:
                logger.error(e)
        return result


class Fetch(BCSStorageClient):
    """获取项目下的集群信息"""

    action: ClassVar[str] = "fetch"
    method: ClassVar[str] = "GET"

    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = "{cluster_id}/{type}?offset={offset}&limit={limit}"


fetch_client = Fetch()
