"""
测试 MemberFormatter 成员格式化器

测试枚举值翻译、展示名称生成等功能。
"""

from unittest.mock import MagicMock, patch

from bk_monitor_base.domains.dynamic_group.utils.formatter import MemberFormatter


class TestFormatMembers:
    """测试 format_members 方法"""

    @patch.object(MemberFormatter, "_get_cloud_area_translations")
    @patch.object(MemberFormatter, "_get_enum_translations")
    @patch("bk_monitor_base.domains.dynamic_group.utils.formatter.list_object_models")
    def test_format_members_success(self, mock_list_models, mock_get_enum, mock_get_cloud_areas):
        """测试成功格式化成员"""
        # 模拟对象模型
        mock_model = MagicMock()
        mock_model.display_fields = [
            {"bk_property_id": "bk_host_innerip"},
            {"bk_property_id": "status"},
            {"bk_property_id": "bk_cloud_id"},
        ]
        mock_model.bk_cmdb_obj_id = "host"
        mock_model.inst_display_name = "${bk_host_innerip}"
        mock_list_models.return_value = [mock_model]

        # 模拟枚举翻译
        mock_get_enum.return_value = {"status": {"1": "运行中", "2": "已停止"}}
        mock_get_cloud_areas.return_value = {"0": "--[0]"}

        members = [
            {"bk_host_innerip": "10.0.0.1", "status": "1", "bk_cloud_id": 0},
            {"bk_host_innerip": "10.0.0.2", "status": "2", "bk_cloud_id": 0},
        ]

        result = MemberFormatter.format_members(members, "cw-Host", "default")

        assert result[0]["status"] == "运行中"
        assert result[1]["status"] == "已停止"
        assert result[0]["bk_cloud_id"] == "--[0]"
        assert result[0]["bk_inst_display_name"] == "10.0.0.1"
        assert result[1]["bk_inst_display_name"] == "10.0.0.2"

    @patch("bk_monitor_base.domains.dynamic_group.utils.formatter.list_object_models")
    def test_format_members_empty_list(self, mock_list_models):
        """测试空成员列表"""
        result = MemberFormatter.format_members([], "cw-Host", "default")

        assert result == []
        mock_list_models.assert_not_called()

    @patch("bk_monitor_base.domains.dynamic_group.utils.formatter.list_object_models")
    def test_format_members_model_not_found(self, mock_list_models):
        """测试获取对象模型失败时跳过格式化"""
        mock_list_models.side_effect = Exception("Model not found")

        members = [{"bk_host_innerip": "10.0.0.1"}]

        result = MemberFormatter.format_members(members, "nonexistent", "default")

        assert result == members  # 保持原样


class TestFormatDisplayName:
    """测试 _format_display_name 方法"""

    def test_format_with_expression(self):
        """测试根据表达式生成展示名称"""
        inst_list = [
            {"bk_host_innerip": "10.0.0.1", "bk_host_name": "host1"},
            {"bk_host_innerip": "10.0.0.2", "bk_host_name": "host2"},
        ]

        result = MemberFormatter._format_display_name(
            inst_list=inst_list,
            expression="${bk_host_innerip}-${bk_host_name}",
            display_fields=["bk_host_innerip", "bk_host_name"],
            enum_translations={},
            cloud_area_translations={},
        )

        assert result[0]["bk_inst_display_name"] == "10.0.0.1-host1"
        assert result[1]["bk_inst_display_name"] == "10.0.0.2-host2"

    def test_format_with_enum_translation(self):
        """测试枚举值翻译"""
        inst_list = [{"status": "1"}, {"status": "2"}]

        result = MemberFormatter._format_display_name(
            inst_list=inst_list,
            expression="${status}",
            display_fields=["status"],
            enum_translations={"status": {"1": "运行中", "2": "已停止"}},
            cloud_area_translations={},
        )

        assert result[0]["status"] == "运行中"
        assert result[1]["status"] == "已停止"

    def test_format_with_missing_field(self):
        """测试缺少字段时使用空字符串"""
        inst_list = [{"bk_host_innerip": "10.0.0.1"}]

        result = MemberFormatter._format_display_name(
            inst_list=inst_list,
            expression="${bk_host_innerip}-${missing_field}",
            display_fields=["bk_host_innerip"],
            enum_translations={},
            cloud_area_translations={},
        )

        assert result[0]["bk_inst_display_name"] == "10.0.0.1-"

    def test_format_with_none_value(self):
        """测试字段值为 None 时使用空字符串替换，最终结果为默认值 '- -'"""
        inst_list = [{"bk_host_innerip": None}]

        result = MemberFormatter._format_display_name(
            inst_list=inst_list,
            expression="${bk_host_innerip}",
            display_fields=["bk_host_innerip"],
            enum_translations={},
            cloud_area_translations={},
        )

        # 当 expression 替换后为空字符串时，使用默认值 "- -"
        assert result[0]["bk_inst_display_name"] == "- -"

    def test_format_empty_expression_uses_default(self):
        """测试空表达式时使用默认值"""
        inst_list = [{"bk_host_innerip": "10.0.0.1"}]

        result = MemberFormatter._format_display_name(
            inst_list=inst_list,
            expression="",
            display_fields=["bk_host_innerip"],
            enum_translations={},
            cloud_area_translations={},
        )

        assert result[0]["bk_inst_display_name"] == "- -"

    def test_format_field_not_in_display_fields(self):
        """测试字段不在 display_fields 中时使用空字符串替换，最终结果为默认值 '- -'"""
        inst_list = [{"bk_host_innerip": "10.0.0.1"}]

        result = MemberFormatter._format_display_name(
            inst_list=inst_list,
            expression="${bk_host_innerip}",
            display_fields=[],  # bk_host_innerip 不在 display_fields 中
            enum_translations={},
            cloud_area_translations={},
        )

        # 当字段不在 display_fields 中时，替换为空字符串，最终使用默认值 "- -"
        assert result[0]["bk_inst_display_name"] == "- -"

    def test_format_cloud_area_value_keeps_existing_display_value(self):
        """测试已翻译的云区域展示值不被重复包装。"""
        inst_list = [{"bk_cloud_id": "Default Area[0]"}]

        result = MemberFormatter._format_display_name(
            inst_list=inst_list,
            expression="${bk_cloud_id}",
            display_fields=["bk_cloud_id"],
            enum_translations={},
            cloud_area_translations={"0": "Default Area[0]"},
        )

        assert result[0]["bk_cloud_id"] == "Default Area[0]"
        assert result[0]["bk_inst_display_name"] == "Default Area[0]"


class TestGetEnumTranslations:
    """测试 _get_enum_translations 方法"""

    @patch("bk_monitor_base.domains.dynamic_group.utils.formatter.cmdb")
    def test_get_enum_translations_success(self, mock_cmdb):
        """测试成功获取枚举翻译"""
        mock_cmdb.search_object_attribute.return_value = [
            {
                "bk_property_id": "status",
                "bk_property_type": "enum",
                "option": [
                    {"id": "1", "name": "运行中"},
                    {"id": "2", "name": "已停止"},
                ],
            },
            {
                "bk_property_id": "bk_host_name",
                "bk_property_type": "singlechar",  # 非枚举类型，应该被跳过
                "option": None,
            },
        ]

        result = MemberFormatter._get_enum_translations("host", "default")

        assert "status" in result
        assert result["status"]["1"] == "运行中"
        assert result["status"]["2"] == "已停止"
        assert "bk_host_name" not in result

    @patch("bk_monitor_base.domains.dynamic_group.utils.formatter.cmdb")
    def test_get_enum_translations_api_error(self, mock_cmdb):
        """测试 API 调用失败时返回空字典"""
        mock_cmdb.search_object_attribute.side_effect = Exception("API error")

        result = MemberFormatter._get_enum_translations("host", "default")

        assert result == {}


class TestGetCloudAreaTranslations:
    @patch("bk_monitor_base.domains.dynamic_group.utils.formatter.cmdb")
    def test_get_cloud_area_translations_success(self, mock_cmdb):
        """测试云区域映射生成，缺失名称时使用默认占位。"""
        MemberFormatter._CLOUD_AREA_CACHE.clear()
        mock_cmdb.search_cloud_area.return_value = [
            {"bk_cloud_id": 0, "bk_cloud_name": "--"},
            {"bk_cloud_id": 2, "bk_cloud_name": "华北"},
            {"bk_cloud_id": 3, "bk_cloud_name": ""},
        ]

        result = MemberFormatter._get_cloud_area_translations("default")

        assert result == {"0": "--[0]", "2": "华北[2]", "3": "--[3]"}

    @patch("bk_monitor_base.domains.dynamic_group.utils.formatter.cmdb")
    def test_get_cloud_area_translations_api_error(self, mock_cmdb):
        MemberFormatter._CLOUD_AREA_CACHE.clear()
        mock_cmdb.search_cloud_area.side_effect = Exception("API error")

        result = MemberFormatter._get_cloud_area_translations("default")

        assert result == {}


class TestFormatCloudAreaValue:
    def test_format_cloud_area_value_uses_mapping(self):
        assert MemberFormatter._format_cloud_area_value(0, {"0": "Default Area[0]"}) == "Default Area[0]"

    def test_format_cloud_area_value_keeps_preformatted_value(self):
        assert (
            MemberFormatter._format_cloud_area_value(
                "Default Area[0]",
                {"0": "Default Area[0]"},
            )
            == "Default Area[0]"
        )

    def test_format_cloud_area_value_falls_back_for_unknown_value(self):
        assert MemberFormatter._format_cloud_area_value("999", {}) == "--[999]"

    @patch("bk_monitor_base.domains.dynamic_group.utils.formatter.cmdb")
    def test_get_enum_translations_empty_option(self, mock_cmdb):
        """测试 option 为空时跳过"""
        mock_cmdb.search_object_attribute.return_value = [
            {
                "bk_property_id": "status",
                "bk_property_type": "enum",
                "option": [],
            },
        ]

        result = MemberFormatter._get_enum_translations("host", "default")

        assert result == {}

    @patch("bk_monitor_base.domains.dynamic_group.utils.formatter.cmdb")
    def test_get_enum_translations_invalid_option_format(self, mock_cmdb):
        """测试无效 option 格式时跳过"""
        mock_cmdb.search_object_attribute.return_value = [
            {
                "bk_property_id": "status",
                "bk_property_type": "enum",
                "option": "invalid",  # 应该是 list
            },
        ]

        result = MemberFormatter._get_enum_translations("host", "default")

        assert result == {}

    @patch("bk_monitor_base.domains.dynamic_group.utils.formatter.cmdb")
    def test_get_enum_translations_missing_id_or_name(self, mock_cmdb):
        """测试 option 中缺少 id 或 name 时跳过"""
        mock_cmdb.search_object_attribute.return_value = [
            {
                "bk_property_id": "status",
                "bk_property_type": "enum",
                "option": [
                    {"id": "1"},  # 缺少 name
                    {"name": "已停止"},  # 缺少 id
                    {"id": "3", "name": "维护中"},  # 正常
                ],
            },
        ]

        result = MemberFormatter._get_enum_translations("host", "default")

        assert "status" in result
        assert result["status"] == {"3": "维护中"}

    @patch("bk_monitor_base.domains.dynamic_group.utils.formatter.cmdb")
    def test_get_enum_translations_missing_property_id(self, mock_cmdb):
        """测试缺少 bk_property_id 时跳过"""
        mock_cmdb.search_object_attribute.return_value = [
            {
                "bk_property_type": "enum",
                "option": [{"id": "1", "name": "运行中"}],
            },
        ]

        result = MemberFormatter._get_enum_translations("host", "default")

        assert result == {}
