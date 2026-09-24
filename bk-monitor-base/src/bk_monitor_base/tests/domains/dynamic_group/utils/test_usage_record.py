"""
测试 UsageRecordOperator 使用记录操作器

测试动态分组对象模型使用记录的创建和删除功能。
"""

from unittest.mock import MagicMock, patch

from bk_monitor_base.domains.dynamic_group.define import DynamicGroup
from bk_monitor_base.domains.dynamic_group.utils.usage_record import UsageRecordOperator


class TestUsageRecordOperatorCreate:
    """测试 UsageRecordOperator.create 方法"""

    @patch("bk_monitor_base.domains.dynamic_group.utils.usage_record.create_object_model_usage_records")
    @patch("bk_monitor_base.domains.dynamic_group.utils.usage_record.list_object_models")
    def test_create_single_group(self, mock_list_models, mock_create_records):
        """测试创建单个动态分组的使用记录"""
        # 模拟对象模型
        mock_model = MagicMock()
        mock_model.object_model_code = "cw-Host"
        mock_model.object_model_id = 1
        mock_list_models.return_value = [mock_model]

        group = DynamicGroup(
            dynamic_group_id=1,
            dynamic_group_name="测试分组",
            condition_list=[],
            object_model_code="cw-Host",
            space_code="bkcc__2",
            bk_tenant_id="system",
            created_by="admin",
        )

        UsageRecordOperator.create(group)

        mock_create_records.assert_called_once()
        records = mock_create_records.call_args[0][0]
        assert len(records) == 1
        assert records[0].object_model_id == 1
        assert records[0].inst_id == "1"
        assert records[0].inst_name == "测试分组"

    @patch("bk_monitor_base.domains.dynamic_group.utils.usage_record.create_object_model_usage_records")
    @patch("bk_monitor_base.domains.dynamic_group.utils.usage_record.list_object_models")
    def test_create_multiple_groups(self, mock_list_models, mock_create_records):
        """测试创建多个动态分组的使用记录"""
        mock_model = MagicMock()
        mock_model.object_model_code = "cw-Host"
        mock_model.object_model_id = 1
        mock_list_models.return_value = [mock_model]

        groups = [
            DynamicGroup(
                dynamic_group_id=1,
                dynamic_group_name="分组1",
                condition_list=[],
                object_model_code="cw-Host",
                space_code="bkcc__2",
                bk_tenant_id="system",
            ),
            DynamicGroup(
                dynamic_group_id=2,
                dynamic_group_name="分组2",
                condition_list=[],
                object_model_code="cw-Host",
                space_code="bkcc__2",
                bk_tenant_id="system",
            ),
        ]

        UsageRecordOperator.create(groups)

        mock_create_records.assert_called_once()
        records = mock_create_records.call_args[0][0]
        assert len(records) == 2

    @patch("bk_monitor_base.domains.dynamic_group.utils.usage_record.create_object_model_usage_records")
    @patch("bk_monitor_base.domains.dynamic_group.utils.usage_record.list_object_models")
    def test_create_empty_list(self, mock_list_models, mock_create_records):
        """测试空列表不创建记录"""
        UsageRecordOperator.create([])

        mock_list_models.assert_not_called()
        mock_create_records.assert_not_called()

    @patch("bk_monitor_base.domains.dynamic_group.utils.usage_record.create_object_model_usage_records")
    @patch("bk_monitor_base.domains.dynamic_group.utils.usage_record.list_object_models")
    def test_create_model_not_found(self, mock_list_models, mock_create_records):
        """测试对象模型不存在时跳过"""
        mock_list_models.return_value = []  # 未找到对象模型

        group = DynamicGroup(
            dynamic_group_id=1,
            dynamic_group_name="测试分组",
            condition_list=[],
            object_model_code="nonexistent",
            space_code="bkcc__2",
            bk_tenant_id="system",
        )

        UsageRecordOperator.create(group)

        # 没有记录时不调用创建
        mock_create_records.assert_not_called()

    @patch("bk_monitor_base.domains.dynamic_group.utils.usage_record.create_object_model_usage_records")
    @patch("bk_monitor_base.domains.dynamic_group.utils.usage_record.list_object_models")
    def test_create_api_error_not_raise(self, mock_list_models, mock_create_records):
        """测试 API 错误不抛出异常"""
        mock_model = MagicMock()
        mock_model.object_model_code = "cw-Host"
        mock_model.object_model_id = 1
        mock_list_models.return_value = [mock_model]
        mock_create_records.side_effect = Exception("API error")

        group = DynamicGroup(
            dynamic_group_id=1,
            dynamic_group_name="测试分组",
            condition_list=[],
            object_model_code="cw-Host",
            space_code="bkcc__2",
            bk_tenant_id="system",
        )

        # 不应抛出异常
        UsageRecordOperator.create(group)


class TestUsageRecordOperatorDelete:
    """测试 UsageRecordOperator.delete 方法"""

    @patch("bk_monitor_base.domains.dynamic_group.utils.usage_record.delete_object_model_usage_records")
    @patch("bk_monitor_base.domains.dynamic_group.utils.usage_record.list_object_models")
    def test_delete_single_group(self, mock_list_models, mock_delete_records):
        """测试删除单个动态分组的使用记录"""
        mock_model = MagicMock()
        mock_model.object_model_code = "cw-Host"
        mock_model.object_model_id = 1
        mock_list_models.return_value = [mock_model]

        group = DynamicGroup(
            dynamic_group_id=1,
            dynamic_group_name="测试分组",
            condition_list=[],
            object_model_code="cw-Host",
            space_code="bkcc__2",
            bk_tenant_id="system",
        )

        UsageRecordOperator.delete(group)

        mock_delete_records.assert_called_once()
        records = mock_delete_records.call_args[0][0]
        assert len(records) == 1
        assert records[0].inst_id == "1"

    @patch("bk_monitor_base.domains.dynamic_group.utils.usage_record.delete_object_model_usage_records")
    @patch("bk_monitor_base.domains.dynamic_group.utils.usage_record.list_object_models")
    def test_delete_multiple_groups(self, mock_list_models, mock_delete_records):
        """测试删除多个动态分组的使用记录"""
        mock_model = MagicMock()
        mock_model.object_model_code = "cw-Host"
        mock_model.object_model_id = 1
        mock_list_models.return_value = [mock_model]

        groups = [
            DynamicGroup(
                dynamic_group_id=1,
                dynamic_group_name="分组1",
                condition_list=[],
                object_model_code="cw-Host",
                space_code="bkcc__2",
                bk_tenant_id="system",
            ),
            DynamicGroup(
                dynamic_group_id=2,
                dynamic_group_name="分组2",
                condition_list=[],
                object_model_code="cw-Host",
                space_code="bkcc__2",
                bk_tenant_id="system",
            ),
        ]

        UsageRecordOperator.delete(groups)

        mock_delete_records.assert_called_once()
        records = mock_delete_records.call_args[0][0]
        assert len(records) == 2

    @patch("bk_monitor_base.domains.dynamic_group.utils.usage_record.delete_object_model_usage_records")
    @patch("bk_monitor_base.domains.dynamic_group.utils.usage_record.list_object_models")
    def test_delete_empty_list(self, mock_list_models, mock_delete_records):
        """测试空列表不删除记录"""
        UsageRecordOperator.delete([])

        mock_list_models.assert_not_called()
        mock_delete_records.assert_not_called()

    @patch("bk_monitor_base.domains.dynamic_group.utils.usage_record.delete_object_model_usage_records")
    @patch("bk_monitor_base.domains.dynamic_group.utils.usage_record.list_object_models")
    def test_delete_api_error_not_raise(self, mock_list_models, mock_delete_records):
        """测试 API 错误不抛出异常"""
        mock_model = MagicMock()
        mock_model.object_model_code = "cw-Host"
        mock_model.object_model_id = 1
        mock_list_models.return_value = [mock_model]
        mock_delete_records.side_effect = Exception("API error")

        group = DynamicGroup(
            dynamic_group_id=1,
            dynamic_group_name="测试分组",
            condition_list=[],
            object_model_code="cw-Host",
            space_code="bkcc__2",
            bk_tenant_id="system",
        )

        # 不应抛出异常
        UsageRecordOperator.delete(group)


class TestUsageRecordOperatorOperate:
    """测试 UsageRecordOperator._operate 方法"""

    @patch("bk_monitor_base.domains.dynamic_group.utils.usage_record.create_object_model_usage_records")
    @patch("bk_monitor_base.domains.dynamic_group.utils.usage_record.list_object_models")
    def test_operate_unknown_operation(self, mock_list_models, mock_create_records):
        """测试未知操作类型"""
        mock_model = MagicMock()
        mock_model.object_model_code = "cw-Host"
        mock_model.object_model_id = 1
        mock_list_models.return_value = [mock_model]

        group = DynamicGroup(
            dynamic_group_id=1,
            dynamic_group_name="测试分组",
            condition_list=[],
            object_model_code="cw-Host",
            space_code="bkcc__2",
            bk_tenant_id="system",
        )

        # 使用未知操作类型
        UsageRecordOperator._operate("unknown", group)

        # 不应调用任何 API
        mock_create_records.assert_not_called()


class TestUsageRecordOperatorBuildRecords:
    """测试 UsageRecordOperator._build_records 方法"""

    @patch("bk_monitor_base.domains.dynamic_group.utils.usage_record.list_object_models")
    def test_build_records_success(self, mock_list_models):
        """测试成功构建使用记录"""
        mock_model = MagicMock()
        mock_model.object_model_code = "cw-Host"
        mock_model.object_model_id = 1
        mock_list_models.return_value = [mock_model]

        groups = [
            DynamicGroup(
                dynamic_group_id=1,
                dynamic_group_name="分组1",
                condition_list=[],
                object_model_code="cw-Host",
                space_code="bkcc__2",
                bk_tenant_id="system",
                created_by="admin",
            ),
        ]

        records = UsageRecordOperator._build_records(groups)

        assert len(records) == 1
        assert records[0].object_model_id == 1
        assert records[0].inst_id == "1"
        assert records[0].inst_name == "分组1"
        assert records[0].created_by == "admin"

    def test_build_records_empty_list(self):
        """测试空列表返回空记录"""
        records = UsageRecordOperator._build_records([])

        assert records == []

    @patch("bk_monitor_base.domains.dynamic_group.utils.usage_record.list_object_models")
    def test_build_records_multiple_object_models(self, mock_list_models):
        """测试多个对象模型"""
        mock_model1 = MagicMock()
        mock_model1.object_model_code = "cw-Host"
        mock_model1.object_model_id = 1
        mock_model2 = MagicMock()
        mock_model2.object_model_code = "cw-Switch"
        mock_model2.object_model_id = 2
        mock_list_models.return_value = [mock_model1, mock_model2]

        groups = [
            DynamicGroup(
                dynamic_group_id=1,
                dynamic_group_name="主机分组",
                condition_list=[],
                object_model_code="cw-Host",
                space_code="bkcc__2",
                bk_tenant_id="system",
            ),
            DynamicGroup(
                dynamic_group_id=2,
                dynamic_group_name="交换机分组",
                condition_list=[],
                object_model_code="cw-Switch",
                space_code="bkcc__2",
                bk_tenant_id="system",
            ),
        ]

        records = UsageRecordOperator._build_records(groups)

        assert len(records) == 2
        # 验证不同对象模型 ID
        model_ids = [r.object_model_id for r in records]
        assert 1 in model_ids
        assert 2 in model_ids

    @patch("bk_monitor_base.domains.dynamic_group.utils.usage_record.list_object_models")
    def test_build_records_skip_missing_model(self, mock_list_models):
        """测试跳过找不到的对象模型"""
        mock_model = MagicMock()
        mock_model.object_model_code = "cw-Host"
        mock_model.object_model_id = 1
        mock_list_models.return_value = [mock_model]

        groups = [
            DynamicGroup(
                dynamic_group_id=1,
                dynamic_group_name="主机分组",
                condition_list=[],
                object_model_code="cw-Host",
                space_code="bkcc__2",
                bk_tenant_id="system",
            ),
            DynamicGroup(
                dynamic_group_id=2,
                dynamic_group_name="未知分组",
                condition_list=[],
                object_model_code="nonexistent",  # 不存在的模型
                space_code="bkcc__2",
                bk_tenant_id="system",
            ),
        ]

        records = UsageRecordOperator._build_records(groups)

        # 只有一个有效记录
        assert len(records) == 1
        assert records[0].inst_id == "1"

    @patch("bk_monitor_base.domains.dynamic_group.utils.usage_record.list_object_models")
    def test_build_records_with_empty_created_by(self, mock_list_models):
        """测试 created_by 为空字符串时保持空字符串"""
        mock_model = MagicMock()
        mock_model.object_model_code = "cw-Host"
        mock_model.object_model_id = 1
        mock_list_models.return_value = [mock_model]

        groups = [
            DynamicGroup(
                dynamic_group_id=1,
                dynamic_group_name="分组1",
                condition_list=[],
                object_model_code="cw-Host",
                space_code="bkcc__2",
                bk_tenant_id="system",
                created_by="",
            ),
        ]

        records = UsageRecordOperator._build_records(groups)

        assert len(records) == 1
        assert records[0].created_by == ""


class TestUsageRecordOperatorConstants:
    """测试 UsageRecordOperator 常量"""

    def test_operation_constants(self):
        """测试操作类型常量"""
        assert UsageRecordOperator.CREATE == "create"
        assert UsageRecordOperator.DELETE == "delete"
