"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# ==============================================================================
# 用户权限树（_iam_diag.json）全覆盖鉴权测试（live，真实测试 IAM 服务器）
#
# 数据源：bkmonitor/kernel_api/rpc/tests/_iam_diag.json
#   data.actions[].action_id    V3 平台 action ID（如 view_business_v2）
#   data.actions[].grant_type   all（全量）/ partial（部分实例）/ none（无权限）/ error（查询失败，未知）
#   data.actions[].permissions[].path[]  有权实例链（取叶子实例）
#
# 测试策略：
#   1. 覆盖 diag 中全部"有权"组合（all 断言任意 space 放行；partial 断言每个实例放行）
#   2. 覆盖"无权限"组合（none action 断言拒绝；partial action 断言其未授权资源拒绝），
#      确保无权限操作不会出现预期之外的通过
#   3. grant_type=error 的 action（平台批量查询失败、权限未知）仅探测打印，不硬断言
#
# 安全约束：本文件全部为权限查询（is_allowed），无任何授权/迁移/删除类写操作。
# 运行：BK_IAM_ENGINE_USER 必须与 diag 的 username 一致（否则跳过）。
# ==============================================================================

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bkmonitor.iam import Permission, ResourceEnum
from bkmonitor.iam.adapters.v3.codec import MonitorV3Codec

pytestmark = [pytest.mark.live, pytest.mark.django_db(databases=["default", "monitor_api"])]

DIAG_PATH = Path(__file__).resolve().parents[3] / "kernel_api" / "rpc" / "tests" / "_iam_diag.json"

_codec = MonitorV3Codec()


def _load_diag() -> tuple:
    """解析权限树：返回 (data, actions, granted_cases, denied_cases)。

    granted_cases: [(biz_action_id, resource_type, resource_id)] —— 有权组合
    denied_cases:  [(biz_action_id, resource_type, resource_id)] —— 无权限组合
    """
    raw = json.loads(DIAG_PATH.read_text(encoding="utf-8"))
    data = raw["data"]
    actions = []
    for a in data["actions"]:
        actions.append(
            {
                "v3_id": a["action_id"],
                "biz_id": _codec.decode_action(a["action_id"]),
                "rt": a["resource_type"],
                "grant_type": a["grant_type"],
                "perms": a.get("permissions") or [],
            }
        )

    granted = []
    for a in actions:
        if a["grant_type"] == "all":
            # 全量授权：任意 space 均应放行（用已知业务与"不存在"业务双验证）
            granted.append((a["biz_id"], "space", "2"))
            granted.append((a["biz_id"], "space", "999999"))
        elif a["grant_type"] == "partial":
            for p in a["perms"]:
                leaf = p["path"][-1]
                # 子资源 action 的 space path 表示"空间级授权范围"（平台策略为
                # 子资源._bk_iam_path_ starts_with），需具体子资源实例才能验证，
                # 不能用 space 资源直接鉴权（新旧路径一致：均不放行）。只保留
                # 与 action 资源类型匹配的实例叶子作为 granted case。
                if leaf["type"] != a["rt"]:
                    continue
                granted.append((a["biz_id"], leaf["type"], str(leaf["id"])))

    # 全局 space id 池：用于挑选"该 action 未授权"的交叉拒绝资源
    all_space_ids = {
        str(leaf["id"]) for a in actions for p in a["perms"] for leaf in p["path"] if leaf["type"] == "space"
    }
    denied = []
    for a in actions:
        if a["grant_type"] == "none":
            # 完全无权限的 action：任意 space 均应拒绝
            denied.append((a["biz_id"], "space", "2"))
        elif a["grant_type"] == "partial":
            allowed_ids = {str(leaf["id"]) for p in a["perms"] for leaf in p["path"]}
            if a["rt"] == "space":
                denied_id = next((s for s in sorted(all_space_ids) if s not in allowed_ids), "999999")
                denied.append((a["biz_id"], "space", denied_id))
            else:
                # 子资源：用不存在的数字格式实例 id（apm/rum 的 application_id 为
                # 数字字段，字母 id 会让 resolver 的 DB 查询抛 ValueError；
                # 99999999 不存在 -> resolver 查不到 -> 无 path -> 拒绝）
                denied.append((a["biz_id"], a["rt"], "99999999"))

    return data, actions, granted, denied


_DIAG_DATA, _DIAG_ACTIONS, _GRANTED_CASES, _DENIED_CASES = _load_diag()
_DIAG_USERNAME = _DIAG_DATA["username"]
_ERROR_ACTIONS = [a for a in _DIAG_ACTIONS if a["grant_type"] == "error"]
_NONE_ACTIONS = [a for a in _DIAG_ACTIONS if a["grant_type"] == "none"]


def _make_resource(rt: str, rid: str):
    """按资源类型构造 ResourceInstance（space / apm / grafana / rum）。"""
    if rt == "space":
        return ResourceEnum.BUSINESS.create_simple_instance(rid)
    if rt == "apm_application":
        return ResourceEnum.APM_APPLICATION.create_simple_instance(rid)
    if rt == "grafana_dashboard":
        return ResourceEnum.GRAFANA_DASHBOARD.create_simple_instance(rid)
    if rt == "rum_application":
        return ResourceEnum.RUM_APPLICATION.create_simple_instance(rid)
    raise ValueError(f"unknown resource type: {rt}")


@pytest.fixture
def live_permission(live_framework, iam_user):
    """真实框架 + 真实用户；用户必须与权限树文件的 username 一致。"""
    from bkmonitor.iam.iam_engine.django.facade import _set_framework, get_framework

    if iam_user != _DIAG_USERNAME:
        pytest.skip(
            f"BK_IAM_ENGINE_USER={iam_user} 与 _iam_diag.json 的 username={_DIAG_USERNAME} 不一致，跳过权限树对照"
        )

    saved = None
    try:
        saved = get_framework()
    except RuntimeError:
        saved = None
    _set_framework(live_framework)
    perm = Permission(username=iam_user, bk_tenant_id="system")
    yield perm
    _set_framework(saved)


def _check(perm, biz_action, rt, rid, expect):
    """执行鉴权断言。

    grafana 资源依赖 bk_dataview.dashboard 表：测试环境该库不可访问
    （DatabaseOperationForbidden）或缺表（ProgrammingError）时跳过，并注明环境限制。
    """
    from django.db.utils import ProgrammingError
    from django.test.testcases import DatabaseOperationForbidden

    try:
        resource = _make_resource(rt, rid)
        allowed = perm.is_allowed(biz_action, [resource])
    except (ProgrammingError, DatabaseOperationForbidden) as e:
        pytest.skip(f"测试环境 grafana 库不可用（{e}），跳过 {biz_action} {rt}/{rid}")
    if expect:
        assert allowed is True, f"{biz_action} 对 {rt}/{rid} 应放行（权限树显示有权限）"
    else:
        assert allowed is False, f"{biz_action} 对 {rt}/{rid} 不应放行（权限树显示无权限）"


class TestDiagGrantedCoverage:
    """覆盖权限树中全部有权组合（实例级）：必须放行。"""

    @pytest.mark.parametrize("biz_action,rt,rid", _GRANTED_CASES)
    def test_granted(self, live_permission, biz_action, rt, rid):
        _check(live_permission, biz_action, rt, rid, expect=True)


class TestDiagDenied:
    """无权限组合：不得出现预期之外的通过。"""

    @pytest.mark.parametrize("biz_action,rt,rid", _DENIED_CASES)
    def test_denied(self, live_permission, biz_action, rt, rid):
        _check(live_permission, biz_action, rt, rid, expect=False)


class TestDiagCoverageSummary:
    """权限树覆盖情况汇总（纯数据校验 + error action 探测）。"""

    def test_summary(self):
        total = len(_DIAG_ACTIONS)
        granted = len([a for a in _DIAG_ACTIONS if a["grant_type"] in ("all", "partial")])
        none = len(_NONE_ACTIONS)
        error = len(_ERROR_ACTIONS)
        print(f"[diag] username={_DIAG_USERNAME} total={total} granted={granted} none={none} error={error}")
        print(f"[diag] granted_cases={len(_GRANTED_CASES)} denied_cases={len(_DENIED_CASES)}")
        assert total == 53, f"权限树 action 总数应为 53，实际 {total}"
        assert granted + none + error == total

    def test_error_actions_probe(self, live_permission):
        """grant_type=error 的 action（diag 批量查询失败、权限未知）：真实鉴权探测并打印，不硬断言。"""
        for a in _ERROR_ACTIONS:
            allowed = live_permission.is_allowed(a["biz_id"], [ResourceEnum.BUSINESS.create_simple_instance("2")])
            print("[probe] {} on space/2 -> {} (diag: unknown)".format(a["v3_id"], allowed))
