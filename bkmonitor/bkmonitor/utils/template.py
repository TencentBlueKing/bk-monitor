"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import logging
import re
from collections import defaultdict
from os import path

import arrow
from django.conf import settings
from django.template.exceptions import TemplateDoesNotExist
from django.template.loader import get_template
from django.utils import translation
from django.utils.translation import gettext as _
from jinja2.sandbox import SandboxedEnvironment as Environment
from jinja2 import Undefined
from jinja2.compiler import CodeGenerator
from markupsafe import Markup

try:
    from jinja2.utils import pass_context  # jinja2 3.x
except ImportError:
    from jinja2.utils import contextfunction as pass_context  # jinja2 2.x

from bkmonitor.utils.text import cut_str_by_max_bytes, get_content_length
from constants.action import NoticeWay

logger = logging.getLogger(__name__)


class NoticeRowRenderer:
    """
    行渲染器
    """

    LineTemplateMapping = defaultdict(
        lambda: "{title}{content}",
        {
            "mail": '<tr style="background: #FFFFFF;"><td style="color: #979BA5; font-size: 14px; height: 19px; '
            'vertical-align: text-top;">{title}</td><td style="color: #63656E; font-size: 14px; '
            'vertical-align: text-top;">{content}</td></tr><tr style="background: #FFFFFF;">'
            '<td colspan="4" style="height: 20px;"></td></tr>',
            "markdown": "**{title}**{content}",
        },
    )

    @classmethod
    def format(cls, notice_way, title, content):
        """
        格式化
        :param notice_way: 通知方式
        :param title: 标题
        :param content: 文本
        """
        title = str(title).strip()
        content = str(content).strip()
        if title:
            title += ": "
        if not title and not content:
            return ""
        msg_type = notice_way
        if msg_type in settings.MD_SUPPORTED_NOTICE_WAYS:
            msg_type = "markdown"
        return cls.LineTemplateMapping[msg_type].format(title=title, content=content)

    @classmethod
    def render_line(cls, line, context):
        """
        使用行模板渲染一行渲染一行
        :param line:
        :param context:
        :return:
        """
        # 是否符合行模板格式
        if not re.match(r"^#.*#", line):
            return line

        title, content = line[1:].split("#", 1)
        return cls.format(context.get("notice_way"), title=title, content=content)

    @classmethod
    def render(cls, content, context):
        notice_way = context.get("notice_way")

        lines = []
        for line in content.splitlines():
            line = cls.render_line(line, context)
            # markdown模式下，保留空行
            if not line.strip() and notice_way not in settings.MD_SUPPORTED_NOTICE_WAYS:
                continue
            lines.append(line)

        return "\n".join(lines)


class CustomTemplateRenderer:
    """
    自定义模板渲染器
    """

    @staticmethod
    def render(content, context):
        action_id = context.get("action").id if context.get("action") else None
        try:
            content_template = Jinja2Renderer.render(context.get("content_template") or "", context)
        except Exception as error:
            # 默认所有的异常错误都用系统默认模板渲染
            logger.error(
                "$%s render content failed :%s, content_template %s",
                action_id,
                str(error),
                context.get("content_template"),
            )
            error_info = _(
                "用户配置的通知模板渲染失败，默认使用系统内置模板，渲染失败可能是使用了不正确的语法，具体请查看策略配置{}"
            ).format(context.get("alarm").strategy_url)
            content_template = Jinja2Renderer.render(context.get("default_content_template") or "", context)
            content_template += "\n" + NoticeRowRenderer().format(
                context.get("notice_way"), title=_("备注"), content=error_info
            )
        alarm_content = NoticeRowRenderer.render(content_template, context)

        notice_way = context.get("notice_way")
        if notice_way == NoticeWay.MAIL:
            content = content.replace("\n", "")
        context["user_content"] = alarm_content
        encoding = context.get("encoding", None)
        content_length = get_content_length(alarm_content, encoding=encoding)
        if context.get("user_content_length") and content_length > context["user_content_length"]:
            alarm_content = cut_str_by_max_bytes(alarm_content, context["user_content_length"], encoding=encoding)
            context["user_content"] = f"{alarm_content[: len(alarm_content) - 3]}..."
        title_content = ""
        try:
            title_content = Jinja2Renderer.render(context.get("title_template") or "", context)
        except Exception as error:
            logger.error(
                "$%s render title failed :%s, title_template %s", action_id, str(error), context.get("title_template")
            )
        if not title_content:
            # 没有自定义通知标题，用默认模板
            title_content = Jinja2Renderer.render(context.get("default_title_template") or "", context)
        context["user_title"] = title_content
        return content


class CustomOperateTemplateRenderer:
    """
    自定义处理记录模板渲染器
    """

    @staticmethod
    def render(content, context):
        content_template = Jinja2Renderer.render(getattr(context["action_instance"], "content_template", ""), context)
        action_content = NoticeRowRenderer.render(content_template, context)
        context["operate_content"] = action_content
        return content


class Jinja2Renderer:
    """
    Jinja2渲染器
    """

    @staticmethod
    def render(content, context):
        """
        支持json和re函数
        """
        notice_way = context.get("notice_way")
        if notice_way in settings.MD_SUPPORTED_NOTICE_WAYS:
            autoescape = True
            escape_func = escape_markdown
        else:
            autoescape = False
            escape_func = None

        return (
            jinja2_environment(autoescape=autoescape, escape_func=escape_func)
            .from_string(content)
            .render({"json": json, "re": re, "arrow": arrow, **context})
        )


class AlarmNoticeTemplate:
    """
    通知模板
    """

    Renderers = [
        CustomTemplateRenderer,
        Jinja2Renderer,
    ]

    def __init__(self, template_path=None, template_content=None, language_suffix=None):
        """
        :param template_path: 模板路径
        :param language_suffix: 语言后缀
        :type template_path: str or unicode
        """
        if template_path:
            self.template = self.get_template(template_path, language_suffix)
        elif template_content is not None:
            self.template = template_content
        else:
            self.template = ""

    def render(self, context):
        """
        模板渲染
        :param context: 上下文
        :return: 渲染后内容
        :rtype: str
        """
        template_message = self.template
        for renderer in self.Renderers:
            template_message = renderer.render(template_message, context)

        return template_message.replace("\\n", "\n").replace("\\t", "\t")

    @staticmethod
    def get_template_source(template_path):
        """
        获取模板文本
        :param template_path: 模板路径
        :return: 模板消息
        """
        raw_template = get_template(template_path)
        with open(raw_template.template.filename, encoding="utf-8") as f:
            return f.read()

    @staticmethod
    def get_default_path(template_path, language_suffix=None):
        """
        获取默认模板路径
        :param template_path: 模板路径
        :param language_suffix: 语言后缀
        """
        if language_suffix:
            # 如果有有语言后缀的情况下，在获取默认的模版时候，需要忽略
            template_path = template_path.replace(language_suffix, "")
        dir_path, filename = path.split(template_path)
        name, ext = path.splitext(filename)
        names = name.split("_")
        name = f"default_{names[-1]}{ext}"
        return path.join(dir_path, name)

    @classmethod
    def get_template(cls, template_path, language_suffix=None):
        """
        查找模板
        :param template_path: 模板路径
        :param language_suffix: 语言后缀
        """
        if not template_path:
            return ""

        try:
            return cls.get_template_source(template_path)
        except TemplateDoesNotExist:
            logger.info(f"use empty template because {template_path} not exists")
        except Exception as e:
            logger.info(f"use default template because {template_path} load fail, {e}")
        template_path = cls.get_default_path(template_path, language_suffix)

        try:
            return cls.get_template_source(template_path)
        except TemplateDoesNotExist:
            logger.info(f"use empty template because {template_path} not exists")
        except Exception as e:
            logger.info(f"use empty template because {template_path} load fail, {e}")
        return ""


class AlarmOperateNoticeTemplate(AlarmNoticeTemplate):
    Renderers = [
        CustomTemplateRenderer,
        CustomOperateTemplateRenderer,
        Jinja2Renderer,
    ]


class UndefinedSilently(Undefined):
    def _fail_with_undefined_error(self, *args, **kwargs):
        return UndefinedSilently()

    def __unicode__(self):
        return ""

    def __str__(self):
        return ""

    __add__ = __radd__ = __mul__ = __rmul__ = __div__ = __rdiv__ = __truediv__ = __rtruediv__ = __floordiv__ = (
        __rfloordiv__
    ) = __mod__ = __rmod__ = __pos__ = __neg__ = __call__ = __getitem__ = __lt__ = __le__ = __gt__ = __ge__ = (
        __int__
    ) = __float__ = __complex__ = __pow__ = __rpow__ = __sub__ = __rsub__ = _fail_with_undefined_error


class LocalOverridingCodeGenerator(CodeGenerator):
    def visit_Template(self, *args, **kwargs):
        super().visit_Template(*args, **kwargs)
        overrides = getattr(self.environment, "_codegen_overrides", {})

        if overrides:
            self.writeline("")

        for name, override in overrides.items():
            self.writeline(f"{name} = {override}")


class DynAutoEscapeEnvironment(Environment):
    code_generator_class = LocalOverridingCodeGenerator

    def __init__(self, *args, **kwargs):
        escape_func = kwargs.pop("escape_func", None)
        markup_class = kwargs.pop("markup_class", None)

        super().__init__(*args, **kwargs)

        # we need to disable constant-evaluation at compile time, because it
        # calls jinja's own escape function.
        #
        # this is done by jinja itself if a finalize function is set and it
        # is marked as a contextfunction. this is accomplished by either
        # suppling a no-op contextfunction itself or wrapping an existing
        # finalize in a contextfunction
        if self.finalize:
            if not (
                getattr(self.finalize, "contextfunction", False)  # jinja2 2.x
                or getattr(self.finalize, "jinja_pass_arg", False)  # jinja2 3.x
            ):
                _finalize = getattr(self, "finalize")
                self.finalize = lambda _, v: _finalize(v)
        else:
            self.finalize = lambda _, v: v
        pass_context(self.finalize)

        self._codegen_overrides = {}

        if escape_func:
            self._codegen_overrides["escape"] = "environment.escape_func"
            self.escape_func = escape_func
            self.filters["e"] = escape_func
            self.filters["escape"] = escape_func

        if markup_class:
            self._codegen_overrides["markup"] = "environment.markup_class"
            self.markup_class = markup_class


def escape_markdown(value):
    """
    markdown字符转义
    """
    if isinstance(value, Markup):
        return value

    if isinstance(value, str):
        if not value or re.match(r"^\*\*.*\*\*", value):
            return value

        value = value.replace("\\", r"\\")
        value = value.replace("*", r"\*")
        value = value.replace("`", r"\`")
        value = value.replace(" _", r" \_")

    return Markup(value)


def jinja2_environment(**options):
    if options.get("autoescape", False) and "escape_func" in options:
        env = DynAutoEscapeEnvironment(
            undefined=UndefinedSilently,
            extensions=["jinja2.ext.i18n"],
            escape_func=options.pop("escape_func"),
            **options,
        )
    else:
        options.pop("escape_func", None)
        env = Environment(undefined=UndefinedSilently, extensions=["jinja2.ext.i18n"], **options)
    env.install_gettext_translations(translation, newstyle=True)
    return env


def jinja_render(template_value, context):
    """
    支持object的jinja2渲染
    :param context: 上下文
    :param template_value:渲染模板
    :return:
    """
    if isinstance(template_value, str):
        return Jinja2Renderer.render(template_value, context) or template_value
    if isinstance(template_value, dict):
        render_value = {}
        for key, value in template_value.items():
            render_value[key] = jinja_render(value, context)
        return render_value
    if isinstance(template_value, list):
        return [jinja_render(value, context) for value in template_value]
    return template_value
