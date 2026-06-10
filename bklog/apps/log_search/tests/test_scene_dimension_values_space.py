"""
Regression test for IndexSetTag.get_dimension_values business isolation.

旧实现用 space_uid__endswith=str(bk_biz_id) 后缀匹配会串业务
（bk_biz_id=2 命中 bkcc__12 / bkcc__102）。修复后必须按
bk_biz_id_to_space_uid(bk_biz_id) 精确匹配 space_uid（P1）。
"""

from unittest.mock import patch

from django.test import TestCase

from apps.log_search.models import IndexSetTag


class TestGetDimensionValuesExactSpaceMatch(TestCase):
    def test_uses_exact_space_uid_not_suffix(self):
        with patch(
            "apps.log_search.models.bk_biz_id_to_space_uid", return_value="bkcc__2"
        ) as m_space, patch.object(
            IndexSetTag, "get_tag_id", return_value=1
        ), patch.object(
            IndexSetTag, "_normalize_dimension_filters", return_value=[]
        ), patch(
            "apps.log_search.models.LogIndexSet"
        ) as m_idx:
            m_idx.objects.filter.return_value.values_list.return_value = []
            result = IndexSetTag.get_dimension_values(
                bk_biz_id=2, scene="host", dimension_key="cluster_id"
            )
            m_space.assert_called_once_with(2)
            # 精确匹配 space_uid，而不是 endswith 后缀匹配
            m_idx.objects.filter.assert_called_once_with(
                space_uid="bkcc__2", is_active=True
            )
        self.assertEqual(result, [])
