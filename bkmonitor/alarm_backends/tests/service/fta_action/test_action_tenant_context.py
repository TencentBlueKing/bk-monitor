"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

"""
回归测试：自愈动作执行入口 run_action 运行在 celery worker（无 HTTP request）上下文中，
必须将 action 所属租户写入 thread-local，否则多租户模式下游资源（如作业平台轮询
GetJobInstanceStatusResource → get_admin_username(get_request_tenant_id())）会抛
Exception("get_request_tenant_id: cannot get tenant_id.")。

- 前 3 个用例直接测纯函数 _resolve_action_tenant_id，覆盖：自带 bk_tenant_id / 缺失时按业务兜底
  （如 message_queue 自定义 __init__）/ 连 action 都没有时返回 None，无任何全局副作用。
- 后 2 个用例端到端验证 run_action：执行期下游 get_request_tenant_id 能取到租户、结束后恢复，
  且执行函数抛异常时 finally 仍恢复租户，不污染同 worker 线程的后续任务。
"""
import importlib
import types
from unittest import mock

from alarm_backends.service.fta_action.tasks import action_tasks
from alarm_backends.service.fta_action.tasks.action_tasks import _resolve_action_tenant_id, run_action
from bkmonitor.utils.request import get_request_tenant_id
from bkmonitor.utils.tenant import get_local_tenant_id, set_local_tenant_id


# --------------------------------------------------------------------------- #
# 纯函数：租户解析（无副作用）
# --------------------------------------------------------------------------- #
def test_resolve_prefers_processor_bk_tenant_id():
    processor = types.SimpleNamespace(bk_tenant_id="tenant_demo", action=types.SimpleNamespace(bk_biz_id=2))
    with mock.patch.object(action_tasks, "bk_biz_id_to_bk_tenant_id") as mocked:
        assert _resolve_action_tenant_id(processor) == "tenant_demo"
    mocked.assert_not_called()  # 自带 bk_tenant_id 时不应再查业务


def test_resolve_falls_back_to_biz_when_attr_missing():
    # 模拟 message_queue：自定义 __init__ 设了 action 但未设 bk_tenant_id
    processor = types.SimpleNamespace(action=types.SimpleNamespace(bk_biz_id=2))
    with mock.patch.object(action_tasks, "bk_biz_id_to_bk_tenant_id", return_value="tenant_from_biz") as mocked:
        assert _resolve_action_tenant_id(processor) == "tenant_from_biz"
    mocked.assert_called_once_with(2)


def test_resolve_returns_none_without_action():
    # 模拟 message_queue 未启用时 __init__ 提前 return，什么都没设
    processor = types.SimpleNamespace()
    with mock.patch.object(action_tasks, "bk_biz_id_to_bk_tenant_id") as mocked:
        assert _resolve_action_tenant_id(processor) is None
    mocked.assert_not_called()


# --------------------------------------------------------------------------- #
# 端到端：run_action 执行期注入 + 结束后恢复
# --------------------------------------------------------------------------- #
class _FakeAction:
    bk_biz_id = 2
    signal = "abnormal"
    is_parent_action = True  # 跳过成功/失败状态指标分支
    is_first_process = False  # 跳过处理延迟指标分支
    status = "success"
    failure_type = ""


def _make_processor_module(recorder, tenant_id, *, raise_in_execute=False):
    module = types.ModuleType("fake_action_processor")

    class ActionProcessor:
        def __init__(self, action_id, alerts=None):
            self.bk_tenant_id = tenant_id
            self.action = _FakeAction()
            self.is_finished = True
            self.context = {}

        def can_func_call(self):
            return True

        def execute(self):
            # 记录执行期间下游真正会调用的取租户函数（即此前会抛 cannot get tenant_id 的那条）的返回值
            recorder["tenant_in_func"] = get_request_tenant_id(peaceful=False)
            if raise_in_execute:
                raise RuntimeError("boom in execute")

    module.ActionProcessor = ActionProcessor
    return module


def _patch_run_action_externals(fake_module):
    """注入假 processor 模块，并 mock 掉 metrics / ActionInstance，避免污染全局 registry 与触达 DB。"""
    real_import = importlib.import_module

    def _selective_import(name, *args, **kwargs):
        if name == "alarm_backends.service.fta_action.notice.processor":
            return fake_module
        return real_import(name, *args, **kwargs)

    return [
        mock.patch("importlib.import_module", side_effect=_selective_import),
        mock.patch.object(action_tasks, "metrics", mock.MagicMock()),
        mock.patch.object(action_tasks, "ActionInstance", mock.MagicMock()),
    ]


def test_run_action_sets_then_restores_local_tenant():
    """执行期下游 get_request_tenant_id 取到 action 租户；任务结束后恢复，不污染线程。"""
    saved = get_local_tenant_id()
    try:
        set_local_tenant_id(None)
        recorder = {}
        fake_module = _make_processor_module(recorder, tenant_id="tenant_demo")
        patches = _patch_run_action_externals(fake_module)
        for p in patches:
            p.start()
        try:
            run_action("notice", {"id": 123, "function": "execute"})
        finally:
            for p in reversed(patches):
                p.stop()

        # 此前会抛 cannot get tenant_id 的取租户函数，现在能返回注入的租户
        assert recorder["tenant_in_func"] == "tenant_demo"
        # 任务结束后恢复到先前状态，不污染同线程后续任务
        assert get_local_tenant_id() is None
    finally:
        set_local_tenant_id(saved)


def test_run_action_restores_local_tenant_on_exception():
    """执行函数抛异常时，finally 仍恢复租户，不泄漏到后续任务。"""
    saved = get_local_tenant_id()
    try:
        set_local_tenant_id(None)
        recorder = {}
        fake_module = _make_processor_module(recorder, tenant_id="tenant_demo", raise_in_execute=True)
        patches = _patch_run_action_externals(fake_module)
        for p in patches:
            p.start()
        try:
            # 执行函数抛出的异常由 run_action 内部 except 兜住，run_action 本身不应抛
            run_action("notice", {"id": 123, "function": "execute"})
        finally:
            for p in reversed(patches):
                p.stop()

        # 抛异常前已注入租户
        assert recorder["tenant_in_func"] == "tenant_demo"
        # 即使执行抛异常，finally 仍把线程本地租户恢复为先前状态
        assert get_local_tenant_id() is None
    finally:
        set_local_tenant_id(saved)
