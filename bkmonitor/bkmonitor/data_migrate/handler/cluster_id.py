from __future__ import annotations

from typing import Any

from bkmonitor.data_migrate.handler.base import BaseDirectoryHandler


class ReplaceClusterIdHandler(BaseDirectoryHandler):
    """
    按映射替换导出目录中的集群 ID。

    当前仅处理迁移工具实际导出的、会引用 ``metadata.ClusterInfo`` 的字段：
    - ``metadata.ClusterInfo.pk``
    - ``metadata.DataSource.mq_cluster_id``
    - ``metadata.KafkaStorage.storage_cluster_id``
    - ``metadata.ESStorage.storage_cluster_id``
    - ``metadata.DorisStorage.storage_cluster_id``
    - ``metadata.StorageClusterRecord.cluster_id``
    """

    name = "replace_cluster_id"
    cluster_model_label = "metadata.clusterinfo"
    field_mapping: dict[str, tuple[str, ...]] = {
        "metadata.datasource": ("mq_cluster_id",),
        "metadata.kafkastorage": ("storage_cluster_id",),
        "metadata.esstorage": ("storage_cluster_id",),
        "metadata.dorisstorage": ("storage_cluster_id",),
        "metadata.storageclusterrecord": ("cluster_id",),
    }

    def __init__(self, cluster_id_map: dict[int | str, int | str]):
        self.cluster_id_map = {
            int(source_cluster_id): int(target_cluster_id)
            for source_cluster_id, target_cluster_id in cluster_id_map.items()
        }

    def get_manifest_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "cluster_id_map": {
                str(source_cluster_id): target_cluster_id
                for source_cluster_id, target_cluster_id in self.cluster_id_map.items()
            },
        }

    def _replace_cluster_id(self, value: Any) -> tuple[Any, bool]:
        if value is None:
            return value, False
        try:
            normalized_value = int(value)
        except (TypeError, ValueError):
            return value, False

        if normalized_value not in self.cluster_id_map:
            return value, False

        target_value = self.cluster_id_map[normalized_value]
        if normalized_value == target_value:
            return value, False
        return target_value, True

    def handle_records(
        self,
        records: list[dict[str, Any]],
        biz_id: int,
        relative_file_path: str,
    ) -> bool:
        changed = False
        for record in records:
            model_label = str(record.get("model", "")).strip().lower()

            if model_label == self.cluster_model_label:
                replaced_pk, is_replaced = self._replace_cluster_id(record.get("pk"))
                if is_replaced:
                    record["pk"] = replaced_pk
                    changed = True

            fields = record.get("fields")
            if not isinstance(fields, dict):
                continue

            for field_name in self.field_mapping.get(model_label, ()):
                replaced_value, is_replaced = self._replace_cluster_id(fields.get(field_name))
                if not is_replaced:
                    continue
                fields[field_name] = replaced_value
                changed = True

        return changed
