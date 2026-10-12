"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.grafana.handlers.query import GrafanaQueryHandler
from apps.log_search.models import LogIndexSet, LogIndexSetData, Scenario


class TestGrafanaMetricListPlatformIndex(TestCase):
    """Grafana 平台级索引集：下拉可见范围 + query/query_log/dimension 跨空间隔离。"""

    OWNER_SPACE = "bkcc__2"
    OWNER_BK_BIZ_ID = 2
    TARGET_BK_BIZ_ID = 7
    TARGET_SPACE = "bkcc__7"
    OTHER_BK_BIZ_ID = 8
    CATEGORY_ID = "applications"
    PLATFORM_VISIBILITY = {"type": "multi_biz", "bk_biz_ids": [TARGET_BK_BIZ_ID]}
    PLATFORM_FILTER = {"field": "app_code", "value_ref": "space_id"}
    # get_fields 命中非空 fields_snapshot 时直接返回快照，无需连 ES
    FIELDS_SNAPSHOT = {
        "fields": [
            {"field_name": "level", "description": "日志级别", "es_doc_values": True, "field_type": "keyword"},
            {"field_name": "cost", "description": "耗时", "es_doc_values": True, "field_type": "long"},
        ]
    }

    def setUp(self):
        cache_patcher = patch("apps.log_search.models.cache.get", return_value=None)
        cache_patcher.start()
        self.addCleanup(cache_patcher.stop)

        space_detail = MagicMock()
        space_detail.space_type_id = "bkcc"
        space_detail.extend = {}
        space_detail_patcher = patch(
            "apps.log_search.handlers.index_set.SpaceApi.get_space_detail", return_value=space_detail
        )
        space_detail_patcher.start()
        self.addCleanup(space_detail_patcher.stop)

        related_space_patcher = patch("bkm_space.api.SpaceApi.get_related_space", return_value=None)
        related_space_patcher.start()
        self.addCleanup(related_space_patcher.stop)

    def _create_index_set(self, space_uid, **extra):
        params = {
            "index_set_name": extra.pop("index_set_name", f"idx_{space_uid}"),
            "space_uid": space_uid,
            "scenario_id": Scenario.LOG,
            "is_active": True,
            "category_id": extra.pop("category_id", self.CATEGORY_ID),
            "fields_snapshot": extra.pop("fields_snapshot", self.FIELDS_SNAPSHOT),
        }
        params.update(extra)
        index_set = LogIndexSet.objects.create(**params)
        LogIndexSetData.objects.create(
            index_set_id=index_set.index_set_id,
            result_table_id=f"rt_{index_set.index_set_id}",
            scenario_id=Scenario.LOG,
            bk_biz_id=2,
            apply_status=LogIndexSetData.Status.NORMAL,
        )
        return index_set

    @staticmethod
    def _metric_ids(metric_list):
        return [metric["id"] for group in metric_list for metric in group["children"]]

    def _create_platform_index_set(self, **extra):
        return self._create_index_set(
            self.OWNER_SPACE,
            index_set_name="platform",
            is_platform_index=True,
            platform_index_visibility=self.PLATFORM_VISIBILITY,
            platform_index_filter=self.PLATFORM_FILTER,
            **extra,
        )

    def test_visible_platform_index_set_listed_for_target_space(self):
        """可见范围命中的跨空间平台级索引集要出现在下拉里。"""
        platform = self._create_platform_index_set()

        metric_ids = self._metric_ids(GrafanaQueryHandler(self.TARGET_BK_BIZ_ID).get_metric_list())

        self.assertIn(platform.index_set_id, metric_ids)

    def test_platform_index_set_hidden_from_unlisted_space(self):
        """可见范围没覆盖的空间仍然看不到，避免放大可见面。"""
        platform = self._create_platform_index_set()

        metric_ids = self._metric_ids(GrafanaQueryHandler(self.OTHER_BK_BIZ_ID).get_metric_list())

        self.assertNotIn(platform.index_set_id, metric_ids)

    def test_non_platform_cross_space_index_set_still_hidden(self):
        """未开平台级的跨空间索引集不能被放出来（脏 visibility 也不算数）。"""
        non_platform = self._create_index_set(
            self.OWNER_SPACE,
            index_set_name="dirty",
            is_platform_index=False,
            platform_index_visibility=self.PLATFORM_VISIBILITY,
            platform_index_filter=self.PLATFORM_FILTER,
        )

        metric_ids = self._metric_ids(GrafanaQueryHandler(self.TARGET_BK_BIZ_ID).get_metric_list())

        self.assertNotIn(non_platform.index_set_id, metric_ids)

    def test_own_space_index_set_still_listed(self):
        """归属空间自身的索引集不受本次改动影响。"""
        own = self._create_index_set(self.TARGET_SPACE, index_set_name="own")

        metric_ids = self._metric_ids(GrafanaQueryHandler(self.TARGET_BK_BIZ_ID).get_metric_list())

        self.assertIn(own.index_set_id, metric_ids)

    def test_category_filter_applies_to_platform_index_set(self):
        """category_id 过滤要对平台级分支同样生效：既不能被 OR 条件绕过，也不能把它整体滤掉。"""
        platform = self._create_platform_index_set(category_id="hosts")
        handler = GrafanaQueryHandler(self.TARGET_BK_BIZ_ID)

        mismatched = self._metric_ids(handler.get_metric_list(category_id=self.CATEGORY_ID))
        self.assertNotIn(platform.index_set_id, mismatched)

        matched = self._metric_ids(handler.get_metric_list(category_id="hosts"))
        self.assertIn(platform.index_set_id, matched)

    def _query_dict(self, index_set_id):
        return {
            "dashboard_id": "dash",
            "panel_id": 1,
            "result_table_id": index_set_id,
            "start_time": 1,
            "end_time": 2,
            "method": "value_count",
            "interval": 60,
            "metric_field": "_index",
            "group_by": [],
            "where": [],
            "query_string": "",
        }

    def _fail_closed_patches(self):
        return (
            patch.object(GrafanaQueryHandler, "check_panel_permission", return_value=True),
            patch("apps.log_search.views.search_views.FeatureToggleObject.switch", return_value=False),
            patch("apps.grafana.handlers.query.SearchHandler"),
            patch("apps.grafana.handlers.query.AggsViewAdapter"),
            patch("apps.grafana.handlers.query.UnifyQueryHandler"),
            patch("apps.grafana.handlers.query.UnifyQueryAggHandler"),
        )

    def test_query_cross_space_fail_closed_when_unify_query_off(self):
        from rest_framework import serializers as drf_serializers

        platform = self._create_platform_index_set()
        handler = GrafanaQueryHandler(self.TARGET_BK_BIZ_ID)
        perm, toggle, search, aggs, uq, uq_agg = self._fail_closed_patches()
        with perm, toggle, search as mock_search, aggs, uq, uq_agg:
            with self.assertRaises(drf_serializers.ValidationError):
                handler.query(self._query_dict(platform.index_set_id))
            mock_search.assert_not_called()

    def test_query_log_cross_space_fail_closed_when_unify_query_off(self):
        from rest_framework import serializers as drf_serializers

        platform = self._create_platform_index_set()
        handler = GrafanaQueryHandler(self.TARGET_BK_BIZ_ID)
        perm, toggle, search, aggs, uq, uq_agg = self._fail_closed_patches()
        with perm, toggle, search as mock_search, aggs, uq as mock_uq, uq_agg:
            with self.assertRaises(drf_serializers.ValidationError):
                handler.query_log(self._query_dict(platform.index_set_id))
            mock_search.assert_not_called()
            mock_uq.assert_not_called()

    def test_unify_query_cross_space_fail_closed_when_unify_query_off(self):
        from rest_framework import serializers as drf_serializers

        platform = self._create_platform_index_set()
        handler = GrafanaQueryHandler(self.TARGET_BK_BIZ_ID)
        perm, toggle, search, aggs, uq, uq_agg = self._fail_closed_patches()
        with perm, toggle, search, aggs, uq, uq_agg as mock_uq_agg:
            with self.assertRaises(drf_serializers.ValidationError):
                handler.unify_query(self._query_dict(platform.index_set_id))
            mock_uq_agg.assert_not_called()

    def test_dimension_cross_space_fail_closed_when_unify_query_off(self):
        from rest_framework import serializers as drf_serializers

        platform = self._create_platform_index_set()
        handler = GrafanaQueryHandler(self.TARGET_BK_BIZ_ID)
        perm, toggle, search, aggs, uq, uq_agg = self._fail_closed_patches()
        with perm, toggle, search, aggs as mock_aggs, uq, uq_agg:
            with self.assertRaises(drf_serializers.ValidationError):
                handler.get_dimension_values(platform.index_set_id, "level", 1, 2)
            mock_aggs.assert_not_called()

    def test_query_owner_space_still_allows_esquery_when_unify_query_off(self):
        platform = self._create_platform_index_set()
        handler = GrafanaQueryHandler(self.OWNER_BK_BIZ_ID)
        mock_search = MagicMock()
        mock_search.time_field = "dtEventTimeStamp"
        mock_search.search.return_value = {"aggregations": {}}
        perm, toggle, search, aggs, uq, uq_agg = self._fail_closed_patches()
        search = patch("apps.grafana.handlers.query.SearchHandler", return_value=mock_search)
        with perm, toggle, search, aggs, uq, uq_agg:
            self.assertEqual(handler.query(self._query_dict(platform.index_set_id)), [])
            mock_search.search.assert_called_once()
