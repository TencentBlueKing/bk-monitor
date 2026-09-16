from datetime import datetime

from bk_monitor_base.cmdb_event import CMDBEvent, CMDBEventLabels, CMDBEventMetadata, CMDBEventSpec

"""
pytest 配置文件
"""


import pytest

from bk_monitor_base.config import get_yaml_config, set_config


def pytest_configure() -> None:
    """
    配置 pytest
    """
    try:
        # 加载测试配置（配置已在 tests/config.yaml 中设置）
        config = get_yaml_config("src/bk_monitor_base/tests/config.yaml")
        set_config(config)
    except FileNotFoundError:
        pass

    # django配置初始化
    from bk_monitor_base.django_setup import django_setup

    django_setup()

    # Base is now loaded inside bk-monitor and NodeMan mode is owned by the
    # main project settings.  Standalone Base unit tests exercise the legacy
    # path unless a main-project test explicitly selects V3.
    from django.conf import settings

    settings.NODEMAN_INTEGRATION_MODE = "v2"


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """为所有测试启用数据库访问"""
    pass


def build_event(
    host_id: int,
    source: dict,
    target: dict,
    created_at: datetime | None,
    created_by: str | None,
    updated_at: datetime | None,
    updated_by: str | None,
    resource_type: str = "host_relation",
) -> CMDBEvent:
    return CMDBEvent(
        metadata=CMDBEventMetadata(
            labels=CMDBEventLabels(bk_object_code="cw-Host", bk_object_inst_id=host_id),
            name=f"CMDBEvent{host_id}",
            created_at=created_at,
            created_by=created_by,
            updated_at=updated_at,
            updated_by=updated_by,
        ),
        spec=CMDBEventSpec(
            resource_type=resource_type,
            source=source,
            target=target,
            bk_object_inst_id=host_id,
            bk_object_code="cw-Host",
        ),
    )
