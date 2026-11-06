import os

import pytest
import yaml
from django.conf import settings

from bk_monitor_base.collector import CollectConfig
from bk_monitor_base.infras.declaratives import ResourceEvent
from bk_monitor_base.infras.declaratives.definitions import ApiVersion, Kind, Metadata, Resource, Spec, Status
from bk_monitor_base.infras.declaratives.registry import DefaultResourceRegistry


class FakeResource(Resource):
    api_version = ApiVersion("vFake")
    kind = Kind("FakeResource")


@pytest.fixture(scope="module")
def fake_resource_cls():
    return FakeResource


@pytest.fixture
def fake_resource():
    return FakeResource(metadata=Metadata(name="fake_resource"), spec=Spec(), status=Status())


@pytest.fixture
def mock_search_object_attribute(mocker):
    resource_watch_result = [{"bk_property_id": "bk_cpu"}]
    mocker.patch(
        "kingeye.meta.legacy.cmdb_event_streamer.watch_data_handler.search_object_attribute",
        return_value=resource_watch_result,
    )


def read_fixture(file_path: str) -> dict:
    with open(file_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def make_collect_config(template: str) -> CollectConfig:
    template_path = os.path.join(settings.BASE_DIR, "tests/fixtures", template).replace("\\", "/") + ".yaml"
    data = read_fixture(template_path)
    return CollectConfig(**data)


ResourceEvent.store_class = "bk_monitor_base.infras.declaratives.store.local_db.LocalDBStore"
DefaultResourceRegistry.register(FakeResource)
