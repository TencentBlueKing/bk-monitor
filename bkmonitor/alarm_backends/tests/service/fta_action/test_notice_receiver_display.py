"""
通知接收人展示名回归测试

覆盖缺陷：处理记录「具体信息」列显示「发送邮件告警通知给 <bk_username> 成功」，
把通知接收人的用户标识直接渲染进了文案。

根因在 ActionInstance.get_content：content_template 渲染时上下文里的 notice_receiver
仍是用户标识原文，模板 {{notice_receiver}} 因此原样输出标识。

本文件为纯逻辑测试，不依赖数据库：ActionInstance 通过 __new__ 构造，
所需的模型字段直接赋值，不触发 DB 查询。
"""

import datetime
import json
from pathlib import Path
from unittest.mock import MagicMock

from bkmonitor.models.fta.action import ActionInstance
from constants.action import ActionPluginType, ActionSignal, ActionStatus
from core.errors.api import BKAPIError

MODULE = "bkmonitor.utils.user"

# 库中已存的 config_schema 快照与用户自定义模板用的仍是 {{notice_receiver}}
LEGACY_TEMPLATE = "发送{{notice_way_display}}告警通知给{{notice_receiver}}{{status_display}}"
# 本次改动后内置模板使用 {{notice_receiver_display}}
NEW_TEMPLATE = "发送{{notice_way_display}}告警通知给{{notice_receiver_display}}{{status_display}}"


def make_action(inputs=None, content_template=LEGACY_TEMPLATE):
    """构造一个不触发 DB 访问的 ActionInstance"""
    action = ActionInstance.__new__(ActionInstance)
    action.id = 1
    action.inputs = {"notice_receiver": ["uid_a"], "notice_way": "mail"} if inputs is None else inputs
    action.outputs = {}
    action.status = ActionStatus.SUCCESS
    action.signal = ActionSignal.ABNORMAL
    action.is_parent_action = False
    action.action_config = {"name": "通知"}
    action.action_config_id = 0
    action.action_plugin = {
        "plugin_type": ActionPluginType.NOTICE,
        "plugin_key": ActionPluginType.NOTICE,
        "config_schema": {"content_template": content_template},
    }
    action.bk_biz_id = 100
    action.create_time = datetime.datetime(2026, 11, 12, 9, 38, 31)
    return action


def patch_display_name(monkeypatch, mapping=None, side_effect=None, bk_tenant_id="tenant_demo"):
    """
    替换展示名转换，个人接口与批量接口一起 mock

    多接收人走批量接口、单接收人走个人接口，两边都要替换，
    否则用例会因为走的是另一条路径而拿到原值。
    """
    from django.conf import settings

    mapping = mapping or {}

    def _convert(username, bk_tenant_id=None):
        if side_effect is not None:
            return side_effect(username)
        return mapping.get(username, username)

    def _batch(bk_usernames=None, bk_tenant_id=None):
        return [
            {"bk_username": name, "display_name": _convert(name, bk_tenant_id=bk_tenant_id)}
            for name in bk_usernames or []
        ]

    monkeypatch.setattr(settings, "ENABLE_MULTI_TENANT_MODE", True)
    monkeypatch.setattr("bkmonitor.utils.tenant.bk_biz_id_to_bk_tenant_id", lambda biz_id: bk_tenant_id)
    monkeypatch.setattr(f"{MODULE}.get_user_display_name", _convert)
    monkeypatch.setattr("core.drf_resource.api.bk_login.batch_query_user_display_info", _batch)


class TestGetNoticeReceiverDisplay:
    """get_notice_receiver_display 方法本身"""

    def test_scalar_receiver_converted(self, monkeypatch):
        patch_display_name(monkeypatch, {"uid_a": "张三"})
        action = make_action()

        assert action.get_notice_receiver_display("uid_a") == "张三"

    def test_chat_receiver_not_converted(self, monkeypatch):
        """群机器人的接收人是 chatid，不是用户标识，不做转换"""
        patch_display_name(monkeypatch, {"chatid": "不该出现的展示名"})
        action = make_action(inputs={"notice_receiver": ["chatid"], "notice_way": "wxwork-bot"})

        assert action.get_notice_receiver_display(["chatid"]) == "chatid"

    def test_rtx_alias_converted(self, monkeypatch):
        """
        rtx 是企业微信的历史别名，等价于 qy_weixin，其接收人是用户标识

        rtx 不在 NoticeWayChannel.MAPPING 的键里，直接查表会得到 None，
        若按「查不到就当会话渠道」处理会漏转，必须先经 NoticeWay.ALIASES 归一化。
        """
        patch_display_name(monkeypatch, {"uid_a": "张三"})
        action = make_action(inputs={"notice_receiver": ["uid_a"], "notice_way": "rtx"})

        assert action.get_notice_receiver_display(["uid_a"]) == "张三"

    def test_unknown_notice_way_converted(self, monkeypatch):
        """未知渠道按用户标识处理，漏转比多查一次的代价更大"""
        patch_display_name(monkeypatch, {"uid_a": "张三"})
        action = make_action(inputs={"notice_receiver": ["uid_a"], "notice_way": "__none__"})

        assert action.get_notice_receiver_display(["uid_a"]) == "张三"

    def test_bkchat_receiver_not_converted(self, monkeypatch):
        """蓝鲸信息流的接收人同样是会话 ID"""
        patch_display_name(monkeypatch, {"chatid": "不该出现的展示名"})
        action = make_action(inputs={"notice_receiver": ["chatid"], "notice_way": "bkchat"})

        assert action.get_notice_receiver_display(["chatid"]) == "chatid"

    def test_bkchat_subchannel_receiver_not_converted(self, monkeypatch):
        """bkchat|mail / bkchat|wxwork-bot 等子渠道的接收人是群组 ID，不应误当用户标识查询"""
        called = []

        def _unexpected(*args, **kwargs):
            called.append((args, kwargs))
            return "不该出现的展示名"

        patch_display_name(monkeypatch, side_effect=_unexpected)
        for notice_way in ("bkchat|mail", "bkchat|wxwork-bot", "bkchat|SLACK"):
            action = make_action(inputs={"notice_receiver": ["1"], "notice_way": notice_way})
            assert action.get_notice_receiver_display(["1"]) == "1"

        assert called == []

    def test_none_inputs_tolerated(self, monkeypatch):
        """inputs 为 None 时直接调用 get_notice_receiver_display 不应抛 AttributeError"""
        patch_display_name(monkeypatch, {"uid_a": "张三"})
        action = make_action(inputs=None)
        action.inputs = None

        assert action.get_notice_receiver_display("uid_a") == "张三"

    def test_list_receiver_joined_with_comma(self, monkeypatch):
        patch_display_name(monkeypatch, {"uid_a": "张三", "uid_b": "李四"})
        action = make_action()

        assert action.get_notice_receiver_display(["uid_a", "uid_b"]) == "张三,李四"

    def test_multi_receiver_uses_batch_api(self, monkeypatch, settings):
        """多接收人走批量接口，避免逐个请求"""
        calls = []

        def _batch(bk_usernames=None, bk_tenant_id=None):
            calls.append((list(bk_usernames), bk_tenant_id))
            return [{"bk_username": name, "display_name": f"名字_{name}"} for name in bk_usernames]

        settings.ENABLE_MULTI_TENANT_MODE = True
        monkeypatch.setattr("bkmonitor.utils.tenant.bk_biz_id_to_bk_tenant_id", lambda biz_id: "tenant_demo")
        monkeypatch.setattr("core.drf_resource.api.bk_login.batch_query_user_display_info", _batch)
        action = make_action(inputs={"notice_receiver": ["uid_a", "uid_b", "uid_c"], "notice_way": "mail"})

        assert action.get_notice_receiver_display(["uid_a", "uid_b", "uid_c"]) == "名字_uid_a,名字_uid_b,名字_uid_c"
        assert calls == [(["uid_a", "uid_b", "uid_c"], "tenant_demo")]

    def test_batch_api_failure_falls_back_to_raw(self, monkeypatch, settings):
        """批量接口异常时整体回退原值，文案结构不破坏"""

        def _raise(bk_usernames=None, bk_tenant_id=None):
            raise BKAPIError("bk-user unavailable")

        settings.ENABLE_MULTI_TENANT_MODE = True
        monkeypatch.setattr("bkmonitor.utils.tenant.bk_biz_id_to_bk_tenant_id", lambda biz_id: "tenant_demo")
        monkeypatch.setattr("core.drf_resource.api.bk_login.batch_query_user_display_info", _raise)
        action = make_action(inputs={"notice_receiver": ["uid_a", "uid_b"], "notice_way": "mail"})

        assert action.get_notice_receiver_display(["uid_a", "uid_b"]) == "uid_a,uid_b"

    def test_batch_api_partial_miss_falls_back_per_item(self, monkeypatch, settings):
        """批量接口只返回部分用户时，查不到的逐个回退原值"""
        settings.ENABLE_MULTI_TENANT_MODE = True
        monkeypatch.setattr("bkmonitor.utils.tenant.bk_biz_id_to_bk_tenant_id", lambda biz_id: "tenant_demo")
        monkeypatch.setattr(
            "core.drf_resource.api.bk_login.batch_query_user_display_info",
            lambda bk_usernames=None, bk_tenant_id=None: [{"bk_username": "uid_a", "display_name": "张三"}],
        )
        action = make_action(inputs={"notice_receiver": ["uid_a", "uid_b"], "notice_way": "mail"})

        assert action.get_notice_receiver_display(["uid_a", "uid_b"]) == "张三,uid_b"

    def test_empty_receiver_kept(self, monkeypatch):
        patch_display_name(monkeypatch)
        action = make_action()

        assert action.get_notice_receiver_display([]) == []
        assert action.get_notice_receiver_display(None) is None
        assert action.get_notice_receiver_display("") == ""

    def test_empty_items_in_list_filtered(self, monkeypatch):
        """列表里的空值不应拼出连续逗号"""
        patch_display_name(monkeypatch, {"uid_a": "张三"})
        action = make_action()

        assert action.get_notice_receiver_display(["uid_a", "", None]) == "张三"

    def test_conversion_failure_falls_back_to_raw(self, monkeypatch):
        """转换抛异常时回退原值，不能影响文案生成"""

        def _raise(username):
            raise BKAPIError("bk-user unavailable")

        patch_display_name(monkeypatch, side_effect=_raise)
        action = make_action()

        assert action.get_notice_receiver_display("uid_a") == "uid_a"

    def test_batch_failure_falls_back_all(self, monkeypatch):
        """
        批量接口整体失败时全部回退原值

        逐人转换时单个失败只影响本人，改批量后一次请求覆盖整批，
        失败即整批回退。取舍：多接收人场景（语音串行通知会把整个用户组并进来）
        从 N 次请求降到 1 次，代价是接口整体异常时这一条文案全部显示标识。
        属可接受降级：有 warning 日志，且文案结构不变。
        """

        def _convert(username):
            if username == "uid_b":
                raise BKAPIError("bk-user unavailable")
            return "张三"

        patch_display_name(monkeypatch, side_effect=_convert)
        action = make_action()

        assert action.get_notice_receiver_display(["uid_a", "uid_b"]) == "uid_a,uid_b"

    def test_origin_input_untouched(self, monkeypatch):
        """
        只产出展示名，不改 inputs 里的标识

        notice_receiver 同时是审计事实（通知实际发给了谁）与 ES operator 字段的数据源，
        就地改写会让这些链路丢失可追溯性。
        """
        patch_display_name(monkeypatch, {"uid_a": "张三"})
        action = make_action()

        action.get_notice_receiver_display(action.inputs["notice_receiver"])

        assert action.inputs["notice_receiver"] == ["uid_a"]


class TestGetContentRender:
    """get_content 渲染出的文案使用展示名"""

    def test_new_template_shows_display_name(self, monkeypatch):
        patch_display_name(monkeypatch, {"uid_a": "张三"})
        action = make_action(content_template=NEW_TEMPLATE)

        text = action.get_content(notice_way_display="邮件", status_display="成功")["text"]

        assert text == "发送邮件告警通知给张三成功"

    def test_legacy_template_keeps_identifier(self, monkeypatch):
        """
        存量模板仍然渲染标识

        notice_receiver 变量本身不改值（保留列表类型与审计原文），
        因此只有切到 {{notice_receiver_display}} 的模板才会显示展示名。
        库里的插件记录由 post_migrate 时 register_builtin_plugins 按初始文件覆盖更新。
        """
        patch_display_name(monkeypatch, {"uid_a": "张三"})
        action = make_action(content_template=LEGACY_TEMPLATE)

        text = action.get_content(notice_way_display="邮件", status_display="成功")["text"]

        assert text == "发送邮件告警通知给['uid_a']成功"

    def test_list_type_preserved_for_custom_templates(self, monkeypatch):
        """变量类型不变，自定义模板用 join / 迭代不会按字符拆分"""
        patch_display_name(monkeypatch, {"uid_a": "张三", "uid_b": "李四"})
        action = make_action(
            inputs={"notice_receiver": ["uid_a", "uid_b"], "notice_way": "mail"},
            content_template="接收人：{{notice_receiver | join('/')}}",
        )

        text = action.get_content(notice_way_display="邮件", status_display="成功")["text"]

        assert text == "接收人：uid_a/uid_b"

    def test_display_variable_usable_in_custom_template(self, monkeypatch):
        """自定义模板可自行改用展示名变量"""
        patch_display_name(monkeypatch, {"uid_a": "张三", "uid_b": "李四"})
        action = make_action(
            inputs={"notice_receiver": ["uid_a", "uid_b"], "notice_way": "mail"},
            content_template="接收人：{{notice_receiver_display}}",
        )

        text = action.get_content(notice_way_display="邮件", status_display="成功")["text"]

        assert text == "接收人：张三,李四"

    def test_multiple_receivers_rendered(self, monkeypatch):
        patch_display_name(monkeypatch, {"uid_a": "张三", "uid_b": "李四"})
        action = make_action(
            inputs={"notice_receiver": ["uid_a", "uid_b"], "notice_way": "mail"}, content_template=NEW_TEMPLATE
        )

        text = action.get_content(notice_way_display="邮件", status_display="成功")["text"]

        assert text == "发送邮件告警通知给张三,李四成功"

    def test_scalar_receiver_rendered(self, monkeypatch):
        """部分通知方式的 notice_receiver 是单个字符串"""
        patch_display_name(monkeypatch, {"chatid": "告警群"})
        action = make_action(
            inputs={"notice_receiver": "chatid", "notice_way": "wxwork-bot"}, content_template=NEW_TEMPLATE
        )

        text = action.get_content(notice_way_display="企业微信机器人", status_display="成功")["text"]

        assert text == "发送企业微信机器人告警通知给chatid成功"

    def test_no_receiver_template_unaffected(self, monkeypatch):
        """没有 notice_receiver 的场景（如 webhook）不注入变量，文案不受影响"""
        patch_display_name(monkeypatch, {"uid_a": "张三"})
        action = make_action(inputs={"foo": "bar"}, content_template="任务【{{action_name}}】执行{{status_display}}")

        text = action.get_content(status_display="成功")["text"]

        assert text == "任务【通知】执行成功"

    def test_origin_inputs_untouched_after_render(self, monkeypatch):
        """渲染不改写 inputs，处理记录里回显的仍应是标识"""
        patch_display_name(monkeypatch, {"uid_a": "张三"})
        action = make_action(content_template=NEW_TEMPLATE)

        action.get_content(notice_way_display="邮件", status_display="成功")

        assert action.inputs["notice_receiver"] == ["uid_a"]

    def test_conversion_failure_keeps_text_structure(self, monkeypatch):
        """转换失败时文案结构完整，不丢信息"""

        def _raise(username):
            raise BKAPIError("bk-user unavailable")

        patch_display_name(monkeypatch, side_effect=_raise)
        action = make_action(content_template=NEW_TEMPLATE)

        text = action.get_content(notice_way_display="邮件", status_display="成功")["text"]

        assert text == "发送邮件告警通知给uid_a成功"


class TestSingleTenantBehavior:
    """单租户环境下 get_user_display_name 恒等返回"""

    def test_single_tenant_returns_username(self, monkeypatch, settings):
        """
        单租户下转换是恒等操作，文案仍显示标识

        这是 bkmonitor.utils.user.get_user_display_name 的既有契约，
        不是本次修复的缺陷：名册只在多租户（对接 bk-user）时才有。
        """
        from bkmonitor.utils.user import get_user_display_name

        settings.ENABLE_MULTI_TENANT_MODE = False
        monkeypatch.setattr(f"{MODULE}.get_request", MagicMock(return_value=None), raising=False)

        assert get_user_display_name("uid_a") == "uid_a"

    def test_action_render_keeps_username_in_single_tenant(self, monkeypatch, settings):
        """不 mock 转换函数，走真实单租户分支，文案仍是标识"""
        settings.ENABLE_MULTI_TENANT_MODE = False
        monkeypatch.setattr(f"{MODULE}.get_request", MagicMock(return_value=None), raising=False)
        action = make_action(content_template=NEW_TEMPLATE)

        text = action.get_content(notice_way_display="邮件", status_display="成功")["text"]

        assert text == "发送邮件告警通知给uid_a成功"

    def test_single_tenant_multi_receiver_skips_batch_api(self, monkeypatch, settings):
        """单租户下多接收人直接短路返回原值，不触发批量接口与缓存"""
        called = []
        settings.ENABLE_MULTI_TENANT_MODE = False
        monkeypatch.setattr(
            "core.drf_resource.api.bk_login.batch_query_user_display_info",
            lambda **kwargs: called.append(kwargs) or [],
        )
        action = make_action(
            inputs={"notice_receiver": ["uid_a", "uid_b"], "notice_way": "mail"}, content_template=NEW_TEMPLATE
        )

        text = action.get_content(notice_way_display="邮件", status_display="成功")["text"]

        assert text == "发送邮件告警通知给uid_a,uid_b成功"
        assert called == []


class TestMultiTenantPropagation:
    """多租户无请求上下文（如 Celery cron 同步 ES）下必须按 action 所属租户查询"""

    def test_single_receiver_passes_action_tenant_without_request(self, monkeypatch, settings):
        from bkmonitor.utils.tenant import get_local_tenant_id, set_local_tenant_id

        calls = []

        def _batch(bk_usernames=None, bk_tenant_id=None):
            calls.append((list(bk_usernames or []), bk_tenant_id))
            return [{"bk_username": name, "display_name": "张三"} for name in bk_usernames or []]

        saved_tenant = get_local_tenant_id()
        try:
            set_local_tenant_id(None)
            settings.ENABLE_MULTI_TENANT_MODE = True
            settings.ROLE = "worker"
            monkeypatch.setattr(f"{MODULE}.get_request", MagicMock(return_value=None), raising=False)
            monkeypatch.setattr("bkmonitor.utils.tenant.bk_biz_id_to_bk_tenant_id", lambda biz_id: "tenant_other")
            monkeypatch.setattr("core.drf_resource.api.bk_login.batch_query_user_display_info", _batch)

            action = make_action(content_template=NEW_TEMPLATE)
            action.bk_biz_id = "200"

            text = action.get_content(notice_way_display="邮件", status_display="成功")["text"]

            assert text == "发送邮件告警通知给张三成功"
            assert calls == [(["uid_a"], "tenant_other")]
        finally:
            set_local_tenant_id(saved_tenant)

    def test_multi_receiver_passes_action_tenant_without_request(self, monkeypatch, settings):
        from bkmonitor.utils.tenant import get_local_tenant_id, set_local_tenant_id

        calls = []

        def _batch(bk_usernames=None, bk_tenant_id=None):
            calls.append((list(bk_usernames or []), bk_tenant_id))
            return [
                {"bk_username": "uid_a", "display_name": "张三"},
                {"bk_username": "uid_b", "display_name": "李四"},
            ]

        saved_tenant = get_local_tenant_id()
        try:
            set_local_tenant_id(None)
            settings.ENABLE_MULTI_TENANT_MODE = True
            settings.ROLE = "worker"
            monkeypatch.setattr("bkmonitor.utils.tenant.bk_biz_id_to_bk_tenant_id", lambda biz_id: "tenant_other")
            monkeypatch.setattr("core.drf_resource.api.bk_login.batch_query_user_display_info", _batch)

            action = make_action(
                inputs={"notice_receiver": ["uid_a", "uid_b"], "notice_way": "mail"}, content_template=NEW_TEMPLATE
            )
            action.bk_biz_id = "200"

            text = action.get_content(notice_way_display="邮件", status_display="成功")["text"]

            assert text == "发送邮件告警通知给张三,李四成功"
            assert calls == [(["uid_a", "uid_b"], "tenant_other")]
        finally:
            set_local_tenant_id(saved_tenant)

    def test_web_request_cache_not_used_across_different_tenant(self, monkeypatch, settings):
        """Web 请求上下文下若指定了不同租户，不能误用当前登录用户自己的 display_name"""
        from types import SimpleNamespace
        from bkmonitor.utils.user import get_user_display_name

        calls = []

        def _batch(bk_usernames=None, bk_tenant_id=None):
            calls.append((list(bk_usernames or []), bk_tenant_id))
            return [{"bk_username": "uid_a", "display_name": "租户B张三"}]

        settings.ENABLE_MULTI_TENANT_MODE = True
        settings.ROLE = "web"
        fake_req = SimpleNamespace(user=SimpleNamespace(username="uid_a", display_name="系统张三", tenant_id="system"))
        monkeypatch.setattr(f"{MODULE}.get_request", MagicMock(return_value=fake_req), raising=False)
        monkeypatch.setattr("core.drf_resource.api.bk_login.batch_query_user_display_info", _batch)

        assert get_user_display_name("uid_a", bk_tenant_id="tenant_other") == "租户B张三"
        assert calls == [(["uid_a"], "tenant_other")]

    def test_get_user_display_name_without_tenant_still_populates_cache_tenant(self, monkeypatch, settings):
        """未显式传 bk_tenant_id 时也应按请求/默认租户写入 query_params，防止 CacheType.USER 跨租户串值"""
        from bkmonitor.utils.tenant import get_local_tenant_id, set_local_tenant_id
        from bkmonitor.utils.user import get_user_display_name
        from constants.common import DEFAULT_TENANT_ID

        calls = []

        def _batch(bk_usernames=None, bk_tenant_id=None):
            calls.append((list(bk_usernames or []), bk_tenant_id))
            return [{"bk_username": "uid_a", "display_name": f"{bk_tenant_id}_张三"}]

        saved_tenant = get_local_tenant_id()
        try:
            settings.ENABLE_MULTI_TENANT_MODE = True
            settings.ROLE = "worker"
            monkeypatch.setattr(f"{MODULE}.get_request", MagicMock(return_value=None), raising=False)
            monkeypatch.setattr("core.drf_resource.api.bk_login.batch_query_user_display_info", _batch)

            set_local_tenant_id("tenant_b")
            assert get_user_display_name("uid_a") == "tenant_b_张三"

            set_local_tenant_id(None)
            assert get_user_display_name("uid_a") == f"{DEFAULT_TENANT_ID}_张三"
            assert calls == [(["uid_a"], "tenant_b"), (["uid_a"], DEFAULT_TENANT_ID)]
        finally:
            set_local_tenant_id(saved_tenant)

    def test_zero_bk_biz_id_skips_space_lookup_and_falls_back(self, monkeypatch, settings):
        """bk_biz_id 为 0（全局业务）时不应触发 SpaceApi 报错堆栈，直接回退请求租户"""
        from bkmonitor.utils.tenant import get_local_tenant_id, set_local_tenant_id

        space_calls = []
        saved_tenant = get_local_tenant_id()
        try:
            set_local_tenant_id("tenant_ctx")
            settings.ENABLE_MULTI_TENANT_MODE = True
            monkeypatch.setattr(
                "bkmonitor.utils.tenant.bk_biz_id_to_bk_tenant_id",
                lambda biz_id: space_calls.append(biz_id) or "unexpected",
            )
            for biz_id in (0, "0"):
                action = make_action()
                action.bk_biz_id = biz_id
                assert action._get_tenant_id() == "tenant_ctx"
            assert space_calls == []
        finally:
            set_local_tenant_id(saved_tenant)

    def test_batch_query_resource_passes_tenant_header_and_isolates_cache_key(self, monkeypatch, settings):
        """穿透真实缓存层与生产 **kwargs 入口：验证同租户命中缓存、跨租户隔离缓存且请求头正确"""
        from django.core.cache.backends.locmem import LocMemCache

        from core.drf_resource import api

        sent_headers = []
        fake_cache = LocMemCache("test_batch_user_display_cache", {})
        fake_mem_cache = LocMemCache("test_batch_user_display_mem_cache", {})

        class _FakeResponse:
            def __init__(self, payload):
                self._payload = payload
                self.headers = {}

            def raise_for_status(self):
                return None

            def json(self):
                return {"result": True, "code": 0, "data": self._payload}

        def _fake_get(self, url, params=None, headers=None, **kwargs):
            params = params or {}
            headers = headers or {}
            sent_headers.append((headers.get("X-Bk-Tenant-Id"), params.get("bk_usernames")))
            tenant = headers.get("X-Bk-Tenant-Id")
            return _FakeResponse([{"bk_username": "uid_a", "display_name": f"{tenant}_张三"}])

        # 开启非 development 环境并挂载纯内存缓存后端，使 UsingCache._cached 走真实缓存读写而不依赖 DB
        monkeypatch.setattr(settings, "ENVIRONMENT", "production")
        settings.ENABLE_MULTI_TENANT_MODE = True
        settings.BK_USER_API_BASE_URL = "https://bk-user.example.com"
        monkeypatch.setattr("bkmonitor.utils.cache.cache", fake_cache)
        monkeypatch.setattr("bkmonitor.utils.cache.mem_cache", fake_mem_cache)
        monkeypatch.setattr("bkmonitor.utils.user.get_global_user", lambda **kwargs: "admin")
        monkeypatch.setattr("requests.sessions.Session.get", _fake_get)
        fake_cache.clear()
        fake_mem_cache.clear()

        try:
            # 1. 租户 t1 首次查询：穿透发送 HTTP GET 并写入缓存
            assert api.bk_login.batch_query_user_display_info(bk_usernames=["uid_a"], bk_tenant_id="t1") == [
                {"bk_username": "uid_a", "display_name": "t1_张三"}
            ]
            # 2. 租户 t1 重复查询：命中缓存，不发起第二次 HTTP GET
            assert api.bk_login.batch_query_user_display_info(bk_usernames=["uid_a"], bk_tenant_id="t1") == [
                {"bk_username": "uid_a", "display_name": "t1_张三"}
            ]
            assert sent_headers == [("t1", "uid_a")]

            # 3. 租户 t2 查询同名用户：缓存键隔离，不命中 t1 缓存，发起新 HTTP GET
            assert api.bk_login.batch_query_user_display_info(bk_usernames=["uid_a"], bk_tenant_id="t2") == [
                {"bk_username": "uid_a", "display_name": "t2_张三"}
            ]
            assert sent_headers == [("t1", "uid_a"), ("t2", "uid_a")]
        finally:
            fake_cache.clear()
            fake_mem_cache.clear()

    def test_nonzero_biz_tenant_failure_falls_back_to_raw_without_default_tenant_query(self, monkeypatch, settings):
        """非零业务解析租户失败或非法业务 ID 时直接回退原始 UID，绝不落入 DEFAULT_TENANT_ID 串值"""
        calls = []
        settings.ENABLE_MULTI_TENANT_MODE = True
        monkeypatch.setattr(
            "bkmonitor.utils.tenant.bk_biz_id_to_bk_tenant_id",
            MagicMock(side_effect=ValueError("space archived")),
        )
        monkeypatch.setattr(
            "core.drf_resource.api.bk_login.batch_query_user_display_info",
            lambda **kwargs: calls.append(kwargs) or [{"bk_username": "admin", "display_name": "系统管理员"}],
        )

        for bad_biz in (200, "invalid_biz"):
            single_action = make_action(
                inputs={"notice_receiver": "admin", "notice_way": "mail"}, content_template=NEW_TEMPLATE
            )
            single_action.bk_biz_id = bad_biz
            assert (
                single_action.get_content(notice_way_display="邮件", status_display="成功")["text"]
                == "发送邮件告警通知给admin成功"
            )

            multi_action = make_action(
                inputs={"notice_receiver": ["admin", "uid_b"], "notice_way": "mail"}, content_template=NEW_TEMPLATE
            )
            multi_action.bk_biz_id = bad_biz
            assert (
                multi_action.get_content(notice_way_display="邮件", status_display="成功")["text"]
                == "发送邮件告警通知给admin,uid_b成功"
            )

        assert calls == []


class TestEdgeAndResilience:
    """单测边界补充：空 display_name 回退、超 100 分批去重、不可哈希脏元素、按模板按需查询"""

    def test_single_receiver_null_or_empty_display_name_falls_back(self, monkeypatch, settings):
        """单接收人（含单元素列表）遇到 display_name 为 None/空串/缺键时不抛 TypeError/KeyError"""
        settings.ENABLE_MULTI_TENANT_MODE = True
        settings.ROLE = "worker"
        monkeypatch.setattr(f"{MODULE}.get_request", MagicMock(return_value=None), raising=False)
        monkeypatch.setattr("bkmonitor.utils.tenant.bk_biz_id_to_bk_tenant_id", lambda biz_id: "tenant_demo")

        for payload in (
            [{"bk_username": "uid_a", "display_name": None}],
            [{"bk_username": "uid_a", "display_name": ""}],
            [{"bk_username": "uid_a"}],
        ):
            monkeypatch.setattr(
                "core.drf_resource.api.bk_login.batch_query_user_display_info",
                lambda bk_usernames=None, bk_tenant_id=None, _p=payload: _p,
            )
            action = make_action(content_template=NEW_TEMPLATE)
            assert action.get_notice_receiver_display(["uid_a"]) == "uid_a"
            assert action.get_notice_receiver_display("uid_a") == "uid_a"
            assert (
                action.get_content(notice_way_display="邮件", status_display="成功")["text"]
                == "发送邮件告警通知给uid_a成功"
            )

    def test_batch_convert_chunks_and_deduplicates_over_100_receivers(self, monkeypatch, settings):
        """超过 100 人应先去重再按 100 分批查询，结果按原顺序拼回"""
        calls = []

        def _batch(bk_usernames=None, bk_tenant_id=None):
            calls.append(list(bk_usernames))
            return [{"bk_username": name, "display_name": f"名_{name}"} for name in bk_usernames]

        settings.ENABLE_MULTI_TENANT_MODE = True
        monkeypatch.setattr("bkmonitor.utils.tenant.bk_biz_id_to_bk_tenant_id", lambda biz_id: "tenant_demo")
        monkeypatch.setattr("core.drf_resource.api.bk_login.batch_query_user_display_info", _batch)

        unique_users = [f"u_{i}" for i in range(101)]
        receivers = [*unique_users, "u_0", "u_50"]
        action = make_action(inputs={"notice_receiver": receivers, "notice_way": "voice"})

        result = action.get_notice_receiver_display(receivers).split(",")

        assert len(calls) == 2
        assert len(calls[0]) == 100
        assert calls[1] == ["u_100"]
        assert len(result) == 103
        assert result[0] == "名_u_0"
        assert result[100] == "名_u_100"
        assert result[101] == "名_u_0"

    def test_batch_convert_tolerates_unhashable_non_str_items(self, monkeypatch, settings):
        """列表中混入 dict 等不可哈希非字符串元素时不应在去重阶段抛 TypeError"""
        settings.ENABLE_MULTI_TENANT_MODE = True
        monkeypatch.setattr("bkmonitor.utils.tenant.bk_biz_id_to_bk_tenant_id", lambda biz_id: "tenant_demo")
        monkeypatch.setattr(
            "core.drf_resource.api.bk_login.batch_query_user_display_info",
            lambda bk_usernames=None, bk_tenant_id=None: [
                {"bk_username": name, "display_name": f"名_{name}"} for name in bk_usernames
            ],
        )
        action = make_action()
        result = action.get_notice_receiver_display([{"id": "x"}, "uid_a", "uid_b"])

        assert result == "{'id': 'x'},名_uid_a,名_uid_b"

    def test_get_content_skips_display_lookup_when_template_unused(self, monkeypatch, settings):
        """最终选中的模板未引用 notice_receiver_display 时，不应触发任何展示名查询"""
        called = []
        settings.ENABLE_MULTI_TENANT_MODE = True
        monkeypatch.setattr(
            "core.drf_resource.api.bk_login.batch_query_user_display_info",
            lambda **kwargs: called.append(kwargs) or [],
        )

        # 1. 旧快照模板
        legacy_action = make_action(content_template=LEGACY_TEMPLATE)
        assert (
            legacy_action.get_content(notice_way_display="邮件", status_display="成功")["text"]
            == "发送邮件告警通知给['uid_a']成功"
        )

        # 2. 审批中（WAITING + approve_info）
        waiting_action = make_action(content_template=NEW_TEMPLATE)
        waiting_action.status = ActionStatus.WAITING
        waiting_action.outputs = {"approve_info": {"id": 99}}
        assert (
            "触发异常防御审批" in waiting_action.get_content(notice_way_display="邮件", status_display="审批中")["text"]
        )

        # 3. COLLECT 汇总无 config_schema，走兜底模板
        collect_action = make_action(inputs={"notice_receiver": "uid_a,uid_b", "notice_way": "voice"})
        collect_action.signal = ActionSignal.COLLECT
        collect_action.action_plugin = {"plugin_type": ActionPluginType.COLLECT, "name": "汇总通知"}
        assert "执行" in collect_action.get_content(status_display="成功")["text"]

        assert called == []

    def test_non_str_display_name_and_unhashable_notice_way_tolerated(self, monkeypatch, settings):
        """上游返回非 str display_name 或 inputs.notice_way 含不可哈希对象时不抛 TypeError"""
        settings.ENABLE_MULTI_TENANT_MODE = True
        settings.ROLE = "worker"
        monkeypatch.setattr(f"{MODULE}.get_request", MagicMock(return_value=None), raising=False)
        monkeypatch.setattr("bkmonitor.utils.tenant.bk_biz_id_to_bk_tenant_id", lambda biz_id: "tenant_demo")
        monkeypatch.setattr(
            "core.drf_resource.api.bk_login.batch_query_user_display_info",
            lambda bk_usernames=None, bk_tenant_id=None: [{"bk_username": "uid_a", "display_name": 123}],
        )

        action = make_action(inputs={"notice_receiver": ["uid_a"], "notice_way": {"invalid": 1}})
        assert action.get_notice_receiver_display(["uid_a"]) == "uid_a"
        assert action.get_notice_receiver_display("uid_a") == "uid_a"

    def test_comma_separated_receiver_and_list_notice_way_supported(self, monkeypatch, settings):
        """逗号拼接接收人字符串不应截断丢人，列表型 notice_way 正常按首元素识别渠道"""
        calls = []

        def _batch(bk_usernames=None, bk_tenant_id=None):
            calls.append((list(bk_usernames or []), bk_tenant_id))
            mapping = {"uid_a": "张三", "uid_b": "李四", "uid_c": "王五"}
            return [{"bk_username": u, "display_name": mapping[u]} for u in bk_usernames if u in mapping]

        settings.ENABLE_MULTI_TENANT_MODE = True
        monkeypatch.setattr("bkmonitor.utils.tenant.bk_biz_id_to_bk_tenant_id", lambda biz_id: "tenant_demo")
        monkeypatch.setattr("core.drf_resource.api.bk_login.batch_query_user_display_info", _batch)

        # 1. 逗号分隔标量与混合列表
        action = make_action(
            inputs={"notice_receiver": "uid_a,uid_b", "notice_way": ["mail"]}, content_template=NEW_TEMPLATE
        )
        assert (
            action.get_content(notice_way_display="邮件", status_display="成功")["text"]
            == "发送邮件告警通知给张三,李四成功"
        )
        assert action.get_notice_receiver_display(["uid_a,uid_b", "uid_c"], notice_way=["mail"]) == "张三,李四,王五"

        # 2. 列表型会话渠道跳过转换，不发起额外请求
        before_count = len(calls)
        bot_action = make_action(
            inputs={"notice_receiver": "chat_1,chat_2", "notice_way": ["wxwork-bot"]}, content_template=NEW_TEMPLATE
        )
        assert bot_action.get_notice_receiver_display("chat_1,chat_2") == "chat_1,chat_2"
        assert len(calls) == before_count

    def test_sharding_prefetch_eliminates_n_plus_1_in_to_document(self, monkeypatch, settings):
        """分片同步预取：多条单人通知子任务按租户合并为 1 次批量请求，to_document 循环内零额外请求"""
        from alarm_backends.service.fta_action.utils import prefetch_receiver_display_mappings, to_document

        calls = []

        def _batch(bk_usernames=None, bk_tenant_id=None):
            calls.append((list(bk_usernames or []), bk_tenant_id))
            return [{"bk_username": name, "display_name": f"{bk_tenant_id}_{name}"} for name in bk_usernames or []]

        settings.ENABLE_MULTI_TENANT_MODE = True
        monkeypatch.setattr(
            "bkmonitor.utils.tenant.bk_biz_id_to_bk_tenant_id",
            lambda biz_id: "t1" if int(biz_id) == 100 else "t2",
        )
        monkeypatch.setattr("alarm_backends.service.fta_action.utils.bk_biz_id_to_bk_tenant_id", lambda biz_id: "t1")
        monkeypatch.setattr(
            "alarm_backends.service.fta_action.utils.get_notice_display_mapping",
            lambda way: {"mail": "邮件", "sms": "短信", "qy_weixin": "企业微信", "wxwork-bot": "群机器人"}.get(
                way, way
            ),
        )
        monkeypatch.setattr("alarm_backends.service.fta_action.utils.get_target_info_from_ctx", lambda *a, **kw: {})
        monkeypatch.setattr("core.drf_resource.api.bk_login.batch_query_user_display_info", _batch)

        # 构造同租户 3 条单人通知子任务 + 1 条群机器人子任务 + 1 条异租户单人子任务
        a1 = make_action(inputs={"notice_receiver": "u1", "notice_way": "mail"}, content_template=NEW_TEMPLATE)
        a2 = make_action(inputs={"notice_receiver": "u2", "notice_way": "sms"}, content_template=NEW_TEMPLATE)
        a3 = make_action(inputs={"notice_receiver": "u1", "notice_way": "qy_weixin"}, content_template=NEW_TEMPLATE)
        a_bot = make_action(
            inputs={"notice_receiver": "chat_99", "notice_way": "wxwork-bot"}, content_template=NEW_TEMPLATE
        )
        a_t2 = make_action(inputs={"notice_receiver": "u3", "notice_way": "mail"}, content_template=NEW_TEMPLATE)
        a_t2.bk_biz_id = 200
        for idx, inst in enumerate((a1, a2, a3, a_bot, a_t2), start=1):
            inst.id = idx
            inst.update_time = inst.create_time
            inst.end_time = inst.create_time
            inst.strategy_id = 1
            inst.alert_level = 1
            inst.alerts = []
            inst.ex_data = {}
            inst.assignee = []
            inst.parent_action_id = 0
            inst.execute_times = 1
            inst.failure_type = None

        maps = prefetch_receiver_display_mappings([a1, a2, a3, a_bot, a_t2])
        assert calls == [(["u1", "u2"], "t1"), (["u3"], "t2")]

        # 进入 to_document 循环后不应再触发任何 batch_query_user_display_info 调用
        now = datetime.datetime(2026, 11, 12, 9, 40, 0)
        docs = [to_document(inst, now, receiver_display_maps=maps) for inst in (a1, a2, a3, a_bot, a_t2)]
        assert len(calls) == 2
        assert docs[0].content["text"] == "发送邮件告警通知给t1_u1成功"
        assert docs[1].content["text"] == "发送短信告警通知给t1_u2成功"
        assert docs[2].content["text"] == "发送企业微信告警通知给t1_u1成功"
        assert docs[3].content["text"] == "发送群机器人告警通知给chat_99成功"
        assert docs[4].content["text"] == "发送邮件告警通知给t2_u3成功"

    def test_prefetch_failure_degrades_to_empty_map_without_raising(self, monkeypatch, settings):
        """预取是纯优化：内部异常必须被吞掉并返回空映射，否则整片 action 的 ES 文档会全部丢失"""
        from alarm_backends.service.fta_action.utils import prefetch_receiver_display_mappings

        settings.ENABLE_MULTI_TENANT_MODE = True
        monkeypatch.setattr("bkmonitor.utils.tenant.bk_biz_id_to_bk_tenant_id", lambda biz_id: "t1")

        # 场景 1：批量查询整体抛非超时异常时，内层回退原值但不外溢（不抛即可，内容为原标识）
        def _boom(*args, **kwargs):
            raise BKAPIError(system_name="bk-user", url="display_info", result="unexpected")

        monkeypatch.setattr("core.drf_resource.api.bk_login.batch_query_user_display_info", _boom)
        action = make_action(inputs={"notice_receiver": "u1", "notice_way": "mail"}, content_template=NEW_TEMPLATE)
        assert prefetch_receiver_display_mappings([action]) == {"t1": {"u1": "u1"}}

        # 场景 2：批量函数本身抛异常时，该租户回填原标识映射而非中断分片。
        # 回填而非返回空映射：让渲染阶段直接复用回退结果，不再逐条重试一次。
        monkeypatch.setattr(
            "alarm_backends.service.fta_action.utils.batch_get_user_display_names",
            lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("prefetch exploded")),
        )
        assert prefetch_receiver_display_mappings([action]) == {"t1": {"u1": "u1"}}

        # 场景 3：单条实例的属性访问抛异常时，仅跳过该条，其余实例仍正常预取
        calls = []

        def _batch(bk_usernames=None, bk_tenant_id=None, strict_tenant=False, upstream_state=None):
            calls.append((list(bk_usernames or []), bk_tenant_id))
            return {name: f"{bk_tenant_id}_{name}" for name in bk_usernames or []}

        monkeypatch.setattr("alarm_backends.service.fta_action.utils.batch_get_user_display_names", _batch)
        broken = make_action(inputs={"notice_receiver": "u_bad", "notice_way": "mail"}, content_template=NEW_TEMPLATE)
        # 只覆盖该实例自身，不影响 healthy 实例
        broken._need_convert_receiver = lambda notice_way=None: (_ for _ in ()).throw(ValueError("dirty notice_way"))
        healthy = make_action(inputs={"notice_receiver": "u1", "notice_way": "mail"}, content_template=NEW_TEMPLATE)

        assert prefetch_receiver_display_mappings([broken, healthy]) == {"t1": {"u1": "t1_u1"}}
        assert calls == [(["u1"], "t1")]


class TestBuiltinNoticeTemplate:
    """
    内置通知插件的模板文件守卫

    上面的 NEW_TEMPLATE 是手写常量，只能证明「用了新变量就能正确渲染」。
    真正决定线上文案的是 action_plugin_initial.json，若哪天改回 notice_receiver，
    逻辑用例仍会全绿而缺陷复发，因此单独守护模板文件本身。
    """

    def test_builtin_notice_template_uses_display_variable(self):
        plugin_file = Path(__file__).resolve().parents[4] / "support-files/fta/action_plugin_initial.json"
        plugins = json.loads(plugin_file.read_text(encoding="utf-8"))
        notice_plugin = next(plugin for plugin in plugins if plugin["plugin_type"] == "notice")

        template = notice_plugin["config_schema"]["content_template"]

        # 展示名优先，旧上下文（只有 notice_receiver）用 default 兜底：
        # 滚动升级期间新版模板可能由旧 worker 渲染，缺兜底会把接收人整段渲染成空。
        assert "notice_receiver_display" in template
        assert "default(notice_receiver)" in template
        # 不能直接以 notice_receiver 为主变量，否则展示名改造整体失效
        assert "{{notice_receiver}}{{status_display}}" not in template

    def test_builtin_template_renders_receiver_with_legacy_context(self):
        """新模板配旧 worker 上下文（无 notice_receiver_display）时必须仍显示接收人"""
        from bkmonitor.utils.template import Jinja2Renderer

        plugin_file = Path(__file__).resolve().parents[4] / "support-files/fta/action_plugin_initial.json"
        plugins = json.loads(plugin_file.read_text(encoding="utf-8"))
        notice_plugin = next(plugin for plugin in plugins if plugin["plugin_type"] == "notice")
        template = notice_plugin["config_schema"]["content_template"]

        legacy_context = {"notice_way_display": "邮件", "notice_receiver": "admin", "status_display": "成功"}
        assert Jinja2Renderer.render(template, legacy_context) == "发送邮件告警通知给admin成功"

        new_context = dict(legacy_context, notice_receiver_display="张三")
        assert Jinja2Renderer.render(template, new_context) == "发送邮件告警通知给张三成功"


class TestRetryParamsVersionCompat:
    """熔断补发记录的 kwargs 是跨版本契约，新字段必须能放能容"""

    def test_wxwork_bot_retry_params_keeps_kwargs_contract(self, settings):
        """租户不能塞进 kwargs：旧版 send_wxwork_layouts / send_wxwork_content 没有该形参"""
        import inspect

        from bkmonitor.utils.send import Sender

        settings.ENABLE_MULTI_TENANT_MODE = True
        # 未配置回调地址时会在构造 retry_params 之前提前返回，这里补一个占位值
        settings.WXWORK_BOT_WEBHOOK_URL = "https://example.com/webhook"
        sender = Sender.__new__(Sender)
        sender.msg_type = "markdown"
        sender.content = "content"
        sender.mentioned_users = None
        sender.bk_tenant_id = "tenant_a"
        sender.context = {}
        sender.blocked = False
        sender._is_wxwork_layouts_enabled = True

        captured = {}

        def _capture(notice_type, retry_params):
            captured.update(retry_params)
            # 已捕获到参数，直接中断后续真实发送
            raise RuntimeError("stop")

        sender._check_blocked_and_raise = _capture
        try:
            sender.send_wxwork_bot(["chat_1"])
        except RuntimeError:
            pass

        assert captured["kwargs"] == {}
        assert captured["bk_tenant_id"] == "tenant_a"

        # 旧版方法签名不接受 bk_tenant_id，kwargs 里出现就会绑定失败
        for method_name in ("send_wxwork_layouts", "send_wxwork_content"):
            params = inspect.signature(getattr(Sender, method_name)).parameters
            assert "bk_tenant_id" not in params or captured["kwargs"] == {}

    def test_replay_ignores_unknown_retry_fields_for_old_records(self):
        """旧记录没有 bk_tenant_id 字段时，重放不应额外注入参数"""
        action = ActionInstance.__new__(ActionInstance)
        action.id = 1
        action.strategy_id = 0
        action.ex_data = {"retry_params": []}

        # 空列表直接返回，不触发任何导入与调用
        assert action.replay_blocked_notice() == []


class TestPrefetchTenantShortCircuit:
    """跨租户不叠加等待：上游确认不可用后，剩余租户直接回填原标识"""

    def test_prefetch_skips_remaining_tenants_after_upstream_down(self, monkeypatch, settings):
        from alarm_backends.service.fta_action.utils import prefetch_receiver_display_mappings

        settings.ENABLE_MULTI_TENANT_MODE = True
        # 三个业务分别落到三个租户
        monkeypatch.setattr("bkmonitor.utils.tenant.bk_biz_id_to_bk_tenant_id", lambda biz_id: f"t{biz_id // 100}")

        a1 = make_action(inputs={"notice_receiver": "u1", "notice_way": "mail"}, content_template=NEW_TEMPLATE)
        a1.bk_biz_id = 100
        a2 = make_action(inputs={"notice_receiver": "u2", "notice_way": "mail"}, content_template=NEW_TEMPLATE)
        a2.bk_biz_id = 200
        a3 = make_action(inputs={"notice_receiver": "u3", "notice_way": "mail"}, content_template=NEW_TEMPLATE)
        a3.bk_biz_id = 300

        calls = []

        def _timeout(**kwargs):
            # 必须打在 API 层而非 batch_get_user_display_names：后者内部会吞掉异常，
            # 若把它整个替换掉，就绕过了「异常被吞、外层感知不到」的真实路径，
            # 测试会假绿（曾经如此，导致跨租户短路实际从未生效却未被发现）。
            calls.append(kwargs.get("bk_tenant_id"))
            raise BKAPIError(system_name="bk-user", url="display_info", result="接口返回结果超时")

        monkeypatch.setattr("core.drf_resource.api.bk_login.batch_query_user_display_info", _timeout)

        maps = prefetch_receiver_display_mappings([a1, a2, a3])

        # 只有第一个租户真正发起请求，后两个直接回填
        assert calls == ["t1"]
        assert maps["t1"] == {"u1": "u1"}
        assert maps["t2"] == {"u2": "u2"}
        assert maps["t3"] == {"u3": "u3"}
