from __future__ import annotations

from typing import Any

from monitor_web.data_migrate.handler.base import BaseDirectoryHandler


class SanitizeClusterInfoHandler(BaseDirectoryHandler):
    """
    将 ``metadata.ClusterInfo`` 中的连接信息替换为假数据。

    目的不是做脱敏展示，而是阻断迁移后误连旧环境，因此会直接把连接字段
    改成明显不可用的占位值。
    """

    name = "sanitize_cluster_info"
    cluster_model_label = "metadata.clusterinfo"

    def get_manifest_payload(self) -> dict[str, Any]:
        return {"name": self.name}

    def _build_placeholder_domain(self, fields: dict[str, Any]) -> str:
        cluster_name = fields.get("cluster_name") or "cluster"
        cluster_id = fields.get("cluster_id") or "unknown"
        return f"sanitized-{cluster_name}-{cluster_id}.invalid"

    def handle_records(
        self,
        records: list[dict[str, Any]],
        biz_id: int,
        relative_file_path: str,
    ) -> bool:
        changed = False

        for record in records:
            if str(record.get("model", "")).lower() != self.cluster_model_label:
                continue

            fields = record.get("fields")
            if not isinstance(fields, dict):
                continue

            placeholder_domain = self._build_placeholder_domain(fields)
            replacements = {
                "domain_name": placeholder_domain,
                "port": 0,
                "extranet_domain_name": "",
                "extranet_port": 0,
                "username": "fake_user",
                "password": "fake_password",
                "is_auth": False,
                "schema": "http",
                "is_ssl_verify": False,
                "ssl_verification_mode": "none",
                "ssl_certificate_authorities": "",
                "ssl_certificate": "",
                "ssl_certificate_key": "",
                "ssl_insecure_skip_verify": True,
                "sasl_mechanisms": None,
                "security_protocol": None,
                "registered_to_bkbase": False,
                "gse_stream_to_id": -1,
            }

            for field_name, target_value in replacements.items():
                if field_name not in fields:
                    continue
                if fields[field_name] == target_value:
                    continue
                fields[field_name] = target_value
                changed = True

        return changed
