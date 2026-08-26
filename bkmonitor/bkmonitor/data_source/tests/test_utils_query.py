"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest import mock

import datetime

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


class TestGetRetentionTimeRange:
    """基于保留期构造查询时间窗口的单元测试，覆盖三种时间传参情况。"""

    # 以 7 天保留期、固定 now 为例：retention_seconds = 7 * 86400 = 604800
    NOW = 1_700_000_000
    RETENTION_DAYS = 7
    RETENTION_SECONDS = 7 * 86400  # 604800
    ACCURACY = BaseQuery.TIME_FIELD_ACCURACY  # 1000

    def _run(self, start_time=None, end_time=None):
        fake_now = datetime.datetime.fromtimestamp(self.NOW)
        with mock.patch(
            "bkmonitor.data_source.utils.query.datetime.datetime",
            mock.Mock(now=mock.Mock(return_value=fake_now)),
        ):
            return BaseQuery.get_retention_time_range(self.RETENTION_DAYS, start_time, end_time)

    def test_no_time_returns_full_retention_window_in_ms(self):
        """不传时间时返回完整保留期窗口（秒 -> 毫秒）。"""
        start_ms, end_ms = self._run()
        assert end_ms == (self.NOW + BaseQuery.TIME_PADDING) * self.ACCURACY
        assert start_ms == (self.NOW - self.RETENTION_SECONDS) * self.ACCURACY

    def test_only_end_time_given_is_clamped_and_uses_retention_start(self):
        """只传 end_time 时：限制不超过 now，start 取保留期下界。"""
        start_ms, end_ms = self._run(end_time=self.NOW - 100)
        assert start_ms == (self.NOW - self.RETENTION_SECONDS) * self.ACCURACY
        assert end_ms == (self.NOW - 100) * self.ACCURACY

    def test_future_end_time_is_clamped_to_now(self):
        """传入未来 end_time 时，应被限制到当前时间，避免查询未来数据。"""
        _, end_ms = self._run(end_time=self.NOW + 10_000)
        assert end_ms == self.NOW * self.ACCURACY

    def test_window_outside_retention_is_shifted_into_valid_range(self):
        """查询窗口完全早于保留期下界时，整体右移到 [end-time, end] 区间。"""
        far_end = self.NOW - self.RETENTION_SECONDS - 1000
        start_ms, end_ms = self._run(start_time=far_end - 100, end_time=far_end)
        # start 不应早于 (end - retention_seconds)
        assert start_ms >= (far_end - self.RETENTION_SECONDS) * self.ACCURACY
        assert start_ms <= end_ms

    def test_window_partially_in_retention_keeps_explicit_start(self):
        """查询窗口部分落在保留期内时，保留显式 start，仅限制下界。"""
        explicit_start = self.NOW - self.RETENTION_SECONDS + 100
        start_ms, _ = self._run(start_time=explicit_start, end_time=self.NOW - 10)
        assert start_ms == explicit_start * self.ACCURACY


class TestQueryFieldsTimeConversion:
    """_query_fields 内部经 _get_time_range 把秒级补齐并 ×1000 转毫秒后传给 _query_info_fields。"""

    NOW = 1_700_000_000
    RETENTION_DAYS = 7
    RETENTION_SECONDS = 7 * 86400  # 604800
    ACCURACY = BaseQuery.TIME_FIELD_ACCURACY  # 1000

    def _query_fields_capture_params(self, start_time=None, end_time=None) -> dict[str, int]:
        captured: dict[str, int] = {}

        def fake_query_info_fields(table_id, space_uid, st, et):
            captured["start_time"] = st
            captured["end_time"] = et
            return [_make_field(field_name="cpu_usage")]

        with (
            mock.patch.object(BaseQuery, "_query_info_fields", side_effect=fake_query_info_fields),
            mock.patch(
                "bkmonitor.data_source.utils.query.datetime.datetime",
                mock.Mock(now=mock.Mock(return_value=datetime.datetime.fromtimestamp(self.NOW))),
            ),
        ):
            BaseQuery()._query_fields(targets=[("rt1", "space1")], start_time=start_time, end_time=end_time)
        return captured

    def test_none_time_is_converted_to_milliseconds_in_retention_window(self):
        """不传时间时，传给 _query_info_fields 的 start/end 为毫秒级，且落在保留期窗口内。"""
        captured = self._query_fields_capture_params()
        assert captured["end_time"] == (self.NOW + BaseQuery.TIME_PADDING) * self.ACCURACY
        assert captured["start_time"] == (self.NOW - self.RETENTION_SECONDS) * self.ACCURACY

    def test_explicit_seconds_converted_to_milliseconds(self):
        """显式秒级时间应被 ×1000 转为毫秒级后传入。"""
        start = self.NOW - 10_000
        end = self.NOW - 5_000
        captured = self._query_fields_capture_params(start_time=start, end_time=end)
        assert captured["start_time"] == start * self.ACCURACY
        assert captured["end_time"] == end * self.ACCURACY
