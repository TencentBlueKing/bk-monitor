"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json

import pytest

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry
from kernel_api.rpc.registry import KernelRPCRegistry

# ---------------- kafka-sample ----------------


def test_kafka_sample_registered_as_bkm_cli_op():
    op = BkmCliOpRegistry.resolve("kafka-sample")
    assert op.func_name == "bkm_cli.kafka_sample"
    assert op.capability_level == "readonly"
    assert op.risk_level == "low"
    assert op.requires_confirmation is False
    assert KernelRPCRegistry.get_function_detail("bkm_cli.kafka_sample") is not None


def test_kafka_sample_requires_bk_data_id():
    from kernel_api.rpc.functions.bkm_cli import kafka_sample as mod

    with pytest.raises(CustomException):
        mod.kafka_sample({"bk_tenant_id": "system"})


def test_kafka_sample_size_clamped_and_has_data_true(monkeypatch):
    from kernel_api.rpc.functions.bkm_cli import kafka_sample as mod

    captured = {}

    def fake_admin(params):
        captured.update(params)
        return {
            "data": {"bk_data_id": params["bk_data_id"], "topic": "topic_x", "items": [{"a": 1}, {"a": 2}], "count": 2}
        }

    monkeypatch.setattr(mod, "_admin_kafka_sample", fake_admin)
    # size 超上限须被收敛到 BKM_CLI_KAFKA_SAMPLE_MAX_SIZE
    out = mod.kafka_sample({"bk_tenant_id": "system", "bk_data_id": 624459, "size": 999})
    assert captured["size"] == mod.BKM_CLI_KAFKA_SAMPLE_MAX_SIZE
    assert out["bk_data_id"] == 624459
    assert out["topic"] == "topic_x"
    assert out["count"] == 2
    assert out["has_data"] is True
    assert out["items"] == [{"a": 1}, {"a": 2}]


def test_kafka_sample_empty_has_data_false(monkeypatch):
    from kernel_api.rpc.functions.bkm_cli import kafka_sample as mod

    monkeypatch.setattr(
        mod, "_admin_kafka_sample", lambda params: {"data": {"bk_data_id": 1, "topic": "t", "items": [], "count": 0}}
    )
    out = mod.kafka_sample({"bk_data_id": 1})
    assert out["has_data"] is False
    assert out["count"] == 0


def test_kafka_sample_default_size(monkeypatch):
    from kernel_api.rpc.functions.bkm_cli import kafka_sample as mod

    captured = {}

    def fake_admin(params):
        captured.update(params)
        return {"data": {"bk_data_id": params["bk_data_id"], "topic": "t", "items": [], "count": 0}}

    monkeypatch.setattr(mod, "_admin_kafka_sample", fake_admin)
    mod.kafka_sample({"bk_data_id": 5})
    assert captured["size"] == mod.BKM_CLI_KAFKA_SAMPLE_DEFAULT_SIZE


# ---------------- read-space-router ----------------


def test_read_space_router_registered_as_bkm_cli_op():
    op = BkmCliOpRegistry.resolve("read-space-router")
    assert op.func_name == "bkm_cli.read_space_router"
    assert op.capability_level == "readonly"
    assert op.risk_level == "low"
    assert KernelRPCRegistry.get_function_detail("bkm_cli.read_space_router") is not None


def test_read_space_router_rejects_unknown_operation():
    from kernel_api.rpc.functions.bkm_cli import space_router as mod

    with pytest.raises(CustomException):
        mod.read_space_router({"operation": "bogus"})


def _patch_redis_store(monkeypatch, mod, store: dict):
    """按 field 键的 fake hget，记录被访问的 field；用于验证 field 组装与 flag 分支/兜底。"""
    accessed = []

    def fake_hget(cls, key, field):
        accessed.append(field)
        return store.get(field)

    monkeypatch.setattr(mod.RedisTools, "hget", classmethod(fake_hget))
    return accessed


def _set_multi_tenant(monkeypatch, mod, enabled: bool):
    monkeypatch.setattr(mod.settings, "ENABLE_MULTI_TENANT_MODE", enabled, raising=False)


def test_read_space_router_multitenant_field_has_tenant_suffix(monkeypatch):
    from kernel_api.rpc.functions.bkm_cli import space_router as mod

    _set_multi_tenant(monkeypatch, mod, True)
    payload = json.dumps({"storage_name": "", "storage_id": 10113, "vm_rt": "20001_base_x"}).encode()
    # 多租户：数据存在带 |system 后缀的 field 上
    accessed = _patch_redis_store(monkeypatch, mod, {"system_20001_sys.cpu_summary|system": payload})
    out = mod.read_space_router(
        {"bk_tenant_id": "system", "operation": "result_table_detail", "table_id": "system_20001_sys.cpu_summary"}
    )
    assert out["operation"] == "result_table_detail"
    assert out["field"] == "system_20001_sys.cpu_summary|system"
    assert out["multi_tenant_mode"] is True
    assert out["exists"] is True
    assert out["storage_name_empty"] is True  # storage_name 空串 → 查空坐实
    assert accessed[0] == "system_20001_sys.cpu_summary|system"  # 首选带后缀


def test_read_space_router_single_tenant_field_is_bare(monkeypatch):
    from kernel_api.rpc.functions.bkm_cli import space_router as mod

    _set_multi_tenant(monkeypatch, mod, False)
    payload = json.dumps({"storage_name": "monitor-1", "storage_id": 10113}).encode()
    # 单租户(默认)：数据存在裸 field 上——若 op 误加 |system 后缀会 miss、误报未收录
    accessed = _patch_redis_store(monkeypatch, mod, {"system_20001_sys.cpu_summary": payload})
    out = mod.read_space_router(
        {"bk_tenant_id": "system", "operation": "result_table_detail", "table_id": "system_20001_sys.cpu_summary"}
    )
    assert out["field"] == "system_20001_sys.cpu_summary"  # 裸 field，无后缀
    assert out["multi_tenant_mode"] is False
    assert out["exists"] is True
    assert out["storage_name_empty"] is False
    assert accessed[0] == "system_20001_sys.cpu_summary"  # 首选裸 field


def test_read_space_router_fallback_when_primary_misses(monkeypatch):
    from kernel_api.rpc.functions.bkm_cli import space_router as mod

    # flag=多租户 但数据实际在裸 field 上（flag 与数据不一致的边缘）→ 兜底回退命中
    _set_multi_tenant(monkeypatch, mod, True)
    payload = json.dumps({"storage_name": "monitor-1"}).encode()
    accessed = _patch_redis_store(monkeypatch, mod, {"system_20001_sys.mem": payload})
    out = mod.read_space_router(
        {"bk_tenant_id": "system", "operation": "result_table_detail", "table_id": "system_20001_sys.mem"}
    )
    assert out["exists"] is True
    assert out["field"] == "system_20001_sys.mem"  # 回退命中裸 field
    assert accessed == ["system_20001_sys.mem|system", "system_20001_sys.mem"]  # 先带后缀 miss，再裸


def test_read_space_router_result_table_detail_healthy(monkeypatch):
    from kernel_api.rpc.functions.bkm_cli import space_router as mod

    _set_multi_tenant(monkeypatch, mod, True)
    payload = json.dumps({"storage_name": "monitor-1", "storage_id": 10113}).encode()
    _patch_redis_store(monkeypatch, mod, {"system_20001_sys.mem|system": payload})
    out = mod.read_space_router(
        {"bk_tenant_id": "system", "operation": "result_table_detail", "table_id": "system_20001_sys.mem"}
    )
    assert out["exists"] is True
    assert out["storage_name_empty"] is False
    assert out["detail"]["storage_name"] == "monitor-1"


def test_read_space_router_result_table_detail_missing(monkeypatch):
    from kernel_api.rpc.functions.bkm_cli import space_router as mod

    _set_multi_tenant(monkeypatch, mod, True)
    _patch_redis_store(monkeypatch, mod, {})  # 两种 field 都 miss
    out = mod.read_space_router({"bk_tenant_id": "system", "operation": "result_table_detail", "table_id": "nope"})
    assert out["exists"] is False
    assert out["storage_name_empty"] is False


def test_read_space_router_result_table_detail_requires_table_id():
    from kernel_api.rpc.functions.bkm_cli import space_router as mod

    with pytest.raises(CustomException):
        mod.read_space_router({"operation": "result_table_detail"})


def test_read_space_router_space_to_result_table(monkeypatch):
    from kernel_api.rpc.functions.bkm_cli import space_router as mod

    _set_multi_tenant(monkeypatch, mod, True)
    payload = json.dumps(
        {"system_20001_sys.cpu_summary": {"filters": []}, "system_20001_sys.mem": {"filters": []}}
    ).encode()
    _patch_redis_store(monkeypatch, mod, {"bkcc__20001|system": payload})
    out = mod.read_space_router(
        {"bk_tenant_id": "system", "operation": "space_to_result_table", "space_type": "bkcc", "space_id": "20001"}
    )
    assert out["field"] == "bkcc__20001|system"
    assert out["exists"] is True
    assert out["result_table_count"] == 2
    assert "system_20001_sys.cpu_summary" in out["result_table_ids"]


def test_read_space_router_space_to_result_table_single_tenant(monkeypatch):
    from kernel_api.rpc.functions.bkm_cli import space_router as mod

    _set_multi_tenant(monkeypatch, mod, False)
    payload = json.dumps({"2_system_cpu_summary": {"filters": []}}).encode()
    _patch_redis_store(monkeypatch, mod, {"bkcc__2": payload})
    out = mod.read_space_router({"operation": "space_to_result_table", "space_type": "bkcc", "space_id": "2"})
    assert out["field"] == "bkcc__2"  # 单租户裸 field
    assert out["exists"] is True
    assert out["result_table_count"] == 1


def test_read_space_router_space_to_result_table_requires_space(monkeypatch):
    from kernel_api.rpc.functions.bkm_cli import space_router as mod

    with pytest.raises(CustomException):
        mod.read_space_router({"operation": "space_to_result_table", "space_type": "bkcc"})


# ---------------- read-db-model whitelist: AccessVMRecord + ClusterInfo ----------------


def test_access_vm_record_in_whitelist_and_credentials_excluded():
    from kernel_api.rpc.functions.bkm_cli import db

    spec = db.ALLOWED_MODEL_SPECS["metadata.models.vm.record.AccessVMRecord"]
    safe = db._safe_fields(spec)
    assert "vm_cluster_id" in safe
    assert "result_table_id" in safe
    assert "bk_tenant_id" in safe


def test_cluster_info_in_whitelist_credentials_unreadable():
    from kernel_api.rpc.functions.bkm_cli import db

    spec = db.ALLOWED_MODEL_SPECS["metadata.models.storage.ClusterInfo"]
    safe = db._safe_fields(spec)
    # cluster_type 可过滤（查空判别第二跳按 cluster_type=victoria_metrics 过滤）
    assert "cluster_type" in safe
    assert "cluster_id" in safe
    # 凭据/私钥字段绝不透出、绝不可过滤
    for cred in ("password", "username", "ssl_certificate", "ssl_certificate_key", "ssl_certificate_authorities"):
        assert cred not in safe, f"{cred} must not be readable"
        assert cred in spec.sensitive_fields, f"{cred} must be in sensitive_fields backstop"
