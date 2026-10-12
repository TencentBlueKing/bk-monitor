import pytest

from bk_monitor_base.cmdb_event import CMDBEvent, CMDBEventLabels, CMDBEventMetadata, CMDBEventSpec


class TestCMDBEvent:
    @staticmethod
    def build_event(host_id: int, source: dict, target: dict, resource_type: str = "host_relation") -> CMDBEvent:
        return CMDBEvent(
            metadata=CMDBEventMetadata(
                labels=CMDBEventLabels(bk_object_code="cw-Host", bk_object_inst_id=host_id),
                name=f"CMDBEvent{host_id}",
            ),
            spec=CMDBEventSpec(
                resource_type=resource_type,
                source=source,
                target=target,
                bk_object_inst_id=host_id,
                bk_object_code="cw-Host",
            ),
        )

    def test_source_obj(self):
        source = {"bk_biz_id": 1}
        target = {"bk_biz_id": 2}
        event = self.build_event(1, source, target)

        assert event.spec.source_obj.bk_biz_id == source["bk_biz_id"]

    def test_target_obj(self):
        source = {"bk_biz_id": 1}
        target = {"bk_biz_id": 2}
        event = self.build_event(1, source, target)

        assert event.spec.target_obj.bk_biz_id == target["bk_biz_id"]

    def test_unsupported_resource_type(self):
        source = {"bk_biz_id": 1}
        target = {"bk_biz_id": 2}
        resource_type = "xxxxx"
        with pytest.raises(ValueError, match=f"资源类型 {resource_type} 暂不支持"):
            event = self.build_event(1, source, target, resource_type)
            assert event.spec.target_obj.bk_biz_id == target["bk_biz_id"]

        with pytest.raises(ValueError, match=f"资源类型 {resource_type} 暂不支持"):
            event = self.build_event(1, source, target, resource_type)
            assert event.spec.source_obj.bk_biz_id == target["bk_biz_id"]

    def test_source_obj_bk_biz_id_with_none(self):
        source = {"bk_biz_id": None}
        target = {"bk_biz_id": 2}
        event = self.build_event(1, source, target)

        assert event.spec.source_obj.bk_biz_id == source["bk_biz_id"]

    def test_target_obj_bk_biz_id_with_none(self):
        source = {"bk_biz_id": 2}
        target = {"bk_biz_id": None}
        event = self.build_event(1, source, target)

        assert event.spec.target_obj.bk_biz_id == target["bk_biz_id"]
