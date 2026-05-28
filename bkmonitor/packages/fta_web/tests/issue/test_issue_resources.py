"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

Issue 合并/拆分功能单测：覆盖 Resolver fast-path noop + 异常类 + content JSON 格式。
"""

import pytest

from bkmonitor.issue_merge import (
    IssueMergeResolver,
    MergeResolverContext,
)


class TestListMergeSourcesAnomalyMessage:
    """``_fetch_member_anomaly_messages`` 行为：

    1) 正常路径：terms agg + top_hits 返回 description → 命中的 member 进入结果字典
    2) 部分 member 无 alert → 不在结果字典（caller 兜底 ``"--"``）
    3) AlertDocument.search 抛异常 → 返回空 dict (fail-open)
    4) first_alert_time 全空 → 走 ``now - 30d`` 兜底窗口（不应抛异常）
    """

    @staticmethod
    def _build_search_stub(buckets: list, on_search=None):
        """构造一条链式可调用的 ES search stub，``buckets`` 即 ``result.aggs.issues.buckets``。"""
        from unittest.mock import MagicMock

        result = MagicMock()
        result.aggs.issues.buckets = buckets

        search_obj = MagicMock()
        search_obj.filter.return_value = search_obj
        search_obj.__getitem__.return_value.execute.return_value = result

        def _search(**kwargs):
            if on_search is not None:
                on_search(kwargs)
            return search_obj

        return _search, search_obj

    @staticmethod
    def _make_bucket(member_id: str, description: str | None):
        """模拟单个 issue_id terms 桶。``description=None`` 表示 top_hits 命中但 description 为空。"""
        from unittest.mock import MagicMock

        bucket = MagicMock()
        bucket.key = member_id
        if description is None:
            bucket.latest_alert.hits.hits = []
        else:
            hit = MagicMock()
            hit.to_dict.return_value = {"_source": {"event": {"description": description}}}
            bucket.latest_alert.hits.hits = [hit]
        return bucket

    def test_normal_path_returns_description_map(self, monkeypatch):
        from bkmonitor.documents import alert as alert_mod
        from fta_web.issue.resources import _fetch_member_anomaly_messages

        buckets = [
            self._make_bucket("b1", "AVG(CPU) >= 10%, 当前值 10.19%"),
            self._make_bucket("b2", "Disk IO 异常"),
        ]
        search_fn, _ = self._build_search_stub(buckets)
        monkeypatch.setattr(alert_mod.AlertDocument, "search", search_fn)

        result = _fetch_member_anomaly_messages(["b1", "b2"], {"b1": 1_700_000_000, "b2": 1_700_000_500})
        assert result == {
            "b1": "AVG(CPU) >= 10%, 当前值 10.19%",
            "b2": "Disk IO 异常",
        }

    def test_partial_miss_omits_member(self, monkeypatch):
        from bkmonitor.documents import alert as alert_mod
        from fta_web.issue.resources import _fetch_member_anomaly_messages

        # b1 命中、b2 top_hits 为空、b3 description 为空字符串：均不进入结果
        buckets = [
            self._make_bucket("b1", "CPU 异常"),
            self._make_bucket("b2", None),
            self._make_bucket("b3", ""),
        ]
        search_fn, _ = self._build_search_stub(buckets)
        monkeypatch.setattr(alert_mod.AlertDocument, "search", search_fn)

        result = _fetch_member_anomaly_messages(["b1", "b2", "b3"], {"b1": 1_700_000_000, "b2": 0, "b3": 0})
        assert result == {"b1": "CPU 异常"}

    def test_empty_member_ids_returns_empty(self):
        from fta_web.issue.resources import _fetch_member_anomaly_messages

        # 空入参不应触发 ES 查询，直接返回空 dict
        assert _fetch_member_anomaly_messages([], {}) == {}

    def test_search_exception_fail_open(self, monkeypatch):
        from bkmonitor.documents import alert as alert_mod
        from fta_web.issue.resources import _fetch_member_anomaly_messages

        def _explode(**kwargs):
            raise RuntimeError("ES cluster unreachable")

        monkeypatch.setattr(alert_mod.AlertDocument, "search", _explode)

        # fail-open：返回空 dict，由 caller 在 list_merge_sources 中兜底为 "--"
        assert _fetch_member_anomaly_messages(["b1"], {"b1": 1_700_000_000}) == {}

    def test_all_first_alert_time_empty_uses_fallback_window(self, monkeypatch):
        """所有 member 的 first_alert_time 为空（如旧数据）→ 走 now-30d 兜底窗口，不抛异常。"""
        from bkmonitor.documents import alert as alert_mod
        from fta_web.issue.resources import _MERGE_SOURCES_ANOMALY_FALLBACK_BUFFER, _fetch_member_anomaly_messages

        captured: dict = {}

        def _capture(kwargs):
            captured.update(kwargs)

        search_fn, _ = self._build_search_stub([self._make_bucket("b1", "fallback window hit")], on_search=_capture)
        monkeypatch.setattr(alert_mod.AlertDocument, "search", search_fn)

        result = _fetch_member_anomaly_messages(["b1"], {"b1": 0})
        assert result == {"b1": "fallback window hit"}
        # 兜底窗口 ≈ now - 30d；允许少量调用时延误差
        assert captured["end_time"] - captured["start_time"] == _MERGE_SOURCES_ANOMALY_FALLBACK_BUFFER


class TestSearchInjectsSplitInfo:
    """``IssueQueryHandler.search()`` 列表契约：被拆出的独立 Issue 注入 split_info。

    独立守护"search 流程真的会塞 split_info"——避免后续重构 search 时 resolver 单测仍过、
    但列表契约悄悄断裂。patch 掉 ES / 翻译 / 趋势等重链路，只验证注入这一刀。
    """

    @pytest.mark.skip(
        reason="跨层耦合：fta_web.issue.handlers 在 import 链上会 transitively 引入 "
        "alarm_backends.service.scheduler（模块级读取 worker-only 配置 DEFAULT_CRONTAB / "
        "ACTION_TASK_CRONTAB 等），纯 web 角色无法完成 import。待 feature owner 将该 import "
        "改为惰性或提供 web+worker 全栈测试配置后移除 skip。"
    )
    def test_split_member_injected_normal_untouched(self, monkeypatch):
        from unittest.mock import MagicMock

        from fta_web.alert.handlers import translator as translator_mod
        from fta_web.issue.handlers.issue import IssueQueryHandler

        # __new__ 跳过 BaseBizQueryHandler.__init__（避免触发 IAM 权限装配）
        handler = IssueQueryHandler.__new__(IssueQueryHandler)
        handler.bk_biz_ids = [2]

        issues = [{"id": "split-1", "bk_biz_id": 2}, {"id": "normal-1", "bk_biz_id": 2}]

        fake_result = MagicMock()
        fake_result.hits.total.value = len(issues)

        # patch 重链路：ES 查询 / 清洗 / 翻译 / 合并 ctx 加载 / 告警趋势
        monkeypatch.setattr(handler, "search_raw", lambda **kw: (fake_result, None))
        monkeypatch.setattr(handler, "handle_hit_list", lambda sr: issues)
        monkeypatch.setattr(handler, "add_alert_trend", lambda items: None)
        monkeypatch.setattr(translator_mod.StrategyTranslator, "translate_from_dict", lambda self, *a, **k: None)
        monkeypatch.setattr(translator_mod.BizTranslator, "translate_from_dict", lambda self, *a, **k: None)
        monkeypatch.setattr(MergeResolverContext, "load", lambda self: None)
        monkeypatch.setattr(
            IssueMergeResolver,
            "get_split_info_map",
            classmethod(
                lambda cls, ids: {
                    "split-1": {
                        "split_from_main_issue_id": "A",
                        "split_from_main_issue_name": None,
                        "split_reasons": ["误合并，根因不同"],
                        "split_kind": "manual",
                        "split_time": 1716580800,
                        "split_operator": "willgchen",
                    }
                }
            ),
        )

        result = handler.search()
        by_id = {i["id"]: i for i in result["issues"]}
        # 被拆出的独立 Issue 注入 split_info
        assert "split_info" in by_id["split-1"]
        assert by_id["split-1"]["split_info"]["split_reasons"] == ["误合并，根因不同"]
        # 普通 Issue 不注入
        assert "split_info" not in by_id["normal-1"]


class TestRunBatchFreezePropagation:
    """_run_batch：状态机冻结经 web→api 中转后以 BKAPIError 回来。

    custom_exception_handler 把 Error.extra **平铺到响应顶层**（result.update(exc.extra)），
    故 BKAPIError.data 顶层即带 business_code / conflicting_main_issue_id。web 侧须从顶层识别
    并回填 detail，供前端构造"跳主 Issue"引导。这里用真实平铺 payload 形状防回归。
    """

    def test_bkapi_error_flattened_payload_recognized(self):
        from core.errors.api import BKAPIError
        from fta_web.issue.resources import _run_batch

        # 模拟 api role custom_exception_handler 渲染：extra 平铺在 result_json 顶层
        result_json = {
            "result": False,
            "code": 3337109,
            "message": "Issue b1 已被合并到 #a1，请前往主 Issue 操作或先拆分",
            "data": None,
            "business_code": "MERGE_FREEZE_VIOLATION",
            "conflicting_main_issue_id": "a1",
            "issue_id": "b1",
        }

        def _action(bk_biz_id, issue_id):
            raise BKAPIError(system_name="bkmonitor.issue", url="resolve", result=result_json)

        out = _run_batch([{"bk_biz_id": 2, "issue_id": "b1"}], _action)
        assert out["succeeded"] == []
        assert len(out["failed"]) == 1
        failed = out["failed"][0]
        assert failed["issue_id"] == "b1"
        assert failed["code"] == "MERGE_FREEZE_VIOLATION"
        assert failed["detail"]["conflicting_main_issue_id"] == "a1"

    def test_bkapi_error_non_freeze_only_message(self):
        from core.errors.api import BKAPIError
        from fta_web.issue.resources import _run_batch

        result_json = {"result": False, "code": 3337104, "message": "其他业务错误"}

        def _action(bk_biz_id, issue_id):
            raise BKAPIError(system_name="bkmonitor.issue", url="resolve", result=result_json)

        out = _run_batch([{"bk_biz_id": 2, "issue_id": "x1"}], _action)
        failed = out["failed"][0]
        # 非冻结错误：只保留 message，不带 code/detail
        assert "code" not in failed
        assert "detail" not in failed
        assert failed["message"] == "其他业务错误"


class TestSplitReasonsOptional:
    """拆分依据 reasons 改为非必填：缺省 / 空列表均通过校验，validated_data 兜底为 []。

    下游 bulk_reset_for_split（reasons or []）、模型 split_reasons（null=True）、读侧
    split_info（split_reasons or []）本就容忍空，故只需放开两处 serializer。
    """

    # 合法 Issue ID：前 10 位为时间戳（IssueIDField → IssueDocument.parse_timestamp_by_id）
    VALID_ID = "1716000000abcdef01"

    def test_web_split_serializer_reasons_optional(self):
        from fta_web.issue.resources import SplitIssueResource

        s = SplitIssueResource.RequestSerializer(data={"bk_biz_id": 2, "member_issue_id": self.VALID_ID})
        assert s.is_valid(), s.errors
        assert s.validated_data["reasons"] == []
