"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import cast

from rest_framework import serializers

from core.drf_resource.stubgen import generate_entrypoint_type_stubs, render_entrypoint_type_stubs


class FakeShortcut:
    def __init__(self, methods, package_name=__name__):
        self._methods = methods
        self.loaded = True
        self._package = type("Package", (), {"__name__": package_name})()

    def list_method(self):
        return list(self._methods)


class FakeNamespace:
    pass


class DemoResource:
    """演示资源。"""

    class RequestSerializer(serializers.Serializer):
        name = serializers.CharField(required=True, label="名称", help_text="资源名称")
        age = serializers.IntegerField(required=False, label="年龄")

    class ResponseSerializer(serializers.Serializer):
        message = serializers.CharField(required=True, label="消息", help_text="返回消息")
        count = serializers.IntegerField(required=False, label="数量")


class RequestOnlyResource:
    """仅请求参数资源。"""

    class RequestSerializer(serializers.Serializer):
        keyword = serializers.CharField(required=False, label="关键词", help_text="筛选关键字", default="all")
        type = serializers.CharField(required=False, label="Type", default="monitor")


class BaseDocumentedResource:
    """父类文档不应被子类继承。"""


class ChildUndocumentedResource(BaseDocumentedResource):
    class RequestSerializer(serializers.Serializer):
        value = serializers.CharField(required=True, label="值")


class ItemSerializer(serializers.Serializer):
    metric = serializers.CharField(required=True, label="指标")


class NoticeSerializer(serializers.Serializer):
    channel = serializers.CharField(required=True, label="通知渠道")
    enabled = serializers.BooleanField(required=False, label="Enabled", default=True)
    signal = serializers.MultipleChoiceField(choices=["abnormal", "closed"], required=True, label="信号")


class NestedResource:
    """嵌套资源。"""

    class RequestSerializer(serializers.Serializer):
        items = ItemSerializer(many=True, required=True, label="监控项")
        notice = NoticeSerializer(required=True, label="通知配置")

    class ResponseSerializer(serializers.Serializer):
        result = NoticeSerializer(required=True, label="结果")


def helper(value):
    """辅助函数。"""
    return value


class TestDRFResourceStubgen:
    def test_render_entrypoint_type_stubs(self):
        resource_root = FakeNamespace()
        resource_root.demo = FakeShortcut({"ping": DemoResource, "helper": helper, "cast": cast})

        api_root = FakeNamespace()
        api_root.metadata = FakeShortcut({"get_label": DemoResource})

        source = render_entrypoint_type_stubs({"resource": resource_root, "api": api_root})

        assert "from typing import Any, Literal, Mapping, NotRequired, Required, TypedDict, Unpack, overload" in source
        assert "_resource_demo_ping_Request = TypedDict(" in source
        assert '"name": Required[str]' in source
        assert '"age": NotRequired[int]' in source
        assert "_resource_demo_ping_Response = TypedDict(" in source
        assert '"message": Required[str]' in source
        assert "class _resource_demo:" in source
        assert "# source: core/tests/test_drf_resource_stubgen.py:DemoResource" in source
        assert "# source: core/tests/test_drf_resource_stubgen.py:helper" in source
        assert "@overload" in source
        assert (
            "def ping(self, request_data: _resource_demo_ping_Request | None = ...) -> _resource_demo_ping_Response: ..."
            in source
        )
        assert (
            "def ping(self, **kwargs: Unpack[_resource_demo_ping_Request]) -> _resource_demo_ping_Response: ..."
            in source
        )
        assert "def ping(self, request_data: _resource_demo_ping_Request | None = ..., **kwargs: Any)" not in source
        assert '"""' in source
        assert "演示资源。" in source
        assert "Args:" in source
        assert "├── name (str): 名称；资源名称；必填" in source
        assert "└── age (int): 年龄；可选" in source
        assert "Returns:" in source
        assert "响应数据。" in source
        assert "message (str): 消息；返回消息" in source
        assert "count (int): 数量" in source
        assert "def helper(self, *args: Any, **kwargs: Any) -> Any:" in source
        assert "辅助函数。" in source
        assert "def cast(self, *args: Any, **kwargs: Any) -> Any: ..." not in source
        assert "typing.py:cast" not in source
        assert "class _api_metadata:" in source
        assert (
            "def get_label(self, request_data: _api_metadata_get_label_Request | None = ...) "
            "-> _api_metadata_get_label_Response: ..."
        ) in source
        assert (
            "def get_label(self, **kwargs: Unpack[_api_metadata_get_label_Request]) "
            "-> _api_metadata_get_label_Response: ..."
        ) in source
        assert "resource: _resource" in source
        assert "api: _api" in source
        assert "adapter: Any" in source

    def test_resource_docstring_without_response_section(self):
        resource_root = FakeNamespace()
        resource_root.demo = FakeShortcut({"query": RequestOnlyResource})

        source = render_entrypoint_type_stubs({"resource": resource_root})

        assert "仅请求参数资源。" in source
        assert "├── keyword (str): 关键词；筛选关键字；可选；默认值: 'all'" in source
        assert "└── type (str): 可选；默认值: 'monitor'" in source
        assert "默认值: ''" not in source
        assert "默认值: []" not in source
        assert "默认值: {}" not in source
        query_section = source.split("def query(self, *args: Any, **kwargs: Any) -> Any:", 1)[1]
        assert "Returns:" not in query_section.split("class ", 1)[0]

    def test_generate_entrypoint_type_stubs(self, tmp_path):
        resource_root = FakeNamespace()
        resource_root.demo = FakeShortcut({"ping": DemoResource})

        output_path = tmp_path / "__init__.pyi"
        result = generate_entrypoint_type_stubs(output_path=output_path, root_objects={"resource": resource_root})

        assert result == output_path
        assert output_path.exists()
        assert "class _resource_demo:" in output_path.read_text(encoding="utf-8")

    def test_child_resource_does_not_inherit_parent_docstring(self):
        resource_root = FakeNamespace()
        resource_root.demo = FakeShortcut({"child": ChildUndocumentedResource})

        source = render_entrypoint_type_stubs({"resource": resource_root})

        child_section = source.split("def child(self, *args: Any, **kwargs: Any) -> Any:", 1)[1]
        child_body = child_section.split("class ", 1)[0]
        assert "父类文档不应被子类继承。" not in child_body
        assert "Args:" in child_body
        assert "└── value (str): 值；必填" in child_body

    def test_nested_models_are_rendered_in_docstring(self):
        resource_root = FakeNamespace()
        resource_root.demo = FakeShortcut({"nested": NestedResource})

        source = render_entrypoint_type_stubs({"resource": resource_root})

        assert "├── items (list[ItemsItem]): 监控项；必填" in source
        assert "│   └── metric (str): 指标；必填" in source
        assert "└── notice (NoticeModel): 通知配置；必填" in source
        assert "    ├── channel (str): 通知渠道；必填" in source
        assert "    ├── enabled (bool): 可选；默认值: True" in source
        assert "    └── signal (list[str]): 信号；必填；可选值: 'abnormal', 'closed'" in source
        assert "Request Models:" not in source
        assert "Response Models:" in source
        assert "ResultModel:" in source
