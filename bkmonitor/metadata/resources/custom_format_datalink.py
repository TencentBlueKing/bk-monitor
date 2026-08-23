"""自定义格式 DataLink 的无状态 Clean Debug 接口。"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from bkmonitor.utils.serializers import TenantIdField
from core.drf_resource import Resource, api
from metadata.models import ClusterInfo, DataSource, DataSourceResultTable, ResultTable, ResultTableOption
from metadata.models.data_link.data_link import DataLink
from metadata.models.data_link.utils import generate_result_table_field_list
from metadata.models.result_table import CustomFormatV4DataLinkOption
from metadata.models.space.constants import EtlConfigs


class DebugCustomFormatDataLinkResource(Resource):
    """用样例输入执行 BKBase Clean Debug，并返回规则与字段契约错误。"""

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        table_id = serializers.CharField(label="结果表ID")
        input = serializers.CharField(label="样例输入")
        clean_rules = serializers.ListField(child=serializers.DictField(), min_length=1, label="清洗规则")
        filter_rules = serializers.ListField(child=serializers.DictField(), required=False, default=list)

    @staticmethod
    def _collect_rule_errors(value: Any, path: str = "result") -> list[dict[str, Any]]:
        errors: list[dict[str, Any]] = []
        if isinstance(value, list):
            for index, item in enumerate(value):
                errors.extend(DebugCustomFormatDataLinkResource._collect_rule_errors(item, f"{path}[{index}]"))
        elif isinstance(value, dict):
            status = str(value.get("status", "")).lower()
            if status and status not in {"ok", "success", "true"}:
                errors.append({"path": path, "status": value.get("status"), "error": value.get("error")})
            for key, item in value.items():
                errors.extend(DebugCustomFormatDataLinkResource._collect_rule_errors(item, f"{path}.{key}"))
        return errors

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict[str, Any]:
        bk_tenant_id = validated_request_data["bk_tenant_id"]
        table_id = validated_request_data["table_id"]
        rt = ResultTable.objects.get(bk_tenant_id=bk_tenant_id, table_id=table_id)
        relations = list(
            DataSourceResultTable.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id).values_list(
                "bk_data_id", flat=True
            )[:2]
        )
        if len(relations) != 1:
            raise ValueError(f"自定义格式 ResultTable({table_id}) 必须且只能关联一个 DataSource")
        data_source = DataSource.objects.get(bk_tenant_id=bk_tenant_id, bk_data_id=relations[0])
        if data_source.etl_config != EtlConfigs.BK_CUSTOM_FORMAT.value:
            raise ValueError(f"DataSource({data_source.bk_data_id}) 不是 bk_custom_format 类型")

        option_record = ResultTableOption.objects.get(
            bk_tenant_id=bk_tenant_id,
            table_id=table_id,
            name=ResultTableOption.OPTION_CUSTOM_FORMAT_V4_DATA_LINK,
        )
        option = CustomFormatV4DataLinkOption.from_option_value(option_record.get_value())
        clean_rules = validated_request_data["clean_rules"]
        contract_errors: list[str] = []
        try:
            fields = None
            if option.target_storage_type != ClusterInfo.TYPE_VM:
                fields = generate_result_table_field_list(table_id=table_id, bk_tenant_id=bk_tenant_id)
            DataLink._validate_custom_format_contract(
                fields,
                clean_rules,
                require_vm_contract=option.target_storage_type == ClusterInfo.TYPE_VM,
            )
        except ValueError as error:
            contract_errors.append(str(error))

        debug_result = api.bkdata.data_bus_clean_debug(
            input=validated_request_data["input"],
            rules=clean_rules,
            filter_rules=validated_request_data["filter_rules"],
        )
        return {
            "output": debug_result,
            "rule_errors": self._collect_rule_errors(debug_result),
            "contract_errors": contract_errors,
            "table_id": rt.table_id,
        }
