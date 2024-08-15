# -*- coding: utf-8 -*-
import abc
from collections import defaultdict
from typing import Callable, List, Optional

from django.utils.functional import cached_property

from api.cmdb.define import Business
from bkmonitor.iam.action import ActionMeta
from bkmonitor.utils.request import get_request_username
from core.drf_resource import api, resource


class SearchScope:
    BIZ = "BIZ"  # 当前业务
    GLOBAL = "GLOBAL"  # 所有业务


class SearchResultItem:
    def __init__(
        self,
        bk_biz_id: int,
        title: str,
        view: str,
        view_args: dict = None,
        is_collected: bool = False,
        temp_share_url: Optional[str] = None,
    ):
        self.bk_biz_id = bk_biz_id
        self.title = title
        self.is_allowed = True
        self.view = view
        self.view_args = view_args or {}
        self.bk_biz_name = str(self.bk_biz_id)
        self.is_collected = is_collected
        self.temp_share_url = temp_share_url

    def to_dict(self):
        return {
            "bk_biz_id": self.bk_biz_id,
            "bk_biz_name": self.bk_biz_name,
            "is_allowed": self.is_allowed,
            "title": self.title,
            "view": self.view,
            "view_args": self.view_args,
            "is_collected": self.is_collected,
            "temp_share_url": self.temp_share_url,
        }


class SearchResult:
    def __init__(self, scene: str, results: List[SearchResultItem] = None):
        self.results = results or []
        self.scene = scene

    def to_dict(self):
        return {"scene": self.scene, "results": [result.to_dict() for result in self.results]}


class BaseSearchHandler(metaclass=abc.ABCMeta):
    # 搜索场景
    SCENE: str = ""

    def __init__(self, bk_biz_id: int = None, scope: str = SearchScope.BIZ, username: str = ""):
        if not bk_biz_id and scope == SearchScope.BIZ:
            raise ValueError("`bk_biz_id` must be supplied when scope is `BIZ`")

        self.bk_biz_id = bk_biz_id
        self.scope = scope

        if username:
            self.username = username
        else:
            username = get_request_username()
            if not username:
                raise ValueError("`username` must be supplied when request is unavailable")
            self.username = username

    @cached_property
    def all_business(self) -> List[Business]:
        return api.cmdb.get_business(all=True)

    def add_permission_for_results(self, results: List[SearchResultItem], action: ActionMeta):
        """
        为搜索结果增加访问权限检测
        """
        allowed_biz_ids = resource.space.get_bk_biz_ids_by_user(self.username)
        for item in results:
            item.is_allowed = item.bk_biz_id in allowed_biz_ids

    def _add_biz_name_for_results(self, results: List[SearchResultItem]):
        """
        为搜索结果增加业务名称翻译
        """
        biz_names = {biz.bk_biz_id: biz.bk_biz_name for biz in self.all_business}
        for item in results:
            item.bk_biz_name = biz_names.get(item.bk_biz_id, str(item.bk_biz_id))

    def _sort_results(self, results: List[SearchResultItem]):
        # 按业务ID升序
        results.sort(key=lambda item: item.bk_biz_id)

        # 当前业务优先
        results.sort(key=lambda item: item.bk_biz_id == self.bk_biz_id, reverse=True)

        # 有权限优先
        results.sort(key=lambda item: item.is_allowed, reverse=True)

    def collect_results_by_biz(
        self,
        results: List[SearchResultItem],
        limit: int,
        collect_func: Callable[[int, List[SearchResultItem]], SearchResultItem],
    ) -> List[SearchResultItem]:
        """
        以业务作为分组，对超出长度的结果进行汇总
        :param results: 原始结果列表
        :param limit: 长度阈值
        :param collect_func: 汇总函数, 输入参数 bk_biz_id, items, 输出为单个 item 汇总结果
        :return: 汇总后结果列表
        """
        groups = defaultdict(list)
        for result in results:
            groups[result.bk_biz_id].append(result)

        origin_results = []
        merged_results = []

        for bk_biz_id, items in groups.items():
            if len(items) <= limit:
                origin_results.extend(items)
            else:
                item = collect_func(bk_biz_id, items)
                merged_results.append(item)

        return origin_results + merged_results

    def wrap_search_result(self, results: List[SearchResultItem]) -> SearchResult:
        """
        将搜索结果进一步封装，添加场景参数
        """
        return SearchResult(scene=self.SCENE, results=results)

    def post_search(self, items: List[SearchResultItem]) -> SearchResult:
        self._add_biz_name_for_results(items)
        self._sort_results(items)
        result = self.wrap_search_result(items)
        return result

    def handle(self, query: str, limit: int = 10) -> SearchResult:
        items = self.search(query, limit)
        result = self.post_search(items)
        return result

    def search(self, query: str, limit: int = 10) -> List[SearchResultItem]:
        raise NotImplementedError
