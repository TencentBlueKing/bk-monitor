from __future__ import annotations

from typing import Any

from monitor_web.data_migrate.handler.base import BaseDirectoryHandler


class ReplaceTenantIdHandler(BaseDirectoryHandler):
    """
    按业务替换 fixture 记录中的 ``bk_tenant_id``。

    仅当记录字段中真实存在 ``bk_tenant_id`` 时才会替换；
    不存在该字段的模型保持不变。

    支持两类映射键：
    - 具体业务 ID，例如 ``2``
    - 通配符 ``"*"``

    规则：
    - 具体业务 ID 优先级高于 ``"*"``
    - ``"*"` 仅作用于普通业务，不覆盖全局目录 ``bk_biz_id=0``
    """

    name = "replace_bk_tenant_id"

    def __init__(self, biz_tenant_id_map: dict[int | str, str]):
        self.biz_tenant_id_map = {
            ("*" if str(biz_id) == "*" else int(biz_id)): tenant_id for biz_id, tenant_id in biz_tenant_id_map.items()
        }

    def get_manifest_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "biz_tenant_id_map": {str(biz_id): tenant_id for biz_id, tenant_id in self.biz_tenant_id_map.items()},
        }

    def _get_target_tenant_id(self, biz_id: int) -> str | None:
        if biz_id in self.biz_tenant_id_map:
            return self.biz_tenant_id_map[biz_id]
        if biz_id == 0:
            return None
        return self.biz_tenant_id_map.get("*")

    def handle_records(
        self,
        records: list[dict[str, Any]],
        biz_id: int,
        relative_file_path: str,
    ) -> bool:
        target_tenant_id = self._get_target_tenant_id(biz_id)
        if target_tenant_id is None:
            return False

        changed = False
        for record in records:
            fields = record.get("fields")
            if not isinstance(fields, dict) or "bk_tenant_id" not in fields:
                continue
            if fields["bk_tenant_id"] == target_tenant_id:
                continue
            fields["bk_tenant_id"] = target_tenant_id
            changed = True
        return changed
