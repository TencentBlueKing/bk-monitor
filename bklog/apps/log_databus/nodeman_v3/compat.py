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


def adapt_non_bkcc_for_bknode_v3(params: dict) -> dict:
    """
    适配节点管理 V3 的业务 ID。

    非 CC 业务（如蓝盾，bk_biz_id 为负）在节点管理侧不存在，需要换成其关联的 CC 业务。
    V3 的业务 ID 位于 scopes[n].scope.bk_biz_id，与 V2 的 scope.bk_biz_id 结构不同，
    因此不能复用 adapt_non_bkcc_for_bknode。

    create 的 scopes 在顶层，update 的 scopes 挂在 deploy_policies[n] 下，两种形态都要覆盖。
    """
    from apps.api.modules.utils import get_non_bkcc_space_related_bkcc_biz_id

    scope_groups = []
    if params.get("scopes"):
        scope_groups.append(params["scopes"])
    for policy in params.get("deploy_policies") or []:
        if policy.get("scopes"):
            scope_groups.append(policy["scopes"])
    if not scope_groups:
        return params

    cache: dict[int, int] = {}
    for scopes in scope_groups:
        for item in scopes:
            scope = item.get("scope") or {}
            bk_biz_id = scope.get("bk_biz_id")
            if bk_biz_id is None or int(bk_biz_id) >= 0:
                continue
            bk_biz_id = int(bk_biz_id)
            if bk_biz_id not in cache:
                cache[bk_biz_id] = get_non_bkcc_space_related_bkcc_biz_id(bk_biz_id)
            scope["bk_biz_id"] = cache[bk_biz_id]

    return params
