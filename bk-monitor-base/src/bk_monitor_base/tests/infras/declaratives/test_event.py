import datetime
import json

import pytest

from bk_monitor_base.infras.declaratives.base.event import ResourceAction, ResourceEvent, ResourceEventMetadata


@pytest.mark.django_db(databases=["default"])
class TestEventResource:
    def test_event_resource_json(self, fake_resource):
        """测试 EventResource 的 JSON 序列化"""

        event = ResourceEvent(
            metadata=ResourceEventMetadata(name="test-event"),
            action=ResourceAction.Created,
            resource=fake_resource,
            event_time=datetime.datetime.now(),
            source="TEST",
        )
        event_json = event.to_json_with_resource_mark()

        event_dict = json.loads(event_json)
        assert event_dict["resource"]["kind"] == fake_resource.kind
        assert event_dict["resource"]["api_version"] == fake_resource.api_version
