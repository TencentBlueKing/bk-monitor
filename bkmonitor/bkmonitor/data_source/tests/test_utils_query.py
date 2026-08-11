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

from bkmonitor.data_source.constants import FieldTypeEnum
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

    def test_field_type_conflict_when_two_rts_have_different_types(self):
        """两个 RT 同名字段类型不一致时，_query_fields 应将 field_type 标记为 CONFLICT。"""
        rt1_field = _make_field(field_name="status", field_type="keyword", is_agg=True)
        rt2_field = _make_field(field_name="status", field_type="text", is_agg=False, is_analyzed=True)

        # 模拟 _query_fields 中类型不一致时的合并逻辑
        result = BaseQuery.merge_field_metadata(
            {**rt1_field, "field_type": FieldTypeEnum.CONFLICT.value},
            {**rt2_field, "field_type": FieldTypeEnum.CONFLICT.value},
        )

        assert result["field_type"] == FieldTypeEnum.CONFLICT.value
        # is_agg / is_analyzed 仍按 OR 语义合并
        assert result["is_agg"] is True
        assert result["is_analyzed"] is True

    def test_swap_rt_order_produces_same_boolean_flags(self):
        """交换两个 RT 的合并顺序，布尔标志位结果应保持一致（OR/AND 语义均满足交换律）。"""
        rt_a = _make_field(is_agg=True, is_analyzed=False, is_case_sensitive=True)
        rt_b = _make_field(is_agg=False, is_analyzed=True, is_case_sensitive=False)

        result_ab = BaseQuery.merge_field_metadata(rt_a, rt_b)
        result_ba = BaseQuery.merge_field_metadata(rt_b, rt_a)

        assert result_ab["is_agg"] == result_ba["is_agg"]
        assert result_ab["is_analyzed"] == result_ba["is_analyzed"]
        assert result_ab["is_case_sensitive"] == result_ba["is_case_sensitive"]

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
