import logging
from abc import ABC
from typing import Any, ClassVar

import requests
from typing_extensions import override

from bk_monitor_base.config import Config, get_config
from bk_monitor_base.infras.third_party_api.api_client import BkApiClient, UserParams

logger = logging.getLogger(__name__)

config = get_config()


class BCSClusterManagerClient(BkApiClient, ABC):
    abstract_class: ClassVar[bool] = True

    module_name: ClassVar[str] = "bcs_cluster_manager"
    esb_base_url: ClassVar[str] = ""
    apigw_base_url: ClassVar[str] = "bcsapi/v4/clustermanager/v1"

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
    def handle_response(self, response: requests.Response) -> Any:
        """
        处理响应结果，返回数据部分
        """
        return super().handle_response(response).get("data")


class GetProjectClusters(BCSClusterManagerClient):
    """获取项目下的集群信息"""

    action: ClassVar[str] = "get_project_clusters"
    method: ClassVar[str] = "GET"

    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = "cluster"


class FetchClusters(BCSClusterManagerClient):
    """获取项目下的集群信息"""

    action: ClassVar[str] = "get_project_clusters"
    method: ClassVar[str] = "GET"

    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = "cluster"


get_project_clusters_client = GetProjectClusters()
fetch_clusters_client = FetchClusters()
