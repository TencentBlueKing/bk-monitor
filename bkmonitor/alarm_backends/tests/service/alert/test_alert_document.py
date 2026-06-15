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
        mock_search.return_value.filter.return_value.sort.return_value.params.return_value.execute.return_value = []

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
        mock_search.return_value.filter.return_value.sort.return_value.params.return_value.execute.return_value = []

        AlertDocument.mget(ids)

        mock_search.assert_called_once_with(start_time=1776330921, end_time=now_ts)

    @mock.patch("bkmonitor.documents.alert.time.time")
    @mock.patch.object(AlertDocument, "search")
    def test_mget_uses_plain_search_not_scroll(self, mock_search, mock_now):
        """mget 走普通 search(execute) 替代 scroll(scan)，避免 scroll context 积压；按 hit.to_dict() 构造 doc。"""
        mock_now.return_value = 1779100000
        hit = mock.MagicMock()
        hit.to_dict.return_value = {"id": "1776330921000001"}
        params_chain = mock_search.return_value.filter.return_value.sort.return_value.params.return_value
        params_chain.execute.return_value = [hit]

        docs = AlertDocument.mget(["1776330921000001"])

        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].id, "1776330921000001")
        params_chain.execute.assert_called_once()  # 一次 execute 取完该批
        params_chain.scan.assert_not_called()  # 不再用 scroll(scan)

    @mock.patch.object(AlertDocument, "MGET_BATCH_SIZE", 2)
    @mock.patch("bkmonitor.documents.alert.time.time")
    @mock.patch.object(AlertDocument, "search")
    def test_mget_sorts_by_timestamp_then_uses_per_batch_start_time(self, mock_search, mock_now):
        """超过单批容量时：先按 begin_time 排序再分批，每批用本批最小 begin_time 作索引下界，
        而非全量最老时间——避免离散 id 让每个分批都展开到最老窗口；上界恒为 now。"""
        now_ts = 1779999999
        mock_now.return_value = now_ts
        mock_search.return_value.filter.return_value.sort.return_value.params.return_value.execute.return_value = []

        # 乱序输入：newest / oldest / middle
        a_new = "17790000000000001"  # begin = 1779000000
        b_old = "17763309210000002"  # begin = 1776330921
        c_mid = "17779000000000003"  # begin = 1777900000

        AlertDocument.mget([a_new, b_old, c_mid])

        # 排序后分两批：[b_old, c_mid] / [a_new]
        start_times = [kw["start_time"] for _, kw in mock_search.call_args_list]
        end_times = [kw["end_time"] for _, kw in mock_search.call_args_list]
        self.assertEqual(start_times, [1776330921, 1779000000])  # 各批本批最小，非全量最老
        self.assertEqual(end_times, [now_ts, now_ts])  # 上界恒为 now

        # 每批 terms 命中按排序后的 id 分组
        filter_kwargs = [c.kwargs for c in mock_search.return_value.filter.call_args_list]
        self.assertEqual(filter_kwargs, [{"id": [b_old, c_mid]}, {"id": [a_new]}])

    @mock.patch("bkmonitor.documents.alert.time.time")
    @mock.patch.object(AlertDocument, "search")
    def test_mget_dedupes_same_id_keeping_latest(self, mock_search, mock_now):
        """reindex 期间同一 alert 在新旧索引各一份，terms 命中两条同 _id；按 -update_time 排序后
        保首条（最新写副本），按 _id 去重为一条，丢弃旧副本。"""
        mock_now.return_value = 1779100000

        # ES 已按 -update_time 降序：最新副本（RESOLVED）在前，旧副本（ABNORMAL）在后
        newer = mock.MagicMock()
        newer.meta.id = "1776330921000001"
        newer.to_dict.return_value = {"id": "1776330921000001", "update_time": 200, "status": "RESOLVED"}
        older = mock.MagicMock()
        older.meta.id = "1776330921000001"
        older.to_dict.return_value = {"id": "1776330921000001", "update_time": 100, "status": "ABNORMAL"}

        chain = mock_search.return_value.filter.return_value.sort.return_value.params.return_value
        chain.execute.return_value = [newer, older]

        docs = AlertDocument.mget(["1776330921000001"])

        self.assertEqual(len(docs), 1)  # 两条同 _id 去重为一条
        self.assertEqual(docs[0].status, "RESOLVED")  # 保留 update_time 较大的最新副本
        mock_search.return_value.filter.return_value.sort.assert_called_once_with("-update_time")
