import abc
import ipaddress
import logging
import math
import re
import time
from collections.abc import Callable, Generator, Sequence
from datetime import timedelta
from multiprocessing.pool import IMapIterator
from typing import Any, TypeVar

from django.db.models import Count, Q
from django.utils import timezone
from django.utils.translation import gettext as _

from apm.models import DataLink
from apm_web.models import Application, UserVisitRecord
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
from constants.apm import OtlpKey, PreCalculateSpecificField
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import api
from core.errors.alert import AlertNotFoundError
from monitor.models import UserConfig

logger = logging.getLogger("monitor_web")

_T = TypeVar("_T")
_R = TypeVar("_R")


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
    def search(
        cls, bk_tenant_id: str, username: str, query: str, limit: int = 5, current_bk_biz_id: int | None = None
    ) -> list[dict] | None:
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
    def search(
        cls, bk_tenant_id: str, username: str, query: str, limit: int = 5, current_bk_biz_id: int | None = None
    ) -> list[dict] | None:
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
    def search(
        cls, bk_tenant_id: str, username: str, query: str, limit: int = 5, current_bk_biz_id: int | None = None
    ) -> list[dict] | None:
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

    实现两条互补查询路径并行竞速：
    - Path A 预计算：复用 ``DataLink.pre_calculate_config`` 共享表，覆盖老数据广度。
    - Path B 直查：按候选业务/应用打分取 TopN，直查 ``Application.trace_result_table_id``，
      覆盖预计算分钟级写入延迟。
    """

    RE_TRACE_ID = re.compile(r"^[0-9a-z]{32}$")

    _RAW_QUERY_TOP_N = 25
    _CURRENT_BIZ_WEIGHT = 1  # 当前业务基础分
    _DEFAULT_BIZ_WEIGHT = 1  # 默认业务基础分
    _HAS_SERVICE_APP_WEIGHT = 0.5  # 有服务关联的应用加分，提升命中率较低但价值较高的应用
    # 最近访问应用基础分：保证访问过的应用恒定优于未访问层最高分。
    _CURRENT_APP_WEIGHT = _CURRENT_BIZ_WEIGHT + _DEFAULT_BIZ_WEIGHT + _HAS_SERVICE_APP_WEIGHT

    @classmethod
    def match(cls, query: str) -> bool:
        return bool(cls.RE_TRACE_ID.match(query))

    @staticmethod
    def _first_truthy_concurrent(items: Sequence[_T], fn: Callable[[_T], _R], max_workers: int) -> _R | None:
        """并发执行 ``fn(item)``，返回首个 truthy 结果；剩余任务通过 ``terminate`` 取消调度。

        ``fn`` 内部需自行吞掉异常并返回 falsy 值，否则首个抛错的任务会终结迭代。
        """
        if not items:
            return None
        pool = ThreadPool(min(len(items), max(1, max_workers)))
        try:
            for result in pool.imap_unordered(fn, items):
                if result:
                    return result
        finally:
            pool.terminate()
        return None

    @staticmethod
    def _safe_call(fn: Callable[[], _R], err_msg: str) -> _R | None:
        """调用 ``fn``，捕获并记录异常，返回 None。用于路径级隔离。"""
        try:
            return fn()
        except Exception:  # pylint: disable=broad-except
            logger.exception(err_msg)
            return None

    @classmethod
    def _build_item(cls, trace_id: str, app: Application) -> dict[str, Any]:
        """根据 Application 实例装配单条搜索结果"""
        return {
            "bk_biz_id": app.bk_biz_id,
            "bk_biz_name": cls._get_biz_name(app.bk_biz_id),
            "name": trace_id,
            "trace_id": trace_id,
            "app_name": app.app_name,
            "app_alias": app.app_alias,
            "application_id": app.application_id,
        }

    @classmethod
    def _fetch_data(
        cls, trace_id: str, table_id: str, time_field: str, fields: list[str], limit: int
    ) -> list[dict[str, Any]]:
        now: int = int(time.time())
        qs: UnifyQuerySet = (
            UnifyQuerySet()
            .add_query(
                QueryConfigBuilder((DataTypeLabel.LOG, DataSourceLabel.BK_APM))
                .table(table_id)
                .filter(trace_id__eq=trace_id)
                .time_field(time_field)
                .values(*fields)
            )
            .time_align(False)
            .start_time(int((now - timedelta(days=7).total_seconds()) * 1000))
            .end_time(now * 1000)
            .limit(limit)
        )
        return list(qs)

    # ---------- Path A: 预计算 ----------

    @classmethod
    def _query_precalc_apps_by_trace_id(cls, trace_id: str, table_id: str, limit: int = 5) -> list[dict[str, Any]]:
        """单 cluster 预计算表查询，返回 ``[{bk_biz_id, app_name}, ...]``"""
        return cls._fetch_data(
            trace_id,
            table_id,
            PreCalculateSpecificField.MIN_START_TIME,
            [PreCalculateSpecificField.BIZ_ID, PreCalculateSpecificField.APP_NAME],
            limit,
        )

    @classmethod
    def _load_precalc_table_ids(cls) -> list[str]:
        """读取 ``DataLink.pre_calculate_config.cluster`` 中的表名列表，缺失或异常时返回空列表"""
        datalink = DataLink.objects.first()
        if not datalink or not datalink.pre_calculate_config:
            return []
        try:
            cluster_config = datalink.pre_calculate_config["cluster"] or []
            return [t["table_name"] for t in cluster_config]
        except (KeyError, TypeError):
            return []

    @classmethod
    def _path_precalc(cls, bk_tenant_id: str, trace_id: str, limit: int) -> list[dict[str, Any]]:
        """Path A：多 cluster 并发查询预计算表，装配 items 输出"""
        table_ids: list[str] = cls._load_precalc_table_ids()
        if not table_ids:
            return []

        app_infos: list[dict[str, Any]] = (
            cls._first_truthy_concurrent(
                table_ids,
                lambda tid: cls._query_precalc_apps_by_trace_id(trace_id, tid, limit),
                max_workers=5,
            )
            or []
        )

        items: list[dict[str, Any]] = []
        for info in app_infos:
            try:
                bk_biz_id = int(info["bk_biz_id"])
            except (TypeError, ValueError, KeyError):
                continue
            app_name: str | None = info.get("app_name")
            if not app_name:
                continue
            app = Application.objects.filter(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, app_name=app_name).first()
            if not app:
                continue
            items.append(cls._build_item(trace_id, app))
        return items

    # ---------- Path B: 直查 ----------

    @classmethod
    def _query_raw_apps_by_trace_id(cls, trace_id: str, table_id: str) -> bool:
        """直查单应用原始 Trace 表，仅判断 trace_id 是否存在（``limit=1``）"""
        return bool(cls._fetch_data(trace_id, table_id, OtlpKey.END_TIME, [OtlpKey.TRACE_ID], limit=1))

    @classmethod
    def _get_user_config(cls, username: str, key: str) -> Any:
        """读取用户配置项"""
        return UserConfig.objects.filter(username=username, key=key).first()

    @classmethod
    def _get_default_biz_id(cls, username: str) -> int | None:
        """读取 ``UserConfig.DEFAULT_BIZ_ID`` 并尽量转换为 int"""
        config: UserConfig | None = cls._get_user_config(username, key=UserConfig.Keys.DEFAULT_BIZ_ID)
        try:
            return int(config.value) if config else None
        except (TypeError, ValueError):
            return None

    @classmethod
    def _aggregate_user_visits(cls, username: str) -> dict[tuple[int, str], int]:
        """聚合用户最近 N 天的 APM 应用访问次数，返回 ``(bk_biz_id, app_name) → count``"""
        since = timezone.now() - timedelta(days=30)
        rows = (
            UserVisitRecord.objects.filter(created_by=username, created_at__gte=since)
            .values("bk_biz_id", "app_name")
            .annotate(visit_count=Count("id"))
        )
        return {(row["bk_biz_id"], row["app_name"]): row["visit_count"] for row in rows if row["app_name"]}

    @classmethod
    def _collect_candidate_apps(cls, bk_tenant_id: str, username: str, bk_biz_id: int | None) -> list[Application]:
        """构造候选应用列表：候选业务并集 → 应用全量拉取 → 统一打分截 TopN

        应用得分 ``score = VISITED_BONUS + log1p(visit) if visit > 0 else biz_boost + service_boost``，
        同分按 ``application_id`` 升序保障稳定性。
        """
        biz_app_visit_count_map: dict[tuple[int, str], int] = cls._aggregate_user_visits(username)

        default_biz_id = cls._get_default_biz_id(username)
        biz_ids: set[int] = {biz for biz, _ in biz_app_visit_count_map}
        biz_ids.update(cls._get_allowed_bk_biz_ids(bk_tenant_id, username, ActionEnum.VIEW_BUSINESS))
        if bk_biz_id:
            biz_ids.add(bk_biz_id)
        if default_biz_id is not None:
            biz_ids.add(default_biz_id)

        if not biz_ids:
            return []

        apps = list(
            Application.objects.filter(bk_tenant_id=bk_tenant_id, bk_biz_id__in=list(biz_ids)).exclude(
                trace_result_table_id=""
            )
        )
        if not apps:
            return []

        def _score(app: Application) -> float:
            # Q：为什么使用 log1p？
            # A：归一化：直接使用访问次数会导致该因素过于突出，log1p 可以将访问次数映射到一个更小的范围，避免极端值对得分的过度影响。
            visit_count: int = biz_app_visit_count_map.get((app.bk_biz_id, app.app_name), 0)
            if visit_count > 0:
                return cls._CURRENT_APP_WEIGHT + math.log1p(visit_count)

            has_service_score: float = cls._HAS_SERVICE_APP_WEIGHT * (app.service_count > 0)
            current_biz_score: float = cls._CURRENT_BIZ_WEIGHT * (app.bk_biz_id == bk_biz_id)
            default_biz_score: float = cls._DEFAULT_BIZ_WEIGHT * (app.bk_biz_id == default_biz_id)
            return has_service_score + current_biz_score + default_biz_score

        # 先按得分降序、再按 application_id 升序排序，最后截取 TopN 作为 Path B 的查询候选，保障结果稳定且兼顾访问频次和业务相关性。
        return sorted(apps, key=lambda app: (-_score(app), app.application_id))[: cls._RAW_QUERY_TOP_N]

    @classmethod
    def _path_raw(
        cls,
        bk_tenant_id: str,
        username: str,
        trace_id: str,
        bk_biz_id: int | None,
    ) -> list[dict[str, Any]]:
        """Path B：TopN 候选应用并发直查，首个命中即返回。"""
        apps = cls._collect_candidate_apps(bk_tenant_id, username, bk_biz_id)
        if not apps:
            return []

        logger.info(
            "[TraceSearch] raw path candidate apps, trace_id=%s, bk_biz_id=%s, candidates=%s",
            trace_id,
            bk_biz_id,
            ",".join([f"{app.bk_biz_id}-{app.app_name}" for app in apps]),
        )

        def _probe_app(app: Application) -> Application | None:
            """探测单应用原始 Trace 表是否命中 trace_id；异常按 miss 处理"""
            try:
                if cls._query_raw_apps_by_trace_id(trace_id, app.trace_result_table_id):
                    return app
            except Exception:  # pylint: disable=broad-except
                logger.exception(
                    "[TraceSearch] raw query failed, app=%s table=%s",
                    app.application_id,
                    app.trace_result_table_id,
                )
            return None

        hit_app = cls._first_truthy_concurrent(apps, _probe_app, max_workers=min(len(apps), 8))
        return [cls._build_item(trace_id, hit_app)] if hit_app else []

    @classmethod
    def search(
        cls, bk_tenant_id: str, username: str, query: str, limit: int = 5, current_bk_biz_id: int | None = None
    ) -> list[dict] | None:
        """
        Search the trace by trace id
        extended fields: trace_id, app_name, app_alias
        """
        trace_id = query

        # 路径级隔离：单条路径异常被吞掉并返回 None，让另一路仍有机会贡献结果
        path_funcs: list[Callable[[], list[dict[str, Any]] | None]] = [
            lambda: cls._safe_call(
                lambda: cls._path_precalc(bk_tenant_id, trace_id, limit),
                f"[TraceSearch] precalc path failed, trace_id={trace_id}",
            ),
            lambda: cls._safe_call(
                lambda: cls._path_raw(bk_tenant_id, username, trace_id, current_bk_biz_id),
                f"[TraceSearch] raw path failed, trace_id={trace_id}",
            ),
        ]

        items = cls._first_truthy_concurrent(path_funcs, lambda fn: fn(), max_workers=len(path_funcs))
        if not items:
            return None

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
    def search(
        cls, bk_tenant_id: str, username: str, query: str, limit: int = 5, current_bk_biz_id: int | None = None
    ) -> list[dict] | None:
        """
        Search the application by application name
        """

        query_filter = Q(app_alias__icontains=query)
        if cls.RE_APP_NAME.match(query):
            query_filter |= Q(app_name__icontains=query)

        applications = list(Application.objects.filter(bk_tenant_id=bk_tenant_id).filter(query_filter))
        if not applications:
            return

        # 先构建不含业务名的基础数据，避免在权限过滤之前对每条记录发起 SpaceApi 调用（N+1）。
        items = [
            {
                "bk_biz_id": application.bk_biz_id,
                "bk_biz_name": "",
                "name": application.app_alias or application.app_name,
                "app_name": application.app_name,
                "app_alias": application.app_alias,
                "application_id": application.application_id,
            }
            for application in applications
        ]

        # 过滤无权限的应用，并裁剪至目标数量
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

        # 只对最终展示的条目（至多 limit 条）补充业务名，彻底消除 N+1
        for item in items:
            item["bk_biz_name"] = cls._get_biz_name(item["bk_biz_id"])

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
    def search(
        cls, bk_tenant_id: str, username: str, query: str, limit: int = 5, current_bk_biz_id: int | None = None
    ) -> list[dict] | None:
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
    def search(
        cls, bk_tenant_id: str, username: str, query: str, limit: int = 5, current_bk_biz_id: int | None = None
    ) -> list[dict] | None:
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

    def __init__(self, bk_tenant_id: str, username: str, current_bk_biz_id: int | None = None):
        self.bk_tenant_id = bk_tenant_id
        self.username = username
        self.current_bk_biz_id = current_bk_biz_id

    def search(self, query: str, timeout: int = 30, limit: int = 5) -> Generator[dict[str, Any], None, None]:
        """
        Search the query in the search items.
        """
        search_items = [item for item in self.search_items if item.match(query)]

        with ThreadPool() as pool:
            results: IMapIterator = pool.imap_unordered(
                lambda item: item.search(
                    self.bk_tenant_id, self.username, query, limit=limit, current_bk_biz_id=self.current_bk_biz_id
                ),
                search_items,
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
