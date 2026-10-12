"""
拨测模块测试配置

包含共享的pytest fixtures
"""

from unittest.mock import patch

import pytest

from bk_monitor_base.domains.uptime_check.define import UptimeCheckTaskStatus
from bk_monitor_base.infras.constant import DEFAULT_TENANT_ID


@pytest.fixture(autouse=True)
def mock_bk_biz_id_to_bk_tenant_id():
    """Mock 业务ID转租户ID，避免依赖 SpaceModel 数据。

    说明：
        `TaskManager` 初始化会调用 `bk_biz_id_to_bk_tenant_id`，而该函数在开启多租户时会进一步
        查询空间表。单测中无需关注空间域逻辑，因此统一 mock 为默认租户。
    """
    with patch("bk_monitor_base.domains.space.cache.bk_biz_id_to_bk_tenant_id", return_value=DEFAULT_TENANT_ID):
        yield


@pytest.fixture
def mock_settings():
    """Mock Django settings"""
    with patch("django.conf.settings") as mock:
        mock.BK_SUPPLIER_ID = 0
        yield mock


@pytest.fixture
def sample_node(db):
    """创建示例拨测节点"""
    from bk_monitor_base.domains.uptime_check.models import UptimeCheckNodeModel

    return UptimeCheckNodeModel.objects.create(
        bk_tenant_id="default",
        bk_biz_id=2,
        name="测试节点",
        ip="192.168.1.1",
        bk_host_id=12345,
        plat_id=0,
    )


@pytest.fixture
def sample_task(db):
    """创建示例拨测任务"""
    from bk_monitor_base.domains.uptime_check.models import UptimeCheckTaskModel

    return UptimeCheckTaskModel.objects.create(
        bk_biz_id=2,
        name="测试任务",
        protocol=UptimeCheckTaskModel.Protocol.HTTP,
        status=UptimeCheckTaskStatus.NEW_DRAFT.value,
        config={
            "url_list": ["https://www.example.com"],
            "method": "GET",
            "timeout": 3000,
            "period": 60,
        },
    )


@pytest.fixture
def task_with_node(db, sample_node):
    """创建带节点的拨测任务"""
    from bk_monitor_base.domains.uptime_check.models import UptimeCheckTaskModel

    task = UptimeCheckTaskModel.objects.create(
        bk_biz_id=2,
        name="带节点任务",
        protocol=UptimeCheckTaskModel.Protocol.HTTP,
        status=UptimeCheckTaskStatus.NEW_DRAFT.value,
        config={
            "url_list": ["https://www.example.com"],
            "method": "GET",
            "timeout": 3000,
            "period": 60,
        },
    )
    task.nodes.add(sample_node)
    return task


@pytest.fixture
def task_with_subscription(db):
    """创建带订阅的拨测任务"""
    from bk_monitor_base.domains.uptime_check.models import (
        UptimeCheckTaskModel,
        UptimeCheckTaskSubscription,
    )

    task = UptimeCheckTaskModel.objects.create(
        bk_biz_id=2,
        name="带订阅任务",
        protocol=UptimeCheckTaskModel.Protocol.HTTP,
        status=UptimeCheckTaskStatus.STARTING.value,
    )

    UptimeCheckTaskSubscription.objects.create(
        uptimecheck_id=task.pk,
        subscription_id=12345,
        bk_biz_id=2,
    )

    return task
