"""Both actual product codecs use one V4 space-ID implementation, offline."""

import importlib.util
from pathlib import Path

import pytest

from iam_engine.core.requests import ResourceInstance
from iam_engine.v4.codec import SpaceResourceCodec


def load_product_codec(path):
    spec = importlib.util.spec_from_file_location("space_codec_contract_" + path.parent.name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module", params=["monitor", "bklog"])
def codec(request):
    root = Path(__file__).resolve().parents[2]
    if request.param == "monitor":
        module = load_product_codec(root / "bkmonitor/bkmonitor/iam/backends/v4/codec.py")
        return module.MonitorV4Codec()
    module = load_product_codec(root / "bklog/apps/iam/backends/v4/codec.py")
    return module.BklogNameCodec()


@pytest.mark.parametrize(
    "local,wire",
    [
        ("100605", "100605"),
        ("0", "0"),
        ("-42", "-42"),
        ("-1", "-1"),
        ("0007", "0007"),
        ("-00042", "-00042"),
        ("-0", "-0"),
        ("-9223372036854775808", "-9223372036854775808"),
    ],
)
def test_round_trip_and_idempotence(codec, local, wire):
    assert codec.encode_resource_id("space", local) == wire
    assert codec.decode_resource_id("space", wire) == local
    assert codec.encode_resource_id("space", wire) == wire
    assert codec.decode_resource_id("space", local) == local


def test_products_inherit_the_same_methods_instead_of_copying_rules(codec):
    assert type(codec).encode_resource_id is SpaceResourceCodec.encode_resource_id
    assert type(codec).decode_resource_id is SpaceResourceCodec.decode_resource_id


@pytest.mark.parametrize("local,wire", [(100605, "100605"), (0, "0"), (-42, "-42")])
def test_integer_inputs_keep_bklog_string_normalization(codec, local, wire):
    assert codec.encode_resource_id("space", local) == wire
    assert codec.decode_resource_id("space", wire) == str(local)


@pytest.mark.parametrize("value", ["", "neg_", "neg_bad", "-abc", " -42", "-42\n", "neg_42", "space|-42", "*"])
def test_existing_bklog_passthrough_boundaries_are_preserved(codec, value):
    assert codec.encode_resource_id("space", value) == value
    assert codec.decode_resource_id("space", value) == value


def test_old_prefixes_remain_distinct_identities(codec):
    identities = ["-42", "neg_42", "space|-42", "42", "space|42"]
    assert [codec.encode_resource_id("space", value) for value in identities] == identities
    assert [codec.decode_resource_id("space", value) for value in identities] == identities


@pytest.mark.parametrize(
    "resource_type", ["indices", "collection", "es_source", "apm_application", "rum_application", "grafana_dashboard"]
)
@pytest.mark.parametrize("value", ["42", "-42", "neg_42", "folder:3|182"])
def test_other_resource_types_do_not_use_space_encoding(codec, resource_type, value):
    assert codec.encode_resource_id(resource_type, value) == value
    assert codec.decode_resource_id(resource_type, value) == value


def test_payloads_encode_space_ancestors_without_mutating_business_inputs(codec):
    from copy import deepcopy

    space = ResourceInstance(type="space", id="-42")
    attributes = {"_bk_iam_path_": "/space,-42/", "custom": "kept"}
    resource = ResourceInstance(type="indices", id="17", attributes=attributes, ancestor_chain=(space,))
    before = deepcopy(attributes)
    assert codec.encode_resource_for_auth(resource)["attributes"]["_bk_iam_path_"] == "/space,-42/"
    assert codec.encode_resource_for_apply(resource)["ancestors"] == [{"type": "space", "id": "-42"}]
    assert attributes == before
    assert space.id == "-42"


@pytest.mark.parametrize("empty_body", [True, False])
def test_raw_space_grant_through_shared_http_client(codec, monkeypatch, empty_body):
    from copy import deepcopy
    from types import SimpleNamespace
    from unittest.mock import Mock

    import requests

    from iam_engine.v4.client import V4Client
    from iam_engine.v4.config import V4Options, load_v4_paths

    options = V4Options(
        "offline",
        "offline-only",
        "https://iam.example.test/dev/",
        "test_system",
        10,
        20,
        1,
        **load_v4_paths(SimpleNamespace()),
    )
    client = V4Client(options, bk_tenant_id="tenant-a", codec=codec)
    response = Mock(status_code=201, content=b"" if empty_body else b"json")
    response.json.return_value = {"data": None}
    send = Mock(return_value=response)
    monkeypatch.setattr(requests, "request", send)
    items = [
        {
            "subject": {"type": "user", "id": "alice"},
            "role_id": "space_viewer",
            "related_resource_type_id": "space",
            "resources": [{"type": "space", "id": "-42"}],
            "expired_at": 1790000000,
        }
    ]
    before = deepcopy(items)
    assert client.add_authorization(items=items, operator="operator") is None
    send.assert_called_once()
    assert send.call_args.kwargs["url"] == (
        "https://iam.example.test/dev/api/v1/open/rbac/mgmt/systems/test_system/authorizations/"
    )
    assert send.call_args.kwargs["json"] == before
    assert items == before


def test_raw_space_apply_through_shared_http_client(codec, monkeypatch):
    from copy import deepcopy
    from types import SimpleNamespace
    from unittest.mock import Mock

    import requests

    from iam_engine.v4.client import V4Client
    from iam_engine.v4.config import V4Options, load_v4_paths

    options = V4Options(
        "offline",
        "offline-only",
        "https://iam.example.test/dev/",
        "test_system",
        10,
        20,
        1,
        **load_v4_paths(SimpleNamespace()),
    )
    client = V4Client(options, bk_tenant_id="tenant-a", codec=codec)
    response = Mock(status_code=200, content=b"json")
    response.json.return_value = {"data": {"url": "https://iam.example.test/permission/apply"}}
    send = Mock(return_value=response)
    monkeypatch.setattr(requests, "request", send)
    space = ResourceInstance(type="space", id="-42")
    child = ResourceInstance(type="collection", id="17", ancestor_chain=(space,))
    permissions = [
        {"action_id": "view_business", "resources": [codec.encode_resource_for_apply(space)]},
        {"action_id": "view_child", "resources": [codec.encode_resource_for_apply(child)]},
    ]
    before = deepcopy(permissions)
    assert client.generate_perm_apply_url(permissions=permissions) == "https://iam.example.test/permission/apply"
    send.assert_called_once()
    assert send.call_args.kwargs["url"] == (
        "https://iam.example.test/dev/api/v1/open/application/permission-apply-urls/"
    )
    sent = send.call_args.kwargs["json"]["permissions"]
    assert sent[0]["resources"][0]["id"] == "-42"
    assert sent[1]["resources"][0]["ancestors"] == [{"type": "space", "id": "-42"}]
    assert permissions == before


@pytest.mark.parametrize("identity", ["100605", "-42"])
def test_actual_v3_codecs_keep_numeric_space_ids_and_paths(identity):
    from bkmonitor.iam.backends.v3.codec import MonitorV3Codec
    from bkmonitor.iam.backends.v3.client import V3Client

    root = Path(__file__).resolve().parents[2]
    log_module = load_product_codec(root / "bklog/apps/iam/backends/v3/codec.py")
    resource = ResourceInstance(
        system="bk_monitorv3", type="space", id=identity, attributes={"_bk_iam_path_": f"/space,{identity}/"}
    )
    monitor_codec = MonitorV3Codec()
    client = V3Client("offline", "offline", "https://iam.example.test/", "bk_monitorv3", monitor_codec)
    for sdk_resource in (
        monitor_codec.encode_resource(resource, client),
        log_module.V3RequestCodec("bk_log_search").encode_resource(resource),
    ):
        assert sdk_resource.id == identity
        assert sdk_resource.attribute["_bk_iam_path_"] == f"/space,{identity}/"
