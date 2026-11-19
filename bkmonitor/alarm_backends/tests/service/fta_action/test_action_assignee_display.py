"""
负责人展示名回归测试

覆盖 bug：告警状态详情弹窗「执行状态」悬浮提示中显示用户 UID 而非展示名。
根因是 run_node_task 拼装失败文案时直接使用 action.assignee 原值。

本文件为纯逻辑测试，不依赖数据库：ActionProcessor 通过 __new__ 构造，
action 及所有副作用方法均为 MagicMock。
"""

from unittest.mock import MagicMock

from constants.action import ActionStatus
from core.errors.api import BKAPIError

MODULE = "alarm_backends.service.fta_action.common.processor"


def make_processor(assignee):
    """构造一个不触发 __init__ / DB 访问的 ActionProcessor"""
    from alarm_backends.service.fta_action.common.processor import ActionProcessor

    processor = ActionProcessor.__new__(ActionProcessor)
    processor.action = MagicMock()
    processor.action.id = 1
    processor.action.status = ActionStatus.RUNNING
    processor.action.assignee = assignee
    processor.action.outputs = {}
    processor.insert_action_log = MagicMock()
    processor.set_finished = MagicMock()
    return processor


def run_with_api_error(processor, error=None):
    """让节点执行抛出异常，返回写入的 message"""
    processor.run_request_action = MagicMock(side_effect=error or BKAPIError("boom"))
    processor.run_node_task({"name": "创建任务", "function": "create_task"})
    return processor.set_finished.call_args.kwargs.get("message", "")


class TestAssigneeDisplayNames:
    """get_assignee_display_names 方法本身"""

    def test_converts_each_assignee(self, monkeypatch):
        processor = make_processor(["uid_a", "uid_b"])
        monkeypatch.setattr(
            f"{MODULE}.get_user_display_name",
            lambda username: {"uid_a": "张三", "uid_b": "李四"}.get(username, username),
        )

        assert processor.get_assignee_display_names() == ["张三", "李四"]

    def test_empty_assignee(self, monkeypatch):
        processor = make_processor([])
        monkeypatch.setattr(f"{MODULE}.get_user_display_name", lambda username: username)

        assert processor.get_assignee_display_names() == []

    def test_none_assignee(self, monkeypatch):
        processor = make_processor(None)
        monkeypatch.setattr(f"{MODULE}.get_user_display_name", lambda username: username)

        assert processor.get_assignee_display_names() == []

    def test_scalar_assignee_tolerated(self, monkeypatch):
        """历史脏数据 assignee 为标量时不应崩"""
        processor = make_processor("uid_a")
        monkeypatch.setattr(f"{MODULE}.get_user_display_name", lambda username: "张三")

        assert processor.get_assignee_display_names() == ["张三"]

    def test_conversion_failure_falls_back_to_raw(self, monkeypatch):
        """转换抛异常时回退原值"""

        def _raise(username):
            raise BKAPIError("bk-user unavailable")

        processor = make_processor(["uid_a"])
        monkeypatch.setattr(f"{MODULE}.get_user_display_name", _raise)

        assert processor.get_assignee_display_names() == ["uid_a"]

    def test_partial_failure_keeps_other_conversions(self, monkeypatch):
        """单个失败不影响其余负责人的转换"""

        def _convert(username):
            if username == "uid_b":
                raise BKAPIError("bk-user unavailable")
            return "张三"

        processor = make_processor(["uid_a", "uid_b"])
        monkeypatch.setattr(f"{MODULE}.get_user_display_name", _convert)

        assert processor.get_assignee_display_names() == ["张三", "uid_b"]


class TestFailureMessage:
    """失败提示文案使用展示名"""

    def test_uid_converted_in_message(self, monkeypatch):
        processor = make_processor(["uid_a"])
        monkeypatch.setattr(
            f"{MODULE}.get_user_display_name",
            lambda username: "display_a" if username == "uid_a" else username,
        )

        message = run_with_api_error(processor)

        assert "display_a" in message
        assert "uid_a" not in message

    def test_multiple_assignees_joined_with_comma(self, monkeypatch):
        processor = make_processor(["uid_a", "uid_b"])
        monkeypatch.setattr(
            f"{MODULE}.get_user_display_name",
            lambda username: {"uid_a": "张三", "uid_b": "李四"}.get(username, username),
        )

        message = run_with_api_error(processor)

        assert "张三,李四" in message

    def test_message_structure_kept_on_conversion_failure(self, monkeypatch):
        """转换失败时文案结构完整，失败结果不丢失"""

        def _raise(username):
            raise BKAPIError("bk-user unavailable")

        processor = make_processor(["uid_a"])
        monkeypatch.setattr(f"{MODULE}.get_user_display_name", _raise)

        message = run_with_api_error(processor)

        assert "以当前告警负责人" in message
        assert "uid_a" in message

    def test_assignee_origin_value_untouched(self, monkeypatch):
        """
        只改文案，不改 assignee 本体

        assignee 同时是 ES operator 字段、通知对象和 ITSM APPROVER 的数据源，
        改写会让这些链路的标识错乱。
        """
        processor = make_processor(["uid_a"])
        monkeypatch.setattr(f"{MODULE}.get_user_display_name", lambda username: "display_a")

        run_with_api_error(processor)

        assert processor.action.assignee == ["uid_a"]


class TestOtherBranchesUnchanged:
    """其他失败分支行为不变"""

    def test_empty_assignee_error_has_no_assignee_text(self):
        from core.errors.alarm_backends import EmptyAssigneeError

        processor = make_processor(["uid_a"])

        message = run_with_api_error(processor, EmptyAssigneeError())

        assert "以当前告警负责人" not in message
        assert "执行创建任务出错" in message

    def test_generic_exception_branch_unchanged(self):
        processor = make_processor(["uid_a"])

        message = run_with_api_error(processor, ValueError("unexpected"))

        assert "执行创建任务" in message
        assert "unexpected" in message
        assert "以当前告警负责人" not in message


class TestMultiTenantAndBatchAssignee:
    """多租户透传与批量查询加固"""

    def test_single_assignee_passes_processor_tenant_id(self, monkeypatch, settings):
        calls = []

        def _batch(bk_usernames=None, bk_tenant_id=None):
            calls.append((list(bk_usernames or []), bk_tenant_id))
            return [{"bk_username": name, "display_name": "张三"} for name in bk_usernames or []]

        settings.ENABLE_MULTI_TENANT_MODE = True
        settings.ROLE = "worker"
        monkeypatch.setattr("core.drf_resource.api.bk_login.batch_query_user_display_info", _batch)

        processor = make_processor(["uid_a"])
        processor.bk_tenant_id = "tenant_other"

        message = run_with_api_error(processor)

        assert "张三" in message
        assert "uid_a" not in message
        assert calls == [(["uid_a"], "tenant_other")]

    def test_single_assignee_falls_back_to_action_biz_id_without_processor_tenant(self, monkeypatch, settings):
        calls = []

        def _batch(bk_usernames=None, bk_tenant_id=None):
            calls.append((list(bk_usernames or []), bk_tenant_id))
            return [{"bk_username": name, "display_name": "张三"} for name in bk_usernames or []]

        settings.ENABLE_MULTI_TENANT_MODE = True
        settings.ROLE = "worker"
        monkeypatch.setattr("bkmonitor.utils.tenant.bk_biz_id_to_bk_tenant_id", lambda biz_id: "tenant_from_biz")
        monkeypatch.setattr("core.drf_resource.api.bk_login.batch_query_user_display_info", _batch)

        processor = make_processor(["uid_a"])
        processor.action.bk_biz_id = 200

        assert processor.get_assignee_display_names() == ["张三"]
        assert calls == [(["uid_a"], "tenant_from_biz")]

    def test_zero_biz_id_skips_space_lookup(self, monkeypatch, settings):
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
            processor = make_processor(["uid_a"])
            processor.action.bk_biz_id = 0

            assert processor._get_tenant_id() == "tenant_ctx"
            assert space_calls == []
        finally:
            set_local_tenant_id(saved_tenant)

    def test_multi_assignees_use_batch_api_with_tenant_and_fallback(self, monkeypatch, settings):
        calls = []

        def _batch(bk_usernames=None, bk_tenant_id=None):
            calls.append((list(bk_usernames or []), bk_tenant_id))
            return [
                {"bk_username": "uid_a", "display_name": "张三"},
                {"bk_username": "uid_b", "display_name": ""},
            ]

        settings.ENABLE_MULTI_TENANT_MODE = True
        monkeypatch.setattr("core.drf_resource.api.bk_login.batch_query_user_display_info", _batch)

        processor = make_processor([{"id": "x"}, "uid_a", "uid_b", "uid_a", None])
        processor.bk_tenant_id = "tenant_other"

        assert processor.get_assignee_display_names() == ["{'id': 'x'}", "张三", "uid_b", "张三"]
        assert calls == [(["uid_a", "uid_b"], "tenant_other")]

    def test_multi_assignees_batch_failure_falls_back_all(self, monkeypatch, settings):
        def _raise(bk_usernames=None, bk_tenant_id=None):
            raise BKAPIError("bk-user unavailable")

        settings.ENABLE_MULTI_TENANT_MODE = True
        monkeypatch.setattr("core.drf_resource.api.bk_login.batch_query_user_display_info", _raise)

        processor = make_processor(["uid_a", "uid_b"])
        processor.bk_tenant_id = "tenant_other"

        message = run_with_api_error(processor)

        assert "以当前告警负责人[uid_a,uid_b]" in message

    def test_nonzero_biz_tenant_resolution_failure_falls_back_to_raw_without_default_tenant_query(
        self, monkeypatch, settings
    ):
        """非零业务解析租户失败时直接回退原始负责人标识，不查询默认租户防止同名账号串值"""
        calls = []
        settings.ENABLE_MULTI_TENANT_MODE = True
        monkeypatch.setattr(
            "bkmonitor.utils.tenant.bk_biz_id_to_bk_tenant_id",
            MagicMock(side_effect=ValueError("space not found")),
        )
        monkeypatch.setattr(
            "core.drf_resource.api.bk_login.batch_query_user_display_info",
            lambda **kwargs: calls.append(kwargs) or [{"bk_username": "admin", "display_name": "系统管理员"}],
        )

        processor = make_processor(["admin", "uid_b"])
        processor.action.bk_biz_id = 999

        assert processor.get_assignee_display_names() == ["admin", "uid_b"]
        assert calls == []

    def test_over_100_assignees_chunked_and_single_tenant_skips_batch_api(self, monkeypatch, settings):
        calls = []

        def _batch(bk_usernames=None, bk_tenant_id=None):
            calls.append((len(bk_usernames or []), bk_tenant_id))
            return [{"bk_username": name, "display_name": f"名_{name}"} for name in bk_usernames or []]

        monkeypatch.setattr("core.drf_resource.api.bk_login.batch_query_user_display_info", _batch)

        # 单租户多人：不调批量接口
        settings.ENABLE_MULTI_TENANT_MODE = False
        monkeypatch.setattr(f"{MODULE}.get_user_display_name", lambda username, bk_tenant_id=None: username)
        single_proc = make_processor(["u_1", "u_2"])
        assert single_proc.get_assignee_display_names() == ["u_1", "u_2"]
        assert calls == []

        # 多租户 >100 人：去重后按 100 分块
        settings.ENABLE_MULTI_TENANT_MODE = True
        assignees = [*(f"u_{i}" for i in range(101)), "u_0"]
        multi_proc = make_processor(assignees)
        multi_proc.bk_tenant_id = "tenant_batch"
        res = multi_proc.get_assignee_display_names()

        assert calls == [(100, "tenant_batch"), (1, "tenant_batch")]
        assert len(res) == 102
        assert res[0] == "名_u_0"
        assert res[100] == "名_u_100"
        assert res[101] == "名_u_0"
