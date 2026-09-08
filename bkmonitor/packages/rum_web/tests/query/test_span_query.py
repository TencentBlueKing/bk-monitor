"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any
from unittest.mock import patch

from semconv.rum.field import FieldSpec, RatingLevel


# ── 辅助：直接调用静态方法，无需实例化 SpanQuery ──────────────────────────────


def apply_spec(field_dict: dict[str, Any], spec: FieldSpec) -> dict[str, Any]:
    """代理调用 SpanQuery._apply_field_spec，避免在测试中引入重量级依赖。"""
    from packages.rum_web.handlers.query.span import SpanQuery

    return SpanQuery._apply_field_spec(field_dict, spec)


class TestApplyFieldSpec:
    """SpanQuery._apply_field_spec 各分支行为测试。"""

    def test_alias_from_spec(self):
        """spec 有 field_alias 时写入 field_alias。"""
        spec = FieldSpec(field_name="foo", field_alias="Foo 别名")
        result = apply_spec({}, spec)
        assert result["field_alias"] == "Foo 别名"

    def test_alias_fallback_to_existing(self):
        """spec 无 field_alias 时保留 field_dict 中已有的 field_alias。"""
        spec = FieldSpec(field_name="foo")
        result = apply_spec({"field_alias": "已有别名"}, spec)
        assert result["field_alias"] == "已有别名"

    def test_alias_fallback_to_field_name(self):
        """spec 无 field_alias 且 field_dict 无 field_alias 时回退到 field_name。"""
        spec = FieldSpec(field_name="foo")
        result = apply_spec({}, spec)
        assert result["field_alias"] == "foo"

    def test_is_real_written(self):
        """is_real 始终写入。"""
        assert apply_spec({}, FieldSpec(field_name="x", is_real=True))["is_real"] is True
        assert apply_spec({}, FieldSpec(field_name="x", is_real=False))["is_real"] is False

    def test_field_unit_written_when_set(self):
        """spec 有 field_unit 时写入。"""
        spec = FieldSpec(field_name="x", field_unit="ms")
        assert apply_spec({}, spec)["field_unit"] == "ms"

    def test_field_unit_not_written_when_none(self):
        """spec 无 field_unit 时不写入，不覆盖原有值。"""
        spec = FieldSpec(field_name="x")
        result = apply_spec({"field_unit": "us"}, spec)
        assert result["field_unit"] == "us"

    def test_field_type_written_when_set(self):
        """spec 有 field_type 时写入。"""
        spec = FieldSpec(field_name="x", field_type="double")
        assert apply_spec({}, spec)["field_type"] == "double"

    def test_field_type_not_written_when_none(self):
        """spec 无 field_type 时不写入。"""
        spec = FieldSpec(field_name="x")
        assert "field_type" not in apply_spec({}, spec)

    def test_field_display_type_written_when_set(self):
        """spec 有 field_display_type 时写入。"""
        spec = FieldSpec(field_name="x", field_display_type="duration")
        assert apply_spec({}, spec)["field_display_type"] == "duration"

    def test_field_display_type_not_written_when_none(self):
        """spec 无 field_display_type 时不写入。"""
        spec = FieldSpec(field_name="x")
        assert "field_display_type" not in apply_spec({}, spec)

    def test_option_values_serialized(self):
        """option_values 转换为 {value, alias} 列表。"""
        from semconv.rum.constants import RumSpanType

        spec = FieldSpec(field_name="x", option_values=RumSpanType)
        result = apply_spec({}, spec)
        assert "option_values" in result
        assert all("value" in item and "alias" in item for item in result["option_values"])
        values = [item["value"] for item in result["option_values"]]
        assert "view" in values
        assert "resource" in values

    def test_option_values_not_written_when_none(self):
        """spec 无 option_values 时不写入。"""
        spec = FieldSpec(field_name="x")
        assert "option_values" not in apply_spec({}, spec)

    def test_rating_config_poor_omits_value(self):
        """末档 poor（value=None）序列化时省略 value 键。"""
        spec = FieldSpec(
            field_name="LCP",
            rating_config=(
                RatingLevel(rating="good", value=2500),
                RatingLevel(rating="needs_improvement", value=4000),
                RatingLevel(rating="poor"),
            ),
        )
        result = apply_spec({}, spec)
        assert result["rating_config"] == [
            {"rating": "good", "value": 2500},
            {"rating": "needs_improvement", "value": 4000},
            {"rating": "poor"},
        ]
        assert "value" not in result["rating_config"][2]

    def test_rating_config_cls_decimal(self):
        """CLS 评级阈值为小数，末档省略 value。"""
        spec = FieldSpec(
            field_name="CLS",
            rating_config=(
                RatingLevel(rating="good", value=0.1),
                RatingLevel(rating="needs_improvement", value=0.25),
                RatingLevel(rating="poor"),
            ),
        )
        result = apply_spec({}, spec)
        assert result["rating_config"][0] == {"rating": "good", "value": 0.1}
        assert result["rating_config"][1] == {"rating": "needs_improvement", "value": 0.25}
        assert result["rating_config"][2] == {"rating": "poor"}

    def test_rating_config_not_written_when_empty(self):
        """spec 无 rating_config 时不写入。"""
        spec = FieldSpec(field_name="x")
        assert "rating_config" not in apply_spec({}, spec)

    def test_returns_same_dict(self):
        """返回值与传入的 field_dict 是同一对象（原地修改）。"""
        d: dict[str, Any] = {}
        spec = FieldSpec(field_name="x")
        assert apply_spec(d, spec) is d


class TestQueryFieldsVirtual:
    """SpanQuery.query_fields 虚拟字段路径与同名字段场景测试。"""

    def _make_query(self):
        """构造一个最小化的 SpanQuery 实例，_query_fields 返回空 field_map。"""
        from packages.rum_web.handlers.query.span import SpanQuery

        instance = object.__new__(SpanQuery)
        return instance

    def _run_query_fields(self, base_field_map: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """以 base_field_map 作为 _query_fields 的返回值，执行 query_fields 并返回结果。"""
        from bkmonitor.data_source.utils.query import BaseQuery

        instance = self._make_query()
        instance.data_sources = []  # type: ignore[attr-defined]
        with patch.object(BaseQuery, "_query_fields", return_value=base_field_map):
            return instance.query_fields(None, None)

    def test_virtual_fields_injected(self):
        """虚拟字段（is_real=False）被注入到 field_map 中。"""
        result = self._run_query_fields({})
        # CLS/INP/LCP/FCP/TTFB 均为虚拟字段
        assert "LCP" in result
        assert "CLS" in result
        assert "INP" in result
        assert "FCP" in result
        assert "TTFB" in result

    def test_virtual_field_is_real_false(self):
        """注入的虚拟字段 is_real 为 False。"""
        result = self._run_query_fields({})
        assert result["LCP"]["is_real"] is False
        assert result["CLS"]["is_real"] is False

    def test_virtual_field_full_path_as_key(self):
        """虚拟字段以完整路径（get_full_field_name()）作为 field_map 的 key。"""
        from semconv.rum.trace import SpanSpec

        result = self._run_query_fields({})
        # 直接对照 spec 注册的完整路径，确保 key 不是短名
        for spec in SpanSpec.fields():
            if spec.is_real:
                continue
            full_path = spec.get_full_field_name()
            assert full_path in result, f"虚拟字段完整路径 {full_path!r} 未出现在 field_map 中"
            assert result[full_path]["field_name"] == full_path, (
                f"虚拟字段 key={full_path!r} 对应的 field_name={result[full_path]['field_name']!r} 与完整路径不一致"
            )

    def test_virtual_field_origin_field(self):
        """根级虚拟字段（无 .）的 origin_field 等于自身。"""
        result = self._run_query_fields({})
        # LCP 是根级字段，field_name="LCP"，无 . 分隔
        assert result["LCP"]["origin_field"] == "LCP"

    def test_virtual_field_rating_config_poor_no_value(self):
        """虚拟字段 LCP 的 rating_config 末档不含 value 键。"""
        result = self._run_query_fields({})
        lcp = result["LCP"]
        assert "rating_config" in lcp
        poor = lcp["rating_config"][-1]
        assert poor["rating"] == "poor"
        assert "value" not in poor

    def test_real_field_is_real_from_spec(self):
        """真实字段的 is_real 由 spec 决定，spec 注册为 is_real=True 的字段经过 _apply_field_spec 后 is_real 为 True。"""
        base = {"elapsed_time": {"field_name": "elapsed_time"}}
        result = self._run_query_fields(base)
        # elapsed_time 在 SpanSpec 中注册为 is_real=True
        assert result["elapsed_time"]["is_real"] is True

    # ── 嵌套虚拟字段测试辅助 ────────────────────────────────────────────────
    # SpanSpec 目前只有根级虚拟字段（CLS/INP/LCP/FCP/TTFB），无嵌套虚拟字段。
    # 以下三个测试通过 patch SpanSpec.fields() 注入一个嵌套虚拟字段（full_path 含 .），
    # 确保循环体真正执行，而非空转。

    def _nested_virtual_spec(self) -> "FieldSpec":
        """构造一个完整路径为 'attributes.__test_virtual__' 的嵌套虚拟字段 spec。"""
        from semconv.rum.field import FieldSpec
        from semconv.rum.registry import FieldRegistry

        class _FakeParent(FieldSpec):
            CHILD = FieldSpec(field_name="__test_virtual__", is_real=False)

        registry = FieldRegistry(_FakeParent(field_name="attributes"))
        # bound spec 的 get_full_field_name() == "attributes.__test_virtual__"
        return registry.fields()[-1]

    def _run_query_fields_with_nested_virtual(
        self, base_field_map: dict[str, dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        """在 SpanSpec.fields() 中额外注入一个嵌套虚拟字段后执行 query_fields。"""
        from semconv.rum.trace import SpanSpec
        from bkmonitor.data_source.utils.query import BaseQuery

        nested_spec = self._nested_virtual_spec()
        original_fields = SpanSpec.fields()

        instance = self._make_query()
        instance.data_sources = []  # type: ignore[attr-defined]
        with (
            patch.object(BaseQuery, "_query_fields", return_value=base_field_map),
            patch.object(SpanSpec, "fields", return_value=original_fields + [nested_spec]),
        ):
            return instance.query_fields(None, None)

    def test_nested_virtual_field_key_is_full_path(self):
        """嵌套虚拟字段以完整路径（含父级前缀）作为 field_map 的 key，而非短名。"""
        result = self._run_query_fields_with_nested_virtual({})
        nested_key = "attributes.__test_virtual__"
        assert nested_key in result, f"嵌套虚拟字段 {nested_key!r} 未出现在 field_map 中"
        assert result[nested_key]["field_name"] == nested_key, (
            f"嵌套虚拟字段 key={nested_key!r} 对应的 field_name={result[nested_key]['field_name']!r} 与完整路径不一致"
        )

    def test_nested_virtual_field_origin_field(self):
        """嵌套虚拟字段（含 . 的完整路径）的 origin_field 取路径第一段，而非短名。"""
        result = self._run_query_fields_with_nested_virtual({})
        nested_key = "attributes.__test_virtual__"
        assert nested_key in result, f"嵌套虚拟字段 {nested_key!r} 未出现在 field_map 中"
        assert result[nested_key]["origin_field"] == "attributes", (
            f"嵌套虚拟字段 {nested_key!r} 的 origin_field 应为 'attributes'，"
            f"实际为 {result[nested_key]['origin_field']!r}"
        )

    def test_nested_virtual_field_not_keyed_by_short_name(self):
        """嵌套虚拟字段不能以短名（去掉父级前缀后的最后一段）作为 key 写入 field_map。"""
        result = self._run_query_fields_with_nested_virtual({})
        short_name = "__test_virtual__"
        # 短名不应单独出现在 field_map 的 key 中
        assert short_name not in result, f"嵌套虚拟字段的短名 {short_name!r} 不应作为独立 key 出现在 field_map 中"

    def test_real_fields_get_spec_applied(self):
        """真实字段经过 _apply_field_spec 后携带 field_alias。"""
        base = {
            "elapsed_time": {
                "field_name": "elapsed_time",
                "field_type": "long",
                "is_searchable": True,
                "is_agg": True,
                "is_list": True,
            }
        }
        result = self._run_query_fields(base)
        # elapsed_time 在 SpanSpec 中有 field_alias
        assert result["elapsed_time"]["field_alias"] != ""
        assert result["elapsed_time"]["is_real"] is True
