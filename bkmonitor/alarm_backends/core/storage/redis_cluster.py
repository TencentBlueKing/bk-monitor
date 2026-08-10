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
import threading
from contextlib import contextmanager
from time import monotonic

from django.conf import settings
from redis.exceptions import RedisError

from alarm_backends.core.cluster import get_cluster
from alarm_backends.core.storage.redis import CACHE_BACKEND_CONF_MAP, Cache, gen_resilient_socket_conf
from bkmonitor.models import CacheNode, CacheRouter

logger = logging.getLogger("alarm_backends")


class PipelineResultMismatch(RedisError):
    """pipeline 各节点返回的响应数与入队命令数不一致。

    通常由连接异常或节点切换后代理残留的脏命令栈引起。继承 RedisError，
    使既有 ``except RedisError`` 的调用方也能捕获并按可重试错误处理。
    """


class RedisNode:
    redis_type = "RedisCache"

    def __init__(self, host, port, password=None):
        self.host = host
        self.port = port
        self.password = password
        self._connection_kwargs = {"db": 0, "host": self.host, "port": self.port, "password": password}
        self._connection_kwargs.update({"decode_responses": True, "encoding": "utf-8"})
        self._instance_pool = {}

    @property
    def connection_kwargs(self):
        return self._connection_kwargs

    @property
    def node_id(self):
        return f"{self.redis_type}-{self.host}:{self.port}"

    def gen_connection_conf(self, cache_backend):
        conf = self.connection_kwargs.copy()
        backend_conf = CACHE_BACKEND_CONF_MAP.get(cache_backend, {})
        conf["db"] = backend_conf.get("db", 0)
        # 注入连接韧性参数: 分片节点历史上无任何 socket 超时, 主切换时读操作无限挂起。
        # socket_timeout 沿用后端配置(若有), 由 floor 守住"必须大于阻塞命令 server 超时"的红线。
        conf.update(gen_resilient_socket_conf(backend_conf.get("socket_timeout")))
        return conf

    def instance(self, cache_backend):
        backend = f"{self.node_id}:{cache_backend}"
        conf = self.gen_connection_conf(cache_backend)
        conf["_cache_type"] = self.redis_type
        return Cache(backend, conf)


class SentinelRedisNode(RedisNode):
    redis_type = "SentinelRedisCache"

    def __init__(self, host, port, master_name, password=None, sentinel_password=None):
        super().__init__(host, port, password)
        self.master_name = master_name
        self._connection_kwargs.update({"master_name": master_name})
        self.sentinel_kwargs = {}
        self.sentinel_password = sentinel_password

    @property
    def node_id(self):
        return f"{self.redis_type}-{self.host}:{self.port} {self.master_name}"

    def gen_connection_conf(self, cache_backend):
        conf = super().gen_connection_conf(cache_backend)
        if self.sentinel_password:
            conf["sentinel_password"] = self.sentinel_password
        return conf


def setup_client(node, backend):
    client = None
    if node.cache_type == RedisNode.redis_type:
        client = setup_redis_client(node, backend)
    if node.cache_type == SentinelRedisNode.redis_type:
        client = setup_sentinel_client(node, backend)
    if client is None:
        raise Exception(f"nonsupport cache type: {node.cache_type}")
    return client


def setup_redis_client(node, backend):
    redis_node = RedisNode(node.host, node.port, node.password)
    return redis_node.instance(backend)


def setup_sentinel_client(node, backend):
    master_name = node.connection_kwargs["master_name"]
    sentinel_password = node.connection_kwargs.get("sentinel_password")
    sentinel_node = SentinelRedisNode(
        node.host, node.port, master_name, password=node.password, sentinel_password=sentinel_password
    )
    return sentinel_node.instance(backend)


class KeyRouterMixin:
    def strategy_id_from_command(self, *args, **kwargs):
        key = self.key_from_command(*args, **kwargs)
        return self.strategy_id_from_key(key)

    def strategy_id_from_key(self, key):
        return getattr(key, "strategy_id", 0) if key else 0

    def key_from_command(self, *args, **kwargs):
        key = kwargs.get("name", None)
        if key is None and args:
            key = args[0]
        return key


class RedisProxy(KeyRouterMixin):
    def __init__(self, backend):
        self.backend = backend
        self._pipeline = None
        self._client_pool = {}

    def pipeline(self, *args, **kwargs):
        """每次调用视为一个新的逻辑批次入口。

        RedisDataKey 长期缓存本 Proxy，本方法又复用同一 PipelineProxy；
        若上一任务入队后未 execute 就异常退出，必须在此清掉残留的
        command_stack / 路由快照 / 原生 pipeline 缓冲，否则下一任务会重放旧命令
        并可能无限期写旧节点。
        """
        if self._pipeline is None:
            self._pipeline = PipelineProxy(self, *args, **kwargs)
        else:
            self._pipeline.begin_batch(*args, **kwargs)
        return self._pipeline

    def get_client(self, node):
        if node.id not in self._client_pool:
            self._client_pool[node.id] = setup_client(node, self.backend)

        return self._client_pool[node.id]

    def __getattr__(self, name):
        def handle(*args, **kwargs):
            exception = None
            strategy_id = self.strategy_id_from_command(*args, **kwargs)
            cache_node = get_node_by_strategy_id(strategy_id)
            client = self.get_client(cache_node)
            command = getattr(client, name)

            for _ in range(3):
                try:
                    return command(*args, **kwargs)
                except ConnectionError as err:
                    exception = err
                    client.refresh_instance()
            if exception:
                raise exception

        return handle


class PipelineProxy(KeyRouterMixin):
    ALLOWED_METHOD = ["execute"]

    def __init__(self, node_proxy, *args, **kwargs):
        self.node_proxy = node_proxy
        self._pipeline_pool = {}
        self.init_params = (args, kwargs)
        self.command_stack = []
        # 实例级快照：绑定本次 pipeline 批次，避免 thread-local pin 在入队失败/未 execute 时泄漏
        self._routing_snapshot = None

    def begin_batch(self, *args, **kwargs):
        """开启新逻辑批次：丢弃上一批遗留状态（含原生 redis pipeline 已缓冲命令）。"""
        self.init_params = (args, kwargs)
        self.command_stack = []
        self._routing_snapshot = None
        for pipeline_instance in self._pipeline_pool.values():
            try:
                pipeline_instance.reset()
            except Exception:
                pass
        # 清空池，避免 reset 语义不全时旧缓冲命令被带进下一批
        self._pipeline_pool = {}

    def pipeline_instance(self, node):
        if node.id not in self._pipeline_pool:
            self._pipeline_pool[node.id] = self.node_proxy.get_client(node).pipeline(
                *self.init_params[0], **self.init_params[1]
            )

        return self._pipeline_pool[node.id]

    def _clear_routing_snapshot(self):
        self._routing_snapshot = None

    def _ensure_routing_snapshot(self):
        """为当前 pipeline 批次钉死路由表（实例级，不污染线程全局 get_node）。

        - 若外层已有 routing_snapshot()，复用其 routers 列表，保证嵌套一致。
        - command_stack 为空时丢弃遗留 snapshot（上一批失败且未入队成功）。
        """
        if not self.command_stack and self._routing_snapshot is not None:
            self._routing_snapshot = None

        if self._routing_snapshot is not None:
            return

        outer = _get_routing_pin()
        if outer is not None:
            self._routing_snapshot = {"routers": outer["routers"], "node_map": {}}
            return

        _refresh_strategy_router_cache()
        self._routing_snapshot = {"routers": STRATEGY_ROUTER_CACHE, "node_map": {}}

    def execute(self):
        p_result = {}
        result = []
        try:
            for node_id, pipeline_instance in self._pipeline_pool.items():
                p_result[node_id] = list(reversed(getattr(pipeline_instance, "execute")()))
            # 每个节点返回的响应数必须与入队到该节点的命令数一致，否则按 command_stack
            # 顺序回填会与命令错位（历史上会导致下游按下标取值越界 IndexError）
            for node_id, responses in p_result.items():
                expected = self.command_stack.count(node_id)
                if len(responses) != expected:
                    raise PipelineResultMismatch(
                        f"pipeline result mismatch on node({node_id}): got {len(responses)}, expected {expected}"
                    )
            for cmd in self.command_stack:
                resp = p_result[cmd].pop() if p_result[cmd] else None
                result.append(resp)
            return result
        finally:
            # 无论成功或异常，都清空命令栈并重置各节点 pipeline 缓冲。
            # RedisProxy 缓存了本 PipelineProxy 单例并跨调用复用，若异常时不清理，
            # 残留命令会污染下一次复用，使结果与请求错位。
            self.command_stack = []
            for pipeline_instance in self._pipeline_pool.values():
                try:
                    pipeline_instance.reset()
                except Exception:
                    pass
            self._pipeline_pool = {}
            self._clear_routing_snapshot()

    def __getattr__(self, name):
        def handle(*args, **kwargs):
            key = self.key_from_command(*args, **kwargs)
            if key is None:
                if name not in self.ALLOWED_METHOD:
                    return self.execute()
            try:
                self._ensure_routing_snapshot()
                strategy_id = self.strategy_id_from_key(key)
                # 直接走实例快照，不经 get_node_by_strategy_id，避免依赖/泄漏 thread-local pin
                cache_node = _resolve_node(
                    strategy_id,
                    self._routing_snapshot["routers"],
                    self._routing_snapshot["node_map"],
                )
                pipeline = self.pipeline_instance(cache_node)
                command = getattr(pipeline, name)
                self.command_stack.append(cache_node.id)
                return command(*args, **kwargs)
            except Exception:
                # 本批次尚未成功入队任何命令：释放实例快照，避免粘住后续单命令路由
                if not self.command_stack:
                    self._clear_routing_snapshot()
                raise

        return handle


STRATEGY_ROUTER_CACHE = None
STRATEGY_ROUTER_CACHE_AT = 0.0
STRATEGY_ROUTER_CACHE_NEXT_RETRY_AT = 0.0
STRATEGY_NODE_MAP = {}
DEFAULT_NODE = None

# CacheRouter 进程内快照 TTL（秒）。改 DB 路由后最多等该窗口即可生效，无需重启 worker。
# 可用 settings.STRATEGY_ROUTER_CACHE_TTL 覆盖；热路径仅做 monotonic 比较，到期才查库。
STRATEGY_ROUTER_CACHE_TTL = 30
# 刷新失败后的最小重试间隔，避免 DB 抖动时逐命令打库放大。
STRATEGY_ROUTER_CACHE_RETRY_BACKOFF = 5


class _RoutingPinState(threading.local):
    """线程局部：仅供 routing_snapshot() 钉住路由；PipelineProxy 使用实例级 snapshot，避免泄漏。"""

    def __init__(self):
        super().__init__()
        self.stack = []


_routing_pin_state = _RoutingPinState()


def _get_routing_pin():
    stack = getattr(_routing_pin_state, "stack", None)
    if not stack:
        return None
    return stack[-1]


def _push_routing_pin(pin: dict) -> None:
    if not hasattr(_routing_pin_state, "stack"):
        _routing_pin_state.stack = []
    _routing_pin_state.stack.append(pin)


def _pop_routing_pin() -> None:
    stack = getattr(_routing_pin_state, "stack", None)
    if stack:
        stack.pop()


def _reset_routing_pin_for_tests() -> None:
    _routing_pin_state.stack = []


@contextmanager
def routing_snapshot():
    """在非 pipeline 的多命令逻辑操作中钉死路由（如 trigger lrange + ltrim）。

    进入时刷新（或 stale-while-error 保旧），块内 get_node_by_strategy_id 只读 pin，
    不受全局 TTL 边界影响。可嵌套；与 PipelineProxy 自动 pin 兼容（已有外层则复用）。
    """
    outer = _get_routing_pin() is not None
    if not outer:
        _refresh_strategy_router_cache()
        _push_routing_pin({"routers": STRATEGY_ROUTER_CACHE, "node_map": {}})
    try:
        yield
    finally:
        if not outer:
            _pop_routing_pin()


def _router_cache_ttl() -> float:
    return float(getattr(settings, "STRATEGY_ROUTER_CACHE_TTL", STRATEGY_ROUTER_CACHE_TTL))


def _router_cache_retry_backoff() -> float:
    return float(
        getattr(settings, "STRATEGY_ROUTER_CACHE_RETRY_BACKOFF", STRATEGY_ROUTER_CACHE_RETRY_BACKOFF)
    )


def _lookup_node_in_routers(strategy_id: int, routers):
    if not routers:
        return None
    for router in routers:
        if router.strategy_score > strategy_id:
            return router.node
    return None


def _rebase_node_map(new_routers) -> None:
    """按新路由表重算已缓存 sid→node；未变化的 sid 保留同一 node 对象引用可减少抖动。"""
    global STRATEGY_NODE_MAP
    if not STRATEGY_NODE_MAP:
        return
    rebased = {}
    for sid, old_node in STRATEGY_NODE_MAP.items():
        if sid == 0:
            continue
        new_node = _lookup_node_in_routers(sid, new_routers)
        if new_node is None:
            continue
        rebased[sid] = new_node if new_node.id != getattr(old_node, "id", None) else old_node
    STRATEGY_NODE_MAP = rebased


def _report_router_refresh_fail() -> None:
    try:
        from core.prometheus import metrics

        metrics.STRATEGY_ROUTER_CACHE_REFRESH_FAIL.labels(cluster=get_cluster().name).inc()
    except Exception:
        # 指标上报失败不影响主路径
        pass


def _refresh_strategy_router_cache(force: bool = False) -> None:
    """按 TTL 重载 CacheRouter 快照；失败时 stale-while-error，并限制重试频率。"""
    global STRATEGY_ROUTER_CACHE, STRATEGY_ROUTER_CACHE_AT, STRATEGY_ROUTER_CACHE_NEXT_RETRY_AT

    now = monotonic()
    ttl = _router_cache_ttl()

    # 测试或运维可直接注入 STRATEGY_ROUTER_CACHE；AT<=0 表示尚未打戳，采纳后进入正常 TTL
    if not force and STRATEGY_ROUTER_CACHE is not None and STRATEGY_ROUTER_CACHE_AT <= 0:
        STRATEGY_ROUTER_CACHE_AT = now
        return

    if not force and STRATEGY_ROUTER_CACHE is not None and (now - STRATEGY_ROUTER_CACHE_AT) <= ttl:
        return

    # TTL 已过但处于失败退避窗口：继续用旧快照，避免逐命令打库
    if (
        not force
        and STRATEGY_ROUTER_CACHE is not None
        and now < STRATEGY_ROUTER_CACHE_NEXT_RETRY_AT
    ):
        return

    try:
        new_routers = list(
            CacheRouter.objects.filter(cluster_name=get_cluster().name)
            .select_related("node")
            .order_by("strategy_score")
        )
    except Exception:
        if STRATEGY_ROUTER_CACHE is not None:
            STRATEGY_ROUTER_CACHE_NEXT_RETRY_AT = now + _router_cache_retry_backoff()
            logger.warning(
                "strategy router cache refresh failed, keep stale snapshot until %.3f",
                STRATEGY_ROUTER_CACHE_NEXT_RETRY_AT,
                exc_info=True,
            )
            _report_router_refresh_fail()
            return
        raise

    STRATEGY_ROUTER_CACHE = new_routers
    STRATEGY_ROUTER_CACHE_AT = now
    STRATEGY_ROUTER_CACHE_NEXT_RETRY_AT = 0.0
    _rebase_node_map(new_routers)


def _resolve_node(strategy_id: int, routers, node_map: dict):
    from django.utils.translation import gettext as _

    global DEFAULT_NODE

    if strategy_id in node_map:
        return node_map[strategy_id]

    if strategy_id == 0:
        if not DEFAULT_NODE:
            DEFAULT_NODE = CacheNode.default_node()
        node_map[strategy_id] = DEFAULT_NODE
        return DEFAULT_NODE

    node = _lookup_node_in_routers(strategy_id, routers)
    if node is None:
        raise Exception(_("策略ID超过设置的默认上限"))
    node_map[strategy_id] = node
    return node


def get_node_by_strategy_id(strategy_id: int):
    pin = _get_routing_pin()
    if pin is not None:
        return _resolve_node(strategy_id, pin["routers"], pin["node_map"])

    _refresh_strategy_router_cache()
    return _resolve_node(strategy_id, STRATEGY_ROUTER_CACHE, STRATEGY_NODE_MAP)
