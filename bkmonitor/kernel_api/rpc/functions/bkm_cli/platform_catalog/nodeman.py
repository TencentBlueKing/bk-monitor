"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT

platform-source catalog domain：nodeman（节点管理 bk-nodeman，只读）。

能力面：采集订阅在各目标主机上的下发/进程态 —— 回答"采集配置是否部署到主机 X、状态如何"。
- get_subscription_instance_status：按订阅ID列出各实例的部署状态 + 主机归属 + bkmonitorbeat 进程态

典型链路：read-db-model 读 DeploymentConfigVersion 拿 subscription_id → 本接口查该订阅各实例
是否部署成功、主机是否在订阅范围内（区分"配置目标"与"运行时上报"）。

readonly 防线（在 id 前缀白名单 / domain readonly tag 之上叠加 params_guard）：
- 参数 key 白名单：拒绝一切未声明 key，杜绝 RequestSerializer 隐藏参数
  （如 _user_request 切换鉴权方式）经 CLI 整体透传下发
- 不开放 task_result_detail / subscription_info：其返回含渲染后的采集配置（可能携带端点凭据）

边界：实例状态 SUCCESS 仅表示下发/进程就绪，不代表采集数据合法；数据是否正常另查采集健康指标。
"""

from __future__ import annotations

from typing import Any

from core.drf_resource import api

from ._catalog import OperationSpec, ParamsGuardRejected, PlatformSourceCatalog

SUBSCRIPTION_INSTANCE_STATUS_ALLOWED_KEYS = frozenset({"subscription_id_list", "show_task_detail"})


def _reject_unknown_keys(params: dict[str, Any], allowed: frozenset[str], op_id: str) -> None:
    unknown = sorted(str(k) for k in params if k not in allowed)
    if unknown:
        raise ParamsGuardRejected(f"{op_id} 仅接受参数 {sorted(allowed)}，拒绝未声明参数: {unknown}")


def guard_subscription_instance_status(params: dict[str, Any]) -> dict[str, Any]:
    """get_subscription_instance_status 参数防线：仅 subscription_id_list（整数列表）+ show_task_detail。"""
    _reject_unknown_keys(params, SUBSCRIPTION_INSTANCE_STATUS_ALLOWED_KEYS, "get_subscription_instance_status")

    sid_list = params.get("subscription_id_list")
    if not isinstance(sid_list, list) or not sid_list:
        raise ParamsGuardRejected("subscription_id_list 必须为非空列表")
    normalized_ids: list[int] = []
    for sid in sid_list:
        if isinstance(sid, bool):
            raise ParamsGuardRejected(f"subscription_id_list 元素必须为整数: {sid!r}")
        try:
            normalized_ids.append(int(sid))
        except (TypeError, ValueError):
            raise ParamsGuardRejected(f"subscription_id_list 元素必须为整数: {sid!r}")

    normalized: dict[str, Any] = {"subscription_id_list": normalized_ids}
    if "show_task_detail" in params:
        normalized["show_task_detail"] = bool(params["show_task_detail"])
    return normalized


def register() -> None:
    """注册 nodeman domain。模块 import 时调用一次；测试 reset() 后可显式重注册。"""
    PlatformSourceCatalog.register_domain(
        id="nodeman",
        summary=(
            "节点管理（bk-nodeman）只读：采集订阅在各目标实例的下发状态，"
            "定位采集配置在主机上的部署/进程态，区分'配置目标'与'运行时上报'"
        ),
        audit_tags=["readonly", "nodeman"],
        operations=[
            OperationSpec(
                id="get_subscription_instance_status",
                summary="查询采集订阅在各目标实例的下发状态（部署成功/失败、主机归属、bkmonitorbeat 进程态）",
                handler=api.node_man.subscription_instance_status,
                params_guard=guard_subscription_instance_status,
                params_schema_override={
                    "type": "object",
                    "properties": {
                        "subscription_id_list": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": (
                                "节点管理订阅ID列表；采集配置的 subscription_id 可经 read-db-model 读 "
                                "DeploymentConfigVersion 获取"
                            ),
                        },
                        "show_task_detail": {
                            "type": "boolean",
                            "description": "是否展示实例最后一次下发的步骤详情，默认 false",
                        },
                    },
                    "required": ["subscription_id_list"],
                },
                example_params={"subscription_id_list": [10001], "show_task_detail": True},
                required_params=["subscription_id_list"],
                audit_tags=["readonly", "nodeman"],
                notes=(
                    "返回每个订阅下各实例的部署状态与主机信息（bk_host_id / 内网IP / status / host_statuses）。"
                    "实例 status=SUCCESS 仅表示下发/进程就绪，不代表采集数据合法——数据是否正常需另查 "
                    "采集健康指标（gather_up 的 bkm_up_code 等）。本接口不返回渲染后的采集配置内容（含端点凭据）。"
                ),
            ),
        ],
    )


register()
