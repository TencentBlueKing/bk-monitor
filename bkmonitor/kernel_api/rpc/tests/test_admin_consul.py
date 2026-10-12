"""Metadata Consul Admin RPC tests."""

import base64
from unittest.mock import Mock

import pytest

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc.functions.admin import consul as admin_consul
from kernel_api.rpc.registry import KernelRPCRegistry
from metadata import config


def _patch_consul(mocker, *, keys=None, index=1, entry=None):
    client = Mock()
    client.list_keys.return_value = (index, keys)
    client.get.return_value = (index, entry)
    mocker.patch.object(admin_consul.consul_tools, "HashConsul", return_value=client)
    return client


def test_consul_functions_registered():
    for func_name in [admin_consul.FUNC_CONSUL_KEY_LIST, admin_consul.FUNC_CONSUL_VALUE_GET]:
        detail = KernelRPCRegistry.get_function_detail(func_name)
        assert detail is not None
        assert detail["func_name"] == func_name
        assert detail["params_schema"]
        assert detail["example_params"]


@pytest.mark.parametrize("path", ["/absolute", "v1//data_id", "v1/./data_id", "v1/../service", "v1/"])
def test_consul_relative_path_rejects_unsafe_segments(path):
    with pytest.raises(CustomException):
        admin_consul._normalize_relative_path(path, "path", allow_empty=False)


def test_consul_key_list_only_reads_keys_and_paginates(mocker):
    root = config.CONSUL_PATH
    client = _patch_consul(
        mocker,
        keys=[
            f"{root}/v1/default/data_id/1003",
            f"{root}/v1/default/data_id/1001",
            f"{root}/v1/default/data_id/1002",
            "other-app/metadata/v1/default/data_id/9999",
        ],
    )

    result = admin_consul.list_consul_keys(
        {"bk_tenant_id": "system", "prefix": "v1/default/data_id", "page": 2, "page_size": 2}
    )

    client.list_keys.assert_called_once_with(f"{root}/v1/default/data_id")
    assert result["data"] == {
        "root_path": root,
        "prefix": "v1/default/data_id",
        "items": [{"relative_path": "v1/default/data_id/1003"}],
        "page": 2,
        "page_size": 2,
        "total": 3,
    }
    assert result["warnings"][0]["code"] == "CONSUL_OUT_OF_SCOPE_KEYS_IGNORED"


def test_consul_value_get_serializes_json_and_indexes(mocker):
    root = config.CONSUL_PATH
    client = _patch_consul(
        mocker,
        index=99,
        entry={
            "CreateIndex": 10,
            "ModifyIndex": 20,
            "LockIndex": 0,
            "Flags": 7,
            "Session": None,
            "Value": b'{"password":"secret","enabled":true}',
        },
    )

    result = admin_consul.get_consul_value(
        {"bk_tenant_id": "system", "path": "v1/default/data_id/1001", "include_sensitive": False}
    )

    client.get.assert_called_once_with(f"{root}/v1/default/data_id/1001")
    assert result["data"] == {
        "root_path": root,
        "relative_path": "v1/default/data_id/1001",
        "exists": True,
        "consul_index": 99,
        "create_index": 10,
        "modify_index": 20,
        "lock_index": 0,
        "flags": 7,
        "session": None,
        "value_size_bytes": 36,
        "value_format": "json",
        "value": {"password": "[REDACTED]", "enabled": True},
        "content_omitted": False,
        "content_omitted_reason": None,
    }


def test_consul_value_get_serializes_text_and_missing_value(mocker):
    _patch_consul(mocker, entry={"Value": "plain-text"})
    result = admin_consul.get_consul_value({"path": "version"})
    assert result["data"]["value_format"] == "text"
    assert result["data"]["value"] == "plain-text"

    _patch_consul(mocker, index=42, entry=None)
    missing = admin_consul.get_consul_value({"path": "missing"})
    assert missing["data"]["exists"] is False
    assert missing["data"]["consul_index"] == 42


def test_consul_value_get_only_returns_json_secrets_in_sensitive_mode(mocker):
    _patch_consul(mocker, entry={"Value": b'{"password":"secret","nested":{"api_key":"raw-key"}}'})

    masked = admin_consul.get_consul_value({"path": "config", "include_sensitive": False})
    assert masked["data"]["value"] == {
        "password": "[REDACTED]",
        "nested": {"api_key": "[REDACTED]"},
    }

    revealed = admin_consul.get_consul_value({"path": "config", "include_sensitive": True})
    assert revealed["data"]["value"] == {"password": "secret", "nested": {"api_key": "raw-key"}}


def test_consul_binary_value_requires_sensitive_mode(mocker):
    binary_value = b"\xff\x00\x01"
    _patch_consul(mocker, entry={"Value": binary_value})

    masked = admin_consul.get_consul_value({"path": "binary", "include_sensitive": False})
    assert masked["data"]["value"] is None
    assert masked["data"]["value_format"] == "binary"
    assert masked["data"]["content_omitted_reason"] == "binary_redacted"

    revealed = admin_consul.get_consul_value({"path": "binary", "include_sensitive": True})
    assert revealed["data"]["value"] == base64.b64encode(binary_value).decode("ascii")
    assert revealed["data"]["content_omitted"] is False


def test_consul_oversized_value_is_omitted(mocker):
    _patch_consul(mocker, entry={"Value": b"a" * (admin_consul.MAX_VALUE_SIZE_BYTES + 1)})
    result = admin_consul.get_consul_value({"path": "oversized", "include_sensitive": True})
    assert result["data"]["value"] is None
    assert result["data"]["content_omitted_reason"] == "too_large"
    assert result["warnings"][0]["code"] == "CONSUL_VALUE_TOO_LARGE"
