import time
from collections.abc import Sequence

from prometheus_client import Counter, Histogram
from prometheus_client.utils import INF

from apps.iam.iam_engine.core.types import AuthStatus, BatchAuthResultItem
from apps.utils.prometheus import register_metric

# 埋点入口标识，同一次调用在决策级、Provider 级和分歧指标上必须使用同一个值才能对齐。
AUTH_API_IS_ALLOWED = "is_allowed"
AUTH_API_BATCH_IS_ALLOWED = "batch_is_allowed"
AUTH_API_SPACE_SCOPE = "space_scope"

# Action 无关联资源时的 resource_type 占位，单点与批量路径必须取同一个值。
RESOURCE_TYPE_NONE = "none"

IAM_AUTH_DECISION_COUNT = register_metric(
    Counter,
    name="iam_auth_decision_count",
    documentation="auth decision count of IAM dual-stack, before demo business exemption",
    labelnames=("mode", "action_id", "resource_type", "api", "allowed", "hit_provider", "degraded"),
)

IAM_PROVIDER_RESULT_COUNT = register_metric(
    Counter,
    name="iam_provider_result_count",
    documentation="per-provider auth result count of IAM dual-stack",
    labelnames=("mode", "provider", "action_id", "api", "status", "error_type"),
)

IAM_UNION_DIVERGENCE_COUNT = register_metric(
    Counter,
    name="iam_union_divergence_count",
    documentation="divergence and single-side degradation count of IAM union mode",
    labelnames=("action_id", "api", "pattern"),
)

IAM_PROVIDER_LATENCY = register_metric(
    Histogram,
    name="iam_provider_latency",
    documentation="call latency of a single IAM provider",
    labelnames=("provider", "api", "status"),
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, INF),
)

IAM_GRANT_SYNC_COUNT = register_metric(
    Counter,
    name="iam_grant_sync_count",
    documentation="synchronous dual-write result count of IAM creator authorization",
    labelnames=("target_version", "resource_type", "result"),
)


def observe_provider_latency(provider: str, api: str, start_at: float, *, ok: bool) -> None:
    """记录单侧 IAM Provider 的一次调用耗时。

    Provider 把依赖故障转换成 error 结果而不是向上抛异常，所以成功与否只能由调用方按返回结果给出。
    这里只区分 ok 与 error，具体异常类型由 IAM_PROVIDER_RESULT_COUNT 的 error_type 承载。
    """
    IAM_PROVIDER_LATENCY.labels(provider=provider, api=api, status="ok" if ok else "error").observe(
        time.time() - start_at
    )


def observe_batch_latency(provider: str, start_at: float, items: Sequence[BatchAuthResultItem]) -> None:
    """记录一次批量鉴权的耗时。

    ok 的判定只放在这里：任一条目失败即算 error。V3 的逐条失败（IncompleteBatchResult）发生在拿到 HTTP
    响应之后，如果各自判定，两侧的 status=error 分母就不是同一个含义，迁移期做 V3/V4 错误率对比会失真。
    """
    observe_provider_latency(
        provider,
        AUTH_API_BATCH_IS_ALLOWED,
        start_at,
        ok=all(item.result.status is not AuthStatus.ERROR for item in items),
    )
