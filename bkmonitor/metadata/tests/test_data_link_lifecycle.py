from unittest.mock import patch

import pytest
from requests.exceptions import ConnectionError, Timeout

from core.errors.api import BKAPIError as BkApiError
from metadata.data_link_lifecycle import apply_after_terminating_resources_deleted

RESOURCE_CONFIG = {
    "kind": "Databus",
    "metadata": {
        "name": "log_data_link",
        "namespace": "bklog",
    },
    "spec": {},
}


def _bkbase_error(*, status_code: int = 500, code: str | None = None, message: str) -> BkApiError:
    return BkApiError(
        system_name="bkdata",
        url="/v4/apply/",
        result={"code": code, "message": message},
        status_code=status_code,
    )


def test_apply_waits_until_terminating_resource_is_deleted_before_retrying():
    apply_results = iter(
        [
            _bkbase_error(
                status_code=409,
                message='{"code":"RESOURCE_TERMINATING","message":"resource is terminating"}',
            ),
            {"result": True},
        ]
    )
    resource_results = iter(
        [
            {"status": {"phase": "Terminating"}},
            None,
        ]
    )
    apply_attempts = 0
    fetched_resources: list[tuple[str, str, str]] = []

    def apply_resource():
        nonlocal apply_attempts
        apply_attempts += 1
        result = next(apply_results)
        if isinstance(result, Exception):
            raise result
        return result

    def get_resource(kind: str, name: str, namespace: str):
        fetched_resources.append((kind, name, namespace))
        return next(resource_results)

    with patch("metadata.data_link_lifecycle.time.sleep"):
        result = apply_after_terminating_resources_deleted(
            configs=[RESOURCE_CONFIG],
            apply_resource=apply_resource,
            get_resource=get_resource,
            timeout_seconds=60,
            poll_interval_seconds=1,
        )

    assert result == {"result": True}
    assert apply_attempts == 2
    assert fetched_resources == [
        ("Databus", "log_data_link", "bklog"),
        ("Databus", "log_data_link", "bklog"),
    ]


def test_apply_times_out_after_twenty_second_terminating_wait_and_suggests_retry():
    error = _bkbase_error(
        status_code=409,
        message='{"code":"RESOURCE_TERMINATING","message":"resource is terminating"}',
    )

    def apply_resource():
        raise error

    def get_resource(*_args):
        return {"status": {"phase": "Terminating"}}

    with (
        patch(
            "metadata.data_link_lifecycle.time.monotonic",
            side_effect=[100, 118, 120, 160],
        ),
        patch("metadata.data_link_lifecycle.time.sleep") as sleep,
    ):
        with pytest.raises(
            TimeoutError,
            match=r"Databus/bklog/log_data_link.*当前状态：Terminating.*20.*稍后重试",
        ):
            apply_after_terminating_resources_deleted(
                configs=[RESOURCE_CONFIG],
                apply_resource=apply_resource,
                get_resource=get_resource,
            )

    sleep.assert_called_once_with(2)


def test_apply_does_not_retry_non_terminating_bkbase_error():
    error = _bkbase_error(status_code=401, code="INVALID_AUTH", message="invalid auth")
    apply_attempts = 0

    def apply_resource():
        nonlocal apply_attempts
        apply_attempts += 1
        raise error

    with pytest.raises(BkApiError) as exc_info:
        apply_after_terminating_resources_deleted(
            configs=[RESOURCE_CONFIG],
            apply_resource=apply_resource,
            get_resource=lambda *_args: None,
            timeout_seconds=60,
            poll_interval_seconds=1,
        )

    assert exc_info.value is error
    assert apply_attempts == 1


def test_apply_retries_gateway_5xx_error():
    error = _bkbase_error(status_code=503, message="service unavailable")
    apply_attempts = 0

    def apply_resource():
        nonlocal apply_attempts
        apply_attempts += 1
        if apply_attempts == 1:
            raise error
        return {"result": True}

    with patch("metadata.data_link_lifecycle.time.sleep"):
        result = apply_after_terminating_resources_deleted(
            configs=[RESOURCE_CONFIG],
            apply_resource=apply_resource,
            get_resource=lambda *_args: None,
        )

    assert result == {"result": True}
    assert apply_attempts == 2


@pytest.mark.parametrize("error", [ConnectionError("connection reset"), Timeout("request timed out")])
def test_apply_retries_network_transient_error(error: Exception):
    apply_attempts = 0

    def apply_resource():
        nonlocal apply_attempts
        apply_attempts += 1
        if apply_attempts == 1:
            raise error
        return {"result": True}

    with patch("metadata.data_link_lifecycle.time.sleep"):
        result = apply_after_terminating_resources_deleted(
            configs=[RESOURCE_CONFIG],
            apply_resource=apply_resource,
            get_resource=lambda *_args: None,
        )

    assert result == {"result": True}
    assert apply_attempts == 2


def test_apply_stops_after_four_transient_attempts():
    error = _bkbase_error(status_code=503, message="service unavailable")
    apply_attempts = 0

    def apply_resource():
        nonlocal apply_attempts
        apply_attempts += 1
        raise error

    with patch("metadata.data_link_lifecycle.time.sleep"):
        with pytest.raises(BkApiError) as exc_info:
            apply_after_terminating_resources_deleted(
                configs=[RESOURCE_CONFIG],
                apply_resource=apply_resource,
                get_resource=lambda *_args: None,
            )

    assert exc_info.value is error
    assert apply_attempts == 4


def test_apply_does_not_retry_bkbase_application_error_with_error_code():
    error = _bkbase_error(status_code=500, code="INVALID_ARGS", message="invalid config")
    apply_attempts = 0

    def apply_resource():
        nonlocal apply_attempts
        apply_attempts += 1
        raise error

    with pytest.raises(BkApiError) as exc_info:
        apply_after_terminating_resources_deleted(
            configs=[RESOURCE_CONFIG],
            apply_resource=apply_resource,
            get_resource=lambda *_args: None,
        )

    assert exc_info.value is error
    assert apply_attempts == 1
