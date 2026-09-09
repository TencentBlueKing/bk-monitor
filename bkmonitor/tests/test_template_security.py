"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest
from jinja2.exceptions import SecurityError

from bkmonitor.utils.template import Jinja2Renderer


class TestSafeSandboxedEnvironmentCall:
    """覆盖 SafeSandboxedEnvironment.call 对“可调用实参”的安全约束。"""

    def test_undefined_argument_passed_to_gettext_should_not_raise(self):
        """未定义的模板变量会被解析为 UndefinedSilently（其实现了 __call__ 因此 callable 为真），
        作为 gettext 等函数的实参传入时不应触发 SecurityError，应正常渲染为占位空值。

        回归用例：修复前会抛出 `callable arguments are not allowed in templates`，
        导致汇总通知标题（如 abnormal/converge/default_title.jinja）整体渲染失败。
        """
        template = '{{ gettext("hello %(name)s", name=missing_var) }}'
        # missing_var 不在上下文中，渲染应安全降级而非抛错
        result = Jinja2Renderer.render(template, {})
        assert result == "hello "

    def test_real_callable_argument_still_blocked(self):
        """真实的可调用对象（函数）作为实参仍需被拦截，确保安全约束未被削弱。"""
        template = '{{ gettext("%(x)s", x=evil) }}'
        with pytest.raises(SecurityError):
            Jinja2Renderer.render(template, {"evil": lambda: "boom"})

    def test_data_value_argument_allowed(self):
        """普通数据值作为实参可正常传入并渲染。"""
        template = '{{ gettext("count=%(n)d", n=count) }}'
        result = Jinja2Renderer.render(template, {"count": 3})
        assert result == "count=3"


class TestGettextAliasCallTarget:
    """覆盖 i18n `_` 别名的调用目标：只能是已安装的 gettext，不受模板作用域影响。"""

    def test_rebound_gettext_is_not_invoked_by_alias(self):
        """模板内把 gettext 换成上下文对象的方法后，`_()` 不得转而调用该方法。

        `_` 的调用目标不经过 `SafeSandboxedEnvironment.call` 的可调用校验，
        因此必须固定在已安装的 gettext 上，否则等于绕开沙箱调用任意方法。
        """

        class Probe:
            called = False

            def touch(self):
                Probe.called = True
                return "touched"

        template = '{% set gettext = obj.touch %}{{ _("safe") }}'
        assert Jinja2Renderer.render(template, {"obj": Probe()}) == "safe"
        assert Probe.called is False

    def test_alias_still_translates(self):
        """`_("...")` 的正常翻译用法不受影响。"""
        assert Jinja2Renderer.render('{{ _("count=%(n)d", n=count) }}', {"count": 3}) == "count=3"

    def test_trans_block_still_works(self):
        """`{% trans %}` 块的正常用法不受影响。"""
        assert Jinja2Renderer.render("{% trans %}hello{% endtrans %}", {}) == "hello"
