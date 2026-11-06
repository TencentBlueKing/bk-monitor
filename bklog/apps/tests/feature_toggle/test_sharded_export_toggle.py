from django.test import TestCase

from apps.feature_toggle.models import FeatureToggle
from apps.log_search.export.config import FEATURE_ASYNC_EXPORT_SHARDED


class ShardedExportToggleTests(TestCase):
    """开关初始化数据决定首页是否下发，需与迁移保持一致。"""

    def test_toggle_is_visible_for_frontend(self):
        toggle = FeatureToggle.objects.get(name=FEATURE_ASYNC_EXPORT_SHARDED)
        self.assertTrue(toggle.is_viewed)
        self.assertEqual(toggle.biz_id_white_list, [])
        self.assertEqual(toggle.biz_id_black_list, [])
