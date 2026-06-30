"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from dataclasses import dataclass, field
from typing import Any

from django.utils.translation import gettext_lazy as _lazy

from core.drf_resource.exceptions import CustomException


class BkmCliOpNotFound(CustomException):
    # op 未在当前环境后端部署（或 CLI 版本领先于后端发布）时抛出。
    # 用数值 code=404 让 bkm-cli 端 mapStatusToCode(404) 映射为 target_not_found，
    # 而不是落到 invalid_argument 兜底——后者会误导 agent 反复改 schema（以为是参数错），
    # 实际是「该 op 根本不存在/未部署」。CLI 无需改动即可受益于这个语义区分。
    status_code = 404
    code = 404
    name = _lazy("bkm-cli op 未部署")

    def __init__(self, message=None, data=None, code=None):
        # 显式把类属性 code(404) 注入构造，确保进 custom_exception_handler 的 envelope。
        # 不能依赖默认 code=None：父类 CustomException 会把 extra={"code": None} 透传，
        # 而 custom_exception_handler 末尾 result.update(exc.extra) 会用 extra 里的 code
        # 覆盖前面写入的 exc.code——若 extra.code 为 None 则把 envelope 的 code 冲掉。
        # 这里固定传 code=self.code(404)，让 exc.code 与 envelope code 都稳定为 404。
        super().__init__(message=message, data=data, code=code or self.code)


@dataclass
class BkmCliOpFunction:
    op_id: str
    func_name: str
    summary: str
    description: str
    capability_level: str = "L1"
    risk_level: str = "readonly"
    requires_confirmation: bool = False
    audit_tags: list[str] = field(default_factory=list)
    params_schema: dict[str, Any] | None = None
    example_params: dict[str, Any] | None = None

    def to_detail(self) -> dict[str, Any]:
        detail = {
            "op_id": self.op_id,
            "func_name": self.func_name,
            "summary": self.summary,
            "description": self.description,
            "capability_level": self.capability_level,
            "risk_level": self.risk_level,
            "requires_confirmation": self.requires_confirmation,
            "audit_tags": self.audit_tags,
        }
        if self.params_schema is not None:
            detail["params_schema"] = self.params_schema
        if self.example_params is not None:
            detail["example_params"] = self.example_params
        return detail


class BkmCliOpRegistry:
    """bkm-cli op_id 到 Kernel RPC 函数的白名单映射。"""

    _ops: dict[str, BkmCliOpFunction] = {}

    @classmethod
    def register(
        cls,
        *,
        op_id: str,
        func_name: str,
        summary: str | None = None,
        description: str | None = None,
        capability_level: str = "L1",
        risk_level: str = "readonly",
        requires_confirmation: bool = False,
        audit_tags: list[str] | None = None,
        params_schema: dict[str, Any] | None = None,
        example_params: dict[str, Any] | None = None,
    ) -> None:
        op_id = (op_id or "").strip()
        func_name = (func_name or "").strip()
        if not op_id:
            raise ValueError("op_id cannot be empty")
        if not func_name:
            raise ValueError("func_name cannot be empty")

        cls._ops[op_id] = BkmCliOpFunction(
            op_id=op_id,
            func_name=func_name,
            summary=summary or op_id,
            description=description or summary or op_id,
            capability_level=capability_level,
            risk_level=risk_level,
            requires_confirmation=requires_confirmation,
            audit_tags=audit_tags or [],
            params_schema=params_schema,
            example_params=example_params,
        )

    @classmethod
    def resolve(cls, op_id: str) -> BkmCliOpFunction:
        from kernel_api.rpc import KernelRPCRegistry

        KernelRPCRegistry.ensure_loaded()
        op_id = (op_id or "").strip()
        op = cls._ops.get(op_id)
        if op is None:
            raise BkmCliOpNotFound(
                message=(f"未找到 bkm-cli op: {op_id}。该 op 可能未在当前环境后端部署，或 CLI 版本领先于后端发布。")
            )
        return op
