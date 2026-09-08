# pyright: reportUnknownMemberType=false
# pyright: reportCallIssue=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportArgumentType=false
# pyright: reportUnknownVariableType=false
import os
import uuid
from typing import Any, ClassVar
from uuid import uuid4

import elasticsearch
import pytest

from bk_monitor_base.cmdb_event import CMDBEvent, CMDBEventLabels, CMDBEventMetadata, CMDBEventSpec
from bk_monitor_base.collector import (
    CollectTask,
    CollectTaskLabels,
    CollectTaskMetadata,
    CollectTaskSpec,
    CollectTaskStatus,
    CollectType,
    TaskStatus,
)
from bk_monitor_base.infras.declaratives import ApiVersion, ResourceAction, ResourceEvent
from bk_monitor_base.infras.declaratives.base import GeneralDocument, ResourceEventDocument
from bk_monitor_base.infras.declaratives.constants import ES_RESOURCE_STORE
from bk_monitor_base.infras.declaratives.definitions.enums import EventSourceType
from bk_monitor_base.infras.declaratives.definitions.resource import Kind, Resource

CollectTask.store_class = ES_RESOURCE_STORE


class FakeESResource(Resource):
    api_version: ClassVar[ApiVersion] = ApiVersion("vFake")
    kind: ClassVar[Kind] = Kind("FakeResource")
    store_class: ClassVar[str | None] = ES_RESOURCE_STORE


class TestESStore:
    def test_store_attribute(self):
        """测试属性获取"""
        assert FakeESResource.store
        assert FakeESResource.store.__class__.__name__ == ES_RESOURCE_STORE.split(".")[-1]
        assert CMDBEvent.store
        assert CMDBEvent.store.__class__.__name__ == ES_RESOURCE_STORE.split(".")[-1]

    @pytest.mark.skipif(os.getenv("BKAPP_ELASTICSEARCH_HOST") is None, reason="不存在ES")
    def test_get(self):
        """测试 ES DB Store 获取"""
        resource_event_bak = ResourceEvent.store_class
        ResourceEvent.store_class = ES_RESOURCE_STORE
        obj = CMDBEvent(
            metadata=(
                CMDBEventMetadata(
                    labels=CMDBEventLabels(bk_object_code="host", bk_object_inst_id=100), name="CMDBEvent_100"
                )
            ),
            spec=CMDBEventSpec(bk_object_inst_id=100, bk_object_code="host", resource_type="host_relation"),
        )
        obj.store.apply()
        event = CMDBEvent.store.get(uid=obj.metadata.uid.hex)
        assert event
        assert isinstance(event, CMDBEvent)

        with pytest.raises(elasticsearch.exceptions.NotFoundError):
            CMDBEvent.store.get(uid=uuid4().hex)
        ResourceEvent.store_class = resource_event_bak

    def _test_list(self, fake_es_resource: Resource):
        """测试 ES DB Store 存取"""
        count = len(ResourceEvent.store.list(common_filter={"source": "test_list_01"}))
        fake_event = ResourceEvent(action=ResourceAction.Created, resource=fake_es_resource, source="test_list_01")
        fake_event.store.apply()
        # 强制刷新一波, 保证数据正常写入
        ResourceEventDocument._index.refresh()
        assert len(ResourceEvent.store.list(common_filter={"source": "test_list_01"})) == count + 1

        # 没有关联 resource 的 event 无法存储
        fake_event2 = ResourceEvent(
            action=ResourceAction.Created, resource=None, source=EventSourceType.CONTROLLER.value
        )
        with pytest.raises(ValueError):
            fake_event2.store.apply()

    @staticmethod
    def make_collect_task(label_value: int) -> CollectTask:
        collect_task = CollectTask(
            spec=CollectTaskSpec(plugin_primary_id=label_value),
            status=CollectTaskStatus(task_status=TaskStatus.CREATE_SUCCEED, collect_enable=False),
            metadata=CollectTaskMetadata(
                name=f"CollectTask_{label_value}",
                labels=CollectTaskLabels(
                    type=CollectType.BK_PLUGIN_COLLECT,
                    collect_task_id=label_value,
                    config_uid=uuid.uuid4(),
                    template_id=10,
                ),
            ),
        )
        collect_task.status.message = str(label_value)
        return collect_task

    @pytest.mark.skipif(os.getenv("BKAPP_ELASTICSEARCH_HOST") is None, reason="不存在ES")
    @pytest.mark.parametrize("label_value", [10000, 20000, 30000])
    def _test_list_filter(self, label_value: int):
        """测试 ES DB Store 过滤"""
        collect_task = self.make_collect_task(label_value)
        collect_task.store.apply()

        # 强制刷新一波, 保证数据正常写入
        GeneralDocument._index.refresh()

        assert (
            CollectTask.store.list(label_filter={"collect_task_id": label_value})[-1].metadata.name
            == collect_task.metadata.name
        )
        assert (
            CollectTask.store.list(status_filter={"message": str(label_value)})[-1].metadata.name
            == collect_task.metadata.name
        )
        assert not CollectTask.store.list(label_filter={"collect_task_id": "1234"})

        collect_task.store.delete()

    @pytest.mark.skipif(os.getenv("BKAPP_ELASTICSEARCH_HOST") is None, reason="不存在ES")
    @pytest.mark.parametrize(
        "filter_type, field, bad_values, bad_single_value, wrong_suffix",
        [
            (
                "label_filter",
                "collect_task_id__in",
                [9999],
                9999,
                "_in",  # 测试字段后缀错误的情况（应用会自动转换__in）
            ),
            (
                "status_filter",
                "message__in",
                ["9999"],
                "9999",
                "_in",
            ),
        ],
    )
    def test_basic_filter_behavior(
        self, filter_type: Any, field: Any, bad_values: Any, bad_single_value: Any, wrong_suffix: Any
    ):
        """测试基础过滤行为"""
        # 测试不存在值返回空列表
        assert not CollectTask.store.list(**{filter_type: {field: bad_values}})

        # 测试非列表值抛出异常
        with pytest.raises(ValueError, match=f"Value for {field} must be a list"):
            CollectTask.store.list(**{filter_type: {field: bad_single_value}})

        # 测试错误后缀格式抛出异常
        wrong_field = field.replace("__in", wrong_suffix)
        model_name: str = CollectTask.store._get_target_es_model().__name__
        with pytest.raises(ValueError, match=f"{model_name} does not have {wrong_field} field"):
            CollectTask.store.list(**{filter_type: {wrong_field: bad_values}})

    @pytest.mark.skipif(os.getenv("BKAPP_ELASTICSEARCH_HOST") is None, reason="不存在ES")
    @pytest.mark.parametrize(
        "filter_type, base_field, invalid_operator",
        [
            ("label_filter", "collect_task_id", "i2n"),
            ("status_filter", "message", "i2n"),
        ],
    )
    def test_list_unsupported_operator(self, filter_type: Any, base_field: Any, invalid_operator: Any):
        """测试不支持的运算符"""
        # 构造不支持的运算符查询
        invalid_field = f"{base_field}__{invalid_operator}"
        with pytest.raises(ValueError, match=f"Operator {invalid_operator} not supported for field {base_field}"):
            CollectTask.store.list(**{filter_type: {invalid_field: [1000, 2000, 3000]}})
