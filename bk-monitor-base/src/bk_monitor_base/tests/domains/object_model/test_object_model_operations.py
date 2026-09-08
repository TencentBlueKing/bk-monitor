import pytest
from pydantic import ValidationError

from bk_monitor_base.domains.object_model.constants import BuiltinObjectModelGroupCode
from bk_monitor_base.domains.object_model.define import (
    AttributeConfig,
    DatasourceType,
    ObjectModel,
)
from bk_monitor_base.domains.object_model.errors import (
    ObjectModelGroupNotFound,
    ObjectModelNotFound,
    ObjectModelOperateError,
    ObjectModelValidError,
)
from bk_monitor_base.domains.object_model.models import ObjectModelGroupORM, ObjectModelORM, ObjectModelUsageRecordORM
from bk_monitor_base.domains.object_model.operations.object_model import (
    _enrich_extra_fields,
    _validate_delete_object_model,
    create_object_model,
    delete_object_model,
    get_cloud_object_model_code_list,
    list_object_models,
    update_object_model,
)
from bk_monitor_base.tests.domains.object_model import ATTRIBUTE_CONFIG_ENTITY


@pytest.fixture
def db_group():
    """创建Django ORM分组对象的fixture"""
    group = ObjectModelGroupORM.objects.create(
        object_model_group_code="pytest_group",
        object_model_group_name="pytest分组",
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
    child.objectmodelorm_set.all().delete()
    child.delete()


@pytest.fixture
def db_object_model(db_child_group):
    """创建Django ORM对象模型的fixture"""
    model = ObjectModelORM.objects.create(
        object_model_code="pytest_model",
        object_model_name="pytest模型",
        object_model_group=db_child_group,
        datasource=DatasourceType.CMDB,
        is_default=False,
        bk_cmdb_obj_id="test_cmdb",
        display_fields=[{"field": "name"}],
        inst_display_name="test_display",
    )
    yield model
    model.delete()


@pytest.fixture
def db_object_model_custom(db_child_group):
    """创建Django ORM对象模型的fixture"""
    model = ObjectModelORM.objects.create(
        object_model_code="pytest_model_custom",
        object_model_name="pytest模型_custom",
        object_model_group=db_child_group,
        datasource=DatasourceType.CUSTOM,
        is_default=False,
        bk_cmdb_obj_id="test_custom",
        display_fields=[{"field": "name"}],
        inst_display_name="test_display",
    )
    yield model
    model.delete()


@pytest.fixture
def db_usage_record(db_object_model):
    """创建使用记录的fixture"""
    record = ObjectModelUsageRecordORM.objects.create(
        object_model=db_object_model,
        app_id="test_app",
        app_name="测试应用",
        module_id="test_module",
        module_name="测试模块",
        inst_id="test_inst",
        inst_name="测试实例",
        created_by="test_user",
    )
    yield record
    record.delete()


@pytest.fixture
def object_model_entity(db_child_group, default_language):
    """创建Pydantic实体的fixture"""
    return ObjectModel(
        object_model_code="test_model",
        object_model_name="测试模型",
        object_model_name_i18n={default_language.frontend_code: "测试模型"},
        object_model_group_id=db_child_group.object_model_group_id,
        datasource=DatasourceType.CMDB,
        is_default=False,
        bk_cmdb_obj_id="test_cmdb2",
        display_fields=[{"field": "name"}],
        inst_display_name="test_display",
        attribute_config=ATTRIBUTE_CONFIG_ENTITY,
    )


@pytest.fixture
def object_model_custom_entity(db_child_group, default_language):
    """创建Pydantic实体的fixture"""
    return ObjectModel(
        object_model_code="test_model_custom",
        object_model_name="测试模型_custom",
        object_model_name_i18n={default_language.frontend_code: "测试模型_custom"},
        object_model_group_id=db_child_group.object_model_group_id,
        datasource=DatasourceType.CUSTOM,
        is_default=False,
        bk_cmdb_obj_id="test_custom2",
        display_fields=[{"field": "name"}],
        inst_display_name="test_display",
    )


@pytest.mark.django_db(databases=["default"])
class TestListObjectModels:
    """测试 list_object_models 函数"""

    def test_list_object_models_basic(self, db_object_model):
        """测试基本的对象模型列表查询"""
        result = list_object_models()

        assert len(result) == 1
        assert result[0].object_model_name == "pytest模型"
        assert result[0].attribute_config == AttributeConfig()

    @pytest.mark.parametrize(
        "filter_params,expected_min_count",
        [
            ({"object_model_ids": []}, 1),  # 会被动态设置
            ({"object_model_codes": ["pytest_model"]}, 1),
            ({"object_model_codes": ["non_existent"]}, 0),
            ({"object_model_group_ids": []}, 1),  # 会被动态设置
            ({"bk_cmdb_obj_ids": ["test_cmdb"]}, 1),
            ({"bk_cmdb_obj_ids": ["non_existent"]}, 0),
            ({"name_contains": "pytest"}, 1),
            ({"name_contains": "不存在"}, 0),
            ({"datasources": [DatasourceType.CMDB]}, 1),
            ({"datasources": [DatasourceType.CUSTOM]}, 0),
        ],
    )
    def test_list_object_models_with_filters(self, db_object_model, filter_params, expected_min_count):
        """参数化测试带过滤条件的对象模型查询"""
        # 动态设置有效的id值
        if "object_model_ids" in filter_params and filter_params["object_model_ids"] == []:
            filter_params["object_model_ids"] = [db_object_model.object_model_id]
        elif "object_model_group_ids" in filter_params and filter_params["object_model_group_ids"] == []:
            filter_params["object_model_group_ids"] = [db_object_model.object_model_group.object_model_group_id]

        result = list_object_models(**filter_params)
        assert len(result) >= expected_min_count

        if expected_min_count > 0:
            found_model = next((m for m in result if m.object_model_code == "pytest_model"), None)
            assert found_model is not None

    def test_list_object_models_with_pagination(self, db_object_model):
        """测试分页查询"""
        # 测试limit
        result = list_object_models(limit=1)
        assert len(result) <= 1

        # 测试offset
        all_models = list_object_models()
        if len(all_models) > 1:
            result_with_offset = list_object_models(offset=1)
            assert len(result_with_offset) == len(all_models) - 1

        # 测试limit + offset
        result_limited = list_object_models(limit=1, offset=0)
        assert len(result_limited) <= 1

    def test_list_object_models_raise_not_found(self):
        """测试未找到对象模型时抛出异常"""
        with pytest.raises(ObjectModelNotFound):
            list_object_models(object_model_codes=["non_existent_model"], raise_not_found=True)

    def test_list_object_models_datasource_legacy_mapping(self, db_child_group):
        """测试DatasourceType.LEGACY的映射查询"""
        # 创建LEGACY类型的对象模型
        legacy_model = ObjectModelORM.objects.create(
            object_model_code="legacy_model",
            object_model_name="遗留模型",
            object_model_group=db_child_group,
            datasource=DatasourceType.LEGACY,
            is_default=True,
            bk_cmdb_obj_id="legacy_cmdb",
            display_fields=[{"field": "name"}],
            inst_display_name="legacy_display",
        )

        result = list_object_models(datasources=[DatasourceType.LEGACY])
        found_legacy = next((m for m in result if m.object_model_code == "legacy_model"), None)
        assert found_legacy is not None

        # 清理
        legacy_model.delete()

    def test_list_object_models_raise_not_found_true_with_results(self, db_object_model):
        """测试 raise_not_found=True 但有结果的情况"""
        # 这应该不会抛出异常，因为有结果
        result = list_object_models(raise_not_found=True)
        assert len(result) > 0

    def test_list_object_models_with_limit_none_offset_none(self, db_object_model):
        """测试 limit 和 offset 都为 None 的情况"""
        result = list_object_models(limit=None, offset=None)
        assert len(result) >= 1

    def test_list_object_models_with_limit_only(self, db_object_model):
        """测试只有 limit 没有 offset 的情况"""
        result = list_object_models(limit=1, offset=None)
        assert len(result) == 1


@pytest.mark.django_db(databases=["default"])
class TestCreateObjectModel:
    """测试 create_object_model/update_object_model 函数"""

    def test_create_object_model_success(self, object_model_entity):
        """测试成功创建对象模型"""
        result = create_object_model(object_model_entity)

        assert result.object_model_code == "test_model"
        assert result.object_model_name == "测试模型"
        assert result.object_model_id is not None
        assert result.attribute_config == ATTRIBUTE_CONFIG_ENTITY

        # 清理
        ObjectModelORM.objects.filter(object_model_code="test_model").delete()

    def test_create_object_model_group_not_found(self, object_model_entity):
        """测试分组不存在时抛出异常"""
        object_model_entity.object_model_group_id = 999  # 不存在的分组ID

        with pytest.raises(ObjectModelGroupNotFound):
            create_object_model(object_model_entity)

    def test_create_object_model_invalid_group_level(self, db_group, object_model_entity):
        """测试分组层级不正确时抛出异常"""
        object_model_entity.object_model_group_id = db_group.object_model_group_id  # 使用一级分组

        with pytest.raises(ObjectModelValidError, match="对象模型分组必须选择二级分组"):
            create_object_model(object_model_entity)

    @pytest.mark.parametrize(
        "duplicate_field,error,error_message",
        [
            ("object_model_code", ObjectModelValidError, "对象模型code已存在"),
            ("object_model_name", ObjectModelValidError, "对象模型名称已存在"),
            ("bk_cmdb_obj_id", ObjectModelValidError, "CMDB对象ID已存在"),
        ],
    )
    def test_create_object_model_duplicate_fields(
        self, db_object_model, object_model_entity, duplicate_field, error, error_message, default_language
    ):
        """参数化测试创建对象模型时各种重复字段的异常"""
        if duplicate_field == "object_model_code":
            object_model_entity.object_model_code = "pytest_model"
        elif duplicate_field == "object_model_name":
            object_model_entity.object_model_name = "pytest模型"
            object_model_entity.object_model_name_i18n = {default_language.frontend_code: "pytest模型"}
        elif duplicate_field == "bk_cmdb_obj_id":
            object_model_entity.bk_cmdb_obj_id = "test_cmdb"

        with pytest.raises(error, match=error_message):
            create_object_model(object_model_entity)

    def test_create_object_model_cmdb_obj_id_duplicate_edge_case(self, db_child_group, default_language):
        """测试 CMDB 对象 ID 重复检查的边界情况"""
        # 先创建一个CMDB类型的对象模型
        existing_model = ObjectModelORM.objects.create(
            object_model_code="existing_cmdb",
            object_model_name="existing_cmdb_model",
            object_model_group=db_child_group,
            datasource=DatasourceType.CMDB,
            bk_cmdb_obj_id="duplicate_id",
            display_fields=[{"field": "name"}],
            inst_display_name="display",
        )

        # 尝试创建具有相同 bk_cmdb_obj_id 的模型应该失败
        with pytest.raises(ObjectModelValidError) as exc_info:
            create_object_model(
                ObjectModel(
                    object_model_code="new_cmdb",
                    object_model_name="new_cmdb_model",
                    object_model_group_id=db_child_group.object_model_group_id,
                    datasource=DatasourceType.CMDB,
                    bk_cmdb_obj_id="duplicate_id",
                    display_fields=[{"field": "name"}],
                    inst_display_name="display",
                    object_model_name_i18n={default_language.frontend_code: "new_cmdb_model"},
                )
            )

        assert "CMDB对象ID已存在" in str(exc_info.value)

        # 尝试创建具有相同 bk_cmdb_obj_id 的自定义模型应该成功
        create_object_model(
            ObjectModel(
                object_model_code="new_custom",
                object_model_name="new_custom_model",
                object_model_group_id=db_child_group.object_model_group_id,
                datasource=DatasourceType.CUSTOM,
                bk_cmdb_obj_id="duplicate_id",
                display_fields=[{"field": "name"}],
                inst_display_name="display",
                object_model_name_i18n={default_language.frontend_code: "new_cmdb_model"},
            )
        )
        existing_model.delete()
        ObjectModelORM.objects.filter(object_model_code="new_custom").delete()

    @pytest.mark.parametrize(
        "field,value,expected_exception",
        [
            ("object_model_code", "", ValidationError),
            ("object_model_name", "", ObjectModelValidError),
            ("bk_cmdb_obj_id", "", ObjectModelValidError),
            ("inst_display_name", "", ObjectModelValidError),
            ("display_fields", [], ObjectModelValidError),
            ("display_fields", [{"field": "name"}] * 6, ObjectModelValidError),  # 超过5个
        ],
    )
    def test_create_object_model_invalid_fields(
        self, field, value, expected_exception, db_child_group, default_language
    ):
        """参数化测试对象模型字段校验"""
        entity = ObjectModel(
            object_model_code="test_model",
            object_model_name="测试模型",
            object_model_name_i18n={default_language.frontend_code: "测试模型"},
            object_model_group_id=db_child_group.object_model_group_id,
            datasource=DatasourceType.CMDB,
            is_default=False,
            bk_cmdb_obj_id="test_cmdb",
            display_fields=[{"field": "name"}],
            inst_display_name="test_display",
        )

        # 设置无效字段值
        setattr(entity, field, value)
        if field == "object_model_name":
            entity.object_model_name_i18n[default_language.frontend_code] = value

        with pytest.raises(expected_exception):
            create_object_model(entity)

    def test_create_object_model_with_i18n_names(self, object_model_entity, default_language):
        """测试创建带多语言名称的对象模型"""
        object_model_entity.object_model_name_i18n = {"en": "Test Model", "zh-cn": "测试模型"}

        result = create_object_model(object_model_entity)
        assert result.object_model_name == object_model_entity.object_model_name_i18n[default_language.frontend_code]

        # 验证数据库中的多语言字段
        db_model = ObjectModelORM.objects.get(object_model_id=result.object_model_id)
        assert db_model.object_model_name_en == "Test Model"
        assert db_model.object_model_name_zh_hans == "测试模型"

        # 清理
        db_model.delete()

    def test_create_object_model_duplicate_i18n_name(self, db_object_model, object_model_entity, default_language):
        """测试创建对象模型时多语言名称重复"""
        # 设置与已存在模型相同的英文名称
        object_model_entity.object_model_name_i18n = {default_language.frontend_code: "pytest模型"}

        # 假设db_object_model也有相同的英文名称
        db_object_model.object_model_name_en = "pytest模型"
        db_object_model.save()

        with pytest.raises(ObjectModelValidError, match="对象模型名称已存在"):
            create_object_model(object_model_entity)


@pytest.mark.django_db(databases=["default"])
class TestUpdateObjectModel:
    """测试 create_object_model/update_object_model 函数"""

    def test_update_object_model_success(self, db_object_model, default_language):
        """测试成功更新对象模型"""
        entity = db_object_model.to_entity()
        entity.object_model_name = "Updated Model Name"
        entity.object_model_name_i18n = {"en": "Updated Model Name", "zh-cn": "更新后的模型名称"}
        entity.attribute_config = ATTRIBUTE_CONFIG_ENTITY
        result = update_object_model(entity)

        assert result.object_model_name == entity.object_model_name_i18n[default_language.frontend_code]
        assert result.attribute_config.config[0].bk_property_id == ATTRIBUTE_CONFIG_ENTITY.config[0].bk_property_id
        assert result.attribute_config.config[0].bk_property_name == ATTRIBUTE_CONFIG_ENTITY.config[0].bk_property_name

    def test_update_object_model_not_found(self, object_model_entity):
        """测试更新不存在的对象模型时抛出异常"""
        object_model_entity.object_model_id = 999  # 不存在的ID

        with pytest.raises(ObjectModelNotFound):
            update_object_model(object_model_entity)

    def test_update_object_model_code_change_not_allowed(self, db_object_model):
        """测试更新对象模型时不允许修改code"""
        entity = db_object_model.to_entity()
        entity.object_model_code = "new_code"

        with pytest.raises(ObjectModelValidError, match="对象模型code不允许更新"):
            update_object_model(entity)

    @pytest.mark.parametrize(
        "duplicate_field,error_message",
        [
            ("object_model_name", "对象模型名称已存在"),
            ("bk_cmdb_obj_id", "CMDB对象ID已存在"),
        ],
    )
    def test_update_object_model_duplicate_fields(
        self, db_object_model, db_child_group, duplicate_field, error_message, default_language
    ):
        """参数化测试更新对象模型时各种重复字段的异常"""
        # 创建另一个对象模型
        another_model = ObjectModelORM.objects.create(
            object_model_code="another_model",
            object_model_name="另一个模型",
            object_model_group=db_child_group,
            datasource=DatasourceType.CMDB,
            is_default=False,
            bk_cmdb_obj_id="another_cmdb",
            display_fields=[{"field": "name"}],
            inst_display_name="another_display",
        )

        entity = db_object_model.to_entity()
        if duplicate_field == "object_model_name":
            entity.object_model_name = "另一个模型"
            entity.object_model_name_i18n = {default_language.frontend_code: "另一个模型"}
        elif duplicate_field == "bk_cmdb_obj_id":
            entity.bk_cmdb_obj_id = "another_cmdb"

        with pytest.raises(ObjectModelValidError, match=error_message):
            update_object_model(entity)

        # 清理
        another_model.delete()

    def test_update_object_model_cmdb_obj_id_duplicate_edge_case(self, db_child_group, default_language):
        """测试更新时 CMDB 对象 ID 重复检查的边界情况"""
        # 创建两个CMDB类型的对象模型
        model1 = ObjectModelORM.objects.create(
            object_model_code="cmdb1",
            object_model_name="cmdb_model1",
            object_model_group=db_child_group,
            datasource=DatasourceType.CMDB,
            bk_cmdb_obj_id="id1",
            display_fields=[{"field": "name"}],
            inst_display_name="display1",
        )

        model2 = ObjectModelORM.objects.create(
            object_model_code="cmdb2",
            object_model_name="cmdb_model2",
            object_model_group=db_child_group,
            datasource=DatasourceType.CMDB,
            bk_cmdb_obj_id="id2",
            display_fields=[{"field": "name"}],
            inst_display_name="display2",
        )

        model3 = ObjectModelORM.objects.create(
            object_model_code="custom1",
            object_model_name="custom_model1",
            object_model_group=db_child_group,
            datasource=DatasourceType.CUSTOM,
            bk_cmdb_obj_id="id3",
            display_fields=[{"field": "name"}],
            inst_display_name="display3",
        )

        # 尝试将 model2 的 bk_cmdb_obj_id 更新为 model1 的值应该失败
        with pytest.raises(ObjectModelValidError) as exc_info:
            update_object_model(
                ObjectModel(
                    object_model_id=model2.object_model_id,
                    object_model_code="cmdb2",
                    object_model_name="updated_name",
                    object_model_group_id=db_child_group.object_model_group_id,
                    datasource=DatasourceType.CMDB,
                    bk_cmdb_obj_id="id1",  # 与 model1 重复
                    display_fields=[{"field": "name"}],
                    inst_display_name="display2",
                    object_model_name_i18n={default_language.frontend_code: "updated_name"},
                )
            )

        assert "CMDB对象ID已存在" in str(exc_info.value)

        # 尝试将 model3 的 bk_cmdb_obj_id 更新为 model1 的值应该成功
        update_object_model(
            ObjectModel(
                object_model_id=model3.object_model_id,
                object_model_code=model3.object_model_code,
                object_model_name="updated_name",
                object_model_group_id=db_child_group.object_model_group_id,
                datasource=DatasourceType.CUSTOM,
                bk_cmdb_obj_id="id1",  # 与 model1 重复
                display_fields=[{"field": "name"}],
                inst_display_name="display2",
                object_model_name_i18n={default_language.frontend_code: "updated_name"},
            )
        )
        model1.delete()
        model2.delete()
        model3.delete()


@pytest.mark.django_db(databases=["default"])
class TestDeleteObjectModel:
    """测试 delete_object_model 函数"""

    def test_delete_object_model_valid_only(self, db_object_model):
        """测试仅校验删除（不实际删除）"""
        delete_object_model(db_object_model.object_model_id, valid_only=True)

        # 验证对象模型仍然存在
        assert ObjectModelORM.objects.filter(object_model_id=db_object_model.object_model_id).exists()

    def test_delete_object_model_success(self, db_object_model):
        """测试成功删除对象模型"""
        model_id = db_object_model.object_model_id
        result = delete_object_model(model_id)

        assert result.object_model_code == "pytest_model"
        # 验证对象模型已删除
        assert not ObjectModelORM.objects.filter(object_model_id=model_id).exists()

    def test_delete_object_model_not_found(self):
        """测试删除不存在的对象模型时抛出异常"""
        with pytest.raises(ObjectModelNotFound):
            delete_object_model(999)

    def test_delete_builtin_object_model(self, db_child_group):
        """测试删除内置对象模型时抛出异常"""
        builtin_model = ObjectModelORM.objects.create(
            object_model_code="builtin_model",
            object_model_name="内置模型",
            object_model_group=db_child_group,
            datasource=DatasourceType.CMDB,
            is_default=True,  # 内置模型
            bk_cmdb_obj_id="builtin_cmdb",
            display_fields=[{"field": "name"}],
            inst_display_name="builtin_display",
        )

        with pytest.raises(ObjectModelOperateError, match="内置对象模型不可删除"):
            delete_object_model(builtin_model.object_model_id)

        # 清理
        builtin_model.delete()

    def test_delete_object_model_with_usage_records(self, db_object_model, db_usage_record):
        """测试删除有使用记录的对象模型时抛出异常"""
        with pytest.raises(ObjectModelValidError, match="该对象与模块.*关联, 无法删除"):
            delete_object_model(db_object_model.object_model_id)


@pytest.mark.django_db(databases=["default"])
class TestValidateDeleteObjectModel:
    """测试 _validate_delete_object_model 函数"""

    def test_validate_delete_object_model_success(self, db_object_model):
        """测试校验删除成功"""
        # 应该不抛出异常
        _validate_delete_object_model(db_object_model)

    def test_validate_delete_builtin_model(self, db_child_group):
        """测试校验删除内置模型"""
        builtin_model = ObjectModelORM.objects.create(
            object_model_code="builtin_model",
            object_model_name="内置模型",
            object_model_group=db_child_group,
            datasource=DatasourceType.CMDB,
            is_default=True,
            bk_cmdb_obj_id="builtin_cmdb",
            display_fields=[{"field": "name"}],
            inst_display_name="builtin_display",
        )

        with pytest.raises(ObjectModelOperateError, match="内置对象模型不可删除"):
            _validate_delete_object_model(builtin_model)

        # 清理
        builtin_model.delete()

    def test_validate_delete_model_with_usage_records(self, db_object_model, db_usage_record):
        """测试校验删除有使用记录的模型"""
        with pytest.raises(ObjectModelValidError):
            _validate_delete_object_model(db_object_model)


@pytest.mark.django_db(databases=["default"])
class TestGetCloudObjectModelCodeList:
    """测试 get_cloud_object_model_code_list 函数"""

    def test_get_cloud_object_model_code_list_success(self, db_child_group):
        """测试成功获取云平台对象模型code列表"""
        # 创建云平台分组
        cloud_group = ObjectModelGroupORM.objects.create(
            object_model_group_code=BuiltinObjectModelGroupCode.CLOUD_PLATFORMS,
            object_model_group_name="云平台",
            is_default=True,
        )

        vm_group = ObjectModelGroupORM.objects.create(
            object_model_group_code=BuiltinObjectModelGroupCode.CLOUD_VIRTUAL_MACHINE,
            object_model_group_name="云平台虚拟机",
            parent_object_model_group=cloud_group,
            is_default=True,
        )

        # 创建云平台对象模型
        cloud_model = ObjectModelORM.objects.create(
            object_model_code="cloud_model",
            object_model_name="云平台模型",
            object_model_group=vm_group,
            datasource=DatasourceType.CMDB,
            is_default=True,
            bk_cmdb_obj_id="cloud_cmdb",
            display_fields=[{"field": "name"}],
            inst_display_name="cloud_display",
        )

        result = get_cloud_object_model_code_list()

        assert "cloud_model" in result

        # 清理
        cloud_model.delete()
        vm_group.delete()
        cloud_group.delete()

    def test_get_cloud_object_model_code_list_group_not_found(self):
        """测试云平台分组不存在时返回空列表"""
        result = get_cloud_object_model_code_list()

        # 如果没有云平台分组，应该返回空列表
        assert isinstance(result, list)

    def test_get_cloud_object_model_code_list_empty_group(self):
        """测试云平台分组存在但没有子分组时返回空列表"""
        cloud_group = ObjectModelGroupORM.objects.create(
            object_model_group_code=BuiltinObjectModelGroupCode.CLOUD_PLATFORMS,
            object_model_group_name="云平台",
            is_default=True,
        )

        result = get_cloud_object_model_code_list()
        assert result == []

        # 清理
        cloud_group.delete()


@pytest.mark.django_db(databases=["default"])
class TestEnrichExtraFields:
    """测试 _enrich_extra_fields 函数"""

    def test_enrich_extra_fields_basic(self, db_object_model):
        """测试补充对象模型额外字段"""
        entity_list = [db_object_model.to_entity()]
        result = _enrich_extra_fields(entity_list)

        assert len(result) == 1
        entity = result[0]

        # 验证额外字段被添加
        assert hasattr(entity, "can_update")
        assert hasattr(entity, "can_delete")
        assert hasattr(entity, "plugin_manage")

        # 非内置模型应该可以更新和删除
        assert entity.can_update is True
        assert entity.can_delete is True
        assert entity.plugin_manage is True

    def test_enrich_extra_fields_builtin_model(self, db_child_group):
        """测试内置模型的额外字段"""
        builtin_model = ObjectModelORM.objects.create(
            object_model_code="builtin_model",
            object_model_name="内置模型",
            object_model_group=db_child_group,
            datasource=DatasourceType.CMDB,
            is_default=True,
            bk_cmdb_obj_id="builtin_cmdb",
            display_fields=[{"field": "name"}],
            inst_display_name="builtin_display",
        )

        entity_list = [builtin_model.to_entity()]
        result = _enrich_extra_fields(entity_list)

        entity = result[0]
        # 内置模型不能删除
        assert entity.can_delete is False

        # 清理
        builtin_model.delete()

    def test_enrich_extra_fields_cloud_model(self):
        """测试云平台模型的额外字段"""
        # 创建云平台分组结构
        cloud_group = ObjectModelGroupORM.objects.create(
            object_model_group_code=BuiltinObjectModelGroupCode.CLOUD_PLATFORMS,
            object_model_group_name="云平台",
            is_default=True,
        )

        vm_group = ObjectModelGroupORM.objects.create(
            object_model_group_code=BuiltinObjectModelGroupCode.CLOUD_VIRTUAL_MACHINE,
            object_model_group_name="云平台虚拟机",
            parent_object_model_group=cloud_group,
            is_default=True,
        )

        # 创建云平台对象模型
        cloud_model = ObjectModelORM.objects.create(
            object_model_code="cloud_model",
            object_model_name="云平台模型",
            object_model_group=vm_group,
            datasource=DatasourceType.CMDB,
            is_default=True,
            bk_cmdb_obj_id="cloud_cmdb",
            display_fields=[{"field": "name"}],
            inst_display_name="cloud_display",
        )

        entity_list = [cloud_model.to_entity()]
        result = _enrich_extra_fields(entity_list)

        entity = result[0]
        # 云平台虚拟机模型应该可以更新
        assert entity.can_update is True

        # 清理
        cloud_model.delete()
        vm_group.delete()
        cloud_group.delete()

    def test_enrich_extra_fields_custom_datasource(self, db_child_group):
        """测试自定义数据源模型的额外字段"""
        custom_model = ObjectModelORM.objects.create(
            object_model_code="custom_model",
            object_model_name="自定义模型",
            object_model_group=db_child_group,
            datasource=DatasourceType.CUSTOM,
            is_default=False,
            bk_cmdb_obj_id="",
            display_fields=[],
            inst_display_name="",
        )

        entity_list = [custom_model.to_entity()]
        result = _enrich_extra_fields(entity_list)

        entity = result[0]
        # 自定义数据源模型应该可以管理插件
        assert entity.plugin_manage is True

        # 清理
        custom_model.delete()

    def test_enrich_extra_fields_empty_list(self):
        """测试空列表的额外字段补充"""
        result = _enrich_extra_fields([])
        assert result == []

    def test_enrich_extra_fields_multiple_models(self, db_object_model, db_child_group):
        """测试多个模型的额外字段补充"""
        # 创建另一个模型
        another_model = ObjectModelORM.objects.create(
            object_model_code="another_model",
            object_model_name="另一个模型",
            object_model_group=db_child_group,
            datasource=DatasourceType.CUSTOM,
            is_default=True,
            bk_cmdb_obj_id="",
            display_fields=[],
            inst_display_name="",
        )

        entity_list = [db_object_model.to_entity(), another_model.to_entity()]
        result = _enrich_extra_fields(entity_list)

        assert len(result) == 2

        # 验证每个模型都有额外字段
        for entity in result:
            assert hasattr(entity, "can_update")
            assert hasattr(entity, "can_delete")
            assert hasattr(entity, "plugin_manage")

        # 清理
        another_model.delete()

    def test_enrich_extra_fields_vm_group_can_update(self, db_child_group):
        """测试云平台虚拟机分组中的对象模型可以更新"""
        # 创建云平台虚拟机分组
        vm_group = ObjectModelGroupORM.objects.create(
            object_model_group_code=(BuiltinObjectModelGroupCode.CLOUD_VIRTUAL_MACHINE),
            object_model_group_name="云平台虚拟机",
            is_default=True,
        )

        # 在虚拟机分组中创建内置的不可更新对象模型
        vm_model = ObjectModelORM.objects.create(
            object_model_code="cw-Cloud_Virtual_Machine_Test",
            object_model_name="测试虚拟机",
            object_model_group=vm_group,
            datasource=DatasourceType.CUSTOM,
            is_default=True,
            bk_cmdb_obj_id="",
            display_fields=[],
            inst_display_name="test_vm",
        )

        entity_list = [vm_model.to_entity()]
        result = _enrich_extra_fields(entity_list)

        # 由于是在虚拟机分组中，即使是内置代码也应该可以更新
        assert result[0].can_update is True

        vm_model.delete()
        vm_group.delete()

    def test_enrich_extra_fields_hardware_model_can_delete(self, db_child_group):
        """测试默认硬件模型不可以删除"""
        from bk_monitor_base.domains.object_model.constants import (
            HardwareObjectModelCode,
        )

        # 创建硬件设备对象模型（内置且默认）
        hardware_model = ObjectModelORM.objects.create(
            object_model_code=HardwareObjectModelCode.FIREWALL,
            object_model_name="防火墙",
            object_model_group=db_child_group,
            datasource=DatasourceType.CUSTOM,
            is_default=True,  # 默认模型
            bk_cmdb_obj_id="",
            display_fields=[],
            inst_display_name="firewall",
        )

        entity_list = [hardware_model.to_entity()]
        result = _enrich_extra_fields(entity_list)

        assert result[0].can_delete is False

        hardware_model.delete()

    def test_enrich_extra_fields_plugin_manage_cmdb_datasource(self, db_child_group):
        """测试 CMDB 数据源的插件管理逻辑"""
        # 创建CMDB数据源的对象模型
        cmdb_model = ObjectModelORM.objects.create(
            object_model_code="test_cmdb_plugin",
            object_model_name="CMDB插件测试",
            object_model_group=db_child_group,
            datasource=DatasourceType.CMDB,
            is_default=False,
            bk_cmdb_obj_id="test_obj",
            display_fields=[{"field": "name"}],
            inst_display_name="test_display",
        )

        entity_list = [cmdb_model.to_entity()]
        result = _enrich_extra_fields(entity_list)

        # CMDB 数据源应该支持插件管理
        assert result[0].plugin_manage is True

        cmdb_model.delete()

    def test_enrich_extra_fields_legacy_datasource_mapping(self, db_child_group):
        """测试 Legacy 数据源的can_update 和 can_delete 逻辑"""
        # 创建 Legacy 数据源的对象模型
        legacy_model = ObjectModelORM.objects.create(
            object_model_code="test_legacy",
            object_model_name="Legacy测试",
            object_model_group=db_child_group,
            datasource=DatasourceType.LEGACY,
            is_default=False,
            bk_cmdb_obj_id="",
            display_fields=[],
            inst_display_name="legacy_display",
        )

        entity_list = [legacy_model.to_entity()]
        result = _enrich_extra_fields(entity_list)

        # 验证 Legacy 数据源被正确处理
        entity = result[0]
        assert entity.datasource == DatasourceType.LEGACY
        assert not entity.can_update
        assert entity.can_delete

        legacy_model.delete()


if __name__ == "__main__":
    pytest.main([__file__])
