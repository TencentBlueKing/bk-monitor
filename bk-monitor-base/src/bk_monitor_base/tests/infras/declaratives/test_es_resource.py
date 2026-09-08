import os
from datetime import datetime, timedelta

import pytest
from django.utils import timezone

from bk_monitor_base.cmdb_event import CMDBEvent
from bk_monitor_base.infras.declaratives.base.es_resource import CMDBEventDocument
from bk_monitor_base.infras.declaratives.constants import ES_RESOURCE_STORE
from bk_monitor_base.tests.conftest import build_event


@pytest.mark.skipif(os.getenv("BKAPP_ELASTICSEARCH_HOST") is None, reason="未配置ES")
class TestESResource:
    def test_resource_metadata(self):
        """测试 ES Resource 的元数据"""
        source = {"bk_biz_id": 1}
        target = {"bk_biz_id": 2}
        time = timezone.now() - timedelta(minutes=10)
        created_by = "fake_none_user_n"
        CMDBEvent.store_class = ES_RESOURCE_STORE
        event = build_event(
            1, source, target, created_at=time, updated_at=time, created_by=created_by, updated_by=created_by
        )
        event.store.apply()
        # 强制刷新一波, 保证数据正常写入
        CMDBEventDocument._index.refresh()
        result = CMDBEvent.store.list(label_filter={"bk_object_code": "cw-Host", "bk_object_inst_id": 1})[-1]
        assert isinstance(result.metadata.created_at, datetime)
        assert isinstance(result.metadata.updated_at, datetime)
        assert result.metadata.created_at != time
        assert result.metadata.updated_at != time
        assert result.metadata.created_by != created_by
        assert result.metadata.updated_by != created_by
