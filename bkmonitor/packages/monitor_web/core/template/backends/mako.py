# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import copy

from blueapps.utils import get_request

"""
Learn more at:
https://gist.github.com/artscoop/0eba5033527f9e488ee17b346d16284d
"""


from django.conf import settings
from django.template import TemplateDoesNotExist, TemplateSyntaxError
from django.template.backends.base import BaseEngine
from django.template.backends.utils import csrf_input_lazy, csrf_token_lazy
from django.template.context import _builtin_context_processors
from django.utils.functional import cached_property
from django.utils.module_loading import import_string
from mako import exceptions as mako_exceptions
from mako.lookup import TemplateLookup as MakoTemplateLookup
from mako.template import Template as MakoTemplate


class MakoTemplates(BaseEngine):

    app_dirname = "mako"

    def __init__(self, params):
        params = params.copy()
        options = params.pop("OPTIONS").copy()
        super(MakoTemplates, self).__init__(params)

        # Defaut values for initializing the MakoTemplateLookup class
        # You can define them in the backend OPTIONS dict.
        options.setdefault("directories", self.template_dirs)
        options.setdefault("module_directory", settings.MAKO_TEMPLATE_MODULE_DIR)
        options.setdefault("input_encoding", settings.FILE_CHARSET)
        options.setdefault("output_encoding", settings.FILE_CHARSET)
        options.setdefault("encoding_errors", "replace")
        options.setdefault("collection_size", 500)

        # Use context processors like Django
        context_processors = options.pop("context_processors", [])
        self.context_processors = context_processors

        # Use the mako template lookup class to find templates
        self.lookup = MakoTemplateLookup(**options)

    @cached_property
    def template_context_processors(self):
        context_processors = _builtin_context_processors
        context_processors += tuple(self.context_processors)
        return tuple(import_string(path) for path in set(context_processors))

    def from_string(self, template_code):
        try:
            return Template(MakoTemplate(template_code, lookup=self.lookup))
        except mako_exceptions.SyntaxException as e:
            raise TemplateSyntaxError(e.args)

    def get_template(self, template_name):
        try:
            return Template(self.lookup.get_template(template_name), self.template_context_processors)
        except mako_exceptions.TemplateLookupException as e:
            raise TemplateDoesNotExist(e.args)
        except mako_exceptions.CompileException as e:
            raise TemplateSyntaxError(e.args)


class Template(object):
    def __init__(self, template, context_processors):
        self.template = template
        self.context_processors = context_processors

    def render(self, context=None, request=None):
        if context is None:
            context = {}

        if request is None:
            try:
                request = get_request()
            except Exception:
                pass

        if request is not None:
            origin_context = copy.deepcopy(context)
            for processor in self.context_processors:
                try:
                    context.update(processor(request))
                except Exception:
                    pass

            context["request"] = request
            context["csrf_input"] = csrf_input_lazy(request)
            context["csrf_token"] = csrf_token_lazy(request)
            context.update(origin_context)

        return self.template.render_unicode(**context)
