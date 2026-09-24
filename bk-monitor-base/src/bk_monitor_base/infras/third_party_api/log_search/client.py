from abc import ABC
from typing import Any, ClassVar

import requests
from typing_extensions import override

from bk_monitor_base.infras.third_party_api.api_client import BkApiClient


class LogSearchClient(BkApiClient, ABC):
    abstract_class: ClassVar[bool] = True

    module_name: ClassVar[str] = "log_search"
    esb_base_url: ClassVar[str] = "api/c/compapi/v2/bk_log/"
    apigw_base_url: ClassVar[str] = "api/bk-log-search/prod/"

    @override
    def handle_response(self, response: requests.Response) -> Any:
        """
        处理响应结果，返回数据部分
        """
        return super().handle_response(response).get("data")


class ListEsRouter(LogSearchClient):
    """获取Es的结果表"""

    action: ClassVar[str] = "list_es_router"
    method: ClassVar[str] = "GET"

    esb_path: ClassVar[str] = "index_set/list_es_router/"
    apigw_path: ClassVar[str] = "index_set/list_es_router/"


class FetchStatisticsInfo(LogSearchClient):
    """获取字段统计信息"""

    action: ClassVar[str] = "fetch_statistics_info"
    method: ClassVar[str] = "POST"

    esb_path: ClassVar[str] = "field/index_set/statistics/info/"
    apigw_path: ClassVar[str] = "field/index_set/statistics/info/"


class FetchStatisticsGraph(LogSearchClient):
    """获取字段统计图表"""

    action: ClassVar[str] = "fetch_statistics_graph"
    method: ClassVar[str] = "POST"

    esb_path: ClassVar[str] = "field/index_set/statistics/graph/"
    apigw_path: ClassVar[str] = "field/index_set/statistics/graph/"


class FetchTopkList(LogSearchClient):
    """获取字段topk计数列表"""

    action: ClassVar[str] = "fetch_topk_list"
    method: ClassVar[str] = "POST"

    esb_path: ClassVar[str] = "field/index_set/fetch_topk_list/"
    apigw_path: ClassVar[str] = "field/index_set/fetch_topk_list/"


fetch_statistics_info_client = FetchStatisticsInfo()
fetch_statistics_graph_client = FetchStatisticsGraph()
fetch_topk_list_client = FetchTopkList()
list_es_router_client = ListEsRouter()
