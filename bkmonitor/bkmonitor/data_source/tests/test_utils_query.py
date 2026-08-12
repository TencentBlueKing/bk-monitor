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

from constants.otel_query import FieldTypeEnum
from bkmonitor.data_source.utils.query import BaseQuery


def _make_field(
    *,
    is_agg: bool = False,
    is_analyzed: bool = False,
    is_case_sensitive: bool = True,
    field_type: str = "keyword",
    field_name: str = "cpu_usage",
    **extra,
) -> dict:
    """构造字段元数据字典，方便测试用例复用。"""
    return {
        "field_name": field_name,
        "field_type": field_type,
        "is_agg": is_agg,
        "is_analyzed": is_analyzed,
        "is_case_sensitive": is_case_sensitive,
        **extra,
    }


class TestBaseQuery:
    # ------------------------------------------------------------------
    # merge_field_metadata
    # ------------------------------------------------------------------

    @pytest.mark.parametrize(
        ("current_kwargs", "incoming_kwargs", "expected"),
        [
            # 两者均为 False → 结果为 False
            (
                {"is_agg": False, "is_analyzed": False},
                {"is_agg": False, "is_analyzed": False},
                {"is_agg": False, "is_analyzed": False},
            ),
            # current 为 True → 结果为 True（OR 语义）
            (
                {"is_agg": True, "is_analyzed": True},
                {"is_agg": False, "is_analyzed": False},
                {"is_agg": True, "is_analyzed": True},
            ),
            # incoming 为 True → 结果为 True（OR 语义）
            (
                {"is_agg": False, "is_analyzed": False},
                {"is_agg": True, "is_analyzed": True},
                {"is_agg": True, "is_analyzed": True},
            ),
            # 两者均为 True → 结果为 True
            (
                {"is_agg": True, "is_analyzed": True},
                {"is_agg": True, "is_analyzed": True},
                {"is_agg": True, "is_analyzed": True},
            ),
        ],
    )
    def test_is_agg_and_is_analyzed_use_or_semantics(self, current_kwargs, incoming_kwargs, expected):
        """is_agg 和 is_analyzed 任一为真则合并结果为真。"""
        current = _make_field(**current_kwargs)
        incoming = _make_field(**incoming_kwargs)
        result = BaseQuery.merge_field_metadata(current, incoming)
        assert result["is_agg"] is expected["is_agg"]
        assert result["is_analyzed"] is expected["is_analyzed"]

    @pytest.mark.parametrize(
        ("current_sensitive", "incoming_sensitive", "expected_sensitive"),
        [
            (True, True, True),  # 两者均区分大小写 → 保持区分
            (True, False, False),  # 任一不区分 → 合并后不区分
            (False, True, False),  # 任一不区分 → 合并后不区分
            (False, False, False),  # 两者均不区分 → 合并后不区分
        ],
    )
    def test_is_case_sensitive_uses_and_semantics(self, current_sensitive, incoming_sensitive, expected_sensitive):
        """is_case_sensitive 仅当两者均为 True 时结果才为 True（AND 语义）。"""
        current = _make_field(is_case_sensitive=current_sensitive)
        incoming = _make_field(is_case_sensitive=incoming_sensitive)
        result = BaseQuery.merge_field_metadata(current, incoming)
        assert result["is_case_sensitive"] is expected_sensitive

    def test_field_type_conflict_when_two_rts_have_different_types(self, mocker):
        """两个 RT 同名字段类型不一致时，_query_fields 应将 field_type 标记为 CONFLICT。"""
        rt1_fields = [_make_field(field_name="status", field_type="keyword", is_agg=True)]
        rt2_fields = [_make_field(field_name="status", field_type="text", is_agg=False, is_analyzed=True)]

        mocker.patch.object(BaseQuery, "_query_info_fields", side_effect=[rt1_fields, rt2_fields])

        query = BaseQuery()
        result = query._query_fields(
            targets=[("rt1", "space1"), ("rt2", "space1")],
            start_time=1717000000,
            end_time=1717003600,
        )

        assert result["status"]["field_type"] == FieldTypeEnum.CONFLICT.value
        # is_agg / is_analyzed 仍按 OR 语义合并
        assert result["status"]["is_agg"] is True
        assert result["status"]["is_analyzed"] is True

    def test_swap_rt_order_produces_same_boolean_flags(self, mocker):
        """交换两个 RT 的合并顺序，布尔标志位结果应保持一致（OR/AND 语义均满足交换律）。"""
        rt_a_fields = [_make_field(is_agg=True, is_analyzed=False, is_case_sensitive=True)]
        rt_b_fields = [_make_field(is_agg=False, is_analyzed=True, is_case_sensitive=False)]

        mocker.patch.object(BaseQuery, "_query_info_fields", side_effect=[rt_a_fields, rt_b_fields])
        query = BaseQuery()
        result_ab = query._query_fields(
            targets=[("rt_a", "space1"), ("rt_b", "space1")],
            start_time=1717000000,
            end_time=1717003600,
        )

        mocker.patch.object(BaseQuery, "_query_info_fields", side_effect=[rt_b_fields, rt_a_fields])
        result_ba = query._query_fields(
            targets=[("rt_b", "space1"), ("rt_a", "space1")],
            start_time=1717000000,
            end_time=1717003600,
        )

        field_ab = result_ab["cpu_usage"]
        field_ba = result_ba["cpu_usage"]
        assert field_ab["is_agg"] == field_ba["is_agg"]
        assert field_ab["is_analyzed"] == field_ba["is_analyzed"]
        assert field_ab["is_case_sensitive"] == field_ba["is_case_sensitive"]

    def test_returns_new_dict_without_mutating_inputs(self):
        """merge_field_metadata 应返回新字典，不修改原始入参。"""
        current = _make_field(is_agg=False)
        incoming = _make_field(is_agg=True)
        current_copy = dict(current)
        incoming_copy = dict(incoming)

        result = BaseQuery.merge_field_metadata(current, incoming)

        assert result is not current
        assert result is not incoming
        assert current == current_copy
        assert incoming == incoming_copy

    # ------------------------------------------------------------------
    # is_searchable
    # ------------------------------------------------------------------

    @pytest.mark.parametrize(
        ("field_type", "expected_searchable"),
        [
            ("keyword", True),
            ("text", True),
            ("long", True),
            ("double", True),
            ("date", True),
            ("boolean", True),
            ("object", False),
            ("nested", False),
        ],
    )
    def test_is_searchable_by_field_type(self, mocker, field_type, expected_searchable):
        """object 和 nested 类型字段 is_searchable 为 False，其余类型为 True。"""
        mocker.patch.object(
            BaseQuery,
            "_query_info_fields",
            return_value=[_make_field(field_name="f", field_type=field_type)],
        )
        query = BaseQuery()
        result = query._query_fields(
            targets=[("rt1", "space1")],
            start_time=1717000000,
            end_time=1717003600,
        )
        assert result["f"]["is_searchable"] is expected_searchable

    def test_is_searchable_reflects_merged_field_type(self, mocker):
        """两个 RT 同名字段类型冲突时，合并后 field_type 为 CONFLICT，is_searchable 应为 True。"""
        rt1_fields = [_make_field(field_name="status", field_type="keyword")]
        rt2_fields = [_make_field(field_name="status", field_type="text")]

        mocker.patch.object(BaseQuery, "_query_info_fields", side_effect=[rt1_fields, rt2_fields])
        query = BaseQuery()
        result = query._query_fields(
            targets=[("rt1", "space1"), ("rt2", "space1")],
            start_time=1717000000,
            end_time=1717003600,
        )
        # CONFLICT 不属于 object/nested，is_searchable 应为 True
        assert result["status"]["is_searchable"] is True

    def test_is_searchable_false_when_both_rts_have_object_type(self, mocker):
        """两个 RT 同名字段均为 object 类型时，合并后 is_searchable 仍为 False。"""
        rt1_fields = [_make_field(field_name="attrs", field_type="object")]
        rt2_fields = [_make_field(field_name="attrs", field_type="object")]

        mocker.patch.object(BaseQuery, "_query_info_fields", side_effect=[rt1_fields, rt2_fields])
        query = BaseQuery()
        result = query._query_fields(
            targets=[("rt1", "space1"), ("rt2", "space1")],
            start_time=1717000000,
            end_time=1717003600,
        )
        assert result["attrs"]["is_searchable"] is False
