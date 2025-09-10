# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


import inspect
import logging

from django.template import engines

django_engine = engines["django"]

logger = logging.getLogger(__name__)

TEMPLATE = """# -*- coding: UTF-8 -*-

class ConfigureMixin(object):
    {% for module, methods in tree.items %}{% if module == "adapter" %}
    class adapter:
        {% for adapter_module, adapter_methods in methods.items %}
        class {{ adapter_module }}:{% for method_name, method in adapter_methods.items %}
            from {{ method.module }} import {{ method.name}} as {{ method_name }}{% endfor %}
            {% for method_name, method in adapter_methods.items %}{% if method.type == "function" %}
            {{ method_name }}: function = {{ method_name }}{% else %}
            {{ method_name }}: {{ method_name }} = ...{% endif %}{% endfor %}
            ...
        {% endfor %}
    {% else %}
    class {{ module }}:{% for method_name, method in methods.items %}
        from {{ method.module }} import {{ method.name}} as {{ method_name }}{% endfor %}
        {% for method_name, method in methods.items %}{% if method.type == "function" %}
        {{ method_name }}: function = {{ method_name }}{% else %}
        {{ method_name }}: {{ method_name }} = ...{% endif %}{% endfor %}
        ...
    {% endif %}{% endfor %}
    ...
"""


template = django_engine.from_string(TEMPLATE)


def render(define_tree, tab=0):
    result = ""
    # 初始化
    if tab == 0:
        result += "# -*- coding: UTF-8 -*-\n\nclass ConfigureMixin(object):\n"
        result += render(define_tree, tab + 1)
        result += "    ...\n"
        return result

    # 缩进数量计算
    tab_string = "    " * tab

    # 引入依赖
    for key, value in list(define_tree.items()):
        if value.get("type") in ["class", "function"]:
            result += "{}from {} import {} as {}\n".format(tab_string, value["module"], value["name"], key)

    # 函数及类定义
    for key, value in list(define_tree.items()):
        if value.get("type") == "class":
            result += "{}{}: {} = ...\n".format(tab_string, key, key)
        elif value.get("type") == "function":
            result += "{}{}: function = {}\n".format(tab_string, key, key)

    # 递归定义子类
    for key, value in list(define_tree.items()):
        if value.get("type") not in ["class", "function"]:
            result += "\n{}class {}:\n".format(tab_string, key)
            result += render(value, tab + 1)
            result += "%s    ...\n" % tab_string

    return result


def search_attr(instance):
    resource_tree = {}

    for name in dir(instance):
        if name.startswith("_"):
            continue
        obj = getattr(instance, name)

        if hasattr(obj, "list_method"):
            try:
                obj._setup()
            except Exception as err:
                logger.exception(err)
            resource_tree[name] = {}
            for key, value in list(obj._methods.items()):
                resource_tree[name][key] = {"name": value.__name__, "module": value.__module__, "cls": value}
                if inspect.isfunction(value):
                    resource_tree[name][key]["type"] = "function"
                else:
                    resource_tree[name][key]["type"] = "class"
        else:
            resource_tree[name] = search_attr(obj)

    return resource_tree


def update_stub_file():
    import os

    from core.drf_resource import resource

    tree = search_attr(resource)

    with open(os.path.join(os.path.dirname(__file__), "config.pyi"), "w+") as fp:
        fp.write(render(tree))
