"""
测试 space.cache 模块
"""

import pytest
from pytest_mock import MockerFixture

from bk_monitor_base.domains.space.cache import (
    bk_biz_id_to_bk_tenant_id,
    bk_biz_id_to_space_uid,
    check_bk_biz_id_and_bk_tenant_id,
    space_uid_to_bk_biz_id,
    space_uid_to_bk_tenant_id,
)
from bk_monitor_base.domains.space.define import Space, SpaceStatus, SpaceTypeEnum
from bk_monitor_base.domains.space.models import SpaceModel
from bk_monitor_base.infras.constant import DEFAULT_TENANT_ID, SPACE_UID_HYPHEN

# 为整个模块启用数据库访问
pytestmark = pytest.mark.django_db(databases=["default"])


@pytest.fixture(scope="module")
def space_test_data(django_db_blocker):
    """统一初始化测试数据，整个文件只初始化一次"""
    # 使用 django_db_blocker 在 module-scoped fixture 中启用数据库访问
    with django_db_blocker.unblock():
        # 创建测试用的 SpaceModel 实例（用于测试负数 bk_biz_id 的场景）
        space_model = SpaceModel.objects.create(
            space_type_id="bcs",
            space_id="test_cache_space_1",
            bk_tenant_id="test_tenant_cache",
            space_name="测试缓存空间",
            status=SpaceStatus.NORMAL.value,
            time_zone="Asia/Shanghai",
            language="zh-cn",
            creator="test_user",
            updater="test_user",
        )

        test_data = {
            "space_model": space_model,
            "negative_bk_biz_id": -space_model.pk,
            "space_uid": space_model.space_uid,
            "bk_tenant_id": space_model.bk_tenant_id,
            "space_type_id": space_model.space_type_id,
            "space_id": space_model.space_id,
        }

    yield test_data

    # 清理数据
    with django_db_blocker.unblock():
        space_model.delete()

    # 清理所有 lru_cache 缓存，确保测试独立性
    bk_biz_id_to_space_uid.cache_clear()
    bk_biz_id_to_bk_tenant_id.cache_clear()
    space_uid_to_bk_biz_id.cache_clear()
    space_uid_to_bk_tenant_id.cache_clear()


class TestBkBizIdToSpaceUid:
    """测试 bk_biz_id_to_space_uid 函数"""

    def test_bk_biz_id_positive(self):
        """测试正数 bk_biz_id（BKCC类型），应返回 bkcc__{bk_biz_id} 格式"""
        # Arrange
        bk_biz_id = 100

        # Act
        result = bk_biz_id_to_space_uid(bk_biz_id)

        # Assert
        expected = f"{SpaceTypeEnum.BKCC.value}{SPACE_UID_HYPHEN}{bk_biz_id}"
        assert result == expected

    def test_bk_biz_id_negative(self, space_test_data):
        """测试负数 bk_biz_id（非BKCC类型），需要从数据库查询并返回 space_uid"""
        # Arrange
        negative_bk_biz_id = space_test_data["negative_bk_biz_id"]
        expected_space_uid = space_test_data["space_uid"]

        # Act
        result = bk_biz_id_to_space_uid(negative_bk_biz_id)

        # Assert
        assert result == expected_space_uid

    def test_bk_biz_id_positive_str(self):
        """测试字符串类型的正数 bk_biz_id，适配外层传参为字符串的场景"""
        # Arrange
        bk_biz_id = "100"

        # Act
        result = bk_biz_id_to_space_uid(bk_biz_id)

        # Assert
        expected = f"{SpaceTypeEnum.BKCC.value}{SPACE_UID_HYPHEN}100"
        assert result == expected

    def test_bk_biz_id_negative_str(self, space_test_data):
        """测试字符串类型的负数 bk_biz_id，适配外层传参为字符串的场景"""
        # Arrange
        negative_bk_biz_id = str(space_test_data["negative_bk_biz_id"])
        expected_space_uid = space_test_data["space_uid"]

        # Act
        result = bk_biz_id_to_space_uid(negative_bk_biz_id)

        # Assert
        assert result == expected_space_uid

    def test_bk_biz_id_cached(self):
        """测试缓存机制，多次调用相同参数应使用缓存"""
        # Arrange
        bk_biz_id = 200

        # Act - 第一次调用
        result1 = bk_biz_id_to_space_uid(bk_biz_id)
        cache_info_before = bk_biz_id_to_space_uid.cache_info()

        # Act - 第二次调用相同参数
        result2 = bk_biz_id_to_space_uid(bk_biz_id)
        cache_info_after = bk_biz_id_to_space_uid.cache_info()

        # Assert
        assert result1 == result2
        assert cache_info_after.hits > cache_info_before.hits


class TestBkBizIdToBkTenantId:
    """测试 bk_biz_id_to_bk_tenant_id 函数"""

    def test_multi_tenancy_disabled(self, mocker: MockerFixture):
        """测试多租户关闭时，应返回 DEFAULT_TENANT_ID"""
        # Arrange
        mock_config = mocker.MagicMock()
        mock_config.blueking.enable_multi_tenancy = False
        mocker.patch("bk_monitor_base.domains.space.cache.get_config", return_value=mock_config)

        # 清理缓存，确保使用新的配置
        bk_biz_id_to_bk_tenant_id.cache_clear()

        bk_biz_id = 300

        # Act
        result = bk_biz_id_to_bk_tenant_id(bk_biz_id)

        # Assert
        assert result == DEFAULT_TENANT_ID

    def test_multi_tenancy_enabled(self, mocker: MockerFixture, space_test_data):
        """测试多租户开启时，应调用 get_space 获取租户ID"""
        # Arrange
        mock_config = mocker.MagicMock()
        mock_config.blueking.enable_multi_tenancy = True
        mocker.patch("bk_monitor_base.domains.space.cache.get_config", return_value=mock_config)

        # Mock get_space 返回 Space 对象
        expected_tenant_id = space_test_data["bk_tenant_id"]
        mock_space = Space(
            bk_biz_id=space_test_data["negative_bk_biz_id"],
            uid=space_test_data["space_uid"],
            bk_tenant_id=expected_tenant_id,
            type=SpaceTypeEnum.BCS,
            name="测试空间",
            status=SpaceStatus.NORMAL,
            creator="test_user",
            updater="test_user",
        )
        mocker.patch("bk_monitor_base.domains.space.cache.get_space", return_value=mock_space)

        # 清理缓存，确保使用新的配置
        bk_biz_id_to_bk_tenant_id.cache_clear()

        bk_biz_id = space_test_data["negative_bk_biz_id"]

        # Act
        result = bk_biz_id_to_bk_tenant_id(bk_biz_id)

        # Assert
        assert result == expected_tenant_id

    def test_multi_tenancy_disabled_str_bk_biz_id(self, mocker: MockerFixture):
        """测试字符串类型的 bk_biz_id，适配外层传参为字符串的场景"""
        # Arrange
        mock_config = mocker.MagicMock()
        mock_config.blueking.enable_multi_tenancy = False
        mocker.patch("bk_monitor_base.domains.space.cache.get_config", return_value=mock_config)

        bk_biz_id_to_bk_tenant_id.cache_clear()

        # Act — 传入字符串
        result = bk_biz_id_to_bk_tenant_id("300")

        # Assert
        assert result == DEFAULT_TENANT_ID

    def test_multi_tenancy_enabled_str_bk_biz_id(self, mocker: MockerFixture, space_test_data):
        """测试多租户开启时使用字符串类型的 bk_biz_id"""
        # Arrange
        mock_config = mocker.MagicMock()
        mock_config.blueking.enable_multi_tenancy = True
        mocker.patch("bk_monitor_base.domains.space.cache.get_config", return_value=mock_config)

        expected_tenant_id = space_test_data["bk_tenant_id"]
        mock_space = Space(
            bk_biz_id=space_test_data["negative_bk_biz_id"],
            uid=space_test_data["space_uid"],
            bk_tenant_id=expected_tenant_id,
            type=SpaceTypeEnum.BCS,
            name="测试空间",
            status=SpaceStatus.NORMAL,
            creator="test_user",
            updater="test_user",
        )
        mocker.patch("bk_monitor_base.domains.space.cache.get_space", return_value=mock_space)

        bk_biz_id_to_bk_tenant_id.cache_clear()

        # Act — 传入字符串形式的负数 bk_biz_id
        result = bk_biz_id_to_bk_tenant_id(str(space_test_data["negative_bk_biz_id"]))

        # Assert
        assert result == expected_tenant_id

    def test_cached_result(self, mocker: MockerFixture):
        """测试缓存机制"""
        # Arrange
        mock_config = mocker.MagicMock()
        mock_config.blueking.enable_multi_tenancy = False
        mocker.patch("bk_monitor_base.domains.space.cache.get_config", return_value=mock_config)

        # 清理缓存
        bk_biz_id_to_bk_tenant_id.cache_clear()

        bk_biz_id = 400

        # Act - 第一次调用
        result1 = bk_biz_id_to_bk_tenant_id(bk_biz_id)
        cache_info_before = bk_biz_id_to_bk_tenant_id.cache_info()

        # Act - 第二次调用相同参数
        result2 = bk_biz_id_to_bk_tenant_id(bk_biz_id)
        cache_info_after = bk_biz_id_to_bk_tenant_id.cache_info()

        # Assert
        assert result1 == result2
        assert cache_info_after.hits > cache_info_before.hits


class TestSpaceUidToBkBizId:
    """测试 space_uid_to_bk_biz_id 函数"""

    def test_bkcc_space_uid(self):
        """测试 BKCC 类型的 space_uid，应正确解析出 bk_biz_id"""
        # Arrange
        bk_biz_id = 500
        space_uid = f"{SpaceTypeEnum.BKCC.value}{SPACE_UID_HYPHEN}{bk_biz_id}"

        # Act
        result = space_uid_to_bk_biz_id(space_uid)

        # Assert
        assert result == bk_biz_id

    def test_other_space_uid(self, space_test_data):
        """测试其他类型的 space_uid"""
        # Arrange
        # space_uid 格式为 "bcs__test_cache_space_1"，解析后应该得到 "test_cache_space_1"
        # 但函数会尝试转换为 int，这里我们需要使用一个有效的数字 space_id
        space_model = SpaceModel.objects.create(
            space_type_id="bkci",
            space_id="12345",
            bk_tenant_id="test_tenant",
            space_name="测试空间",
            status=SpaceStatus.NORMAL.value,
            time_zone="Asia/Shanghai",
            language="zh-cn",
            creator="test_user",
            updater="test_user",
        )

        try:
            space_uid = space_model.space_uid

            # Act
            result = space_uid_to_bk_biz_id(space_uid)

            # Assert - 应该解析出 space_id 的整数值
            assert result == 12345
        finally:
            space_model.delete()


class TestSpaceUidToBkTenantId:
    """测试 space_uid_to_bk_tenant_id 函数"""

    def test_multi_tenancy_disabled(self, mocker: MockerFixture):
        """测试多租户关闭时，应返回 DEFAULT_TENANT_ID"""
        # Arrange
        mock_config = mocker.MagicMock()
        mock_config.blueking.enable_multi_tenancy = False
        mocker.patch("bk_monitor_base.domains.space.cache.get_config", return_value=mock_config)

        # 清理缓存，确保使用新的配置
        space_uid_to_bk_tenant_id.cache_clear()

        space_uid = f"{SpaceTypeEnum.BKCC.value}{SPACE_UID_HYPHEN}600"

        # Act
        result = space_uid_to_bk_tenant_id(space_uid)

        # Assert
        assert result == DEFAULT_TENANT_ID

    def test_multi_tenancy_enabled(self, mocker: MockerFixture, space_test_data):
        """测试多租户开启时，应调用 get_space 获取租户ID"""
        # Arrange
        mock_config = mocker.MagicMock()
        mock_config.blueking.enable_multi_tenancy = True
        mocker.patch("bk_monitor_base.domains.space.cache.get_config", return_value=mock_config)

        # Mock get_space 返回 Space 对象
        expected_tenant_id = space_test_data["bk_tenant_id"]
        space_uid = space_test_data["space_uid"]
        mock_space = Space(
            bk_biz_id=space_test_data["negative_bk_biz_id"],
            uid=space_uid,
            bk_tenant_id=expected_tenant_id,
            type=SpaceTypeEnum.BCS,
            name="测试空间",
            status=SpaceStatus.NORMAL,
            creator="test_user",
            updater="test_user",
        )
        mocker.patch("bk_monitor_base.domains.space.cache.get_space", return_value=mock_space)

        # 清理缓存，确保使用新的配置
        space_uid_to_bk_tenant_id.cache_clear()

        # Act
        result = space_uid_to_bk_tenant_id(space_uid)

        # Assert
        assert result == expected_tenant_id

    def test_cached_result(self, mocker: MockerFixture):
        """测试缓存机制"""
        # Arrange
        mock_config = mocker.MagicMock()
        mock_config.blueking.enable_multi_tenancy = False
        mocker.patch("bk_monitor_base.domains.space.cache.get_config", return_value=mock_config)

        # 清理缓存
        space_uid_to_bk_tenant_id.cache_clear()

        space_uid = f"{SpaceTypeEnum.BKCC.value}{SPACE_UID_HYPHEN}700"

        # Act - 第一次调用
        result1 = space_uid_to_bk_tenant_id(space_uid)
        cache_info_before = space_uid_to_bk_tenant_id.cache_info()

        # Act - 第二次调用相同参数
        result2 = space_uid_to_bk_tenant_id(space_uid)
        cache_info_after = space_uid_to_bk_tenant_id.cache_info()

        # Assert
        assert result1 == result2
        assert cache_info_after.hits > cache_info_before.hits


class TestCheckBkBizIdAndBkTenantId:
    """测试 check_bk_biz_id_and_bk_tenant_id 装饰器"""

    def test_decorator_matching(self, mocker: MockerFixture):
        """测试装饰器在参数匹配时正常执行函数"""
        # Arrange
        mock_config = mocker.MagicMock()
        mock_config.blueking.enable_multi_tenancy = True
        mocker.patch("bk_monitor_base.domains.space.cache.get_config", return_value=mock_config)

        # Mock get_space 和 bk_biz_id_to_bk_tenant_id
        expected_tenant_id = "test_tenant_1"
        bk_biz_id = 800
        mocker.patch(
            "bk_monitor_base.domains.space.cache.bk_biz_id_to_bk_tenant_id",
            return_value=expected_tenant_id,
        )

        # 清理缓存
        bk_biz_id_to_bk_tenant_id.cache_clear()

        @check_bk_biz_id_and_bk_tenant_id
        def test_function(bk_tenant_id: str, bk_biz_id: int, other_param: str) -> str:
            """测试函数"""
            return f"success: {other_param}"

        # Act
        result = test_function(bk_tenant_id=expected_tenant_id, bk_biz_id=bk_biz_id, other_param="test")

        # Assert
        assert result == "success: test"

    def test_decorator_mismatching(self, mocker: MockerFixture):
        """测试装饰器在参数不匹配时抛出 ValueError"""
        # Arrange
        mock_config = mocker.MagicMock()
        mock_config.blueking.enable_multi_tenancy = True
        mocker.patch("bk_monitor_base.domains.space.cache.get_config", return_value=mock_config)

        # Mock bk_biz_id_to_bk_tenant_id 返回不同的租户ID
        expected_tenant_id = "expected_tenant"
        wrong_tenant_id = "wrong_tenant"
        bk_biz_id = 900
        mocker.patch(
            "bk_monitor_base.domains.space.cache.bk_biz_id_to_bk_tenant_id",
            return_value=expected_tenant_id,
        )

        # 清理缓存
        bk_biz_id_to_bk_tenant_id.cache_clear()

        @check_bk_biz_id_and_bk_tenant_id
        def test_function(bk_tenant_id: str, bk_biz_id: int) -> str:
            """测试函数"""
            return "should not reach here"

        # Act & Assert
        with pytest.raises(ValueError, match="业务ID和租户ID不匹配"):
            test_function(bk_tenant_id=wrong_tenant_id, bk_biz_id=bk_biz_id)

    def test_decorator_with_none(self, mocker: MockerFixture):
        """测试装饰器在参数为 None 时不进行验证"""

        # Arrange
        @check_bk_biz_id_and_bk_tenant_id
        def test_function(bk_tenant_id: str | None, bk_biz_id: int | None, other_param: str) -> str:
            """测试函数"""
            return f"success: {other_param}"

        # Act - 两个参数都为 None
        result1 = test_function(bk_tenant_id=None, bk_biz_id=None, other_param="test1")

        # Act - 一个参数为 None
        result2 = test_function(bk_tenant_id=None, bk_biz_id=1000, other_param="test2")

        # Assert
        assert result1 == "success: test1"
        assert result2 == "success: test2"

    def test_decorator_missing_params(self):
        """测试装饰器在缺少参数时不进行验证"""

        # Arrange
        @check_bk_biz_id_and_bk_tenant_id
        def test_function(other_param: str) -> str:
            """测试函数，不包含 bk_tenant_id 和 bk_biz_id 参数"""
            return f"success: {other_param}"

        # Act
        result = test_function(other_param="test")

        # Assert
        assert result == "success: test"

    def test_decorator_positional_args(self, mocker: MockerFixture):
        """测试装饰器支持位置参数"""
        # Arrange
        mock_config = mocker.MagicMock()
        mock_config.blueking.enable_multi_tenancy = True
        mocker.patch("bk_monitor_base.domains.space.cache.get_config", return_value=mock_config)

        expected_tenant_id = "test_tenant_2"
        bk_biz_id = 1100
        mocker.patch(
            "bk_monitor_base.domains.space.cache.bk_biz_id_to_bk_tenant_id",
            return_value=expected_tenant_id,
        )

        # 清理缓存
        bk_biz_id_to_bk_tenant_id.cache_clear()

        @check_bk_biz_id_and_bk_tenant_id
        def test_function(bk_tenant_id: str, bk_biz_id: int, other_param: str) -> str:
            """测试函数"""
            return f"success: {other_param}"

        # Act - 使用位置参数
        result = test_function(expected_tenant_id, bk_biz_id, "test")

        # Assert
        assert result == "success: test"

    def test_decorator_keyword_args(self, mocker: MockerFixture):
        """测试装饰器支持关键字参数"""
        # Arrange
        mock_config = mocker.MagicMock()
        mock_config.blueking.enable_multi_tenancy = True
        mocker.patch("bk_monitor_base.domains.space.cache.get_config", return_value=mock_config)

        expected_tenant_id = "test_tenant_3"
        bk_biz_id = 1200
        mocker.patch(
            "bk_monitor_base.domains.space.cache.bk_biz_id_to_bk_tenant_id",
            return_value=expected_tenant_id,
        )

        # 清理缓存
        bk_biz_id_to_bk_tenant_id.cache_clear()

        @check_bk_biz_id_and_bk_tenant_id
        def test_function(bk_tenant_id: str, bk_biz_id: int, other_param: str) -> str:
            """测试函数"""
            return f"success: {other_param}"

        # Act - 使用关键字参数
        result = test_function(other_param="test", bk_biz_id=bk_biz_id, bk_tenant_id=expected_tenant_id)

        # Assert
        assert result == "success: test"

    def test_decorator_mixed_args(self, mocker: MockerFixture):
        """测试装饰器支持混合参数"""
        # Arrange
        mock_config = mocker.MagicMock()
        mock_config.blueking.enable_multi_tenancy = True
        mocker.patch("bk_monitor_base.domains.space.cache.get_config", return_value=mock_config)

        expected_tenant_id = "test_tenant_4"
        bk_biz_id = 1300
        mocker.patch(
            "bk_monitor_base.domains.space.cache.bk_biz_id_to_bk_tenant_id",
            return_value=expected_tenant_id,
        )

        # 清理缓存
        bk_biz_id_to_bk_tenant_id.cache_clear()

        @check_bk_biz_id_and_bk_tenant_id
        def test_function(bk_tenant_id: str, bk_biz_id: int, other_param: str) -> str:
            """测试函数"""
            return f"success: {other_param}"

        # Act - 使用混合参数（位置参数 + 关键字参数）
        result = test_function(expected_tenant_id, bk_biz_id=bk_biz_id, other_param="test")

        # Assert
        assert result == "success: test"
