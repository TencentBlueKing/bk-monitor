import abc
import logging
import re
import socket
import time
from multiprocessing.pool import IMapIterator
from typing import Any, Dict, Generator, List, Optional, Union

from django.db.models import Q
from django.utils.translation import gettext as _

from apm.models import DataLink
from apm_web.models import Application
from bkm_space.api import SpaceApi
from bkm_space.define import Space
from bkmonitor.documents import AlertDocument
from bkmonitor.iam import Permission
from bkmonitor.iam.action import ActionEnum, ActionMeta
from bkmonitor.models import StrategyModel
from bkmonitor.models.bcs_cluster import BCSCluster
from bkmonitor.utils.thread_backend import ThreadPool
from bkmonitor.utils.time_tools import time_interval_align
from core.drf_resource import api
from core.errors.alert import AlertNotFoundError

logger = logging.getLogger("monitor_web")


class SearchItem(metaclass=abc.ABCMeta):
    """
    Abstract class for search items.
    """

    _bk_biz_names_cache = {}

    @classmethod
    def _get_biz_name(cls, bk_biz_id: int) -> Optional[str]:
        """
        Get the space info by bk_biz_id.
        """
        if bk_biz_id not in cls._bk_biz_names_cache:
            space_info: Optional[Space] = SpaceApi.get_space_detail(bk_biz_id=bk_biz_id)
            if not space_info:
                cls._bk_biz_names_cache[bk_biz_id] = str(bk_biz_id)
            else:
                cls._bk_biz_names_cache[bk_biz_id] = space_info.space_name
        return cls._bk_biz_names_cache[bk_biz_id]

    @classmethod
    def _get_allowed_bk_biz_ids(cls, username: str, action: Union[str, ActionMeta]) -> List[int]:
        """
        Get the allowed bk_biz_ids by username.
        """
        permission = Permission(username)
        spaces = permission.filter_space_list_by_action(action)

        # 缓存业务信息
        for space in spaces:
            cls._bk_biz_names_cache[space["bk_biz_id"]] = space["space_name"]

        return [space["bk_biz_id"] for space in spaces]

    @classmethod
    def match(cls, query: str) -> bool:
        """
        Match the query with the search item.
        """
        raise NotImplementedError

    @classmethod
    def search(cls, username: str, query: str, limit: int = 5) -> Generator:
        """
        Search the query in the search item.
        数据格式:
        {
            "type": "trace",
            "name": "Trace",
            "items": [
                {
                    "bk_biz_id": 2,
                    "bk_biz_name": "蓝鲸",
                    "name": "xxx"
                },
            ]
        }
        item中可以扩展其他字段
        """
        raise NotImplementedError


class AlertSearchItem(SearchItem):
    """
    Search item for alert
    """

    # 大于 15 位的数字
    RE_ALERT_ID = re.compile(r"^\d{14,}$")

    @classmethod
    def match(cls, query: str) -> bool:
        return bool(cls.RE_ALERT_ID.match(query))

    @classmethod
    def search(cls, username: str, query: str, limit: int = 5) -> Generator:
        """
        Search the alert by alert id
        extended fields: alert_id, start_time, end_time
        """
        bk_biz_ids = cls._get_allowed_bk_biz_ids(username, ActionEnum.VIEW_EVENT)

        alert_id = int(query)
        try:
            alert = AlertDocument.get(alert_id)
        except (AlertNotFoundError, ValueError):
            return

        bk_biz_id = alert.event.bk_biz_id

        # 如果用户没有权限查看该业务，且不是告警的处理人，则不返回
        if bk_biz_id not in bk_biz_ids and username not in alert.assignee:
            return

        # 时间按小时对齐
        alert_time = time_interval_align(alert.create_time, 3600)

        # 前后各一个小时
        start_time = alert_time - 3600
        end_time = alert_time + 3600

        yield {
            "type": "alert",
            "name": _("告警事件"),
            "items": [
                {
                    "bk_biz_id": bk_biz_id,
                    "bk_biz_name": cls._get_biz_name(bk_biz_id),
                    "name": alert.alert_name,
                    "alert_id": alert_id,
                    "start_time": start_time,
                    "end_time": end_time,
                },
            ],
        }


class StrategySearchItem(SearchItem):
    """
    Search item for strategy.
    """

    @classmethod
    def match(cls, query: str) -> bool:
        """
        排除trace_id和alert_id
        """
        return not AlertSearchItem.match(query) and not TraceSearchItem.match(query)

    @classmethod
    def search(cls, username: str, query: str, limit: int = 5) -> Generator:
        """
        Search the strategy by strategy id
        extended fields: strategy_id
        """
        bk_biz_ids = cls._get_allowed_bk_biz_ids(username, ActionEnum.VIEW_RULE)
        if not bk_biz_ids:
            return

        try:
            strategy_id = int(query)
        except ValueError:
            strategy_id = None

        q = Q(name__icontains=query)
        if strategy_id:
            q |= Q(id=strategy_id)

        strategies = StrategyModel.objects.filter(q)

        # 业务过滤
        if len(bk_biz_ids) <= 20:
            strategies = strategies.filter(bk_biz_id__in=bk_biz_ids)[:limit]
        else:
            strategies = [s for s in strategies if s.bk_biz_id in bk_biz_ids][:limit]

        items = []
        for strategy in strategies:
            # 获取业务信息
            items.append(
                {
                    "bk_biz_id": strategy.bk_biz_id,
                    "bk_biz_name": cls._get_biz_name(strategy.bk_biz_id),
                    "name": strategy.name,
                    "strategy_id": strategy.id,
                }
            )

        if not items:
            return

        yield {"type": "strategy", "name": _("告警策略"), "items": items}


class TraceSearchItem(SearchItem):
    """
    Search item for trace.
    """

    RE_TRACE_ID = re.compile(r"^[0-9a-z]{32}$")

    @classmethod
    def match(cls, query: str) -> bool:
        return bool(cls.RE_TRACE_ID.match(query))

    @classmethod
    def search(cls, username: str, query: str, limit: int = 5) -> Generator:
        """
        Search the trace by trace id
        extended fields: trace_id, app_name, app_alias
        """
        bk_biz_ids = cls._get_allowed_bk_biz_ids(username, ActionEnum.VIEW_APM_APPLICATION)
        if not bk_biz_ids:
            return

        trace_id = query
        query_body = {"query": {"bool": {"filter": [{"term": {"trace_id": trace_id}}]}}, "size": limit}

        # 获取预计算表
        datalink = DataLink.objects.first()
        if not datalink or not datalink.pre_calculate_config:
            return
        table_ids = [table["table_name"] for table in datalink.pre_calculate_config["cluster"]]

        # 使用多线程查询预计算表
        pool = ThreadPool(5)
        results = pool.imap_unordered(
            lambda tid: api.metadata.get_es_data(table_id=tid, query_body=query_body, use_full_index_names=True),
            table_ids,
        )
        pool.close()

        # 获取第一个有数据的结果
        traces = None
        for result in results:
            if result["hits"]["hits"]:
                traces = result["hits"]["hits"]
                pool.terminate()
                break

        if not traces:
            return

        items = []
        for trace in traces:
            bk_biz_id = int(trace["_source"]["bk_biz_id"])

            if bk_biz_id not in bk_biz_ids:
                continue

            app_name = trace["_source"]["app_name"]

            # 获取apm应用信息
            apm_app = Application.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
            if not apm_app:
                continue

            items.append(
                {
                    "bk_biz_id": bk_biz_id,
                    "bk_biz_name": trace["_source"]["biz_name"],
                    "name": trace_id,
                    "trace_id": trace_id,
                    "app_name": app_name,
                    "app_alias": apm_app.app_alias,
                    "application_id": apm_app.application_id,
                }
            )

        if not items:
            return

        yield {"type": "trace", "name": "Trace", "items": items}


class ApmApplicationSearchItem(SearchItem):
    """
    Search item for apm application.
    """

    RE_APP_NAME = re.compile(r"^[a-z0-9_-]{1,50}$")

    @classmethod
    def match(cls, query: str) -> bool:
        """
        1-50字符，由小写字母、数字、下划线、中划线组成
        """
        return not AlertSearchItem.RE_ALERT_ID.match(query) and not TraceSearchItem.RE_TRACE_ID.match(query)

    @classmethod
    def search(cls, username: str, query: str, limit: int = 5) -> Generator:
        """
        Search the application by application name
        """
        bk_biz_ids = cls._get_allowed_bk_biz_ids(username, ActionEnum.VIEW_APM_APPLICATION)
        if not bk_biz_ids:
            return

        q = Q(app_alias__icontains=query)
        if cls.RE_APP_NAME.match(query):
            q |= Q(app_name__icontains=query)

        # 业务过滤
        if len(bk_biz_ids) <= 20:
            applications = Application.objects.filter(q, bk_biz_id__in=bk_biz_ids)[:limit]
        else:
            applications = [a for a in Application.objects.filter(q) if a.bk_biz_id in bk_biz_ids][:limit]

        if not applications:
            return

        items = []
        for application in applications:
            items.append(
                {
                    "bk_biz_id": application.bk_biz_id,
                    "bk_biz_name": cls._get_biz_name(application.bk_biz_id),
                    "name": application.app_alias or application.app_name,
                    "app_name": application.app_name,
                    "app_alias": application.app_alias,
                    "application_id": application.application_id,
                }
            )

        if not items:
            return

        yield {"type": "apm_application", "name": _("APM应用"), "items": items}


class HostSearchItem(SearchItem):
    """
    Search item for host.
    """

    RE_IP = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")

    @classmethod
    def match(cls, query: str) -> bool:
        """
        ipv4或ipv6，不要用正则匹配
        """
        if cls.RE_IP.match(query):
            try:
                socket.inet_aton(query)
                return True
            except socket.error:
                pass
        elif ":" in query:
            try:
                socket.inet_pton(socket.AF_INET6, query)
                return True
            except socket.error:
                pass
        return False

    @classmethod
    def search(cls, username: str, query: str, limit: int = 5) -> Generator:
        """
        Search the host by host name
        """
        result = api.cmdb.get_host_without_biz_v2(ips=[query], limit=limit)
        hosts: List[Dict] = result["hosts"]

        items = []
        for host in hosts:
            items.append(
                {
                    "bk_biz_id": host["bk_biz_id"],
                    "bk_biz_name": cls._get_biz_name(host["bk_biz_id"]),
                    "name": query,
                    "bk_host_innerip": host["bk_host_innerip"],
                    "bk_cloud_id": host["bk_cloud_id"],
                    "bk_cloud_name": host["bk_cloud_name"],
                    "bk_host_name": host["bk_host_name"],
                    "bk_host_id": host["bk_host_id"],
                }
            )

        if not items:
            return

        yield {"type": "host", "name": _("主机监控"), "items": items}


class BCSClusterSearchItem(SearchItem):
    """
    Search item for bcs cluster.
    """

    @classmethod
    def match(cls, query: str) -> bool:
        return not TraceSearchItem.match(query) and not AlertSearchItem.match(query) and not HostSearchItem.match(query)

    @classmethod
    def search(cls, username: str, query: str, limit: int = 5) -> Generator:
        """
        Search the bcs cluster by cluster name
        """
        bk_biz_ids = cls._get_allowed_bk_biz_ids(username, ActionEnum.VIEW_BUSINESS)
        if not bk_biz_ids:
            return

        # 构建基础查询
        query_filter = Q(name__icontains=query) | Q(bcs_cluster_id__icontains=query)
        if len(bk_biz_ids) <= 20:
            query_filter &= Q(bk_biz_id__in=bk_biz_ids)

        # 使用迭代器分页查询
        items = []
        offset = 0
        while True:
            clusters = BCSCluster.objects.filter(query_filter)[offset : offset + limit]
            if not clusters:
                break

            for cluster in clusters:
                items.append(
                    {
                        "bk_biz_id": cluster.bk_biz_id,
                        "bk_biz_name": cls._get_biz_name(cluster.bk_biz_id),
                        "name": cluster.name,
                        "cluster_name": cluster.name,
                        "bcs_cluster_id": cluster.bcs_cluster_id,
                    }
                )

                if len(items) >= limit:
                    break

            if len(items) >= limit:
                break

            offset += limit

        if not items:
            return

        yield {"type": "bcs_cluster", "name": _("BCS集群"), "items": items}


class Searcher:
    """
    Searcher class to search the query in the search items.
    run the search items in parallel, yield the results.
    """

    search_items = [
        AlertSearchItem,
        StrategySearchItem,
        TraceSearchItem,
        ApmApplicationSearchItem,
        HostSearchItem,
        BCSClusterSearchItem,
    ]

    def __init__(self, username: str):
        self.username = username

    def search(self, query: str, timeout: int = 30) -> Generator[Dict[str, Any], None, None]:
        """
        Search the query in the search items.
        """
        search_items = [item for item in self.search_items if item.match(query)]

        with ThreadPool() as pool:
            results: IMapIterator = pool.imap_unordered(
                lambda item: item.search(self.username, query, limit=5), search_items
            )

            start_time = time.time()
            while True:
                try:
                    result: Generator = results.next(timeout=5)
                except StopIteration:
                    break
                except TimeoutError:
                    logger.error(f"Searcher search timeout, query: {query}")
                    continue
                except Exception as e:
                    logger.exception(f"Searcher search error, query: {query}, error: {e}")
                    continue

                yield from result

                if time.time() - start_time > timeout:
                    break
