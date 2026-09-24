from bk_monitor_base.infras.declaratives.base import CMDBEventDocument, ResourceEventDocument


class TestESResourceEvent:
    def test_attr(self):
        obj = ResourceEventDocument()

        assert obj.updated_at

        assert obj.spec.to_dict() == {}


class TestESCMDBEvent:
    def test_attr(self):
        obj = CMDBEventDocument()

        assert obj.updated_at

        assert obj.spec.to_dict() == {}
