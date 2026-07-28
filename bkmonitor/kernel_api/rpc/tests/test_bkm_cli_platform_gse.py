"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT

GSE platform-source catalog tests.
"""

from __future__ import annotations

import json

import pytest
from django.conf import settings

from core.drf_resource import api
from metadata import config

from kernel_api.rpc.functions.bkm_cli.platform_catalog import gse
from kernel_api.rpc.functions.bkm_cli.platform_catalog._catalog import ParamsGuardRejected, PlatformSourceCatalog


@pytest.fixture(autouse=True)
def isolated_catalog():
    snapshot = dict(PlatformSourceCatalog._domains)
    PlatformSourceCatalog.reset()
    gse.register()
    yield
    PlatformSourceCatalog._domains = snapshot
    PlatformSourceCatalog._revision = None


def test_gse_domain_registers_only_two_readonly_query_operations():
    domain = PlatformSourceCatalog.get_domain("gse")

    assert domain is not None
    assert domain.audit_tags == ["readonly", "gse"]
    assert set(domain.operations) == {"query_route", "query_stream_to"}
    assert domain.operations["query_route"].handler is api.gse.query_route
    assert domain.operations["query_stream_to"].handler is api.gse.query_stream_to


def test_gse_operations_expose_only_one_required_positive_integer():
    domain = PlatformSourceCatalog.get_domain("gse")
    assert domain is not None

    for operation_id, param_name in (("query_route", "channel_id"), ("query_stream_to", "stream_to_id")):
        operation = domain.operations[operation_id]
        assert operation.required_params == [param_name]
        assert operation.example_params == {param_name: 101}
        assert operation.params_schema_override == {
            "type": "object",
            "properties": {
                param_name: {
                    "oneOf": [
                        {"type": "integer", "minimum": 1},
                        {"type": "string", "pattern": "^[0-9]+$"},
                    ],
                    "description": f"{param_name}，正整数或十进制数字字符串",
                }
            },
            "required": [param_name],
            "additionalProperties": False,
        }


@pytest.mark.parametrize(
    ("guard_name", "param_name"),
    [
        ("guard_query_route", "channel_id"),
        ("guard_query_stream_to", "stream_to_id"),
    ],
)
@pytest.mark.parametrize(("value", "normalized"), [(101, 101), ("101", 101), ("00101", 101)])
def test_gse_guards_build_fixed_nested_provider_payload(guard_name, param_name, value, normalized):
    guard = getattr(gse, guard_name)

    assert guard({param_name: value}) == {
        "condition": {
            param_name: normalized,
            "plat_name": config.DEFAULT_GSE_API_PLAT_NAME,
        },
        "operation": {"operator_name": settings.COMMON_USERNAME},
    }


@pytest.mark.parametrize(
    ("guard_name", "param_name"),
    [
        ("guard_query_route", "channel_id"),
        ("guard_query_stream_to", "stream_to_id"),
    ],
)
@pytest.mark.parametrize("value", [None, "", " 101 ", "1.0", "abc", 0, -1, True, False, 1.0, [], {}])
def test_gse_guards_reject_missing_or_non_positive_integer(guard_name, param_name, value):
    guard = getattr(gse, guard_name)

    with pytest.raises(ParamsGuardRejected, match=param_name):
        guard({param_name: value})


@pytest.mark.parametrize(
    ("guard_name", "param_name"),
    [
        ("guard_query_route", "channel_id"),
        ("guard_query_stream_to", "stream_to_id"),
    ],
)
@pytest.mark.parametrize(
    "extra_key",
    [
        "_user_request",
        "condition",
        "operation",
        "plat_name",
        "label",
        "operator_name",
        "fields",
        "bk_tenant_id",
    ],
)
def test_gse_guards_reject_every_undeclared_key(guard_name, param_name, extra_key):
    guard = getattr(gse, guard_name)

    with pytest.raises(ParamsGuardRejected, match="未声明参数"):
        guard({param_name: 101, extra_key: "blocked"})


@pytest.mark.parametrize("guard_name", ["guard_query_route", "guard_query_stream_to"])
@pytest.mark.parametrize("params", [None, [], "channel_id=101", 101])
def test_gse_guards_are_total_for_non_object_params(guard_name, params):
    guard = getattr(gse, guard_name)

    with pytest.raises(ParamsGuardRejected, match="对象"):
        guard(params)


def test_gse_operations_use_fixed_response_projectors():
    domain = PlatformSourceCatalog.get_domain("gse")
    assert domain is not None

    assert domain.operations["query_route"].response_postprocess is gse.project_query_route
    assert domain.operations["query_stream_to"].response_postprocess is gse.project_query_stream_to
    for operation in domain.operations.values():
        assert operation.default_fields == []
        assert operation.allowed_fields == []


def test_project_query_route_preserves_all_routes_and_only_safe_fields():
    raw = [
        {
            "metadata": {"channel_id": "101", "label": {"source": "blocked"}},
            "route": [
                {
                    "name": "route-main",
                    "stream_to": {
                        "stream_to_id": "201",
                        "kafka": {
                            "topic_name": "topic-main",
                            "storage_address": [{"ip": "broker.example.invalid", "port": 9092}],
                            "sasl_username": "canary-user",
                            "sasl_passwd": "canary-password",
                        },
                    },
                    "filter_name_and": ["blocked-filter"],
                },
                {
                    "name": "route-secondary",
                    "stream_to": {
                        "stream_to_id": 202,
                        "pulsar": {
                            "name": "topic-secondary",
                            "storage_address": [{"ip": "pulsar.example.invalid", "port": 6650}],
                            "token": "canary-token",
                        },
                    },
                    "unknown": "blocked-unknown",
                },
                {
                    "name": "route-redis",
                    "stream_to": {
                        "stream_to_id": 203,
                        "redis": {
                            "channel_name": "blocked-channel-name",
                            "storage_address": [{"ip": "redis.example.invalid", "port": 6379}],
                            "passwd": "canary-redis-password",
                        },
                    },
                },
            ],
        }
    ]

    assert gse.project_query_route(raw, None) == {
        "configuration_scope": "current",
        "projection_meta": {"is_partial": False, "dropped_items": 0, "reasons": []},
        "route_groups": [
            {
                "channel_id": 101,
                "routes": [
                    {
                        "name": "route-main",
                        "stream_to_id": 201,
                        "sink_type": "kafka",
                        "topic_name": "topic-main",
                    },
                    {
                        "name": "route-secondary",
                        "stream_to_id": 202,
                        "sink_type": "pulsar",
                        "topic_name": "topic-secondary",
                    },
                    {
                        "name": "route-redis",
                        "stream_to_id": 203,
                        "sink_type": "redis",
                        "topic_name": None,
                    },
                ],
            }
        ],
    }


def test_project_query_route_accepts_flat_channel_id_and_empty_route_list():
    assert gse.project_query_route([{"channel_id": 101, "route": []}], None) == {
        "configuration_scope": "current",
        "projection_meta": {"is_partial": False, "dropped_items": 0, "reasons": []},
        "route_groups": [{"channel_id": 101, "routes": []}],
    }


def test_project_query_stream_to_handles_nested_and_flat_responses():
    raw = [
        {
            "metadata": {"stream_to_id": "201", "label": {"source": "blocked"}},
            "stream_to": {
                "name": "stream-main",
                "report_mode": "kafka",
                "kafka": {
                    "storage_address": [{"ip": "broker.example.invalid", "port": 9092}],
                    "sasl_passwd": "canary-password",
                },
            },
        },
        {
            "stream_to_id": 202,
            "name": "stream-secondary",
            "report_mode": "redis",
            "redis": {
                "storage_address": [{"ip": "redis.example.invalid", "port": 6379}],
                "passwd": "canary-redis-password",
            },
        },
    ]

    assert gse.project_query_stream_to(raw, None) == {
        "configuration_scope": "current",
        "projection_meta": {"is_partial": False, "dropped_items": 0, "reasons": []},
        "stream_to_summaries": [
            {"stream_to_id": 201, "name": "stream-main", "report_mode": "kafka"},
            {"stream_to_id": 202, "name": "stream-secondary", "report_mode": "redis"},
        ],
    }


def test_project_query_stream_to_infers_missing_mode_from_one_known_sink():
    raw = [
        {
            "stream_to_id": 201,
            "name": "stream-main",
            "kafka": {
                "storage_address": [{"ip": "broker.example.invalid", "port": 9092}],
                "sasl_passwd": "canary-password",
            },
        }
    ]

    assert gse.project_query_stream_to(raw, None) == {
        "configuration_scope": "current",
        "projection_meta": {"is_partial": False, "dropped_items": 0, "reasons": []},
        "stream_to_summaries": [{"stream_to_id": 201, "name": "stream-main", "report_mode": "kafka"}],
    }


@pytest.mark.parametrize(
    ("projector_name", "items_key"),
    [
        ("project_query_route", "route_groups"),
        ("project_query_stream_to", "stream_to_summaries"),
    ],
)
def test_gse_projectors_distinguish_valid_empty_list_from_malformed_top_level(projector_name, items_key):
    projector = getattr(gse, projector_name)

    assert projector([], None) == {
        "configuration_scope": "current",
        "projection_meta": {"is_partial": False, "dropped_items": 0, "reasons": []},
        items_key: [],
    }
    assert projector({"unexpected": []}, None) == {
        "configuration_scope": "current",
        "projection_meta": {
            "is_partial": True,
            "dropped_items": 1,
            "reasons": ["invalid_top_level"],
        },
        items_key: [],
    }


def test_project_query_route_counts_malformed_entries_and_leaf_types():
    raw = [
        "not-a-route-group",
        {"metadata": {"channel_id": {"nested": 101}}, "route": []},
        {"channel_id": 102, "route": "not-a-list"},
        {
            "channel_id": 103,
            "route": [
                {
                    "name": {"nested": "route"},
                    "stream_to": {"stream_to_id": 201, "kafka": {"topic_name": "topic-main"}},
                },
                {
                    "name": "route-bad-id",
                    "stream_to": {"stream_to_id": [202], "kafka": {"topic_name": "topic-main"}},
                },
                {
                    "name": "route-bad-topic",
                    "stream_to": {"stream_to_id": 203, "kafka": {"topic_name": ["topic-main"]}},
                },
                {"name": "route-bad-stream", "stream_to": []},
                "not-a-route",
            ],
        },
    ]

    assert gse.project_query_route(raw, None) == {
        "configuration_scope": "current",
        "projection_meta": {
            "is_partial": True,
            "dropped_items": 8,
            "reasons": [
                "invalid_route_group",
                "invalid_channel_id",
                "invalid_routes",
                "invalid_route_name",
                "invalid_stream_to_id",
                "invalid_topic_name",
                "invalid_stream_to",
                "invalid_route",
            ],
        },
        "route_groups": [
            {"channel_id": 102, "routes": []},
            {"channel_id": 103, "routes": []},
        ],
    }


def test_project_query_stream_to_counts_malformed_entries_and_leaf_types():
    raw = [
        "not-a-summary",
        {
            "metadata": ["not-an-object"],
            "stream_to_id": 201,
            "name": "stream-main",
            "report_mode": "kafka",
        },
        {"stream_to_id": 202, "stream_to": []},
        {"stream_to_id": {"nested": 203}, "name": "bad-id", "report_mode": "kafka"},
        {"stream_to_id": 204, "name": ["bad-name"], "report_mode": "kafka"},
        {"stream_to_id": 205, "name": "bad-mode-type", "report_mode": {"nested": "kafka"}},
        {"stream_to_id": 206, "name": "bad-mode", "report_mode": "unknown"},
    ]

    assert gse.project_query_stream_to(raw, None) == {
        "configuration_scope": "current",
        "projection_meta": {
            "is_partial": True,
            "dropped_items": 7,
            "reasons": [
                "invalid_stream_to_summary",
                "invalid_stream_to_metadata",
                "invalid_stream_to",
                "invalid_stream_to_id",
                "invalid_stream_to_name",
                "invalid_report_mode",
            ],
        },
        "stream_to_summaries": [{"stream_to_id": 201, "name": "stream-main", "report_mode": "kafka"}],
    }


def test_gse_projectors_do_not_leak_sensitive_or_unknown_canaries():
    route_result = gse.project_query_route(
        [
            {
                "metadata": {"channel_id": 101, "label": {"blocked": "canary-label"}},
                "route": [
                    {
                        "name": "route-main",
                        "stream_to": {
                            "stream_to_id": 201,
                            "kafka": {
                                "topic_name": "topic-main",
                                "storage_address": [{"ip": "broker.example.invalid", "port": 9092}],
                                "sasl_username": "canary-user",
                                "sasl_passwd": "canary-password",
                                "security_protocol": "canary-protocol",
                            },
                            "secret": "canary-secret",
                        },
                        "filter_name_and": ["canary-filter"],
                        "field_data_value": "canary-filter-value",
                    }
                ],
            }
        ],
        None,
    )
    stream_result = gse.project_query_stream_to(
        [
            {
                "metadata": {"stream_to_id": 201, "label": {"blocked": "canary-label"}},
                "stream_to": {
                    "name": "stream-main",
                    "report_mode": "pulsar",
                    "pulsar": {
                        "storage_address": [{"ip": "pulsar.example.invalid", "port": 6650}],
                        "token": "canary-token",
                    },
                    "data_log_path": "canary-path",
                },
            }
        ],
        None,
    )

    serialized = json.dumps([route_result, stream_result], ensure_ascii=False)
    for canary in [
        "canary-label",
        "broker.example.invalid",
        "canary-user",
        "canary-password",
        "canary-protocol",
        "canary-secret",
        "canary-filter",
        "canary-filter-value",
        "pulsar.example.invalid",
        "canary-token",
        "canary-path",
    ]:
        assert canary not in serialized
