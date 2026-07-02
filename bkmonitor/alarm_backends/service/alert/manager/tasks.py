"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
import time

from elasticsearch.exceptions import ConnectionError as ESConnectionError
from elasticsearch.exceptions import TransportError
from elasticsearch.helpers import BulkIndexError
from elasticsearch.helpers.errors import ScanError
from elasticsearch_dsl import Q
from kombu.exceptions import OperationalError as KombuOperationalError
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import ReadOnlyError
from redis.exceptions import TimeoutError as RedisTimeoutError

from alarm_backends.constants import CONST_ONE_DAY, CONST_ONE_HOUR
from alarm_backends.core.alert.alert import Alert, AlertCache, AlertKey
from alarm_backends.core.cache.strategy import StrategyCacheManager
from alarm_backends.core.cluster import get_cluster_bk_biz_ids
from alarm_backends.core.storage.redis_cluster import PipelineResultMismatch
from alarm_backends.service.alert.manager.processor import AlertManager
from alarm_backends.service.scheduler.app import app
from bkmonitor.documents import AlertDocument, AlertLog
from bkmonitor.documents.base import BulkActionType
from constants.alert import EventStatus
from core.prometheus import metrics

logger = logging.getLogger("alert.manager")

# 批处理条数
BATCH_SIZE = 200
# 默认检测周期
DEFAULT_CHECK_INTERVAL = 60
# ES 深分页每页大小
SCAN_PAGE_SIZE = 5000

# 瞬态基础设施异常(计 deferred 而非 failed): 仅纳入"本批未 finalize、下一周期重跑可自愈"的类型，
# 其余一律计 failed。收口原则——基于已知可恢复类型显式纳入，不用基类宽松匹配：否则会把代码 / 数据 /
# 配置类错误(不会靠重跑恢复)漂白成 deferred，从成功率口径里抹掉真实故障。新可恢复类型经确认后再扩。
# Redis: 连接(含 BusyLoadingError 子类) / 超时 / 主从切换只读(ReadOnlyError) / pipeline 结果错位；
#   不含 ResponseError / DataError / NoScriptError 等命令·数据·脚本错(不会自愈)。
# Broker(Celery/kombu): RabbitMQ/AMQP 可恢复连接错误(kombu.exceptions.OperationalError)仅在 finalize 前
#   (save_alerts 之前的 .delay)计 deferred；finalize 后(send_signal)抛出会丢 signal、终态不重发,仍计 failed
#   (见下 is_transient_retry_exc 分支)。同名的 django.db.utils.OperationalError(DB 逻辑错)任何阶段都计 failed。
REDIS_RETRY_EXCEPTIONS = (RedisConnectionError, RedisTimeoutError, ReadOnlyError, PipelineResultMismatch)


def is_transient_retry_exc(exc: Exception, finalized: bool = False) -> bool:
    """异常是否为"下一周期重跑可自愈"的瞬态基础设施错误：是则计 deferred，否则计 failed。

    finalized: 本批告警状态是否已落库(save_alerts 完成)。仅影响 broker 异常的判定：finalize 后抛出的
    broker 异常会丢 signal、终态不会被下周期重发,不可靠自愈,不计 deferred。
    """
    if isinstance(exc, REDIS_RETRY_EXCEPTIONS):
        return True
    if isinstance(exc, KombuOperationalError):
        # Celery broker(RabbitMQ/AMQP)可恢复连接错误(kombu.exceptions.OperationalError 语义即 recoverable
        # connection error)：publish 任务(.delay)时新建 broker 连接偶发建连/通道超时、连接重置。是否可靠
        # 自愈取决于发生阶段:
        #   - finalize 前(check_all 的 create_actions.delay,在告警状态/ES 持久化之前):本批未落库,下一
        #     周期 check_abnormal_alert 重跑重发,可自愈 → deferred。
        #   - finalize 后(send_signal 的 check_action_and_composite.delay,在 save_alerts 之后):告警状态
        #     (含 recovered/closed)已落库,终态不会被下周期重新捞起重发 signal → 是实际丢 signal 的失败,
        #     仍计 failed,不能从成功率口径抹掉。
        # 按类型匹配可与同名的 django.db.utils.OperationalError(DB 逻辑错)区分,后者任何阶段都计 failed。
        return not finalized
    if isinstance(exc, ScanError):
        # scan / scroll 部分分片失败，重跑可恢复
        return True
    if isinstance(exc, ESConnectionError):
        # ES 连接类(ConnectionTimeout 为其子类)无 HTTP 状态码，视为瞬态
        return True
    if isinstance(exc, TransportError):
        # ES 其余传输错误：仅 429(限流) / 5xx(服务端) 视为瞬态；4xx(查询 / 权限 / 版本冲突)多为代码或
        # 配置问题，仍计 failed。status_code 取自 es-py<8；es8 起无此属性 → 落入 failed(安全方向)。
        code = getattr(exc, "status_code", None)
        return isinstance(code, int) and (code == 429 or 500 <= code <= 599)
    return False


def _search_after_hits(search, page_size: int):
    """
    基于 search_after + PIT 对 elasticsearch_dsl Search 对象做深分页迭代。

    替代 scan()（scroll API），既避免 ES scroll context 积压，又通过 PIT 保留查询
    开始时的快照语义，防止分页期间 refresh 导致的漏扫或重复扫描。

    :param search: 已配置好 filter/source 的 elasticsearch_dsl Search 对象
    :param page_size: 每页大小
    """
    es_client = AlertDocument._index._get_connection()
    # 从 search 对象自身提取 index，保留调用方指定的 all_indices / 时间范围等差异
    index = search._index
    base_body = search.to_dict()
    # 使用映射字段 id（Keyword，带 doc_values）而非元字段 _id，与 Elastic 官方推荐一致
    base_body["sort"] = [{"id": "asc"}]
    base_body["size"] = page_size

    pit_resp = es_client.open_point_in_time(index=index, keep_alive="1m", ignore_unavailable=True)
    pit_id = pit_resp["id"]

    try:
        search_after = None
        while True:
            # 每次构造独立 body，避免多次迭代间共享 dict 引发的状态污染
            body = {**base_body, "pit": {"id": pit_id, "keep_alive": "1m"}}
            if search_after:
                body["search_after"] = search_after
            # 使用 PIT 时不传 index，PIT 已携带索引快照信息
            resp = es_client.search(body=body, request_timeout=30)
            # ES 每轮响应可能刷新 pit_id，需同步更新
            if resp.get("pit_id"):
                pit_id = resp["pit_id"]
            hits = resp["hits"]["hits"]
            if not hits:
                break
            yield from hits
            search_after = hits[-1]["sort"]
    finally:
        try:
            es_client.close_point_in_time(body={"id": pit_id})
        except Exception:
            logger.warning("[_search_after_hits] failed to close PIT %s", pit_id)


def check_abnormal_alert():
    """
    拉取异常告警，对这些告警进行状态管理
    """
    search = (
        AlertDocument.search(all_indices=True)
        .filter(Q("term", status=EventStatus.ABNORMAL) & ~Q("term", is_blocked=True))
        .source(fields=["id", "strategy_id", "event.bk_biz_id"])
    )

    # 获取集群内的业务ID
    cluster_bk_biz_ids = set(get_cluster_bk_biz_ids())

    alerts = []
    # 使用 search_after 深分页替代 scan()，避免 ES scroll context 积压
    for hit in _search_after_hits(search, page_size=SCAN_PAGE_SIZE):
        src = hit.get("_source") or {}
        alert_id = src.get("id")
        bk_biz_id = (src.get("event") or {}).get("bk_biz_id")
        if not alert_id or not bk_biz_id:
            continue
        # 只处理集群内的告警
        if bk_biz_id not in cluster_bk_biz_ids:
            continue
        alerts.append({"id": alert_id, "strategy_id": src.get("strategy_id")})

    if alerts:
        send_check_task(alerts)


def check_blocked_alert():
    """
    拉取被流控的异常告警，对这些告警进行状态管理
    """
    current_time = int(time.time())
    end_time = current_time - CONST_ONE_HOUR
    start_time = current_time - CONST_ONE_DAY
    logger.info("[check_blocked_alert] begin %s - %s", start_time, end_time)
    search = (
        AlertDocument.search(start_time=start_time, end_time=end_time)
        .filter(Q("term", status=EventStatus.ABNORMAL) & Q("term", is_blocked=True))
        .source(fields=["id", "strategy_id", "event.bk_biz_id"])
    )

    # 获取集群内的业务ID
    cluster_bk_biz_ids = set(get_cluster_bk_biz_ids())

    alerts = []
    total = 0
    # 使用 search_after 深分页替代 scan()，避免 ES scroll context 积压
    for hit in _search_after_hits(search, page_size=BATCH_SIZE):
        src = hit.get("_source") or {}
        alert_id = src.get("id")
        bk_biz_id = (src.get("event") or {}).get("bk_biz_id")
        if not alert_id or not bk_biz_id:
            continue
        # 只处理集群内的告警
        if bk_biz_id not in cluster_bk_biz_ids:
            continue
        alerts.append({"id": alert_id, "strategy_id": src.get("strategy_id")})
        total += 1
        if total % BATCH_SIZE == 0:
            alert_keys = [AlertKey(alert_id=alert["id"], strategy_id=alert.get("strategy_id")) for alert in alerts]
            check_blocked_alert_finished(alert_keys)
            logger.info("[check_blocked_alert]  blocked alert processed (%s)", len(alert_keys))
            alerts = []

    alert_keys = [AlertKey(alert_id=alert["id"], strategy_id=alert.get("strategy_id")) for alert in alerts]
    check_blocked_alert_finished(alert_keys)
    total += len(alerts)
    logger.info("[check_blocked_alert]  blocked alert total count(%s)", total)


def check_blocked_alert_finished(alert_keys):
    alerts = Alert.mget(alert_keys)
    for alert in alerts:
        alert.move_to_next_status()

    alert_logs = []
    alert_documents = []
    closed_alerts = []
    updated_alert_snaps = []
    for alert in alerts:
        if alert.should_refresh_db():
            alert_logs.extend(alert.list_log_documents())
            alert_documents.append(alert.to_document())
            updated_alert_snaps.append(alert)
        if alert.status == EventStatus.CLOSED:
            closed_alerts.append(alert.id)
    if alert_documents:
        try:
            AlertDocument.bulk_create(alert_documents, action=BulkActionType.UPSERT)
        except BulkIndexError as e:
            logger.error(
                "[check_blocked_alert_finished] save blocked alert document failed, total count(%s), "
                " updated(%s), error detail: %s",
                len(alert_keys),
                len(alert_documents),
                e.errors,
            )
            return
    if updated_alert_snaps:
        AlertCache.save_alert_to_cache(updated_alert_snaps)
        AlertCache.save_alert_snapshot(updated_alert_snaps)

    if alert_logs:
        try:
            AlertLog.bulk_create(alert_logs)
        except BulkIndexError as e:
            logger.error(
                "[check_blocked_alert_finished] save alert log document total count(%s) error: %s",
                len(alert_logs),
                e.errors,
            )
    logger.info(
        "[check_blocked_alert_finished] update blocked alert next status succeed, "
        "total count(%s), updated(%s), closed(%s)",
        len(alerts),
        len(alert_documents),
        len(closed_alerts),
    )


def send_check_task(alerts: list[dict], run_immediately=True):
    """
    生成告警检测任务
    :param alerts: 告警对象列表
    :param run_immediately: 是否立即发送一个检查任务
    """
    if not alerts:
        return

    alert_ids_with_interval = cal_alerts_check_interval(alerts)

    for check_interval, alerts in alert_ids_with_interval.items():
        countdown = 0 if run_immediately else check_interval
        while countdown < DEFAULT_CHECK_INTERVAL:
            # 通过创建延时任务来满足1分钟内进行多次检测，其中：
            # 监控周期<30s，一分钟检测4次
            # 监控周期<60s，一分钟检测2次
            # 其他情况，一分钟检测1次
            for index in range(0, len(alerts), BATCH_SIZE):
                handle_alerts.apply_async(
                    countdown=countdown,
                    expires=120,
                    kwargs={
                        "alert_keys": [
                            AlertKey(alert_id=alert["id"], strategy_id=alert.get("strategy_id"))
                            for alert in alerts[index : index + BATCH_SIZE]
                        ]
                    },
                )
            countdown += check_interval

    logger.info(
        "[check_abnormal_alert] alerts(%s/60s, %s/30s, %s/15s) sent to AlertManager",
        len(alert_ids_with_interval[60]),
        len(alert_ids_with_interval[30]),
        len(alert_ids_with_interval[15]),
    )


@app.task(ignore_result=True, queue="celery_alert_manager")
def handle_alerts(alert_keys: list[AlertKey]):
    """
    处理告警（异步任务）
    """
    exc = None
    if not alert_keys:
        return
    total = len(alert_keys)
    manager = AlertManager(alert_keys)
    start_time = time.time()
    try:
        manager.logger.info("[alert.manager start] with total alerts(%s)", total)
        manager.process()
    except Exception as e:
        manager.logger.exception("[alert.manager ERROR] detail: %s", e)
        exc = e
        cost = time.time() - start_time
    else:
        cost = time.time() - start_time
        manager.logger.info("[alert.manager end] cost: %s", cost)

    # 按单条告警进行统计耗时，因为这有两个入口：
    # 1. 周期维护未恢复的告警， 按 total=200 分批跑
    # 2. 产生新告警时，由alert.builder 立刻执行一次周期任务管理， total 较小。
    # 因此会存在耗时跟随total值的变化抖动。所以这里算单条告警的处理平均耗时才能体现出实际情况
    if exc is not None and is_transient_retry_exc(exc, finalized=getattr(manager, "alerts_finalized", False)):
        # 瞬态基础设施错误且本批可下周期重跑自愈: 计入 deferred 而非 failed，避免把一次节点抖动 / ES 瞬态 /
        # finalize 前的 broker 建连抖动放大成整批失败、压垮处理成功率指标。
        metrics.ALERT_MANAGE_TIME.labels(status=metrics.StatusEnum.DEFERRED, exception=exc).observe(cost / total)
        metrics.ALERT_MANAGE_DEFERRED_COUNT.labels(exception=exc).inc(total)
    else:
        # 成功，或非瞬态(逻辑类)异常: 保留原有 success / failed 计数与可见性。
        status = metrics.StatusEnum.from_exc(exc)
        metrics.ALERT_MANAGE_TIME.labels(status=status, exception=exc).observe(cost / total)
        metrics.ALERT_MANAGE_COUNT.labels(status=status, exception=exc).inc(total)
    metrics.report_all()


def fetch_agg_interval(strategy_ids: list[int]):
    """
    根据策略ID获取每个策略的聚合周期
    """
    agg_interval_by_strategy = {}

    strategies = StrategyCacheManager.get_strategy_by_ids(strategy_ids)

    for strategy in strategies:
        for item in strategy["items"]:
            # 补充周期缓存
            if "query_configs" not in item:
                continue

            for config in item["query_configs"]:
                if "agg_interval" not in config:
                    continue
                if strategy["id"] in agg_interval_by_strategy:
                    # 如果一个策略存在多个agg_interval，则取最小值
                    agg_interval_by_strategy[strategy["id"]] = min(
                        agg_interval_by_strategy[strategy["id"]], config["agg_interval"]
                    )
                else:
                    agg_interval_by_strategy[strategy["id"]] = config["agg_interval"]
    return agg_interval_by_strategy


def cal_alerts_check_interval(alerts: list[dict]):
    """
    计算告警的检查周期
    监控周期<30s，每15s检查一次
    监控周期<60s，每30s检查一次
    其他情况统一每60s检查一次
    """
    check_interval = {
        15: [],
        30: [],
        60: [],
    }

    strategy_ids = set()

    for alert in alerts:
        strategy_id = alert.get("strategy_id")
        if strategy_id:
            strategy_ids.add(strategy_id)

    agg_interval_config = fetch_agg_interval(strategy_ids=list(strategy_ids))

    for alert in alerts:
        strategy_id = alert.get("strategy_id")
        if not strategy_id or strategy_id not in agg_interval_config:
            # 告警没有策略ID，或者策略中没有周期配置，则按默认60秒检查一次
            check_interval[60].append(alert)
            continue

        agg_interval = agg_interval_config[strategy_id]
        if agg_interval < 30:
            check_interval[15].append(alert)
        elif agg_interval < 60:
            check_interval[30].append(alert)
        else:
            check_interval[60].append(alert)
    return check_interval
