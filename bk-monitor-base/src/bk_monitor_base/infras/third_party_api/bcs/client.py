import json
import logging
from abc import ABC
from typing import Any, ClassVar

import requests
from typing_extensions import override

from bk_monitor_base.config import get_config
from bk_monitor_base.infras.third_party_api.api_client import BkApiClient, UserParams

logger = logging.getLogger(__name__)


class BCSClient(BkApiClient, ABC):
    abstract_class: ClassVar[bool] = True

    module_name: ClassVar[str] = "bcs"
    esb_base_url: ClassVar[str] = ""
    apigw_base_url: ClassVar[str] = "api/bcs-api-gateway/prod/"

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
        resp = super().handle_response(response)
        code = resp.get("code")
        if code != 0:
            logger.error("BcsApiBaseResource: request bcs api error, response: %s", json.dumps(resp))
        return resp.get("data")


class FetchSharedClusterNamespaces(BCSClient):
    action: ClassVar[str] = "fetch_shared_cluster_namespaces"
    method: ClassVar[str] = "GET"

    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = "bcsproject/v1/projects/{project_code}/clusters/{cluster_id}/native/namespaces"


class GetFederationClusters(BCSClient):
    action: ClassVar[str] = "get_federation_clusters"
    method: ClassVar[str] = "POST"

    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = "federationmanager/v1/clusters/all/sub_clusters"


class GetProjects(BCSClient):
    action: ClassVar[str] = "get_projects"
    method: ClassVar[str] = "GET"

    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = "bcsproject/v1/projects"


fetch_shared_cluster_namespaces_client = FetchSharedClusterNamespaces()
get_federation_clusters_client = GetFederationClusters()
get_projects_client = GetProjects()
