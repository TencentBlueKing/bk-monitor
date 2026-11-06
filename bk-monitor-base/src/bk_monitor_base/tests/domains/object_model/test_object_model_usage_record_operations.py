import pytest
from django.utils import timezone

from bk_monitor_base.domains.object_model.define import DatasourceType, ObjectModelUsageRecord
from bk_monitor_base.domains.object_model.models import ObjectModelGroupORM, ObjectModelORM, ObjectModelUsageRecordORM
from bk_monitor_base.domains.object_model.operations.object_model_usage_record import (
    create_object_model_usage_records,
    delete_object_model_usage_records,
    list_object_model_usage_records,
    update_object_model_usage_records,
)


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
def usage_record_entity(db_object_model):
    """创建使用记录实体的fixture"""
    return ObjectModelUsageRecord(
        object_model_id=db_object_model.object_model_id,
        app_id="new_app",
        app_name="新应用",
        module_id="new_module",
        module_name="新模块",
        inst_id="new_inst",
        inst_name="新实例",
    )


@pytest.mark.django_db(databases=["default"])
class TestListObjectModelUsageRecords:
    """测试 list_object_model_usage_records 函数"""

    def test_list_usage_records_basic(self, db_usage_record):
        """测试基本的使用记录列表查询"""
        result = list_object_model_usage_records()

        assert len(result) >= 1
        found_record = next((r for r in result if r.app_id == "test_app"), None)
        assert found_record is not None
        assert found_record.app_name == "测试应用"
        assert found_record.module_name == "测试模块"
        assert found_record.inst_name == "测试实例"

    @pytest.mark.parametrize(
        "filter_params,expected_count",
        [
            ({"ids": []}, 0),  # 空id列表
            ({"object_model_ids": []}, 0),  # 空模型id列表
            ({"app_ids": ["test_app"]}, 1),  # 按app_id过滤
            ({"app_ids": ["non_existent"]}, 0),  # 不存在的app_id
            ({"app_name_contains": "测试"}, 1),  # app名称模糊查询
            ({"app_name_contains": "不存在"}, 0),  # 不存在的app名称
            ({"module_ids": ["test_module"]}, 1),  # 按module_id过滤
            ({"module_name_contains": "测试"}, 1),  # module名称模糊查询
            ({"inst_ids": ["test_inst"]}, 1),  # 按inst_id过滤
            ({"inst_name_contains": "测试"}, 1),  # inst名称模糊查询
        ],
    )
    def test_list_usage_records_with_filters(self, db_usage_record, filter_params, expected_count):
        """参数化测试带过滤条件的使用记录查询"""
        # 动态设置有效的id值
        if "ids" in filter_params and filter_params["ids"] == []:
            filter_params["ids"] = [db_usage_record.id]
            expected_count = 1
        elif "object_model_ids" in filter_params and filter_params["object_model_ids"] == []:
            filter_params["object_model_ids"] = [db_usage_record.object_model.object_model_id]
            expected_count = 1

        result = list_object_model_usage_records(**filter_params)
        assert len(result) == expected_count

        if expected_count > 0:
            found_record = result[0]
            assert found_record.app_id == "test_app"

    def test_list_usage_records_with_pagination(self, db_usage_record):
        """测试分页查询"""
        # 测试limit
        result = list_object_model_usage_records(limit=1)
        assert len(result) <= 1

        # 测试offset
        all_records = list_object_model_usage_records()
        if len(all_records) > 1:
            result_with_offset = list_object_model_usage_records(offset=1)
            assert len(result_with_offset) == len(all_records) - 1

        # 测试limit + offset
        result_limited = list_object_model_usage_records(limit=1, offset=0)
        assert len(result_limited) <= 1


@pytest.mark.django_db(databases=["default"])
class TestCreateObjectModelUsageRecords:
    """测试 create_object_model_usage_records 函数"""

    def test_create_usage_records_success(self, usage_record_entity):
        """测试成功创建使用记录"""
        records = [usage_record_entity]
        result = create_object_model_usage_records(records)

        assert len(result) == 1
        assert result[0].app_id == "new_app"
        assert result[0].app_name == "新应用"

        # 清理
        ObjectModelUsageRecordORM.objects.filter(app_id="new_app").delete()

    def test_create_usage_records_empty_list(self):
        """测试创建空记录列表"""
        result = create_object_model_usage_records([])
        assert result == []

    def test_create_usage_records_invalid_object_model(self, usage_record_entity):
        """测试创建记录时对象模型不存在"""
        usage_record_entity.object_model_id = 999  # 不存在的模型ID
        records = [usage_record_entity]
        result = create_object_model_usage_records(records)

        # 应该跳过无效记录，返回空列表
        assert result == []

    def test_create_usage_records_batch(self, db_object_model):
        """测试批量创建使用记录"""
        records = []
        for i in range(3):
            record = ObjectModelUsageRecord(
                object_model_id=db_object_model.object_model_id,
                app_id=f"batch_app_{i}",
                app_name=f"批量应用{i}",
                module_id=f"batch_module_{i}",
                module_name=f"批量模块{i}",
                inst_id=f"batch_inst_{i}",
                inst_name=f"批量实例{i}",
            )
            records.append(record)

        result = create_object_model_usage_records(records)
        assert len(result) == 3

        # 清理
        ObjectModelUsageRecordORM.objects.filter(app_id__startswith="batch_app_").delete()


@pytest.mark.django_db(databases=["default"])
class TestUpdateObjectModelUsageRecords:
    """测试 update_object_model_usage_records 函数"""

    def test_update_usage_records_success(self, db_usage_record):
        """测试成功更新使用记录"""
        entity = db_usage_record.to_entity()
        entity.app_name = "更新后的应用名称"
        entity.module_name = "更新后的模块名称"
        entity.inst_name = "更新后的实例名称"
        entity.updated_by = "update_user"
        entity.updated_at = timezone.now()

        update_object_model_usage_records([entity])

        # 验证更新
        updated_record = ObjectModelUsageRecordORM.objects.get(id=db_usage_record.id)
        assert updated_record.app_name == "更新后的应用名称"
        assert updated_record.module_name == "更新后的模块名称"
        assert updated_record.inst_name == "更新后的实例名称"

    def test_update_usage_records_no_id(self, usage_record_entity):
        """测试更新没有ID的记录（应该跳过）"""
        usage_record_entity.id = None
        usage_record_entity.app_name = "应该被跳过"

        # 不应该抛出异常，应该静默跳过
        update_object_model_usage_records([usage_record_entity])

    def test_update_usage_records_empty_list(self):
        """测试更新空记录列表"""
        # 不应该抛出异常
        update_object_model_usage_records([])

    def test_update_usage_records_batch(self, db_object_model):
        """测试批量更新使用记录"""
        # 先创建多个记录
        records = []
        for i in range(2):
            record = ObjectModelUsageRecordORM.objects.create(
                object_model=db_object_model,
                app_id=f"update_app_{i}",
                app_name=f"更新应用{i}",
                module_id=f"update_module_{i}",
                module_name=f"更新模块{i}",
                inst_id=f"update_inst_{i}",
                inst_name=f"更新实例{i}",
            )
            records.append(record)

        # 准备更新数据
        update_entities = []
        for i, record in enumerate(records):
            entity = record.to_entity()
            entity.app_name = f"批量更新应用{i}"
            entity.updated_by = "batch_user"
            entity.updated_at = timezone.now()
            update_entities.append(entity)

        update_object_model_usage_records(update_entities)

        # 验证更新
        for i, record in enumerate(records):
            updated_record = ObjectModelUsageRecordORM.objects.get(id=record.id)
            assert updated_record.app_name == f"批量更新应用{i}"

        # 清理
        for record in records:
            record.delete()


@pytest.mark.django_db(databases=["default"])
class TestDeleteObjectModelUsageRecords:
    """测试 delete_object_model_usage_records 函数"""

    def test_delete_usage_records_success(self, db_usage_record):
        """测试成功删除使用记录"""
        entity = db_usage_record.to_entity()
        record_id = db_usage_record.id

        delete_object_model_usage_records([entity])

        # 验证删除
        assert not ObjectModelUsageRecordORM.objects.filter(id=record_id).exists()

    def test_delete_usage_records_empty_list(self):
        """测试删除空记录列表"""
        # 不应该抛出异常
        delete_object_model_usage_records([])

    def test_delete_usage_records_batch(self, db_object_model):
        """测试批量删除使用记录"""
        # 先创建多个记录
        records = []
        entities = []
        for i in range(3):
            record = ObjectModelUsageRecordORM.objects.create(
                object_model=db_object_model,
                app_id=f"delete_app_{i}",
                app_name=f"删除应用{i}",
                module_id=f"delete_module_{i}",
                module_name=f"删除模块{i}",
                inst_id=f"delete_inst_{i}",
                inst_name=f"删除实例{i}",
            )
            records.append(record)
            entities.append(record.to_entity())

        delete_object_model_usage_records(entities)

        # 验证删除
        for record in records:
            assert not ObjectModelUsageRecordORM.objects.filter(id=record.id).exists()

    def test_delete_usage_records_non_existent(self, usage_record_entity):
        """测试删除不存在的记录（应该不抛出异常）"""
        # 不应该抛出异常
        delete_object_model_usage_records([usage_record_entity])

    def test_delete_usage_records_large_batch(self, db_object_model):
        """测试大批量删除（验证批处理逻辑）"""
        # 创建超过batch_size的记录数量
        records = []
        entities = []
        for i in range(150):  # 超过batch_size=100
            record = ObjectModelUsageRecordORM.objects.create(
                object_model=db_object_model,
                app_id=f"large_delete_app_{i}",
                app_name=f"大批量删除应用{i}",
                module_id=f"large_delete_module_{i}",
                module_name=f"大批量删除模块{i}",
                inst_id=f"large_delete_inst_{i}",
                inst_name=f"大批量删除实例{i}",
            )
            records.append(record)
            entities.append(record.to_entity())

        delete_object_model_usage_records(entities)

        # 验证删除
        for record in records:
            assert not ObjectModelUsageRecordORM.objects.filter(id=record.id).exists()
