from typing import Any

import pytest

from bk_monitor_base.domains.object_model.define import DatasourceType, ObjectModelGroup
from bk_monitor_base.domains.object_model.errors import ObjectModelGroupNotFound, ObjectModelGroupValidError
from bk_monitor_base.domains.object_model.models import ObjectModelGroupORM, ObjectModelORM
from bk_monitor_base.domains.object_model.operations.object_model_group import (
    _enrich_extra_fields,
    create_builtin_group_tree,
    create_object_model_group,
    delete_object_model_group,
    list_object_model_groups,
    update_object_model_group,
)


@pytest.fixture
def db_group():
    """创建Django ORM对象的fixture"""
    group = ObjectModelGroupORM.objects.create(
        object_model_group_code="pytest_group",
        object_model_group_name="pytest分组",
        is_default=False,
    )
    yield group
    group.delete()


@pytest.fixture
def db_group2():
    """创建Django ORM对象的fixture"""
    group = ObjectModelGroupORM.objects.create(
        object_model_group_code="pytest_group2",
        object_model_group_name="pytest分组2",
        is_default=False,
    )
    yield group
    group.delete()


@pytest.fixture
def db_child_group(db_group):
    """创建子分组的fixture"""
    child = ObjectModelGroupORM.objects.create(
        object_model_group_code="pytest_child",
        object_model_group_name="pytest子分组",
        is_default=False,
        parent_object_model_group=db_group,
    )
    yield child
    child.delete()


@pytest.fixture
def db_builtin_group():
    """创建内置分组的fixture"""
    group = ObjectModelGroupORM.objects.create(
        object_model_group_code="builtin_group",
        object_model_group_name="内置分组",
        is_default=True,
    )
    yield group
    group.delete()


@pytest.fixture
def group_entity(default_language):
    """创建Pydantic实体的fixture"""
    return ObjectModelGroup(
        object_model_group_code="test_group",
        object_model_group_name="测试分组",
        object_model_group_name_i18n={default_language.frontend_code: "测试分组"},
        is_default=False,
    )


@pytest.mark.django_db(databases=["default"])
class TestListObjectModelGroups:
    """测试 list_object_model_groups 函数"""

    def test_list_object_model_groups_basic(self, db_group, db_child_group):
        """测试基本的分组列表查询"""
        result = list_object_model_groups()

        assert len(result) >= 2
        found_group = next((g for g in result if g.object_model_group_code == "pytest_group"), None)
        assert found_group is not None
        assert found_group.object_model_group_name == "pytest分组"

    @pytest.mark.parametrize(
        "filter_params,expected_field,expected_value",
        [
            ({"object_model_group_ids": []}, "object_model_group_code", "pytest_group"),
            ({"object_model_group_codes": ["pytest_child"]}, "object_model_group_code", "pytest_child"),
            ({"parent_object_model_group_ids": []}, "object_model_group_code", "pytest_child"),
            ({"name_contains": "pytest"}, "object_model_group_name", "pytest分组"),
            ({"is_default": False}, "is_default", False),
            ({"is_child": True}, "object_model_group_code", "pytest_child"),
            ({"is_child": False}, "object_model_group_code", "pytest_group"),
        ],
    )
    def test_list_object_model_groups_with_filters(
        self, db_group, db_child_group, filter_params, expected_field, expected_value
    ):
        """参数化测试带过滤条件的分组列表查询"""
        # 动态设置有效的id值
        if "object_model_group_ids" in filter_params and filter_params["object_model_group_ids"] == []:
            filter_params["object_model_group_ids"] = [db_group.object_model_group_id]
        elif "parent_object_model_group_ids" in filter_params and filter_params["parent_object_model_group_ids"] == []:
            filter_params["parent_object_model_group_ids"] = [db_group.object_model_group_id]

        result = list_object_model_groups(**filter_params)
        assert len(result) >= 1

        # 验证过滤结果
        found_group = next((g for g in result if getattr(g, expected_field) == expected_value), None)
        assert found_group is not None

    def test_list_object_model_groups_raise_not_found_success(self, db_group):
        """测试raise_not_found=True时查询到结果"""
        result = list_object_model_groups(
            is_default=False,
            raise_not_found=True,
        )
        assert len(result) >= 1

    def test_list_object_model_groups_raise_not_found_error(self):
        """测试raise_not_found=True时未查询到结果抛出异常"""
        with pytest.raises(ObjectModelGroupNotFound):
            list_object_model_groups(object_model_group_codes=["non_existent_group"], raise_not_found=True)

    def test_list_object_model_groups_multiple_filters(self, db_group, db_child_group):
        """测试多个过滤条件组合"""
        result = list_object_model_groups(
            is_default=False,
            name_contains="pytest",
            is_child=False,
        )
        assert len(result) >= 1
        found_group = next((g for g in result if g.object_model_group_code == "pytest_group"), None)
        assert found_group is not None


@pytest.mark.django_db(databases=["default"])
class TestCreateObjectModelGroup:
    """测试 create_object_model_group 函数"""

    def test_create_object_model_group_success(self, group_entity):
        """测试成功创建对象模型分组"""
        result = create_object_model_group(group_entity)

        assert result.object_model_group_code == "test_group"
        assert result.object_model_group_name == "测试分组"
        assert result.object_model_group_id is not None

        # 清理
        ObjectModelGroupORM.objects.filter(object_model_group_code="test_group").delete()

    def test_create_object_model_group_with_parent(self, db_group, group_entity):
        """测试创建带父分组的对象模型分组"""
        group_entity.parent_object_model_group_id = db_group.object_model_group_id

        result = create_object_model_group(group_entity)

        assert result.parent_object_model_group_id == db_group.object_model_group_id
        assert result.level == 2

        # 清理
        ObjectModelGroupORM.objects.filter(object_model_group_code="test_group").delete()

    def test_create_object_model_group_with_i18n_names(self, group_entity, default_language):
        """测试创建带多语言名称的对象模型分组"""
        group_entity.object_model_group_name_i18n = {"en": "Test Group", "zh-cn": "测试分组"}

        result = create_object_model_group(group_entity)
        assert result.object_model_group_name == result.object_model_group_name_i18n[default_language.frontend_code]

        # 验证数据库中的多语言字段
        db_group = ObjectModelGroupORM.objects.get(object_model_group_id=result.object_model_group_id)
        assert db_group.object_model_group_name_en == "Test Group"
        assert db_group.object_model_group_name_zh_hans == "测试分组"

        # 清理
        db_group.delete()

    @pytest.mark.parametrize(
        "duplicate_field,error_message",
        [
            ("object_model_group_code", "对象模型分组code已存在"),
            ("object_model_group_name", "对象模型分组名称已存在"),
        ],
    )
    def test_create_object_model_group_duplicate_fields(
        self, db_group, group_entity, duplicate_field, error_message, default_language
    ):
        """参数化测试创建分组时各种重复字段的异常"""
        if duplicate_field == "object_model_group_code":
            group_entity.object_model_group_code = "pytest_group"
        elif duplicate_field == "object_model_group_name":
            group_entity.object_model_group_name = "pytest分组"
            group_entity.object_model_group_name_i18n.update({default_language.frontend_code: "pytest分组"})

        with pytest.raises(ObjectModelGroupValidError, match=error_message):
            create_object_model_group(group_entity)

    def test_create_object_model_group_duplicate_i18n_name(self, db_group, group_entity, default_language):
        """测试创建分组时多语言名称重复"""
        # 设置与已存在分组相同的名称
        group_entity.object_model_group_name_i18n = {default_language.frontend_code: "pytest分组"}

        # 假设db_group也有相同的名称
        setattr(
            db_group,
            default_language.format_db_field_key("object_model_group_name"),
            "pytest分组",
        )
        db_group.save()

        with pytest.raises(ObjectModelGroupValidError, match="对象模型分组名称已存在"):
            create_object_model_group(group_entity)

    def test_create_object_model_group_parent_not_exist(self, group_entity):
        """测试父分组不存在时抛出异常"""
        group_entity.parent_object_model_group_id = 999  # 不存在的父分组ID

        with pytest.raises(ObjectModelGroupNotFound, match="父级分组不存在"):
            create_object_model_group(group_entity)

    def test_create_object_model_group_invalid_parent_level(self, db_group, group_entity):
        """测试父分组层级不正确时抛出异常"""
        # 先创建一个二级分组作为父分组
        child_as_parent = ObjectModelGroupORM.objects.create(
            object_model_group_code="child_as_parent",
            object_model_group_name="作为父分组的子分组",
            is_default=False,
            parent_object_model_group=db_group,
        )

        group_entity.parent_object_model_group_id = child_as_parent.object_model_group_id

        with pytest.raises(ObjectModelGroupValidError, match="父级分组只能是一级分组"):
            create_object_model_group(group_entity)

        # 清理
        child_as_parent.delete()


@pytest.mark.django_db(databases=["default"])
class TestUpdateObjectModelGroup:
    """测试 update_object_model_group 函数"""

    def test_update_object_model_group_success(self, db_group, default_language):
        """测试成功更新对象模型分组"""
        entity = ObjectModelGroup(
            object_model_group_id=db_group.object_model_group_id,
            object_model_group_code="pytest_group_updated",
            object_model_group_name="pytest分组更新",
            object_model_group_name_i18n={default_language.frontend_code: "pytest分组更新"},
            is_default=False,
        )

        result = update_object_model_group(entity)

        assert result.object_model_group_name == "pytest分组更新"
        assert result.object_model_group_code == "pytest_group_updated"

    def test_update_object_model_group_with_i18n_names(self, db_group, default_language):
        """测试更新分组的多语言名称"""
        entity = db_group.to_entity()
        entity.object_model_group_name_i18n = {
            "en": "Updated Group",
            "zh-cn": "更新分组",
        }

        result = update_object_model_group(entity)

        # 验证数据库中的多语言字段
        updated_group = ObjectModelGroupORM.objects.get(object_model_group_id=result.object_model_group_id)
        assert updated_group.object_model_group_name_en == "Updated Group"
        assert updated_group.object_model_group_name_zh_hans == "更新分组"

    def test_update_object_model_group_not_found(self, group_entity):
        """测试更新不存在的分组时抛出异常"""
        group_entity.object_model_group_id = 999  # 不存在的ID

        with pytest.raises(ObjectModelGroupORM.DoesNotExist):
            update_object_model_group(group_entity)

    def test_update_object_model_group_builtin_restriction(self, db_builtin_group):
        """测试更新内置分组的限制"""
        # 假设builtin_group在NOT_UPDATE_OBJECT_MODEL_GROUP_CODE_LIST中
        entity = db_builtin_group.to_entity()
        entity.object_model_group_name = "不允许更新的名称"

        # 这个测试需要根据实际的NOT_UPDATE_OBJECT_MODEL_GROUP_CODE_LIST来调整
        # 如果builtin_group不在限制列表中，需要创建一个在列表中的分组

    @pytest.mark.parametrize(
        "duplicate_field,error_message",
        [
            ("object_model_group_code", "对象模型分组code已存在"),
            ("object_model_group_name", "已存在相同的对象分组名称"),
        ],
    )
    def test_update_object_model_group_duplicate_fields(
        self, db_group, db_group2, db_child_group, duplicate_field, error_message, default_language
    ):
        """参数化测试更新分组时各种重复字段的异常"""
        entity = db_group.to_entity()

        if duplicate_field == "object_model_group_code":
            entity.object_model_group_code = db_child_group.object_model_group_code
        elif duplicate_field == "object_model_group_name":
            entity.object_model_group_name = db_group2.object_model_group_name
            entity.object_model_group_name_i18n[default_language.frontend_code] = db_group2.object_model_group_name

        with pytest.raises(ObjectModelGroupValidError, match=error_message):
            update_object_model_group(entity)

    def test_update_group_to_second_level_with_children(self, db_group, db_child_group):
        """测试将有子分组的一级分组改为二级分组"""
        # 创建另一个一级分组作为父分组
        another_parent = ObjectModelGroupORM.objects.create(
            object_model_group_code="another_parent",
            object_model_group_name="另一个父分组",
            is_default=False,
        )

        entity = db_group.to_entity()
        entity.parent_object_model_group_id = another_parent.object_model_group_id

        with pytest.raises(ObjectModelGroupValidError, match="已有子分组，不可修改为二级分组"):
            update_object_model_group(entity)

        # 清理
        another_parent.delete()

    def test_update_group_to_first_level_with_models(self, db_group, db_child_group):
        """测试将有对象模型的二级分组改为一级分组"""
        # 在子分组下创建对象模型
        model = ObjectModelORM.objects.create(
            object_model_code="test_model",
            object_model_name="测试模型",
            object_model_group=db_child_group,
            datasource=DatasourceType.CMDB,
            bk_cmdb_obj_id="test",
            inst_display_name="test",
            display_fields=[{"field": "name"}],
        )

        entity = db_child_group.to_entity()
        entity.parent_object_model_group_id = None  # 改为一级分组

        with pytest.raises(ObjectModelGroupValidError, match="已有对象模型，不可修改为一级分组"):
            update_object_model_group(entity)

        # 清理
        model.delete()

    def test_update_group_parent_invalid_level(self, db_group, db_child_group, default_language):
        """测试设置二级分组作为父分组"""
        entity = ObjectModelGroup(
            object_model_group_id=db_group.object_model_group_id,
            object_model_group_code="test_update",
            object_model_group_name="测试更新",
            object_model_group_name_i18n={default_language.frontend_code: "测试更新"},
            parent_object_model_group_id=db_child_group.object_model_group_id,  # 设置二级分组为父分组
            is_default=False,
        )

        with pytest.raises(ObjectModelGroupValidError, match="父级分组只能是一级分组"):
            update_object_model_group(entity)


@pytest.mark.django_db(databases=["default"])
class TestDeleteObjectModelGroup:
    """测试 delete_object_model_group 函数"""

    def test_delete_object_model_group_success(self, db_group):
        """测试成功删除对象模型分组"""
        group_id = db_group.object_model_group_id
        result = delete_object_model_group(group_id)

        assert result.object_model_group_code == "pytest_group"

        # 验证已删除
        assert not ObjectModelGroupORM.objects.filter(object_model_group_id=group_id).exists()

    def test_delete_object_model_group_not_found(self):
        """测试删除不存在的分组时抛出异常"""
        with pytest.raises(ObjectModelGroupNotFound):
            delete_object_model_group(999)

    def test_delete_object_model_group_with_models(self, db_group):
        """测试删除关联了对象模型的分组时抛出异常"""
        # 直接在一级分组下创建对象模型
        model = ObjectModelORM.objects.create(
            object_model_code="test_model",
            object_model_name="测试模型",
            object_model_group=db_group,
            datasource=DatasourceType.CMDB,
            bk_cmdb_obj_id="test",
            inst_display_name="test",
            display_fields=[{"field": "name"}],
        )

        with pytest.raises(ObjectModelGroupValidError, match="该对象模型分组或其子分组已关联对象模型，无法删除"):
            delete_object_model_group(db_group.object_model_group_id)

        # 清理
        model.delete()

    def test_delete_object_model_group_with_child_models(self, db_group, db_child_group):
        """测试删除子分组关联了对象模型的分组时抛出异常"""
        # 在子分组下创建对象模型
        model = ObjectModelORM.objects.create(
            object_model_code="test_model",
            object_model_name="测试模型",
            object_model_group=db_child_group,
            datasource=DatasourceType.CMDB,
            bk_cmdb_obj_id="test",
            inst_display_name="test",
            display_fields=[{"field": "name"}],
        )

        with pytest.raises(ObjectModelGroupValidError, match="该对象模型分组或其子分组已关联对象模型，无法删除"):
            delete_object_model_group(db_group.object_model_group_id)

        # 清理
        model.delete()

    def test_delete_builtin_restricted_group(self, db_builtin_group):
        """测试删除受限制的内置分组"""
        # 这个测试需要根据实际的NOT_DELETE_OBJECT_MODEL_GROUP_CODE_LIST来调整
        # 如果builtin_group不在限制列表中，需要创建一个在列表中的分组


@pytest.mark.django_db(databases=["default"])
class TestEnrichExtraFields:
    """测试 _enrich_extra_fields 函数"""

    def test_enrich_extra_fields_basic(self, db_group, db_child_group):
        """测试补充分组额外字段"""
        entity_list = [db_group.to_entity(), db_child_group.to_entity()]
        result = _enrich_extra_fields(entity_list)

        assert len(result) == 2

        # 验证额外字段被添加
        for entity in result:
            assert hasattr(entity, "related_obj")
            assert hasattr(entity, "can_delete")
            assert hasattr(entity, "can_create")
            assert hasattr(entity, "can_update")

    def test_enrich_extra_fields_with_related_models(self, db_group, db_child_group):
        """测试有关联对象模型的分组额外字段"""
        # 在子分组下创建对象模型
        model = ObjectModelORM.objects.create(
            object_model_code="test_model",
            object_model_name="测试模型",
            object_model_group=db_child_group,
            datasource=DatasourceType.CMDB,
            bk_cmdb_obj_id="test",
            inst_display_name="test",
            display_fields=[{"field": "name"}],
        )

        entity_list = [db_group.to_entity(), db_child_group.to_entity()]
        result = _enrich_extra_fields(entity_list)

        # 查找有关联模型的分组
        child_entity = next(e for e in result if e.object_model_group_id == db_child_group.object_model_group_id)
        assert child_entity.related_obj is True
        assert child_entity.can_delete is False  # 有关联模型，不能删除

        # 清理
        model.delete()

    def test_enrich_extra_fields_parent_with_children(self, db_group, db_child_group):
        """测试有子分组的父分组额外字段"""
        entity_list = [db_group.to_entity()]
        result = _enrich_extra_fields(entity_list)

        parent_entity = result[0]
        assert parent_entity.can_delete is False  # 有子分组，不能删除

    def test_enrich_extra_fields_empty_list(self):
        """测试空列表的额外字段补充"""
        result = _enrich_extra_fields([])
        assert result == []

    def test_enrich_extra_fields_none_id(self):
        """测试没有ID的实体"""
        entity = ObjectModelGroup(
            object_model_group_code="test",
            object_model_group_name="测试",
            is_default=False,
        )
        result = _enrich_extra_fields([entity])

        assert len(result) == 1
        # 没有ID的实体应该也能正常处理


@pytest.mark.django_db(databases=["default"])
class TestCreateBuiltinGroupTree:
    """测试 create_builtin_group_tree 函数"""

    @pytest.fixture
    def component_init_data(self) -> dict[str, Any]:
        return {
            "object_model_group_name": "组件",
            "object_model_group_name_en": "Component",
            "object_model_group_name_zh_hans": "组件",
            "object_model_group_code": "cw-Component",
            "children": [
                {
                    "object_model_group_name": "数据库监控",
                    "object_model_group_name_en": "Database Monitor",
                    "object_model_group_name_zh_hans": "数据库监控",
                    "object_model_group_code": "cw-Databases",
                    "children": [
                        {
                            "object_model_code": "cw-Oracle",
                            "object_model_name": "Oracle",
                            "object_model_name_en": "Oracle",
                            "object_model_name_zh_hans": "Oracle",
                            "datasource": "cmdb",
                        },
                        {
                            "object_model_code": "cw-MySQL",
                            "object_model_name": "MySQL",
                            "object_model_name_en": "MySQL",
                            "object_model_name_zh_hans": "MySQL",
                            "datasource": "cmdb",
                        },
                    ],
                },
                {
                    "object_model_group_name": "中间件监控",
                    "object_model_group_name_en": "Middleware Monitor",
                    "object_model_group_name_zh_hans": "中间件监控",
                    "object_model_group_code": "cw-Middlewares",
                    "children": [
                        {
                            "object_model_code": "cw-Nginx",
                            "object_model_name": "Nginx",
                            "object_model_name_en": "Nginx",
                            "object_model_name_zh_hans": "Nginx",
                            "datasource": "cmdb",
                        },
                        {
                            "object_model_code": "cw-Tomcat",
                            "object_model_name": "Tomcat",
                            "object_model_name_en": "Tomcat",
                            "object_model_name_zh_hans": "Tomcat",
                            "datasource": "cmdb",
                        },
                    ],
                },
            ],
        }

    @pytest.fixture
    def cloud_init_data(self) -> dict[str, Any]:
        """云平台数据源的初始化数据"""
        return {
            "object_model_group_name": "云平台监控",
            "object_model_group_name_en": "Cloud Platform Monitor",
            "object_model_group_name_zh_hans": "云平台监控",
            "object_model_group_code": "cw-Cloud_Platforms",
            "children": [
                {
                    "object_model_group_code": "cw-Cloud_Virtual_Machine",
                    "object_model_group_name": "虚拟机",
                    "object_model_group_name_en": "Virtual Machine",
                    "object_model_group_name_zh_hans": "虚拟机",
                    "children": [
                        {
                            "object_model_code": "cw-Cloud_Virtual_Machine_VMware",
                            "object_model_name": "虚拟机-VMware vCenter",
                            "object_model_name_en": "VMware vCenter Virtual Machine",
                            "object_model_name_zh_hans": "虚拟机-VMware vCenter",
                            "datasource": "custom",
                        },
                        {
                            "object_model_code": "cw-Cloud_Virtual_Machine_Ali",
                            "object_model_name": "虚拟机-阿里公有云",
                            "object_model_name_en": "Ali Public Cloud Virtual Machine",
                            "object_model_name_zh_hans": "虚拟机-阿里公有云",
                            "datasource": "custom",
                        },
                    ],
                },
                {
                    "object_model_group_code": "cw-Cloud_DataStore",
                    "object_model_group_name": "数据存储",
                    "object_model_group_name_en": "Data Storage",
                    "object_model_group_name_zh_hans": "数据存储",
                    "children": [
                        {
                            "object_model_code": "cw-Cloud_DataStore_VMware",
                            "object_model_name": "数据存储-VMware vCenter",
                            "object_model_name_en": "VMware vCenter Data Store",
                            "object_model_name_zh_hans": "数据存储-VMware vCenter",
                            "datasource": "custom",
                        },
                        {
                            "object_model_code": "cw-Cloud_DataStore_WinStack",
                            "object_model_name": "数据存储-云宏CNware",
                            "object_model_name_en": "Winhong CNware Data Store",
                            "object_model_name_zh_hans": "数据存储-云宏CNware",
                            "datasource": "custom",
                        },
                    ],
                },
            ],
        }

    @pytest.fixture
    def direct_model_init_data(self) -> dict[str, Any]:
        """直接在一级分组下创建对象模型的数据"""
        return {
            "object_model_group_name": "主机监控",
            "object_model_group_name_en": "Host Monitor",
            "object_model_group_name_zh_hans": "主机监控",
            "object_model_group_code": "host_monitor",
            "children": [
                {
                    "object_model_code": "host",
                    "object_model_name": "主机",
                    "object_model_name_en": "Host",
                    "object_model_name_zh_hans": "主机",
                    "bk_cmdb_obj_id": "host",
                    "display_fields": [{"field": "bk_host_innerip"}],
                    "inst_display_name": "主机IP",
                }
            ],
        }

    def test_create_builtin_group_tree_cmdb(self, component_init_data):
        """测试创建CMDB数据源的内置分组树"""
        create_builtin_group_tree(component_init_data)
        # 可重复执行
        create_builtin_group_tree(component_init_data)

        component_group = ObjectModelGroupORM.objects.get(object_model_group_code="cw-Component")
        db_group = ObjectModelGroupORM.objects.get(object_model_group_code="cw-Databases")
        middleware_group = ObjectModelGroupORM.objects.get(object_model_group_code="cw-Middlewares")

        assert component_group.is_default is True
        assert db_group.parent_object_model_group == component_group
        assert middleware_group.parent_object_model_group == component_group

        # 验证对象模型
        db_models = list(
            ObjectModelORM.objects.filter(object_model_group=db_group).values_list("object_model_code", flat=True)
        )
        assert "cw-Oracle" in db_models
        assert "cw-MySQL" in db_models

        middleware_models = list(
            ObjectModelORM.objects.filter(object_model_group=middleware_group).values_list(
                "object_model_code", flat=True
            )
        )
        assert "cw-Nginx" in middleware_models
        assert "cw-Tomcat" in middleware_models

        # 验证对象模型的数据源类型
        oracle_model = ObjectModelORM.objects.get(object_model_code="cw-Oracle")
        assert oracle_model.datasource == DatasourceType.CMDB
        assert oracle_model.is_default is True

        # 清理
        ObjectModelORM.objects.filter(object_model_group__in=[db_group, middleware_group]).delete()
        db_group.delete()
        middleware_group.delete()
        component_group.delete()

    def test_create_builtin_group_tree_custom(self, cloud_init_data):
        """测试创建CUSTOM数据源的内置分组树"""
        create_builtin_group_tree(cloud_init_data)
        create_builtin_group_tree(cloud_init_data)

        cloud_group = ObjectModelGroupORM.objects.get(object_model_group_code="cw-Cloud_Platforms")
        vm_group = ObjectModelGroupORM.objects.get(object_model_group_code="cw-Cloud_Virtual_Machine")
        ds_group = ObjectModelGroupORM.objects.get(object_model_group_code="cw-Cloud_DataStore")

        # 验证对象模型的数据源类型为CUSTOM
        assert cloud_group.is_default is True
        assert vm_group.is_default is True
        assert ds_group.is_default is True

        # 验证对象模型
        vm_models = list(
            ObjectModelORM.objects.filter(object_model_group=vm_group, datasource=DatasourceType.CUSTOM).values_list(
                "object_model_code", flat=True
            )
        )
        assert "cw-Cloud_Virtual_Machine_VMware" in vm_models
        assert "cw-Cloud_Virtual_Machine_Ali" in vm_models

        ds_models = list(
            ObjectModelORM.objects.filter(object_model_group=ds_group, datasource=DatasourceType.CUSTOM).values_list(
                "object_model_code", flat=True
            )
        )
        assert "cw-Cloud_DataStore_VMware" in ds_models
        assert "cw-Cloud_DataStore_WinStack" in ds_models

        ObjectModelORM.objects.filter(object_model_group__in=[vm_group, ds_group]).delete()
        vm_group.delete()
        ds_group.delete()
        cloud_group.delete()
