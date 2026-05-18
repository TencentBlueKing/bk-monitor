"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

覆盖 AlertDocument.get / mget 跨期搜索修复：

老实现把 end_time 等同于 alert_id 前 10 位反解出的 begin_time，但 AlertDocument
的 doc 实际索引位置由状态决定（REINDEX_ENABLED=True，详见 ai-docs
alert文档存储与查询行为.md §2）：
- ABNORMAL 告警每天被 reindex 搬运到当天索引；
- RESOLVED 告警永久停在状态切换那天索引。

因此 begin_time 单点窗口只能命中"begin 和 RESOLVED 同一天"的告警，对所有
跨期 doc 都会 0 命中。修复后 end_time 固定为 int(time.time())，配合
build_index_name_by_time 的"跨度 > 15 天退化月通配"规则保证 ES 负载可控。
"""

from unittest import TestCase, mock

from bkmonitor.documents.alert import AlertDocument
from core.errors.alert import AlertNotFoundError


def _build_hits(exists: bool, doc_dict: dict | None = None):
    """构造能让 cls(**hits[0].to_dict()) 工作的 .execute() 返回对象"""
    execute_result = mock.MagicMock()
    if exists:
        hit = mock.MagicMock()
        hit.to_dict.return_value = doc_dict or {"id": "x"}
        execute_result.hits = [hit]
    else:
        execute_result.hits = []
    return execute_result


class TestAlertDocumentGet(TestCase):
    @mock.patch("bkmonitor.documents.alert.time.time")
    @mock.patch.object(AlertDocument, "search")
    def test_get_uses_now_as_end_time(self, mock_search, mock_now):
        """跨期告警：begin_time 30 天前、doc 可能在今天或中间任意一天索引，
        end_time 必须扩到 now 才能命中；否则只搜 begin_time 当天会 0 命中。"""
        alert_id = "1776330921292201387"  # 来自真实 trace case 8be317b143d4
        begin_ts = 1776330921  # 2026-04-16 09:15:21Z
        now_ts = 1779000000  # ~30 天后

        mock_now.return_value = now_ts
        mock_search.return_value.filter.return_value.execute.return_value = _build_hits(True, {"id": alert_id})

        AlertDocument.get(alert_id)

        mock_search.assert_called_once_with(start_time=begin_ts, end_time=now_ts)
        mock_search.return_value.filter.assert_called_once_with("term", id=alert_id)

    @mock.patch("bkmonitor.documents.alert.time.time")
    @mock.patch.object(AlertDocument, "search")
    def test_get_short_lifecycle_alert_still_works(self, mock_search, mock_now):
        """回归：短生命周期告警（begin 与 RESOLVED 同日），扩窗不影响命中。"""
        alert_id = "17789934880001"
        begin_ts = 1778993488
        now_ts = 1778993500  # 12 秒后

        mock_now.return_value = now_ts
        mock_search.return_value.filter.return_value.execute.return_value = _build_hits(True, {"id": alert_id})

        AlertDocument.get(alert_id)

        mock_search.assert_called_once_with(start_time=begin_ts, end_time=now_ts)

    def test_get_invalid_alert_id_raises_value_error(self):
        """alert_id 解析失败保持原 ValueError 行为；本次修复不触动异常路径。"""
        with self.assertRaises(ValueError) as ctx:
            AlertDocument.get("not-a-number")
        self.assertIn("invalid alert_id", str(ctx.exception))

    @mock.patch("bkmonitor.documents.alert.time.time")
    @mock.patch.object(AlertDocument, "search")
    def test_get_no_hit_raises_alert_not_found(self, mock_search, mock_now):
        """命中为空时仍抛 AlertNotFoundError，不被扩窗修复改变。"""
        mock_now.return_value = 1779000000
        mock_search.return_value.filter.return_value.execute.return_value = _build_hits(False)

        with self.assertRaises(AlertNotFoundError):
            AlertDocument.get("1776330921292201387")


class TestAlertDocumentMget(TestCase):
    @mock.patch("bkmonitor.documents.alert.time.time")
    @mock.patch.object(AlertDocument, "search")
    def test_mget_uses_min_begin_and_now_window(self, mock_search, mock_now):
        """mget 同源修复：start_time = min(ids 反解 begin_time)，end_time = now。"""
        ids = [
            "17763309210000001",  # begin = 1776330921 (2026-04-16)
            "17779000000000002",  # begin = 1777900000 (~2026-05-04)
        ]
        now_ts = 1779100000

        mock_now.return_value = now_ts
        mock_search.return_value.filter.return_value.params.return_value.scan.return_value = []

        list(AlertDocument.mget(ids))

        mock_search.assert_called_once_with(start_time=1776330921, end_time=now_ts)
        mock_search.return_value.filter.assert_called_once_with("terms", id=ids)

    @mock.patch.object(AlertDocument, "search")
    def test_mget_empty_ids_returns_empty_list(self, mock_search):
        """空 ids 早返回，不应调用 search。"""
        self.assertEqual([], AlertDocument.mget([]))
        mock_search.assert_not_called()

    @mock.patch("bkmonitor.documents.alert.time.time")
    @mock.patch.object(AlertDocument, "search")
    def test_mget_skips_unparseable_ids_for_start_time(self, mock_search, mock_now):
        """ids 中含无法反解时间戳的项时跳过这些项，用余下的算 min(begin_time)。"""
        ids = ["bad-id", "1776330921000001"]
        now_ts = 1779100000
        mock_now.return_value = now_ts
        mock_search.return_value.filter.return_value.params.return_value.scan.return_value = []

        AlertDocument.mget(ids)

        mock_search.assert_called_once_with(start_time=1776330921, end_time=now_ts)
