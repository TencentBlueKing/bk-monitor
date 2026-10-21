"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

"""
锁定契约：列表"维度"列(`tags` 字段)与详情"维度"信息(`dimensions` 字段)必须同源。

修复背景：
- AlertQueryHandler.query_fields 中 `QueryField("tags", es_field="event.tags")` 导致列表
  从 `data["event"]["tags"]` 取值；详情则从 `data["dimensions"]` 取值。
- `event.tags` 在 Trigger 阶段一次性写入后**不会被 enricher 更新**；
  `dimensions` 在 Alert 创建后由 `StandardTranslateEnricher` 持续补充 CMDB 维度
  （ip/bk_host_id/bk_topo_node/target_type 等）。
- 系统类告警（如主机重启/Corefile/OOM）event.tags 原本为空，但 dimensions 含 enricher
  补充的 CMDB 维度 → 列表显示 "--" 但详情有数据。

修复：clean_document 在 cleaned_data.update 阶段强制将 `tags` 字段值绑定到 `dimensions`，
回退 event.tags（兼容旧数据），与详情同源。query_string 检索仍走 event.tags（向后兼容）。
"""
from unittest.mock import MagicMock, patch


def _build_doc(dimensions, event_tags):
    """构造 mock AlertDocument，提供 to_dict + 必需的属性。"""
    doc = MagicMock()
    doc.to_dict.return_value = {
        "id": "alert-1",
        "dimensions": dimensions,
        "event": {"tags": event_tags},
    }
    doc.stage_display = ""
    doc.duration = 0
    doc.shield_left_time = 0
    return doc


class TestCleanDocumentTagsBoundToDimensions:
    """clean_document 输出 row 的 `tags` 字段必须取自 `dimensions`，与详情同源。"""

    def _clean(self, doc):
        from fta_web.alert.handlers.alert import AlertQueryHandler

        # query_fields 循环里会调 field.get_value_by_es_field(data) 等，依赖 ES Document 上下文，
        # 直接 patch 跳过；本测试只关心 cleaned_data.update 阶段对 tags 的覆盖
        with (
            patch.object(AlertQueryHandler, "EXCLUDED_EXPORT_FIELDS", set()),
            patch("fta_web.alert.handlers.alert.hms_string", side_effect=lambda x: str(x)),
            patch(
                "fta_web.alert.handlers.alert.AlertDimensionFormatter.get_dimensions_str",
                return_value="",
            ),
            patch(
                "fta_web.alert.handlers.alert.AlertDimensionFormatter.get_target_key",
                return_value="",
            ),
        ):
            # 让 query_fields 循环里 get_value_by_es_field 都返回 None，避免依赖完整 doc
            for field in AlertQueryHandler.query_transformer.query_fields:
                field.get_value_by_es_field = MagicMock(return_value=None)
            return AlertQueryHandler.clean_document(doc)

    def test_tags_bound_to_dimensions_when_both_present(self):
        """dimensions 非空 → tags 取自 dimensions（CMDB 补充场景的典型修复）。"""
        dimensions = [
            {"key": "bk_host_id", "value": "9185731", "display_key": "主机ID", "display_value": "9185731"},
            {"key": "bk_target_ip", "value": "<ip>", "display_key": "目标IP", "display_value": "<ip>"},
        ]
        event_tags = [{"key": "old", "value": "v"}]  # 故意与 dimensions 不同

        cleaned = self._clean(_build_doc(dimensions, event_tags))

        assert cleaned["tags"] == dimensions, "tags 应与 dimensions 同源（修复列表/详情维度不一致 bug）"
        assert cleaned["dimensions"] == dimensions

    def test_tags_falls_back_to_event_tags_when_dimensions_empty(self):
        """dimensions 为空但 event.tags 非空 → 回退用 event.tags（兼容仅有 tags 的旧数据）。"""
        event_tags = [{"key": "legacy", "value": "v", "display_key": "legacy", "display_value": "v"}]

        cleaned = self._clean(_build_doc([], event_tags))

        assert cleaned["tags"] == event_tags
        assert cleaned["dimensions"] == []

    def test_tags_empty_when_both_empty(self):
        """两端都为空 → tags 为空列表（不为 None）。"""
        cleaned = self._clean(_build_doc([], []))

        assert cleaned["tags"] == []
        assert cleaned["dimensions"] == []

    def test_dimensions_value_reused_for_dimension_message_and_target_key(self):
        """dimensions_value 也用于 dimension_message / target_key（避免重复 data.get 不一致）。"""
        from fta_web.alert.handlers.alert import AlertDimensionFormatter, AlertQueryHandler

        dimensions = [{"key": "bk_host_id", "value": "X"}]
        doc = _build_doc(dimensions, [])

        with (
            patch.object(AlertQueryHandler, "EXCLUDED_EXPORT_FIELDS", set()),
            patch("fta_web.alert.handlers.alert.hms_string", side_effect=lambda x: str(x)),
            patch.object(AlertDimensionFormatter, "get_dimensions_str", return_value="DIM_MSG") as mock_msg,
            patch.object(AlertDimensionFormatter, "get_target_key", return_value="TKEY") as mock_tkey,
        ):
            for field in AlertQueryHandler.query_transformer.query_fields:
                field.get_value_by_es_field = MagicMock(return_value=None)
            AlertQueryHandler.clean_document(doc)

            # 两个 helper 都应收到与 cleaned["dimensions"] 同款的列表
            assert mock_msg.call_args[0][0] == dimensions
            assert mock_tkey.call_args[0][1] == dimensions
