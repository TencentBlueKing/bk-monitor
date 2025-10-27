import abc
import ipaddress
import logging
import re
import time
from collections.abc import Generator
from datetime import timedelta
from multiprocessing.pool import IMapIterator
from typing import Any

from django.db.models import Q
from django.utils.translation import gettext as _

from apm.models import DataLink
from apm_web.models import Application
from bkm_space.api import SpaceApi
from bkm_space.define import Space
from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from bkmonitor.documents import AlertDocument
from bkmonitor.iam import Permission
from bkmonitor.iam.action import ActionEnum, ActionMeta
from bkmonitor.iam.drf import filter_data_by_permission
from bkmonitor.iam.resource import ResourceEnum
from bkmonitor.models import StrategyModel
from bkmonitor.models.bcs_cluster import BCSCluster
from bkmonitor.utils.thread_backend import ThreadPool
from bkmonitor.utils.time_tools import time_interval_align
from constants.apm import PreCalculateSpecificField
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import api
from core.errors.alert import AlertNotFoundError

logger = logging.getLogger("monitor_web")


class SearchItem(metaclass=abc.ABCMeta):
    """
    Abstract class for search items.
    """

    _bk_biz_names_cache = {}

    @classmethod
    def _get_biz_name(cls, bk_biz_id: int) -> str | None:
        """
        Get the space info by bk_biz_id.
        """
        if bk_biz_id not in cls._bk_biz_names_cache:
            space_info: Space | None = SpaceApi.get_space_detail(bk_biz_id=bk_biz_id)
            if not space_info:
                cls._bk_biz_names_cache[bk_biz_id] = str(bk_biz_id)
            else:
                cls._bk_biz_names_cache[bk_biz_id] = space_info.space_name
        return cls._bk_biz_names_cache[bk_biz_id]

    @classmethod
    def _get_allowed_bk_biz_ids(cls, bk_tenant_id: str, username: str, action: str | ActionMeta) -> list[int]:
        """
        Get the allowed bk_biz_ids by username.
        """
        permission = Permission(username=username, bk_tenant_id=bk_tenant_id)
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
    def search(cls, bk_tenant_id: str, username: str, query: str, limit: int = 5) -> list[dict] | None:
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
    def search(cls, bk_tenant_id: str, username: str, query: str, limit: int = 5) -> list[dict] | None:
        """
        Search the alert by alert id
        extended fields: alert_id, start_time, end_time
        """
        bk_biz_ids = cls._get_allowed_bk_biz_ids(bk_tenant_id, username, ActionEnum.VIEW_EVENT)

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

        return [
            {
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
        ]


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
    def search(cls, bk_tenant_id: str, username: str, query: str, limit: int = 5) -> list[dict] | None:
        """
        Search the strategy by strategy id
        extended fields: strategy_id
        """
        bk_biz_ids = cls._get_allowed_bk_biz_ids(bk_tenant_id, username, ActionEnum.VIEW_RULE)
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
                    "strategy_id": strategy.pk,
                }
            )

        if not items:
            return

        return [{"type": "strategy", "name": _("告警策略"), "items": items}]


class TraceSearchItem(SearchItem):
    """
    Search item for trace.
    """

    RE_TRACE_ID = re.compile(r"^[0-9a-z]{32}$")

    @classmethod
    def match(cls, query: str) -> bool:
        return bool(cls.RE_TRACE_ID.match(query))

    @classmethod
    def _query_apps_by_trace_id(cls, trace_id: str, table_id: str, limit: int = 5) -> list[dict[str, Any]]:
        """Query app infos by TraceId"""
        q: QueryConfigBuilder = (
            QueryConfigBuilder((DataTypeLabel.LOG, DataSourceLabel.BK_APM))
            .table(table_id)
            .filter(trace_id__eq=trace_id)
            .time_field(PreCalculateSpecificField.MIN_START_TIME)
            .values(PreCalculateSpecificField.BIZ_ID, PreCalculateSpecificField.APP_NAME)
        )

        now: int = int(time.time())
        qs: UnifyQuerySet = (
            UnifyQuerySet()
            .add_query(q)
            .time_align(False)
            .start_time(int((now - timedelta(days=7).total_seconds()) * 1000))
            .end_time(now * 1000)
            .limit(limit)
        )

        return list(qs)

    @classmethod
    def search(cls, bk_tenant_id: str, username: str, query: str, limit: int = 5) -> list[dict] | None:
        """
        Search the trace by trace id
        extended fields: trace_id, app_name, app_alias
        """
        trace_id = query

        # 获取预计算表
        datalink = DataLink.objects.first()
        if not datalink or not datalink.pre_calculate_config:
            return
        table_ids = [table["table_name"] for table in datalink.pre_calculate_config["cluster"]]

        # 使用多线程查询预计算表
        pool = ThreadPool(5)
        results = pool.imap_unordered(lambda tid: cls._query_apps_by_trace_id(trace_id, tid, limit), table_ids)
        pool.close()

        # 获取第一个有数据的结果
        app_infos = None
        for result in results:
            if result:
                app_infos = result
                pool.terminate()
                break

        if not app_infos:
            return

        items = []
        for app_info in app_infos:
            bk_biz_id = int(app_info["bk_biz_id"])
            app_name = app_info["app_name"]

            # 获取apm应用信息
            apm_app = Application.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
            if not apm_app:
                continue

            items.append(
                {
                    "bk_biz_id": bk_biz_id,
                    "bk_biz_name": cls._get_biz_name(bk_biz_id),
                    "name": trace_id,
                    "trace_id": trace_id,
                    "app_name": app_name,
                    "app_alias": apm_app.app_alias,
                    "application_id": apm_app.application_id,
                }
            )

        if not items:
            return

        return [{"type": "trace", "name": "Trace", "items": items}]


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
    def search(cls, bk_tenant_id: str, username: str, query: str, limit: int = 5) -> list[dict] | None:
        """
        Search the application by application name
        """

        query_filter = Q(app_alias__icontains=query)
        if cls.RE_APP_NAME.match(query):
            query_filter |= Q(app_name__icontains=query)

        # 业务过滤
        applications = Application.objects.filter(bk_tenant_id=bk_tenant_id).filter(query_filter)
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

        # 过滤无权限的应用
        items = filter_data_by_permission(
            bk_tenant_id=bk_tenant_id,
            data=items,
            actions=[ActionEnum.VIEW_APM_APPLICATION],
            resource_meta=ResourceEnum.APM_APPLICATION,
            id_field=lambda d: d["application_id"],
            instance_create_func=ResourceEnum.APM_APPLICATION.create_instance_by_info,
            mode="any",
            username=username,
        )[:limit]

        if not items:
            return

        return [{"type": "apm_application", "name": _("APM应用"), "items": items}]


class HostSearchItem(SearchItem):
    """
    Search item for host.
    """

    RE_IP = re.compile(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}")

    @classmethod
    def match(cls, query: str) -> bool:
        """
        ipv4或ipv6，不要用正则匹配
        """
        return bool(cls.RE_IP.findall(query)) or ":" in query

    @classmethod
    def search(cls, bk_tenant_id: str, username: str, query: str, limit: int = 5) -> list[dict] | None:
        """
        Search the host by host name
        """
        query = query.strip()

        ips = []
        try:
            ipaddress.ip_address(query)
            ips = [query]
        except ValueError:
            # 提取所有的ipv4
            for ip in cls.RE_IP.findall(query):
                try:
                    ipaddress.ip_address(ip)
                    ips.append(ip)
                except ValueError:
                    pass

        # 如果没有任何ip，则不进行查询
        if not ips:
            return

        result = api.cmdb.get_host_without_biz_v2(bk_tenant_id=bk_tenant_id, ips=ips)
        hosts: list[dict] = result["hosts"]

        items = []
        biz_hosts = {}
        for host in hosts:
            compare_hosts = []
            # 批量对比模式，同业务的主机放在一起
            if len(ips) > 1:
                if host["bk_biz_id"] not in biz_hosts:
                    biz_hosts[host["bk_biz_id"]] = []
                    compare_hosts = biz_hosts[host["bk_biz_id"]]
                else:
                    biz_hosts[host["bk_biz_id"]].append(
                        {
                            "bk_host_id": host["bk_host_id"],
                            "bk_target_ip": host["bk_host_innerip"],
                            "bk_target_cloud_id": host["bk_cloud_id"],
                        }
                    )
                    continue

            items.append(
                {
                    "bk_biz_id": host["bk_biz_id"],
                    "bk_biz_name": cls._get_biz_name(host["bk_biz_id"]),
                    "name": host["bk_host_innerip"],
                    "bk_host_innerip": host["bk_host_innerip"],
                    "bk_cloud_id": host["bk_cloud_id"],
                    "bk_cloud_name": host["bk_cloud_name"],
                    "bk_host_name": host["bk_host_name"],
                    "bk_host_id": host["bk_host_id"],
                    "compare_hosts": compare_hosts,
                }
            )

        if not items:
            return

        return [{"type": "host", "name": _("主机监控"), "items": items[:limit]}]


class BCSClusterSearchItem(SearchItem):
    """
    Search item for bcs cluster.
    """

    @classmethod
    def match(cls, query: str) -> bool:
        return not TraceSearchItem.match(query) and not AlertSearchItem.match(query) and not HostSearchItem.match(query)

    @classmethod
    def search(cls, bk_tenant_id: str, username: str, query: str, limit: int = 5) -> list[dict] | None:
        """
        Search the bcs cluster by cluster name
        """
        bk_biz_ids = cls._get_allowed_bk_biz_ids(bk_tenant_id, username, ActionEnum.VIEW_BUSINESS)
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
                        "project_name": cluster.space_uid.split("__")[1] if cluster.space_uid else "",
                    }
                )

                if len(items) >= limit:
                    break

            if len(items) >= limit:
                break

            offset += limit

        if not items:
            return

        return [{"type": "bcs_cluster", "name": _("BCS集群"), "items": items}]


class Searcher:
    """
    Searcher class to search the query in the search items.
    run the search items in parallel, yield the results.
    """

    search_items: list[type[SearchItem]] = [
        AlertSearchItem,
        StrategySearchItem,
        TraceSearchItem,
        ApmApplicationSearchItem,
        HostSearchItem,
        BCSClusterSearchItem,
    ]

    def __init__(self, bk_tenant_id: str, username: str):
        self.bk_tenant_id = bk_tenant_id
        self.username = username

    def search(self, query: str, timeout: int = 30) -> Generator[dict[str, Any], None, None]:
        """
        Search the query in the search items.
        """
        search_items = [item for item in self.search_items if item.match(query)]

        with ThreadPool() as pool:
            results: IMapIterator = pool.imap_unordered(
                lambda item: item.search(self.bk_tenant_id, self.username, query, limit=5), search_items
            )

            start_time = time.time()
            for __ in range(len(search_items)):
                try:
                    result: list[dict] | None = results.next(timeout=5)
                except StopIteration:
                    break
                except TimeoutError:
                    logger.error(f"Searcher search timeout, query: {query}")
                    continue
                except Exception as e:
                    logger.exception(f"Searcher search error, query: {query}, error: {e}")
                    continue

                if time.time() - start_time > timeout:
                    break

                if result:
                    yield from result
