"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

覆盖 IncidentDocument.get 跨期搜索修复：

IncidentDocument REINDEX_ENABLED=True，rollover_indices 定时任务（每 24 分钟）会把
status=abnormal 的故障 reindex 到当前索引（旧索引中删除），RESOLVED/CLOSED 故障停在结束
那天的索引。老实现把 end_time 等同于 id 反解出的 create_time（单日窗口），对所有已被
reindex 的活跃故障都会 0 命中、误抛 IncidentNotFoundError。修复后 end_time 固定为
int(time.time())，并按 -update_time 取 reindex 瞬态双副本中的最新那份。
"""

from unittest import TestCase, mock

from bkmonitor.documents.incident import IncidentDocument
from core.errors.incident import IncidentNotFoundError


def _build_hits(exists: bool, doc_dict: dict | None = None):
    """构造能让 cls(**hits[0].to_dict()) 工作的 .execute() 返回对象"""
    execute_result = mock.MagicMock()
    if exists:
        hit = mock.MagicMock()
        hit.to_dict.return_value = doc_dict or {"id": "x", "incident_id": "x"}
        execute_result.hits = [hit]
    else:
        execute_result.hits = []
    return execute_result


class TestIncidentDocumentGet(TestCase):
    @mock.patch("bkmonitor.documents.incident.time.time")
    @mock.patch.object(IncidentDocument, "search")
    def test_get_uses_now_as_end_time(self, mock_search, mock_now):
        """跨期故障：create_time 多天前、abnormal 已被 reindex 到当前索引，
        end_time 必须扩到 now 才能命中；否则只搜 create_time 当天会 0 命中。"""
        incident_id = "177633092112345"  # create_time=1776330921 + incident_id=12345
        create_ts = 1776330921
        now_ts = 1779000000  # ~30 天后
        mock_now.return_value = now_ts
        chain = mock_search.return_value.filter.return_value.sort.return_value
        chain.execute.return_value = _build_hits(
            True, {"id": incident_id, "incident_id": "12345", "status": "abnormal"}
        )

        IncidentDocument.get(incident_id, fetch_remote=False)

        mock_search.assert_called_once_with(start_time=create_ts, end_time=now_ts)
        mock_search.return_value.filter.assert_called_once_with("term", id=incident_id)
        # reindex 瞬态可能新旧索引各一份，按 -update_time 取最新
        mock_search.return_value.filter.return_value.sort.assert_called_once_with("-update_time")

    @mock.patch("bkmonitor.documents.incident.time.time")
    @mock.patch.object(IncidentDocument, "search")
    def test_get_no_hit_raises_not_found(self, mock_search, mock_now):
        """命中为空时仍抛 IncidentNotFoundError，不被扩窗修复改变。"""
        mock_now.return_value = 1779000000
        mock_search.return_value.filter.return_value.sort.return_value.execute.return_value = _build_hits(False)

        with self.assertRaises(IncidentNotFoundError):
            IncidentDocument.get("177633092112345", fetch_remote=False)

    def test_get_invalid_id_raises_value_error(self):
        """id 反解失败保持原 ValueError 行为；本次修复不触动异常路径。"""
        with self.assertRaises(ValueError):
            IncidentDocument.get("not-a-number", fetch_remote=False)
