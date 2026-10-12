"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from semconv.rum.field import FieldSpec


class FieldRegistry:
    """字段注册表。

    遍历以 ``root`` 为根的字段树，将每个字段的完整路径（父级路径 + 字段名，以 ``.`` 连接）
    注册到内部映射。支持同一 ``FieldSpec`` 实例出现在多条路径（共享引用），
    但同一路径不允许重复注册。

    用法::

        registry = FieldRegistry(SpanSpec(field_name=""))
        spec = registry.from_field("attributes.span_type")
    """

    def __init__(self, root: FieldSpec) -> None:
        self.originals: dict[str, FieldSpec] = {}
        self.bound_fields: dict[str, FieldSpec] = {}
        self._collect(root, parent_path="")

    def _collect(self, field: FieldSpec, parent_path: str) -> None:
        full_path = f"{parent_path}.{field.field_name}" if parent_path else field.field_name
        if full_path:
            if full_path in self.originals:
                raise ValueError(f"字段路径重复注册: {full_path}")
            self.originals[full_path] = field
            self.bound_fields[full_path] = field.bind(full_path)
        for child in field.children():
            self._collect(child, parent_path=full_path)

    def from_field(self, field_name: str) -> FieldSpec:
        """按完整路径查找字段描述符。

        :param field_name: 字段完整路径，如 ``"attributes.span_type"``。
        :return: 已注册的 bound ``FieldSpec`` 对象（``get_full_field_name()`` 返回完整路径）；
            未注册时返回仅含原始字段名的新 ``FieldSpec``。
        """
        spec = self.bound_fields.get(field_name)
        return spec if spec is not None else FieldSpec(field_name)

    def fields(self) -> list[FieldSpec]:
        return list(self.bound_fields.values())
