"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from types import SimpleNamespace

import pytest

from core.drf_resource.exceptions import CustomException
from kernel_api.resource.bkm_cli import BkmCliOpCallResource
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry
from kernel_api.rpc.registry import KernelRPCRegistry


class FakeQuerySet:
    def __init__(self, rows):
        self.rows = rows
        self.filter_kwargs = None
        self.order_by_args = None
        self.slice_value = None

    def filter(self, **kwargs):
        self.filter_kwargs = kwargs
        return self

    def order_by(self, *args):
        self.order_by_args = args
        return self

    def __getitem__(self, value):
        self.slice_value = value
        return self.rows[value]


class FakeManager:
    def __init__(self, queryset):
        self.queryset = queryset

    def all(self):
        return self.queryset


class FakeModel:
    objects = None


def test_read_db_model_registered_as_bkm_cli_op():
    op = BkmCliOpRegistry.resolve("read-db-model")
    function_detail = KernelRPCRegistry.get_function_detail("bkm_cli.read_db_model")

    assert op.func_name == "bkm_cli.read_db_model"
    assert op.capability_level == "readonly"
    assert op.risk_level == "low"
    assert function_detail is not None


def test_list_db_models_registered_as_bkm_cli_op():
    op = BkmCliOpRegistry.resolve("list-db-models")
    function_detail = KernelRPCRegistry.get_function_detail("bkm_cli.list_db_models")

    assert op.func_name == "bkm_cli.list_db_models"
    assert op.capability_level == "readonly"
    assert op.risk_level == "low"
    assert function_detail is not None


def test_list_db_models_returns_read_db_model_allowlist(monkeypatch):
    from kernel_api.rpc.functions.bkm_cli import db

    monkeypatch.setattr(db, "ALLOWED_MODEL_SPECS", {})
    monkeypatch.setitem(
        db.ALLOWED_MODEL_SPECS,
        "demo.Model",
        db.ModelSpec(
            model_path="demo.Model",
            fields={"id", "name", "token"},
            sensitive_fields={"token"},
            examples=[
                {
                    "filter": {"id": 1},
                    "fields": ["id", "name"],
                    "limit": 20,
                }
            ],
        ),
    )

    result = BkmCliOpCallResource().perform_request({"op_id": "list-db-models", "params": {}})

    assert result["op_id"] == "list-db-models"
    assert result["func_name"] == "bkm_cli.list_db_models"
    assert result["protocol"] == "bkm_cli_op_call"
    assert result["result"] == {
        "count": 1,
        "items": [
            {
                "model": "demo.Model",
                "allowed_fields": ["id", "name"],
                "allowed_filter_fields": ["id", "name"],
                "allowed_order_by": ["id", "name"],
                "allowed_lookups": ["contains", "endswith", "exact", "gte", "in", "isnull", "lte", "startswith"],
                "default_fields": ["id", "name"],
                "max_limit": 500,
                "examples": [{"filter": {"id": 1}, "fields": ["id", "name"], "limit": 20}],
            }
        ],
    }


def test_read_db_model_rejects_model_outside_allowlist():
    with pytest.raises(CustomException) as exc:
        BkmCliOpCallResource().perform_request(
            {
                "op_id": "read-db-model",
                "params": {
                    "model": "django.contrib.auth.models.User",
                    "filter": {"id": 1},
                },
            }
        )

    assert "不在 bkm-cli read-db-model 白名单" in str(exc.value)
    assert exc.value.data == {
        "next_actions": ["调用 list-db-models 获取当前环境可读模型、字段、filter、排序和 limit 上限。"]
    }


def test_read_db_model_rejects_unsafe_lookup(monkeypatch):
    from kernel_api.rpc.functions.bkm_cli import db

    monkeypatch.setitem(
        db.ALLOWED_MODEL_SPECS, "demo.Model", db.ModelSpec(model_path="demo.Model", fields={"id", "name"})
    )
    monkeypatch.setattr(db, "import_string", lambda _model_path: FakeModel)

    with pytest.raises(CustomException) as exc:
        BkmCliOpCallResource().perform_request(
            {
                "op_id": "read-db-model",
                "params": {
                    "model": "demo.Model",
                    "filter": {"name__regex": "^admin"},
                },
            }
        )

    assert "不支持的 lookup" in str(exc.value)
    assert exc.value.data == {
        "next_actions": ["调用 list-db-models 获取当前环境可读模型、字段、filter、排序和 limit 上限。"]
    }


def test_read_db_model_rejects_invalid_limit_with_discovery_next_actions():
    with pytest.raises(CustomException) as exc:
        BkmCliOpCallResource().perform_request(
            {
                "op_id": "read-db-model",
                "params": {
                    "model": "metadata.models.space.space.Space",
                    "limit": 501,
                },
            }
        )

    assert "limit 超过硬上限" in str(exc.value)
    assert exc.value.data == {
        "next_actions": ["调用 list-db-models 获取当前环境可读模型、字段、filter、排序和 limit 上限。"]
    }


def test_read_db_model_rejects_invalid_filter_shape_with_discovery_next_actions():
    with pytest.raises(CustomException) as exc:
        BkmCliOpCallResource().perform_request(
            {
                "op_id": "read-db-model",
                "params": {
                    "model": "metadata.models.space.space.Space",
                    "filter": "space_id=2",
                },
            }
        )

    assert "filter 必须是对象" in str(exc.value)
    assert exc.value.data == {
        "next_actions": ["调用 list-db-models 获取当前环境可读模型、字段、filter、排序和 limit 上限。"]
    }


def test_read_db_model_filters_limits_and_returns_allowed_fields(monkeypatch):
    from kernel_api.rpc.functions.bkm_cli import db

    queryset = FakeQuerySet(
        [
            SimpleNamespace(id=1, name="demo", token="secret-token", payload="x" * 10),
            SimpleNamespace(id=2, name="next", token="secret-token-2", payload="y" * 10),
        ]
    )
    FakeModel.objects = FakeManager(queryset)

    monkeypatch.setitem(
        db.ALLOWED_MODEL_SPECS,
        "demo.Model",
        db.ModelSpec(model_path="demo.Model", fields={"id", "name", "payload"}, sensitive_fields={"token"}),
    )
    monkeypatch.setattr(db, "import_string", lambda _model_path: FakeModel)

    result = BkmCliOpCallResource().perform_request(
        {
            "op_id": "read-db-model",
            "params": {
                "model": "demo.Model",
                "filter": {"id__in": [1, 2]},
                "fields": ["id", "name", "token"],
                "order_by": ["-id"],
                "limit": 1,
            },
        }
    )

    assert result["result"]["model"] == "demo.Model"
    assert result["result"]["count"] == 1
    assert result["result"]["items"] == [{"id": 1, "name": "demo"}]
    assert queryset.filter_kwargs == {"id__in": [1, 2]}
    assert queryset.order_by_args == ("-id",)
    assert queryset.slice_value == slice(None, 1, None)


def test_bcs_cluster_info_allowlist_has_diagnostic_fields():
    from kernel_api.rpc.functions.bkm_cli.db import ALLOWED_MODEL_SPECS

    spec = ALLOWED_MODEL_SPECS["metadata.models.bcs.cluster.BCSClusterInfo"]

    required = {"bk_env", "K8sMetricDataID", "K8sEventDataID", "operator_ns", "create_time", "last_modify_time"}
    assert required <= spec.fields, f"Missing fields: {required - spec.fields}"

    stale = {"created_at", "updated_at"}
    assert not (stale & spec.fields), f"Stale field names still present: {stale & spec.fields}"


def test_allowlist_excludes_deprecated_and_low_value_models():
    from kernel_api.rpc.functions.bkm_cli.db import ALLOWED_MODEL_SPECS

    removed = {
        "bkmonitor.models.base.ReportItems",
        "bkmonitor.models.base.ReportContents",
        "bkmonitor.models.base.ReportStatus",
        "bkmonitor.models.fta.action.ActionInstance",
        "bkmonitor.models.fta.action.ActionInstanceLog",
    }
    present = removed & set(ALLOWED_MODEL_SPECS.keys())
    assert not present, f"Deprecated/low-value models still in allowlist: {present}"
