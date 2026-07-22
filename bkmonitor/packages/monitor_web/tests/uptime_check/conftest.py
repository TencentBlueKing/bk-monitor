"""
conftest.py for uptime_check tests

断开 fta_web 的 post_migrate signal（rollover_es_indices / migrate_legacy_issues），
避免测试数据库创建时因 Elasticsearch 不可用而失败。
提供通用 fixture 供集成测试使用。
"""

import pytest
from django.apps import apps
from django.db.models.signals import post_migrate

TENANT_ID = "system"
BK_BIZ_ID = 2


@pytest.fixture(scope="session", autouse=True)
def disconnect_es_post_migrate_signals():
    """断开 fta_web post_migrate 中的 ES 相关 signal，避免测试环境无 ES 时报错"""
    from fta_web.handlers import migrate_legacy_issues, rollover_es_indices

    sender = apps.get_app_config("fta_web")
    post_migrate.disconnect(rollover_es_indices, sender=sender)
    post_migrate.disconnect(migrate_legacy_issues, sender=sender)
    yield
    post_migrate.connect(rollover_es_indices, sender=sender)
    post_migrate.connect(migrate_legacy_issues, sender=sender)


@pytest.fixture(autouse=True)
def mock_tenant(mocker):
    """mock 租户相关函数，所有测试自动生效"""
    mocker.patch(
        "monitor_web.uptime_check.resources.get_request_tenant_id",
        return_value=TENANT_ID,
    )
    mocker.patch(
        "bk_monitor_base.domains.uptime_check.models.bk_biz_id_to_bk_tenant_id",
        return_value=TENANT_ID,
    )
    # operation 层也会调用 bk_biz_id_to_bk_tenant_id 做校验
    mocker.patch(
        "bk_monitor_base.domains.uptime_check.operation.bk_biz_id_to_bk_tenant_id",
        return_value=TENANT_ID,
    )


@pytest.fixture()
def mock_third_party(mocker):
    """mock 第三方服务（ES 告警查询 + InfluxDB 指标查询），返回 mock 对象供测试自定义"""
    from types import SimpleNamespace

    mocks = SimpleNamespace(
        alarm_info=mocker.patch(
            "monitor_web.uptime_check.resources._query_task_alarm_info",
            return_value={},
        ),
        batch_metric=mocker.patch(
            "monitor_web.uptime_check.resources._batch_query_task_metric",
        ),
    )
    return mocks


@pytest.fixture()
def create_task(db):
    """工厂 fixture：创建拨测任务并写入数据库"""
    from bk_monitor_base.domains.uptime_check.models import UptimeCheckTaskModel

    def _create(
        name="测试任务",
        protocol="HTTP",
        status="running",
        bk_biz_id=BK_BIZ_ID,
        config=None,
        **kwargs,
    ):
        if config is None:
            config = {"period": 60, "url_list": ["http://example.com"]}
        return UptimeCheckTaskModel.objects.create(
            bk_biz_id=bk_biz_id,
            name=name,
            protocol=protocol,
            status=status,
            config=config,
            create_user="admin",
            update_user="admin",
            **kwargs,
        )

    return _create


@pytest.fixture()
def create_node(db):
    """工厂 fixture：创建拨测节点并写入数据库"""
    from bk_monitor_base.domains.uptime_check.models import UptimeCheckNodeModel

    def _create(
        name="测试节点",
        bk_biz_id=BK_BIZ_ID,
        bk_host_id=1,
        ip="127.0.0.1",
        is_common=False,
        **kwargs,
    ):
        return UptimeCheckNodeModel.objects.create(
            bk_tenant_id=TENANT_ID,
            bk_biz_id=bk_biz_id,
            name=name,
            bk_host_id=bk_host_id,
            ip=ip,
            is_common=is_common,
            create_user="admin",
            update_user="admin",
            **kwargs,
        )

    return _create


@pytest.fixture()
def create_group(db):
    """工厂 fixture：创建拨测分组并写入数据库"""
    from bk_monitor_base.domains.uptime_check.models import UptimeCheckGroupModel

    def _create(name="测试分组", bk_biz_id=BK_BIZ_ID, tasks=None, **kwargs):
        group = UptimeCheckGroupModel.objects.create(
            bk_biz_id=bk_biz_id,
            name=name,
            create_user="admin",
            update_user="admin",
            **kwargs,
        )
        if tasks:
            for task in tasks:
                group.tasks.add(task)
        return group

    return _create
