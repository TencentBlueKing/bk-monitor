"""
dynamic_group 测试配置

提供 dynamic_group 模块测试所需的公共 fixtures。

注意：Django ORM models 的导入需要延迟到 fixture 内部，
否则在 pytest 收集测试时会因为 Django 尚未初始化而报错。
"""

import pytest


@pytest.fixture
def mock_dynamic_group():
    """创建模拟的动态分组实体"""
    from bk_monitor_base.domains.dynamic_group.define import DynamicGroup

    return DynamicGroup(
        dynamic_group_id=1,
        dynamic_group_name="测试动态分组",
        condition_list=[{"field": "bk_host_innerip", "value": "10.", "operator": "contains"}],
        object_model_code="cw-Host",
        space_code="bkcc__2",
        bk_tenant_id="system",
        member_count=10,
    )


@pytest.fixture
def mock_dynamic_group_query_filter():
    """创建模拟的动态分组查询过滤条件"""
    from bk_monitor_base.domains.dynamic_group.define import DynamicGroupQueryFilter

    return DynamicGroupQueryFilter(
        dynamic_group_ids=[1, 2, 3],
        space_codes=["bkcc__2"],
        name_keywords=["测试"],
        object_model_code="cw-Host",
        page=1,
        page_size=20,
    )


@pytest.fixture
def mock_dynamic_group_member():
    """创建模拟的动态分组成员"""
    from bk_monitor_base.domains.dynamic_group.define import DynamicGroupMember

    return DynamicGroupMember(
        id=1,
        dynamic_group_id=1,
        member={"bk_inst_id": 101, "bk_host_innerip": "10.0.0.1"},
    )


@pytest.fixture
def mock_dynamic_group_permission():
    """创建模拟的动态分组权限"""
    from bk_monitor_base.domains.dynamic_group.define import DynamicGroupPermission

    return DynamicGroupPermission(
        edit_allowed=True,
        edit_message="",
        delete_allowed=False,
        delete_message="该分组被其他模块引用，无法删除",
    )


@pytest.fixture
def db_object_model_group():
    """创建 Django ORM 对象模型分组的 fixture（一级分组）"""
    from bk_monitor_base.domains.object_model.models import ObjectModelGroupORM

    group = ObjectModelGroupORM.objects.create(
        object_model_group_code="pytest_group",
        object_model_group_name="pytest分组",
        is_default=False,
    )
    yield group
    group.delete()


@pytest.fixture
def db_object_model_child_group(db_object_model_group):
    """创建 Django ORM 对象模型子分组的 fixture（二级分组）"""
    from bk_monitor_base.domains.object_model.models import ObjectModelGroupORM, ObjectModelORM

    child = ObjectModelGroupORM.objects.create(
        object_model_group_code="pytest_child_group",
        object_model_group_name="pytest子分组",
        is_default=False,
        parent_object_model_group=db_object_model_group,
    )
    yield child
    # 先删除关联的 ObjectModelORM
    ObjectModelORM.objects.filter(object_model_group=child).delete()
    child.delete()


@pytest.fixture
def db_object_model(db_object_model_child_group):
    """创建 Django ORM 对象模型的 fixture"""
    from bk_monitor_base.domains.object_model.define import DatasourceType
    from bk_monitor_base.domains.object_model.models import ObjectModelORM

    model = ObjectModelORM.objects.create(
        object_model_code="cw-Host",
        object_model_name="主机",
        object_model_group=db_object_model_child_group,
        datasource=DatasourceType.CMDB,
        is_default=True,
        bk_cmdb_obj_id="host",
        display_fields=[{"bk_property_id": "bk_host_innerip"}],
        inst_display_name="${bk_host_innerip}",
    )
    yield model
    model.delete()


@pytest.fixture
def db_dynamic_group(db_object_model):
    """创建 Django ORM 动态分组的 fixture"""
    from bk_monitor_base.domains.dynamic_group.models import DynamicGroupORM

    group = DynamicGroupORM.objects.create(
        dynamic_group_name="测试动态分组",
        condition_list=[{"field": "bk_host_innerip", "value": "10.", "operator": "contains"}],
        object_model_code="cw-Host",
        space_code="bkcc__2",
        bk_tenant_id="system",
        created_by="admin",
        updated_by="admin",
    )
    yield group
    group.delete()


@pytest.fixture
def db_dynamic_group_with_members(db_dynamic_group):
    """创建带成员的 Django ORM 动态分组的 fixture"""
    from bk_monitor_base.domains.dynamic_group.models import DynamicGroupMemberORM

    members = [
        DynamicGroupMemberORM(
            dynamic_group=db_dynamic_group,
            member={"bk_inst_id": 101, "ip_list": [{"ip": "10.0.0.1", "bk_cloud_id": 0}]},
        ),
        DynamicGroupMemberORM(
            dynamic_group=db_dynamic_group,
            member={"bk_inst_id": 102, "ip_list": [{"ip": "10.0.0.2", "bk_cloud_id": 0}]},
        ),
        DynamicGroupMemberORM(
            dynamic_group=db_dynamic_group,
            member={"bk_inst_id": 103, "ip_list": [{"ip": "10.0.0.3", "bk_cloud_id": 0}]},
        ),
    ]
    DynamicGroupMemberORM.objects.bulk_create(members)
    yield db_dynamic_group
    DynamicGroupMemberORM.objects.filter(dynamic_group=db_dynamic_group).delete()


@pytest.fixture
def sample_member_list():
    """创建示例成员列表"""
    return [
        {"bk_inst_id": 101, "ip_list": [{"ip": "10.0.0.1", "bk_cloud_id": 0, "bk_host_id": 101}]},
        {"bk_inst_id": 102, "ip_list": [{"ip": "10.0.0.2", "bk_cloud_id": 0, "bk_host_id": 102}]},
        {"bk_inst_id": 103, "ip_list": [{"ip": "10.0.0.3", "bk_cloud_id": 0, "bk_host_id": 103}]},
    ]


@pytest.fixture
def sample_condition_list():
    """创建示例条件列表"""
    return [
        {"field": "bk_host_innerip", "value": "10.", "operator": "contains"},
        {"field": "bk_cloud_id", "value": 0, "operator": "equal"},
    ]
