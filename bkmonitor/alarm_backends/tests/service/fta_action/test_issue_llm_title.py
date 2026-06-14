"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import types

import pytest
from django.conf import settings

from alarm_backends.service.fta_action import llm_title
from alarm_backends.service.fta_action.issue_processor import IssueAggregationProcessor


class TestRenderUserPrompt:
    """占位符契约：必需/可选占位、缺省追加、整块注入、容错。"""

    def test_examples_placeholder_respected(self):
        """模板写了 {examples} 时按作者位置渲染，不追加。"""
        template = "头部\n{examples}\n日志：{log}\n"
        rendered = llm_title.render_user_prompt(template, log="LOG", examples_block="示例块")
        assert rendered == "头部\n示例块\n日志：LOG\n"

    def test_examples_missing_appended(self):
        """模板漏写 {examples} 且有示例时缺省追加到尾部，不浪费 few-shot 数据。"""
        template = "日志：{log}"
        rendered = llm_title.render_user_prompt(template, log="LOG", examples_block="示例块")
        assert rendered == "日志：LOG\n示例块"

    def test_examples_missing_and_empty_no_append(self):
        """无示例时不追加，也不残留段落头。"""
        rendered = llm_title.render_user_prompt("日志：{log}", log="LOG", examples_block="")
        assert rendered == "日志：LOG"

    def test_unknown_placeholder_kept_as_is(self):
        """业务模板写错变量不炸任务，未知占位符原样保留。"""
        rendered = llm_title.render_user_prompt("{not_a_var} {log}", log="LOG")
        assert rendered == "{not_a_var} LOG"

    def test_log_truncated(self):
        rendered = llm_title.render_user_prompt("{log}", log="x" * (llm_title.LOG_MAX_LEN + 100))
        assert len(rendered) == llm_title.LOG_MAX_LEN

    def test_adaptive_template_render(self):
        """内置自适应模板必须能用任务侧的全部上下文渲染且无占位符残留。"""
        rendered = llm_title.render_user_prompt(
            llm_title.ADAPTIVE_TEMPLATE,
            log="LOG",
            examples_block="",
            strategy_name="s",
            description="d",
            app="a",
            namespace="n",
            severity="ERROR",
            dimensions="{}",
        )
        assert "{log}" not in rendered
        assert "{examples}" not in rendered
        assert "{strategy_name}" not in rendered


class TestValidateBizTemplate:
    def test_missing_required_placeholder_rejected(self):
        with pytest.raises(ValueError):
            llm_title.validate_biz_template("没有日志占位符的模板")

    def test_empty_rejected(self):
        with pytest.raises(ValueError):
            llm_title.validate_biz_template("  ")

    def test_valid_template_passes(self):
        llm_title.validate_biz_template("任务说明 {log}")

    def test_non_str_rejected_as_value_error(self):
        # 误配成旧结构 {alert_type: 模板} 这种 dict，必须抛 ValueError（非 AttributeError），
        # 否则 resolve_template 只 catch ValueError 会漏，任务崩溃。
        for bad in ({"default": "x {log}"}, ["x"], 123, None):
            with pytest.raises(ValueError):
                llm_title.validate_biz_template(bad)


class TestResolveTemplate:
    def test_builtin_when_no_biz_template(self, monkeypatch):
        monkeypatch.setattr(settings, "ISSUE_LLM_TITLE_BIZ_TEMPLATES", {}, raising=False)
        assert llm_title.resolve_template(2) == llm_title.ADAPTIVE_TEMPLATE

    def test_biz_template_first(self, monkeypatch):
        monkeypatch.setattr(settings, "ISSUE_LLM_TITLE_BIZ_TEMPLATES", {"2": "业务模板 {log}"}, raising=False)
        assert llm_title.resolve_template(2) == "业务模板 {log}"
        assert llm_title.resolve_template(3) == llm_title.ADAPTIVE_TEMPLATE  # 其它业务退内置

    def test_invalid_biz_template_falls_back_builtin(self, monkeypatch):
        """业务模板缺必需占位符时跳过该层，不阻塞生成。"""
        monkeypatch.setattr(settings, "ISSUE_LLM_TITLE_BIZ_TEMPLATES", {"2": "缺日志占位"}, raising=False)
        assert llm_title.resolve_template(2) == llm_title.ADAPTIVE_TEMPLATE

    def test_dict_biz_template_falls_back_not_crash(self, monkeypatch):
        """误配成旧的嵌套 dict 结构时 resolve_template 不崩溃，安全 fallback 内置（P2 回归）。"""
        monkeypatch.setattr(settings, "ISSUE_LLM_TITLE_BIZ_TEMPLATES", {"2": {"default": "x {log}"}}, raising=False)
        assert llm_title.resolve_template(2) == llm_title.ADAPTIVE_TEMPLATE


class TestSetBizTemplate:
    """django shell 快速配置辅助。重点保证合并不抹掉其他业务（直接赋值的 footgun）。"""

    def test_example_constant_is_valid(self):
        # 范例常量本身必须能过校验，否则误导使用者
        llm_title.validate_biz_template(llm_title.EXAMPLE_BIZ_TEMPLATE)

    def test_merge_keeps_other_biz(self, monkeypatch):
        monkeypatch.setattr(settings, "ISSUE_LLM_TITLE_BIZ_TEMPLATES", {"2": "旧 {log}"}, raising=False)
        result = llm_title.set_biz_template(3, "新模板 {log}")
        assert result == {"2": "旧 {log}", "3": "新模板 {log}"}
        assert settings.ISSUE_LLM_TITLE_BIZ_TEMPLATES["2"] == "旧 {log}"  # 未被抹掉

    def test_delete_removes_only_target(self, monkeypatch):
        monkeypatch.setattr(settings, "ISSUE_LLM_TITLE_BIZ_TEMPLATES", {"2": "a {log}", "3": "b {log}"}, raising=False)
        result = llm_title.set_biz_template(3)  # 不传模板 = 删除
        assert result == {"2": "a {log}"}

    def test_invalid_template_rejected_before_write(self, monkeypatch):
        monkeypatch.setattr(settings, "ISSUE_LLM_TITLE_BIZ_TEMPLATES", {"2": "a {log}"}, raising=False)
        with pytest.raises(ValueError):
            llm_title.set_biz_template(3, "缺日志占位")  # 缺 {log}
        assert settings.ISSUE_LLM_TITLE_BIZ_TEMPLATES == {"2": "a {log}"}  # 写入前就拒绝，无副作用

    def test_preview_uses_effective_template(self, monkeypatch):
        monkeypatch.setattr(settings, "ISSUE_LLM_TITLE_BIZ_TEMPLATES", {"2": "业务模板 头部\n{log}"}, raising=False)
        out = llm_title.preview_biz_template(2, sample_log="样例日志行")
        assert "业务模板 头部" in out and "样例日志行" in out


class TestValidateTitle:
    def test_normal(self):
        assert (
            llm_title.validate_title("svc 调用 Foo 失败：ErrNotExist(10086)") == "svc 调用 Foo 失败：ErrNotExist(10086)"
        )

    def test_strip_quotes_and_spaces(self):
        assert llm_title.validate_title('  "标题"  ') == "标题"

    def test_multiline_rejected(self):
        assert llm_title.validate_title("第一行\n第二行") == ""

    def test_md5_rejected(self):
        assert llm_title.validate_title("出现新类 a4090f2c1e4046756113421665b8dbfd") == ""

    def test_ip_rejected(self):
        assert llm_title.validate_title("调用 10.0.0.1 失败") == ""

    def test_trace_id_rejected(self):
        assert llm_title.validate_title("trace 673c4ed76679bb15 异常") == ""

    def test_truncated_to_max_len(self):
        assert len(llm_title.validate_title("标" * 200)) == llm_title.TITLE_MAX_LEN

    def test_empty_rejected(self):
        assert llm_title.validate_title("") == ""
        assert llm_title.validate_title("   ") == ""


class _FakeRedis:
    def __init__(self, data=None):
        self.data = data or {}

    def get(self, key):
        return self.data.get(key)


class TestResolveExamples:
    @pytest.fixture(autouse=True)
    def _patch_clients(self, monkeypatch):
        from alarm_backends.core.cache import key as cache_key

        # client 是 RedisDataKey 的类级 property（数据描述符），类层 patch 对两级 key 同时生效；
        # strategy/biz 两级共用一个 fake 存储，靠 key 模板前缀天然区分
        self.store = _FakeRedis()
        monkeypatch.setattr(type(cache_key.ISSUE_LLM_EXAMPLES_STRATEGY_KEY), "client", property(lambda s: self.store))
        self.strategy_key = cache_key.ISSUE_LLM_EXAMPLES_STRATEGY_KEY.get_key(strategy_id="100")
        self.biz_key = cache_key.ISSUE_LLM_EXAMPLES_BIZ_KEY.get_key(bk_biz_id="2")

    def test_strategy_level_hit(self):
        self.store.data[self.strategy_key] = json.dumps(["标题A", "标题B"])
        block, source = llm_title.resolve_examples("100", "2")
        assert source == "strategy"
        assert "标题A" in block and "参考示例" in block

    def test_biz_level_fallback(self):
        self.store.data[self.biz_key] = json.dumps(["业务标题"])
        block, source = llm_title.resolve_examples("100", "2")
        assert source == "biz"
        assert "业务标题" in block

    def test_static_on_miss(self):
        block, source = llm_title.resolve_examples("100", "2")
        assert source == "static"
        assert block == ""

    def test_static_on_broken_payload(self):
        self.store.data[self.strategy_key] = "not json"
        block, source = llm_title.resolve_examples("100", "2")
        assert source == "static"

    def test_examples_capped(self):
        self.store.data[self.strategy_key] = json.dumps([f"标题{i}" for i in range(10)])
        block, _ = llm_title.resolve_examples("100", "2")
        assert block.count("- 标题") == llm_title.MAX_AUTO_EXAMPLES


class TestBizWhiteList:
    def test_empty_means_disabled(self, monkeypatch):
        monkeypatch.setattr(settings, "ISSUE_LLM_TITLE_BIZ_WHITE_LIST", [], raising=False)
        assert llm_title.is_llm_title_enabled_for_biz(2) is False

    def test_minus_one_means_all(self, monkeypatch):
        monkeypatch.setattr(settings, "ISSUE_LLM_TITLE_BIZ_WHITE_LIST", [-1], raising=False)
        assert llm_title.is_llm_title_enabled_for_biz(999) is True

    def test_hit_and_miss(self, monkeypatch):
        monkeypatch.setattr(settings, "ISSUE_LLM_TITLE_BIZ_WHITE_LIST", ["2"], raising=False)
        assert llm_title.is_llm_title_enabled_for_biz(2) is True
        assert llm_title.is_llm_title_enabled_for_biz(3) is False

    def test_invalid_values_disabled(self, monkeypatch):
        monkeypatch.setattr(settings, "ISSUE_LLM_TITLE_BIZ_WHITE_LIST", ["abc"], raising=False)
        assert llm_title.is_llm_title_enabled_for_biz(2) is False


class TestDispatchGate:
    """issue_processor 派发闸门：env 不存在零行为；env + 白名单命中才 apply_async。"""

    def _build_processor(self):
        alert = types.SimpleNamespace(id="17000000001", strategy_id="100", severity=2)
        strategy = {"id": 100, "bk_biz_id": 2, "name": "s"}
        return IssueAggregationProcessor(alert, strategy)

    def _fake_issue(self):
        return types.SimpleNamespace(id="issue1", bk_biz_id="2", name="默认名")

    def test_env_unset_no_dispatch(self, monkeypatch):
        monkeypatch.delenv("ENABLE_ISSUE_LLM_TITLE", raising=False)
        calls = []
        monkeypatch.setattr(
            "alarm_backends.service.fta_action.tasks.issue_tasks.generate_issue_llm_title",
            types.SimpleNamespace(apply_async=lambda **kw: calls.append(kw)),
        )
        self._build_processor()._maybe_dispatch_llm_title(self._fake_issue())
        assert calls == []

    def test_env_set_biz_not_in_white_list(self, monkeypatch):
        monkeypatch.setenv("ENABLE_ISSUE_LLM_TITLE", "true")
        monkeypatch.setattr(settings, "ISSUE_LLM_TITLE_BIZ_WHITE_LIST", [], raising=False)
        calls = []
        monkeypatch.setattr(
            "alarm_backends.service.fta_action.tasks.issue_tasks.generate_issue_llm_title",
            types.SimpleNamespace(apply_async=lambda **kw: calls.append(kw)),
        )
        self._build_processor()._maybe_dispatch_llm_title(self._fake_issue())
        assert calls == []

    def test_env_set_biz_hit_dispatches(self, monkeypatch):
        monkeypatch.setenv("ENABLE_ISSUE_LLM_TITLE", "true")
        monkeypatch.setattr(settings, "ISSUE_LLM_TITLE_BIZ_WHITE_LIST", [2], raising=False)
        calls = []
        monkeypatch.setattr(
            "alarm_backends.service.fta_action.tasks.issue_tasks.generate_issue_llm_title",
            types.SimpleNamespace(apply_async=lambda **kw: calls.append(kw)),
        )
        self._build_processor()._maybe_dispatch_llm_title(self._fake_issue())
        assert len(calls) == 1
        kwargs = calls[0]["kwargs"]
        assert kwargs == {"issue_id": "issue1", "bk_biz_id": "2", "default_name": "默认名", "alert_id": "17000000001"}

    def test_dispatch_failure_swallowed(self, monkeypatch):
        """派发异常不冒泡：标题生成失败不影响 Issue 主链路。"""
        monkeypatch.setenv("ENABLE_ISSUE_LLM_TITLE", "true")
        monkeypatch.setattr(settings, "ISSUE_LLM_TITLE_BIZ_WHITE_LIST", [-1], raising=False)

        def _boom(**kwargs):
            raise RuntimeError("broker down")

        monkeypatch.setattr(
            "alarm_backends.service.fta_action.tasks.issue_tasks.generate_issue_llm_title",
            types.SimpleNamespace(apply_async=_boom),
        )
        self._build_processor()._maybe_dispatch_llm_title(self._fake_issue())  # 不抛即通过


class _FakeMeta:
    def __init__(self, id):
        self.id = id


class _FakeHit:
    def __init__(self, id, name=None, strategy_id="", bk_biz_id=""):
        self.meta = _FakeMeta(id)
        if name is not None:
            self.name = name
        self.strategy_id = strategy_id
        self.bk_biz_id = bk_biz_id


class TestCollectExampleGroups:
    """周期任务筛选规则（纯函数）：未改回校验 / 禁项清洗 / 分组去重。"""

    def _collect(self, latest, hits):
        from alarm_backends.service.fta_action.tasks.issue_tasks import _collect_example_groups

        return _collect_example_groups(latest, hits)

    def test_reverted_rename_dropped(self):
        """issue 当前 name 与最新改名值不一致（被改回/再次修改）→ 丢弃。"""
        by_s, by_b = self._collect({"i1": "新标题"}, [_FakeHit("i1", name="旧标题", strategy_id="100", bk_biz_id="2")])
        assert not by_s and not by_b

    def test_kept_rename_grouped(self):
        by_s, by_b = self._collect({"i1": "新标题"}, [_FakeHit("i1", name="新标题", strategy_id="100", bk_biz_id="2")])
        assert by_s == {"100": ["新标题"]}
        assert by_b == {"2": ["新标题"]}

    def test_forbidden_title_cleaned_out(self):
        """含 md5 的用户改名不进示例区（不可信输入入缓存前清洗）。"""
        bad = "标题 a4090f2c1e4046756113421665b8dbfd"
        by_s, by_b = self._collect({"i1": bad}, [_FakeHit("i1", name=bad, strategy_id="100", bk_biz_id="2")])
        assert not by_s and not by_b

    def test_dedupe_within_group(self):
        hits = [
            _FakeHit("i1", name="同标题", strategy_id="100", bk_biz_id="2"),
            _FakeHit("i2", name="同标题", strategy_id="100", bk_biz_id="2"),
        ]
        by_s, by_b = self._collect({"i1": "同标题", "i2": "同标题"}, hits)
        assert by_s == {"100": ["同标题"]}
        assert by_b == {"2": ["同标题"]}


class TestGenerateIssueLlmTitleBranches:
    """任务体关键分支：shadow / CAS / 限流 / 无效输出。重依赖全 mock，不触 ES/网关。"""

    @pytest.fixture(autouse=True)
    def _patch_world(self, monkeypatch):
        from alarm_backends.service.fta_action import llm_title as lt
        from alarm_backends.service.fta_action.tasks import issue_tasks as it
        from core.prometheus import metrics as prom_metrics

        self.renames = []
        fake_alert = types.SimpleNamespace(
            strategy={"id": 100, "bk_biz_id": 2},
            strategy_id="100",
            alert_name="策略名",
            event=types.SimpleNamespace(description="desc"),
            origin_alarm={"data": {"dimensions": {"app": "svc", "namespace": "ns", "severity_text": "ERROR"}}},
        )
        monkeypatch.setattr(it.AlertDocument, "get", classmethod(lambda cls, _id: fake_alert))
        monkeypatch.setattr(
            "bkmonitor.utils.event_related_info.get_alert_relation_info",
            lambda alert, length_limit=False: '{"log": "ERROR demo failed: ErrX(1)"}',
        )
        monkeypatch.setattr(lt, "acquire_rate_limit_token", lambda biz: True)
        monkeypatch.setattr(lt, "resolve_examples", lambda s, b: ("", "static"))
        self.llm_reply = {"choices": [{"message": {"content": "svc 调用 demo 失败：ErrX(1)"}}]}
        from core.drf_resource import api as drf_api

        monkeypatch.setattr(
            drf_api, "aidev", types.SimpleNamespace(chat_completion=lambda **kw: self.llm_reply), raising=False
        )
        monkeypatch.setattr(prom_metrics, "report_all", lambda *a, **kw: None)
        fake_issue = types.SimpleNamespace(
            name="默认名", rename=lambda title, operator: self.renames.append((title, operator))
        )
        self.fake_issue = fake_issue
        monkeypatch.setattr(it.IssueDocument, "get_issue_or_raise", classmethod(lambda cls, *a, **kw: fake_issue))
        monkeypatch.setattr(settings, "ISSUE_LLM_TITLE_SHADOW", True, raising=False)
        self.lt = lt
        self.it = it
        self.monkeypatch = monkeypatch

    def _run(self):
        self.it.generate_issue_llm_title("issue1", 2, "默认名", "17000000001")

    def test_shadow_mode_no_write(self):
        self._run()
        assert self.renames == []

    def test_write_when_shadow_off(self):
        self.monkeypatch.setattr(settings, "ISSUE_LLM_TITLE_SHADOW", False, raising=False)
        self._run()
        assert self.renames == [("svc 调用 demo 失败：ErrX(1)", "system")]

    def test_cas_name_changed_no_write(self):
        self.monkeypatch.setattr(settings, "ISSUE_LLM_TITLE_SHADOW", False, raising=False)
        self.fake_issue.name = "用户已改名"
        self._run()
        assert self.renames == []

    def test_ratelimited_no_llm_call(self):
        calls = []
        self.monkeypatch.setattr(self.lt, "acquire_rate_limit_token", lambda biz: False)
        from core.drf_resource import api as drf_api

        self.monkeypatch.setattr(
            drf_api, "aidev", types.SimpleNamespace(chat_completion=lambda **kw: calls.append(1)), raising=False
        )
        self._run()
        assert calls == [] and self.renames == []

    def test_invalid_output_no_write(self):
        self.monkeypatch.setattr(settings, "ISSUE_LLM_TITLE_SHADOW", False, raising=False)
        self.llm_reply["choices"][0]["message"]["content"] = "第一行\n第二行"
        self._run()
        assert self.renames == []

    def test_regression_prefix_kept(self):
        self.monkeypatch.setattr(settings, "ISSUE_LLM_TITLE_SHADOW", False, raising=False)
        self.it.generate_issue_llm_title("issue1", 2, "[回归] 默认名", "17000000001")
        # CAS 比较用创建时默认名，fake issue.name 需同步
        assert self.renames == []  # name(默认名) != default_name([回归] 默认名) -> name_changed

    def test_regression_prefix_written(self):
        self.monkeypatch.setattr(settings, "ISSUE_LLM_TITLE_SHADOW", False, raising=False)
        self.fake_issue.name = "[回归] 默认名"
        self.it.generate_issue_llm_title("issue1", 2, "[回归] 默认名", "17000000001")
        assert self.renames and self.renames[0][0].startswith("[回归] ")


class TestRefreshExamplesGate:
    """周期任务白名单门控：功能未开启（白名单空）时零 ES 副作用。"""

    def test_skipped_when_white_list_empty(self, monkeypatch):
        from alarm_backends.service.fta_action.tasks import issue_tasks as it
        from bkmonitor.documents.issue import IssueActivityDocument

        monkeypatch.setattr(settings, "ISSUE_LLM_TITLE_BIZ_WHITE_LIST", [], raising=False)
        called = []
        monkeypatch.setattr(IssueActivityDocument, "search", classmethod(lambda cls, **kw: called.append(1)))
        it.refresh_issue_llm_title_examples()
        assert called == []  # 白名单空 → 在 ES 查询前就 return

    def test_enters_query_when_white_list_set(self, monkeypatch):
        from alarm_backends.service.fta_action.tasks import issue_tasks as it
        from bkmonitor.documents.issue import IssueActivityDocument

        monkeypatch.setattr(settings, "ISSUE_LLM_TITLE_BIZ_WHITE_LIST", [2], raising=False)
        marker = []

        def fake_search(cls, **kw):
            marker.append(1)
            raise RuntimeError("stop")  # 任务体 try/except 会吞掉，仅验证进入查询段

        monkeypatch.setattr(IssueActivityDocument, "search", classmethod(fake_search))
        it.refresh_issue_llm_title_examples()
        assert marker == [1]


class TestChatCompletionResourceContract:
    """api.aidev.ChatCompletionResource 的 endpoint/凭据契约（防回退到 403 的 appspace 旧路径）。

    背景：get_llm(BLUEKING) 走 /appspace/gateway/llm/v1（平台自身 app bkmonitorv3，对目标模型 403）；
    本 Resource 必须走 /openapi/aidev/gateway/llm/v1 + AIDEV_AGENT 凭据——该 URL 经 django shell 实测
    可用，且与 bkte 后台 env BK_AIDEV_AGENT_LLM_GW_ENDPOINT 一致。本测试固化此契约。
    """

    def _cls(self):
        from api.aidev.default import ChatCompletionResource

        return ChatCompletionResource

    def test_endpoint_is_openapi_not_appspace(self):
        cls = self._cls()
        assert cls.action == "/openapi/aidev/gateway/llm/v1/chat/completions"
        assert "appspace" not in cls.action  # 防误改回 403 的旧路径

    def test_openai_format_contract(self):
        cls = self._cls()
        assert cls.IS_STANDARD_FORMAT is False  # OpenAI 响应非蓝鲸 {result,code,data} 信封，整体透传
        assert cls.INSERT_BK_USERNAME_TO_REQUEST_DATA is False  # 不向 OpenAI messages 注入 bk_username
        assert cls.method == "POST"

    def test_headers_use_aidev_agent_credentials(self, monkeypatch):
        from api.aidev.default import AidevAPIGWResource, ChatCompletionResource

        monkeypatch.setattr(settings, "AIDEV_AGENT_APP_CODE", "aidev-bkmonitor", raising=False)
        monkeypatch.setattr(settings, "AIDEV_AGENT_APP_SECRET", "secret-x", raising=False)
        # 父类返回平台自身 app 的 header，子类应覆盖成 AIDEV_AGENT 凭据
        monkeypatch.setattr(
            AidevAPIGWResource,
            "get_headers",
            lambda self: {"x-bkapi-authorization": json.dumps({"bk_app_code": "bkmonitorv3", "bk_app_secret": "old"})},
        )
        headers = ChatCompletionResource.__new__(ChatCompletionResource).get_headers()
        auth = json.loads(headers["x-bkapi-authorization"])
        assert auth["bk_app_code"] == "aidev-bkmonitor"  # 用 agent 凭据，不是平台自身（后者 403）
        assert auth["bk_app_secret"] == "secret-x"

    def test_headers_fallback_when_no_agent_credentials(self, monkeypatch):
        from api.aidev.default import AidevAPIGWResource, ChatCompletionResource

        monkeypatch.setattr(settings, "AIDEV_AGENT_APP_CODE", "", raising=False)
        monkeypatch.setattr(settings, "AIDEV_AGENT_APP_SECRET", "", raising=False)
        base = {"x-bkapi-authorization": json.dumps({"bk_app_code": "plat", "bk_app_secret": "p"})}
        monkeypatch.setattr(AidevAPIGWResource, "get_headers", lambda self: dict(base))
        headers = ChatCompletionResource.__new__(ChatCompletionResource).get_headers()
        # 未配 agent 凭据时不覆盖，沿用父类（不报错）
        assert json.loads(headers["x-bkapi-authorization"])["bk_app_code"] == "plat"
