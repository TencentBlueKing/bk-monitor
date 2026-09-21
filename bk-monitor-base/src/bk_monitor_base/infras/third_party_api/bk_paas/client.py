import logging
from abc import ABC
from typing import Any, ClassVar

import requests
from typing_extensions import override

from bk_monitor_base.infras.third_party_api.api_client import BkApiClient

logger = logging.getLogger(__name__)


class BKPAASClient(BkApiClient, ABC):
    abstract_class: ClassVar[bool] = True

    module_name: ClassVar[str] = "bk_paas"
    esb_base_url: ClassVar[str] = "api/c/compapi/v2/bk_paas"
    apigw_base_url: ClassVar[str] = ""

    @override
    def handle_response(self, response: requests.Response) -> Any:
        """
        处理响应结果，返回数据部分
        """
        return super().handle_response(response).get("data")


class GetAppClusterNamespace(BKPAASClient):
    """获取项目下的集群信息"""

    action: ClassVar[str] = "get_app_cluster_namespace"
    method: ClassVar[str] = "GET"

    esb_path: ClassVar[str] = "system/bkapps/applications/{app_code}/cluster_namespaces/"
    apigw_path: ClassVar[str] = ""


get_app_cluster_namespace_client = GetAppClusterNamespace()
