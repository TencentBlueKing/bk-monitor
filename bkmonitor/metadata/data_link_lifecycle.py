import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar

from requests.exceptions import ConnectionError, Timeout

from core.errors.api import BKAPIError as BkApiError

logger = logging.getLogger("metadata")

BKBASE_RESOURCE_TERMINATING_CODE = "RESOURCE_TERMINATING"
BKBASE_TERMINATING_PHASE = "Terminating"
BKBASE_TERMINATING_WAIT_TIMEOUT_SECONDS = 20
BKBASE_TERMINATING_POLL_INTERVAL_SECONDS = 2
BKBASE_MAX_APPLY_ATTEMPTS = 4
BKBASE_APPLY_RETRY_INITIAL_INTERVAL_SECONDS = 1
BKBASE_APPLY_RETRY_MAX_INTERVAL_SECONDS = 10
BKBASE_RETRYABLE_HTTP_STATUS_CODES = {408, 429}

T = TypeVar("T")


def is_resource_terminating_error(error: BkApiError) -> bool:
    """判断 BKBase apply 是否因同名资源正在删除而被拒绝。"""
    return (
        error.third_api_error_code == BKBASE_RESOURCE_TERMINATING_CODE
        or BKBASE_RESOURCE_TERMINATING_CODE.lower() in error.message.lower()
    )


def is_transient_bkbase_apply_error(error: Exception) -> bool:
    """判断 BKBase apply 失败是否适合短暂重试。"""
    if isinstance(error, ConnectionError | Timeout):
        return True

    if not isinstance(error, BkApiError):
        return False

    # BkApiClient 会将 HTTP 200 的业务失败包装为 BkApiError，且该异常的
    # status_code 默认值为 500。只要 BKBase 已返回业务错误码，就不能按 5xx
    # 处理，避免对参数、鉴权等确定性失败进行无意义重试。
    if error.third_api_error_code:
        return False

    return error.status_code in BKBASE_RETRYABLE_HTTP_STATUS_CODES or 500 <= error.status_code <= 599


def _transient_retry_wait_seconds(failed_attempt: int) -> int:
    return min(
        BKBASE_APPLY_RETRY_INITIAL_INTERVAL_SECONDS * (2 ** (failed_attempt - 1)),
        BKBASE_APPLY_RETRY_MAX_INTERVAL_SECONDS,
    )


def _terminating_resources(
    configs: list[dict[str, Any]],
    get_resource: Callable[[str, str, str], dict[str, Any] | None],
) -> list[str]:
    terminating: list[str] = []
    for config in configs:
        metadata = config["metadata"]
        kind = config["kind"]
        name = metadata["name"]
        namespace = metadata["namespace"]
        resource = get_resource(kind, name, namespace)
        if not isinstance(resource, dict):
            continue
        status = resource.get("status")
        phase = status.get("phase") if isinstance(status, dict) else None
        if phase == BKBASE_TERMINATING_PHASE:
            terminating.append(f"{kind}/{namespace}/{name}（当前状态：{phase}）")
    return terminating


def _wait_until_terminating_resources_deleted(
    *,
    configs: list[dict[str, Any]],
    get_resource: Callable[[str, str, str], dict[str, Any] | None],
    deadline: float,
    timeout_seconds: float,
    poll_interval_seconds: float,
) -> None:
    while True:
        terminating = _terminating_resources(configs, get_resource)
        if not terminating:
            return

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(
                f"BKBase 资源在等待期间仍未删除：{', '.join(terminating)}。"
                f"已等待 {timeout_seconds:g} 秒，请稍后重试本次操作。"
            )

        logger.info("waiting for terminating BKBase resources to be deleted: %s", ", ".join(terminating))
        time.sleep(min(poll_interval_seconds, remaining))


def apply_after_terminating_resources_deleted(
    *,
    configs: list[dict[str, Any]],
    apply_resource: Callable[[], T],
    get_resource: Callable[[str, str, str], dict[str, Any] | None],
    timeout_seconds: float = BKBASE_TERMINATING_WAIT_TIMEOUT_SECONDS,
    poll_interval_seconds: float = BKBASE_TERMINATING_POLL_INTERVAL_SECONDS,
) -> T:
    """按 BKBase 错误类型处理 apply：Terminating 条件等待，瞬时错误指数退避。"""
    transient_failed_attempts = 0
    terminating_deadline: float | None = None
    while True:
        try:
            return apply_resource()
        except BkApiError as error:
            if is_resource_terminating_error(error):
                if terminating_deadline is None:
                    terminating_deadline = time.monotonic() + timeout_seconds
                _wait_until_terminating_resources_deleted(
                    configs=configs,
                    get_resource=get_resource,
                    deadline=terminating_deadline,
                    timeout_seconds=timeout_seconds,
                    poll_interval_seconds=poll_interval_seconds,
                )
                continue
            if not is_transient_bkbase_apply_error(error):
                raise
            failed_error = error
        except Exception as error:
            if not is_transient_bkbase_apply_error(error):
                raise
            failed_error = error

        transient_failed_attempts += 1
        if transient_failed_attempts >= BKBASE_MAX_APPLY_ATTEMPTS:
            raise failed_error

        wait_seconds = _transient_retry_wait_seconds(transient_failed_attempts)
        logger.warning(
            "retrying BKBase apply after transient error: next_attempt=%s/%s, wait_seconds=%s, error=%s",
            transient_failed_attempts + 1,
            BKBASE_MAX_APPLY_ATTEMPTS,
            wait_seconds,
            failed_error,
        )
        time.sleep(wait_seconds)
