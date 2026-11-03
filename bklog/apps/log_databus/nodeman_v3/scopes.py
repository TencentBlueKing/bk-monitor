"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

from django.utils.translation import gettext as _

from apps.log_databus.constants import TargetNodeTypeEnum
from apps.log_databus.nodeman_v3.constants import (
    SCOPE_GRANULARITY_HOST,
    SCOPE_TYPE_DYNAMIC_GROUP,
    SCOPE_TYPE_INSTANCE,
    SCOPE_TYPE_SERVICE_TEMPLATE,
    SCOPE_TYPE_SET_TEMPLATE,
    SCOPE_TYPE_TOPO,
)
from apps.log_databus.nodeman_v3.exceptions import NodeManV3CapabilityBlocked

TARGET_NODE_TYPE_TO_SCOPE_TYPE = {
    TargetNodeTypeEnum.TOPO.value: SCOPE_TYPE_TOPO,
    TargetNodeTypeEnum.INSTANCE.value: SCOPE_TYPE_INSTANCE,
    TargetNodeTypeEnum.SERVICE_TEMPLATE.value: SCOPE_TYPE_SERVICE_TEMPLATE,
    TargetNodeTypeEnum.SET_TEMPLATE.value: SCOPE_TYPE_SET_TEMPLATE,
    TargetNodeTypeEnum.DYNAMIC_GROUP.value: SCOPE_TYPE_DYNAMIC_GROUP,
}


def build_scopes(bk_biz_id: int, target_node_type: str, target_nodes: list[dict] | None) -> list[dict]:
    """
    把日志采集项的采集目标翻译成 V3 部署策略的 scopes。

    目标展开交给节点管理：策略只描述范围表达式，主机集合由 NodeMan 的 ScopeCalculator 计算，
    日志侧不再自己把拓扑展平成主机列表下发，避免两侧展开口径不一致。
    """
    target_nodes = target_nodes or []
    scope_type = TARGET_NODE_TYPE_TO_SCOPE_TYPE.get(target_node_type)
    if not scope_type:
        raise NodeManV3CapabilityBlocked(
            NodeManV3CapabilityBlocked.MESSAGE.format(err=_("不支持的采集目标类型: {}").format(target_node_type))
        )
    if not target_nodes:
        return []

    if scope_type == SCOPE_TYPE_INSTANCE:
        instance_ids = [node["bk_host_id"] for node in target_nodes if node.get("bk_host_id")]
        if len(instance_ids) != len(target_nodes):
            # V3 instance scope 只认 host_id。历史采集项可能只存了 ip + bk_cloud_id，
            # 这类目标必须先补齐 bk_host_id 再下发，否则会静默少下发主机。
            raise NodeManV3CapabilityBlocked(
                NodeManV3CapabilityBlocked.MESSAGE.format(
                    err=_("采集目标存在缺少 bk_host_id 的主机实例，V3 instance 范围只支持主机 ID")
                )
            )
        return [
            {
                "type": SCOPE_TYPE_INSTANCE,
                "scope": {
                    "granularity": SCOPE_GRANULARITY_HOST,
                    "bk_biz_id": bk_biz_id,
                    "instance_ids": instance_ids,
                },
            }
        ]

    if scope_type == SCOPE_TYPE_TOPO:
        paths = [
            {"topo_obj_id": node["bk_obj_id"], "topo_inst_id": int(node["bk_inst_id"])}
            for node in target_nodes
            if node.get("bk_obj_id") and node.get("bk_inst_id") is not None
        ]
        return [
            {
                "type": SCOPE_TYPE_TOPO,
                "scope": {
                    "granularity": SCOPE_GRANULARITY_HOST,
                    "bk_biz_id": bk_biz_id,
                    "paths": paths,
                },
            }
        ]

    if scope_type == SCOPE_TYPE_SERVICE_TEMPLATE:
        return [
            {
                "type": SCOPE_TYPE_SERVICE_TEMPLATE,
                "scope": {
                    "granularity": SCOPE_GRANULARITY_HOST,
                    "bk_biz_id": bk_biz_id,
                    "service_template_ids": [int(node["bk_inst_id"]) for node in target_nodes],
                },
            }
        ]

    if scope_type == SCOPE_TYPE_SET_TEMPLATE:
        return [
            {
                "type": SCOPE_TYPE_SET_TEMPLATE,
                "scope": {
                    "granularity": SCOPE_GRANULARITY_HOST,
                    "bk_biz_id": bk_biz_id,
                    "set_template_ids": [int(node["bk_inst_id"]) for node in target_nodes],
                },
            }
        ]

    # 动态分组 ID 在 CMDB 里是字符串，且 V3 只支持 host 粒度
    return [
        {
            "type": SCOPE_TYPE_DYNAMIC_GROUP,
            "scope": {
                "granularity": SCOPE_GRANULARITY_HOST,
                "bk_biz_id": bk_biz_id,
                "dynamic_group_ids": [str(node["bk_inst_id"]) for node in target_nodes],
            },
        }
    ]
