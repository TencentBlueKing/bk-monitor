"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

AlertQueryHandler 合并视图：按 issue_id 过滤告警时把主 Issue 展开为 [main, ...active members]。

合并不改写 alert.issue_id，主 Issue 详情的告警列表 / 趋势 / 维度统计需在查询期展开 issue_id
才能聚合被并入 Issue 的告警。本测试直接验证 ``_expand_merged_issue_conditions`` 的条件改写
逻辑（绕过 __init__ 以免依赖 DB/ES），MergeResolverContext 用预填充的内存上下文替身。
"""

from unittest import mock

from bkmonitor.issue_merge import MergeResolverContext
from fta_web.alert.handlers.alert import AlertQueryHandler


def _make_ctx(main_to_members: dict, member_to_main: dict, degraded: bool = False) -> MergeResolverContext:
    ctx = MergeResolverContext(bk_biz_id=2)
    ctx._loaded = True
    ctx.degraded = degraded
    ctx._main_to_members = main_to_members
    ctx._member_to_main = member_to_main
    return ctx


def _handler(conditions: list, bk_biz_ids=None, authorized_bizs=None) -> AlertQueryHandler:
    # 绕过 __init__：被测方法只读 conditions / authorized_bizs，置这两个属性即可，
    # 避免 BaseBizQueryHandler 的鉴权 / ES 依赖。authorized_bizs 默认跟随 bk_biz_ids
    # （等价于 BaseBizQueryHandler 对单业务的解析结果）。
    handler = AlertQueryHandler.__new__(AlertQueryHandler)
    handler.conditions = conditions
    handler.bk_biz_ids = bk_biz_ids if bk_biz_ids is not None else [2]
    handler.authorized_bizs = authorized_bizs if authorized_bizs is not None else handler.bk_biz_ids
    return handler


class TestAlertQueryHandlerIssueExpand:
    """_expand_merged_issue_conditions：仅展开 issue_id 条件，fail-open。"""

    def test_main_issue_condition_expanded(self):
        ctx = _make_ctx(
            {"a1": [{"member_issue_id": "b1"}, {"member_issue_id": "b2"}]},
            {"b1": "a1", "b2": "a1"},
        )
        handler = _handler([{"origin_key": "issue_id", "key": "issue_id", "value": ["a1"], "method": "eq"}])
        with mock.patch("bkmonitor.issue_merge.MergeResolverContext", return_value=ctx):
            handler._expand_merged_issue_conditions()
        assert set(handler.conditions[0]["value"]) == {"a1", "b1", "b2"}

    def test_non_issue_condition_untouched(self):
        ctx = _make_ctx({"a1": [{"member_issue_id": "b1"}]}, {"b1": "a1"})
        handler = _handler([{"origin_key": "status", "key": "status", "value": ["ABNORMAL"], "method": "eq"}])
        with mock.patch("bkmonitor.issue_merge.MergeResolverContext", return_value=ctx):
            handler._expand_merged_issue_conditions()
        assert handler.conditions[0]["value"] == ["ABNORMAL"]

    def test_non_main_issue_passthrough(self):
        # c1 不是任何主 Issue（无 member），展开后保持自身
        ctx = _make_ctx({}, {})
        handler = _handler([{"origin_key": "issue_id", "key": "issue_id", "value": ["c1"], "method": "eq"}])
        with mock.patch("bkmonitor.issue_merge.MergeResolverContext", return_value=ctx):
            handler._expand_merged_issue_conditions()
        assert handler.conditions[0]["value"] == ["c1"]

    def test_degraded_context_keeps_original(self):
        ctx = _make_ctx({"a1": [{"member_issue_id": "b1"}]}, {"b1": "a1"}, degraded=True)
        handler = _handler([{"origin_key": "issue_id", "key": "issue_id", "value": ["a1"], "method": "eq"}])
        with mock.patch("bkmonitor.issue_merge.MergeResolverContext", return_value=ctx):
            handler._expand_merged_issue_conditions()
        assert handler.conditions[0]["value"] == ["a1"]

    def test_empty_bk_biz_ids_skip(self):
        # bk_biz_ids 为空时不展开（无法定位关系），保持原值
        ctx = _make_ctx({"a1": [{"member_issue_id": "b1"}]}, {"b1": "a1"})
        handler = _handler(
            [{"origin_key": "issue_id", "key": "issue_id", "value": ["a1"], "method": "eq"}], bk_biz_ids=[]
        )
        with mock.patch("bkmonitor.issue_merge.MergeResolverContext", return_value=ctx) as m:
            handler._expand_merged_issue_conditions()
        m.assert_not_called()
        assert handler.conditions[0]["value"] == ["a1"]

    def test_no_issue_condition_noop(self):
        handler = _handler([])
        with mock.patch("bkmonitor.issue_merge.MergeResolverContext") as m:
            handler._expand_merged_issue_conditions()
        m.assert_not_called()

    def test_scalar_value_wrapped_and_expanded(self):
        # value 为标量（非 list）时也应被包装后展开
        ctx = _make_ctx({"a1": [{"member_issue_id": "b1"}]}, {"b1": "a1"})
        handler = _handler([{"origin_key": "issue_id", "key": "issue_id", "value": "a1", "method": "eq"}])
        with mock.patch("bkmonitor.issue_merge.MergeResolverContext", return_value=ctx):
            handler._expand_merged_issue_conditions()
        assert set(handler.conditions[0]["value"]) == {"a1", "b1"}

    def test_relation_layer_exception_fail_open(self):
        # 关系层异常被吞掉、warning，不抛、不改原条件
        handler = _handler([{"origin_key": "issue_id", "key": "issue_id", "value": ["a1"], "method": "eq"}])
        boom = mock.Mock(side_effect=RuntimeError("relation layer down"))
        with mock.patch("bkmonitor.issue_merge.MergeResolverContext", boom):
            handler._expand_merged_issue_conditions()  # 不应抛
        assert handler.conditions[0]["value"] == ["a1"]

    def test_all_biz_query_uses_authorized_bizs(self):
        # 全业务查询：bk_biz_ids=[-1]，权限层解析出 authorized_bizs=[2, 3]。
        # 合并关系必须按 authorized_bizs 查（用 [-1] 查 IssueMergeRelation 会无结果，
        # 导致 TopN / histogram / 全业务列表的 issue_id 过滤漏掉 active members）。
        ctx = _make_ctx({"a1": [{"member_issue_id": "b1"}]}, {"b1": "a1"})
        handler = _handler(
            [{"origin_key": "issue_id", "key": "issue_id", "value": ["a1"], "method": "eq"}],
            bk_biz_ids=[-1],
            authorized_bizs=[2, 3],
        )
        captured = {}

        def _capture(biz):
            captured["biz"] = biz
            return ctx

        with mock.patch("bkmonitor.issue_merge.MergeResolverContext", side_effect=_capture):
            handler._expand_merged_issue_conditions()
        # 用 authorized_bizs 而非原始 [-1] 构造上下文
        assert captured["biz"] == [2, 3]
        # 展开生效
        assert set(handler.conditions[0]["value"]) == {"a1", "b1"}
