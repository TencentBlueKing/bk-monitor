"""Base 迁入主仓后的 CI 安全修复回归，不依赖外部服务。"""

import logging
from typing import Any

import pytest
from pytest_mock import MockerFixture
from rest_framework.exceptions import ValidationError

from bk_monitor_base.domains.strategy.strategy import Detect
from bk_monitor_base.metadata.models.result_table import ResultTable
from bk_monitor_base.metadata.models.storage import ClusterInfo
from bk_monitor_base.metadata.resources.bkdata_link import QueryDataLinkMetadataResource
from bk_monitor_base.metadata.resources.vm import ModifyClusterByVmrts
from bk_monitor_base.metadata.utils.bk_collector_config import BkCollectorClusterConfig


def test_cluster_modify_does_not_log_credentials(mocker: MockerFixture, caplog: Any) -> None:
    """修改仍保存凭证，但日志只记录集群和操作者，不访问包含凭证的字典。"""
    cluster = ClusterInfo(cluster_name="test-cluster", cluster_type=ClusterInfo.TYPE_INFLUXDB)
    save = mocker.patch.object(cluster, "save")
    with caplog.at_level(logging.INFO):
        assert cluster.modify(operator="tester", password="private-value", ssl_certificate_key="private-key")
    save.assert_called_once()
    assert cluster.password == "private-value"
    assert cluster.ssl_certificate_key == "private-key"
    assert "private-value" not in caplog.text
    assert "private-key" not in caplog.text
    assert "updated by->[tester] success" in caplog.text


def test_duplicate_cluster_does_not_log_password(mocker: MockerFixture, caplog: Any) -> None:
    """重复集群仍拒绝创建，但不把入参密码写入日志。"""
    mocker.patch.object(ClusterInfo.objects, "filter").return_value.exists.side_effect = [False, True]
    with caplog.at_level(logging.ERROR), pytest.raises(ValueError):
        ClusterInfo.create_cluster(
            bk_tenant_id="default",
            cluster_type=ClusterInfo.TYPE_INFLUXDB,
            domain_name="localhost",
            port=8086,
            registered_system="test",
            operator="tester",
            cluster_name="test-cluster",
            password="private-value",
        )
    assert "private-value" not in caplog.text


def test_secret_listing_error_does_not_log_response_body(mocker: MockerFixture, caplog: Any) -> None:
    """Kubernetes 错误可能包含 Secret 正文，只记录异常类型。"""
    mocker.patch(
        "bk_monitor_base.metadata.utils.bk_collector_config.BkCollectorComp.get_secrets_config_map_by_protocol",
        return_value={"secret_extra_label": "test"},
    )
    client = mocker.patch("bk_monitor_base.metadata.utils.bk_collector_config.BcsKubeClient").return_value
    client.client_request.side_effect = RuntimeError("private-response-body")
    with caplog.at_level(logging.WARNING):
        BkCollectorClusterConfig.clean_dup_secrets("test-cluster", "trace")
    assert "private-response-body" not in caplog.text
    assert "RuntimeError" in caplog.text


@pytest.mark.parametrize("kind", ["result_table", "vm_result_table"])
def test_metadata_resolve_error_does_not_expose_internal_exception(mocker: MockerFixture, kind: str) -> None:
    """错误类型和请求上下文保留，底层异常内容不进入 API 校验结果。"""
    model = "DataSourceResultTable" if kind == "result_table" else "AccessVMRecord"
    mocker.patch(
        f"bk_monitor_base.metadata.resources.bkdata_link.models.{model}.objects.filter",
        side_effect=RuntimeError("private-backend-detail"),
    )
    with pytest.raises(ValidationError) as error:
        QueryDataLinkMetadataResource()._resolve_bk_data_id(
            "default",
            None,
            "test.table" if kind == "result_table" else None,
            "test.table" if kind == "vm_result_table" else None,
        )
    assert "private-backend-detail" not in str(error.value.detail)
    assert "test.table" in str(error.value.detail)


def test_vm_error_does_not_expose_internal_exception(mocker: MockerFixture) -> None:
    """VM 集群查询失败保持 ValidationError，但不透传后端异常内容。"""
    mocker.patch(
        "bk_monitor_base.metadata.resources.vm.models.ClusterInfo.objects.get",
        side_effect=RuntimeError("private-backend-detail"),
    )
    with pytest.raises(ValidationError) as error:
        ModifyClusterByVmrts().perform_request({"vmrts": [], "cluster_name": "test", "bk_tenant_id": "default"})
    assert "private-backend-detail" not in str(error.value.detail)


def test_metadata_query_error_does_not_expose_internal_exception(mocker: MockerFixture) -> None:
    """元数据查询失败保持 ValidationError，不把数据库异常暴露给调用方。"""
    mocker.patch(
        "bk_monitor_base.metadata.resources.bkdata_link.models.DataSource.objects.get",
        side_effect=RuntimeError("private-backend-detail"),
    )
    with pytest.raises(ValidationError) as error:
        QueryDataLinkMetadataResource().perform_request({"bk_tenant_id": "default", "bk_data_id": "1"})
    assert "private-backend-detail" not in str(error.value.detail)


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("2_system.cpu", "system.cpu"),
        ("system_cpu.metric_name", "system_cpu.metric_name"),
        ("数据库.字段", "数据库.字段"),
        ("__name__.__value__", "__name__.__value__"),
        ("_" * 20000, ".__default__"),
    ],
    ids=["business-prefix", "underscore", "unicode", "leading-underscore", "long-underscore"],
)
def test_result_table_fallback_preserves_lookup(mocker: MockerFixture, query: str, expected: str) -> None:
    """简化正则后保留旧查询结果，长下划线输入也能及时结束。"""
    lookup = mocker.patch.object(ResultTable.objects, "get")
    lookup.side_effect = [ResultTable.DoesNotExist()] * 4 + [mocker.sentinel.table]
    assert ResultTable.get_result_table(query) is mocker.sentinel.table
    assert lookup.call_args.kwargs["table_id"] == expected


def test_expression_validation_does_not_expose_unexpected_exception(mocker: MockerFixture) -> None:
    """表达式成功结果不变，异常返回稳定提示而非内部堆栈。"""
    parse = mocker.patch("bk_monitor_base.domains.strategy.strategy.parse_expression")
    assert Detect.Serializer().validate_expression("A && B") == "A && B"
    parse.side_effect = RuntimeError("private-backend-detail")
    with pytest.raises(ValidationError) as error:
        Detect.Serializer().validate_expression("A && B")
    assert "private-backend-detail" not in str(error.value.detail)
