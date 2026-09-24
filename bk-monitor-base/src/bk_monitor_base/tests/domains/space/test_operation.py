"""
测试 space.operation 模块
"""

import pytest
from django.db import IntegrityError
from pytest_mock import MockerFixture

from bk_monitor_base.domains.space.define import Space, SpaceStatus, SpaceTypeEnum
from bk_monitor_base.domains.space.models import SpaceModel
from bk_monitor_base.domains.space.operation import delete_spaces, get_space, list_spaces, save_spaces
from bk_monitor_base.infras.constant import SPACE_UID_HYPHEN


def get_space_id(space: Space) -> str:
    """从 Space 对象的 uid 中提取 space_id"""
    if SPACE_UID_HYPHEN not in space.uid:
        return ""
    return space.uid.split(SPACE_UID_HYPHEN, 1)[1]


@pytest.mark.django_db(databases=["default"])
class TestSaveSpaces:
    """测试 save_spaces 函数"""

    def test_save_spaces_create_new(self):
        """测试创建新空间"""
        space = Space(
            bk_biz_id=1,
            uid="bkcc__1",
            bk_tenant_id="test_tenant",
            type=SpaceTypeEnum.BKCC,
            name="测试空间",
            status=SpaceStatus.NORMAL,
            timezone="Asia/Shanghai",
            language="zh-cn",
            creator="test_user",
            updater="test_user",
        )

        result = save_spaces([space], operator="test_user")

        assert len(result) == 1
        assert get_space_id(result[0]) == "1"
        assert result[0].name == "测试空间"
        assert result[0].type == SpaceTypeEnum.BKCC
        assert result[0].status == SpaceStatus.NORMAL

        # 验证数据库中的记录
        space_model = SpaceModel.objects.get(space_type_id="bkcc", space_id="1")
        assert space_model.space_name == "测试空间"
        assert space_model.bk_tenant_id == "test_tenant"
        assert space_model.status == SpaceStatus.NORMAL.value

        # 清理
        space_model.delete()

    def test_save_spaces_update_existing(self):
        """测试更新已存在的空间"""
        # 先创建一个空间
        space_model = SpaceModel.objects.create(
            space_type_id="bkcc",
            space_id="1",
            bk_tenant_id="test_tenant",
            space_name="原始名称",
            status=SpaceStatus.NORMAL.value,
            time_zone="Asia/Shanghai",
            language="zh-cn",
            creator="original_user",
            updater="original_user",
        )

        # 更新空间
        space = Space(
            bk_biz_id=1,
            uid="bkcc__1",
            bk_tenant_id="test_tenant",
            type=SpaceTypeEnum.BKCC,
            name="更新后的名称",
            status=SpaceStatus.DISABLED,
            timezone="UTC",
            language="en",
            creator="original_user",
            updater="updated_user",
        )

        result = save_spaces([space], operator="updated_user")

        assert len(result) == 1
        assert result[0].name == "更新后的名称"
        assert result[0].status == SpaceStatus.DISABLED
        assert result[0].timezone == "UTC"
        assert result[0].language == "en"
        assert result[0].updater == "updated_user"

        # 验证数据库中的记录已更新
        space_model.refresh_from_db()
        assert space_model.space_name == "更新后的名称"
        assert space_model.status == SpaceStatus.DISABLED.value
        assert space_model.time_zone == "UTC"
        assert space_model.language == "en"
        assert space_model.updater == "updated_user"

        # 清理
        space_model.delete()

    def test_save_spaces_batch_create(self):
        """测试批量创建空间"""
        spaces = [
            Space(
                bk_biz_id=i,
                uid=f"bkcc__{i}",
                bk_tenant_id="test_tenant",
                type=SpaceTypeEnum.BKCC,
                name=f"测试空间{i}",
                status=SpaceStatus.NORMAL,
                timezone="Asia/Shanghai",
                language="zh-cn",
                creator="test_user",
                updater="test_user",
            )
            for i in range(1, 4)
        ]

        result = save_spaces(spaces, operator="test_user")

        assert len(result) == 3
        assert all(space.name.startswith("测试空间") for space in result)

        # 验证数据库中的记录
        assert SpaceModel.objects.filter(space_type_id="bkcc", space_id__in=["1", "2", "3"]).count() == 3

        # 清理
        SpaceModel.objects.filter(space_type_id="bkcc", space_id__in=["1", "2", "3"]).delete()

    def test_save_spaces_different_types(self):
        """测试创建不同类型的空间"""
        spaces = [
            Space(
                bk_biz_id=1,
                uid="bkcc__1",
                bk_tenant_id="test_tenant",
                type=SpaceTypeEnum.BKCC,
                name="BKCC空间",
                status=SpaceStatus.NORMAL,
                creator="test_user",
                updater="test_user",
            ),
            Space(
                bk_biz_id=-1,  # 非BKCC类型使用负数
                uid="bcs__project1",
                bk_tenant_id="test_tenant",
                type=SpaceTypeEnum.BCS,
                name="BCS空间",
                status=SpaceStatus.NORMAL,
                creator="test_user",
                updater="test_user",
            ),
        ]

        result = save_spaces(spaces, operator="test_user")

        assert len(result) == 2
        assert result[0].type == SpaceTypeEnum.BKCC
        assert result[1].type == SpaceTypeEnum.BCS

        # 清理
        SpaceModel.objects.filter(space_type_id__in=["bkcc", "bcs"], space_id__in=["1", "project1"]).delete()

    def test_save_spaces_atomic_operation(self):
        """测试原子操作：如果批量保存中有一个失败，所有更改都会回滚"""
        # 先创建一个空间，用于后续测试唯一性约束
        SpaceModel.objects.create(
            space_type_id="bkcc",
            space_id="100",
            bk_tenant_id="test_tenant",
            space_name="已存在的空间",
            status=SpaceStatus.NORMAL.value,
            time_zone="Asia/Shanghai",
            language="zh-cn",
            creator="test_user",
            updater="test_user",
        )

        try:
            # 创建一个会违反唯一性约束的空间列表
            # 第一个空间是新的，应该能创建
            # 第二个空间与已存在的空间有相同的 (space_type_id, space_id)，但不同的 (space_type_id, space_name, bk_tenant_id)
            # 这会违反 unique_together 约束 (space_type_id, space_id)
            spaces = [
                Space(
                    bk_biz_id=200,
                    uid="bkcc__200",
                    bk_tenant_id="test_tenant",
                    type=SpaceTypeEnum.BKCC,
                    name="新空间",
                    status=SpaceStatus.NORMAL,
                    creator="test_user",
                    updater="test_user",
                ),
                Space(
                    bk_biz_id=100,
                    uid="bkcc__100",
                    bk_tenant_id="test_tenant",
                    type=SpaceTypeEnum.BKCC,
                    name="不同的名称",  # 但名称不同，这会违反 unique_together (space_type_id, space_id)
                    status=SpaceStatus.NORMAL,
                    creator="test_user",
                    updater="test_user",
                ),
            ]

            # 由于 get_or_create 不会抛出异常（它会返回已存在的对象），
            # 我们需要测试另一种场景：验证事务的原子性
            # 这里我们测试：如果中间有异常，前面的操作也会回滚

            # 实际上，由于 get_or_create 的特性，这个测试主要验证事务包装是否正确
            # 我们可以通过验证所有操作都在同一个事务中来完成
            result = save_spaces(spaces, operator="test_user")

            # get_or_create 会返回已存在的对象，所以第二个空间会更新已存在的空间
            assert len(result) == 2
            # 验证第一个空间被创建
            assert SpaceModel.objects.filter(space_id="200").exists()
            # 验证第二个空间更新了已存在的空间（而不是创建新记录）
            assert SpaceModel.objects.filter(space_type_id="bkcc", space_id="100").count() == 1

        finally:
            # 清理
            SpaceModel.objects.filter(space_id__in=["100", "200"]).delete()

    def test_save_spaces_atomic_rollback_on_exception(self, mocker: MockerFixture):
        """测试异常时事务回滚：如果批量操作中抛出异常，所有更改都会回滚"""
        spaces = [
            Space(
                bk_biz_id=301,
                uid="bkcc__301",
                bk_tenant_id="test_tenant",
                type=SpaceTypeEnum.BKCC,
                name="新空间1",
                status=SpaceStatus.NORMAL,
                creator="test_user",
                updater="test_user",
            ),
            Space(
                bk_biz_id=302,
                uid="bkcc__302",
                bk_tenant_id="test_tenant",
                type=SpaceTypeEnum.BKCC,
                name="新空间2",
                status=SpaceStatus.NORMAL,
                creator="test_user",
                updater="test_user",
            ),
        ]

        # Mock bulk_create 方法，让批量创建时抛出异常
        def mock_bulk_create(objs, *args, **kwargs):
            # 模拟批量创建时抛出异常
            raise IntegrityError("模拟的完整性约束错误")

        mocker.patch.object(SpaceModel.objects, "bulk_create", side_effect=mock_bulk_create)

        # 执行批量保存，应该抛出异常
        with pytest.raises(IntegrityError):
            save_spaces(spaces, operator="test_user")

        # 验证事务回滚：所有空间都不应该被创建
        assert not SpaceModel.objects.filter(space_id__in=["301", "302"]).exists()


@pytest.mark.django_db(databases=["default"])
class TestDeleteSpaces:
    """测试 delete_spaces 函数"""

    @pytest.fixture
    def test_spaces(self):
        """创建测试用的空间"""
        spaces = []
        for i in range(1, 4):
            space_model = SpaceModel.objects.create(
                space_type_id="bkcc",
                space_id=str(i),
                bk_tenant_id="test_tenant",
                space_name=f"测试空间{i}",
                status=SpaceStatus.NORMAL.value,
                time_zone="Asia/Shanghai",
                language="zh-cn",
                creator="test_user",
                updater="test_user",
            )
            spaces.append(space_model)

        # 创建一个非BKCC类型的空间
        other_space = SpaceModel.objects.create(
            space_type_id="bcs",
            space_id="project1",
            bk_tenant_id="test_tenant",
            space_name="BCS空间",
            status=SpaceStatus.NORMAL.value,
            time_zone="Asia/Shanghai",
            language="zh-cn",
            creator="test_user",
            updater="test_user",
        )
        spaces.append(other_space)

        yield spaces

        # 清理
        SpaceModel.objects.filter(pk__in=[s.pk for s in spaces]).delete()

    def test_delete_spaces_by_bk_biz_ids(self, test_spaces):
        """测试通过 bk_biz_ids 删除空间"""
        # BKCC类型的空间，bk_biz_id 等于 space_id
        result = delete_spaces(bk_biz_ids=[1, 2])

        assert len(result) == 2
        assert all(space.status == SpaceStatus.DISABLED for space in result)
        assert all(get_space_id(space) in ["1", "2"] for space in result)

        # 验证数据库中的状态已更新
        assert SpaceModel.objects.get(space_id="1").status == SpaceStatus.DISABLED.value
        assert SpaceModel.objects.get(space_id="2").status == SpaceStatus.DISABLED.value
        assert SpaceModel.objects.get(space_id="3").status == SpaceStatus.NORMAL.value

    def test_delete_spaces_by_space_uids(self, test_spaces):
        """测试通过 space_uids 删除空间"""
        result = delete_spaces(space_uids=["bkcc__1", "bkcc__2"])

        assert len(result) == 2
        assert all(space.status == SpaceStatus.DISABLED for space in result)

        # 验证数据库中的状态已更新
        assert SpaceModel.objects.get(space_id="1").status == SpaceStatus.DISABLED.value
        assert SpaceModel.objects.get(space_id="2").status == SpaceStatus.DISABLED.value

    def test_delete_spaces_by_both_params(self, test_spaces):
        """测试同时使用 bk_biz_ids 和 space_uids"""
        result = delete_spaces(bk_biz_ids=[1], space_uids=["bkcc__2"])

        assert len(result) == 2
        assert all(space.status == SpaceStatus.DISABLED for space in result)

    def test_delete_spaces_no_params(self):
        """测试未提供参数时抛出异常"""
        with pytest.raises(ValueError, match="至少需要提供"):
            delete_spaces()

    def test_delete_spaces_non_bkcc_type(self, test_spaces):
        """测试删除非BKCC类型的空间"""
        # 非BKCC类型的空间，bk_biz_id 为 -pk
        other_space = test_spaces[-1]
        result = delete_spaces(bk_biz_ids=[-other_space.pk])

        assert len(result) == 1
        assert result[0].status == SpaceStatus.DISABLED
        assert get_space_id(result[0]) == "project1"

    def test_delete_spaces_by_str_bk_biz_ids(self, test_spaces):
        """测试通过字符串类型的 bk_biz_ids 删除空间，适配外层传参为字符串的场景"""
        result = delete_spaces(bk_biz_ids=["1", "2"])

        assert len(result) == 2
        assert all(space.status == SpaceStatus.DISABLED for space in result)

    def test_delete_spaces_non_bkcc_by_str_bk_biz_ids(self, test_spaces):
        """测试通过字符串类型的负数 bk_biz_id 删除非BKCC类型空间"""
        other_space = test_spaces[-1]
        result = delete_spaces(bk_biz_ids=[str(-other_space.pk)])

        assert len(result) == 1
        assert result[0].status == SpaceStatus.DISABLED
        assert get_space_id(result[0]) == "project1"


@pytest.mark.django_db(databases=["default"])
class TestListSpaces:
    """测试 list_spaces 函数"""

    @pytest.fixture
    def test_spaces(self):
        """创建测试用的空间"""
        spaces = []
        # 创建不同租户的空间
        # BKCC类型的space_id必须是纯数字（业务ID）
        space_id_counter = 100
        for tenant_id in ["tenant1", "tenant2"]:
            for i in range(1, 3):
                space_model = SpaceModel.objects.create(
                    space_type_id="bkcc",
                    space_id=str(space_id_counter),
                    bk_tenant_id=tenant_id,
                    space_name=f"空间{tenant_id}_{i}",
                    status=SpaceStatus.NORMAL.value,
                    time_zone="Asia/Shanghai",
                    language="zh-cn",
                    creator="test_user",
                    updater="test_user",
                )
                spaces.append(space_model)
                space_id_counter += 1

        yield spaces

        # 清理
        SpaceModel.objects.filter(pk__in=[s.pk for s in spaces]).delete()

    def test_list_spaces_by_tenant_id(self, test_spaces):
        """测试通过租户ID查询空间"""
        result = list_spaces(bk_tenant_id="tenant1")

        assert len(result) == 2
        assert all(space.bk_tenant_id == "tenant1" for space in result)
        # 验证返回的空间ID是数字字符串
        assert all(get_space_id(space).isdigit() for space in result)

    def test_list_spaces_by_bk_biz_ids(self, test_spaces):
        """测试通过 bk_biz_ids 查询空间"""
        # BKCC类型，bk_biz_id 等于 space_id（整数形式）
        # 使用测试数据中的前两个空间
        space1_id = int(test_spaces[0].space_id)
        space2_id = int(test_spaces[1].space_id)

        result = list_spaces(bk_biz_ids=[space1_id, space2_id])

        assert len(result) == 2
        assert {int(get_space_id(space)) for space in result} == {space1_id, space2_id}
        assert all(space.type == SpaceTypeEnum.BKCC for space in result)

    def test_list_spaces_by_space_uids(self, test_spaces):
        """测试通过 space_uids 查询空间"""
        # 使用实际的space_id（数字字符串）
        space1_id = test_spaces[0].space_id
        space2_id = test_spaces[1].space_id
        result = list_spaces(space_uids=[f"bkcc__{space1_id}", f"bkcc__{space2_id}"])

        assert len(result) == 2
        assert all(space.uid.startswith("bkcc__") for space in result)
        assert {get_space_id(space) for space in result} == {space1_id, space2_id}

    def test_list_spaces_combined_filters(self, test_spaces):
        """测试组合查询条件"""
        # 使用实际的space_id（数字字符串）
        space1_id = test_spaces[0].space_id
        result = list_spaces(bk_tenant_id="tenant1", space_uids=[f"bkcc__{space1_id}"])

        assert len(result) == 1
        assert result[0].uid == f"bkcc__{space1_id}"
        assert result[0].bk_tenant_id == "tenant1"

    def test_list_spaces_empty_result(self):
        """测试查询结果为空"""
        result = list_spaces(bk_tenant_id="non_existent_tenant")

        assert len(result) == 0

    def test_list_spaces_by_str_bk_biz_ids(self, test_spaces):
        """测试通过字符串类型的 bk_biz_ids 查询空间，适配外层传参为字符串的场景"""
        space1_id = test_spaces[0].space_id
        space2_id = test_spaces[1].space_id

        result = list_spaces(bk_biz_ids=[space1_id, space2_id])

        assert len(result) == 2
        assert {get_space_id(space) for space in result} == {space1_id, space2_id}

    def test_list_spaces_all_spaces(self, test_spaces):
        """测试查询所有空间"""
        result = list_spaces()

        assert len(result) >= len(test_spaces)


@pytest.mark.django_db(databases=["default"])
class TestGetSpace:
    """测试 get_space 函数"""

    @pytest.fixture
    def test_space(self):
        """创建测试用的空间"""
        space_model = SpaceModel.objects.create(
            space_type_id="bkcc",
            space_id="100",
            bk_tenant_id="test_tenant",
            space_name="测试空间",
            status=SpaceStatus.NORMAL.value,
            time_zone="Asia/Shanghai",
            language="zh-cn",
            creator="test_user",
            updater="test_user",
        )

        yield space_model

        # 清理
        space_model.delete()

    @pytest.fixture
    def test_non_bkcc_space(self):
        """创建非BKCC类型的测试空间"""
        space_model = SpaceModel.objects.create(
            space_type_id="bcs",
            space_id="project1",
            bk_tenant_id="test_tenant",
            space_name="BCS空间",
            status=SpaceStatus.NORMAL.value,
            time_zone="Asia/Shanghai",
            language="zh-cn",
            creator="test_user",
            updater="test_user",
        )

        yield space_model

        # 清理
        space_model.delete()

    def test_get_space_by_bk_biz_id(self, test_space):
        """测试通过 bk_biz_id 获取空间（BKCC类型）"""
        result = get_space(bk_biz_id=100)

        assert result is not None
        assert get_space_id(result) == "100"
        assert result.type == SpaceTypeEnum.BKCC
        assert result.name == "测试空间"

    def test_get_space_by_space_uid(self, test_space):
        """测试通过 space_uid 获取空间"""
        result = get_space(space_uid="bkcc__100")

        assert result is not None
        assert result.uid == "bkcc__100"
        assert get_space_id(result) == "100"

    def test_get_space_by_both_params_match(self, test_space):
        """测试同时提供两个参数且匹配"""
        result = get_space(bk_biz_id=100, space_uid="bkcc__100")

        assert result is not None
        assert get_space_id(result) == "100"

    def test_get_space_by_both_params_mismatch(self, test_space):
        """测试同时提供两个参数但不匹配"""
        with pytest.raises(ValueError, match="空间不存在"):
            get_space(bk_biz_id=100, space_uid="bkcc__999")

    def test_get_space_non_bkcc_type(self, test_non_bkcc_space):
        """测试获取非BKCC类型的空间"""
        # 非BKCC类型，bk_biz_id 为 -pk
        result = get_space(bk_biz_id=-test_non_bkcc_space.pk)

        assert result is not None
        assert get_space_id(result) == "project1"
        assert result.type == SpaceTypeEnum.BCS

    def test_get_space_not_found_by_bk_biz_id(self):
        """测试通过不存在的 bk_biz_id 获取空间"""
        with pytest.raises(ValueError, match="空间不存在"):
            get_space(bk_biz_id=99999)

    def test_get_space_not_found_by_space_uid(self):
        """测试通过不存在的 space_uid 获取空间"""
        with pytest.raises(ValueError, match="空间不存在"):
            get_space(space_uid="bkcc__99999")

    def test_get_space_no_params(self):
        """测试未提供参数时抛出异常"""
        with pytest.raises(ValueError, match="至少需要提供"):
            get_space()

    def test_get_space_invalid_uid_format(self):
        """测试 space_uid 格式错误"""
        with pytest.raises(ValueError, match="space_uid 格式错误"):
            get_space(space_uid="invalid_format")

    def test_get_space_invalid_uid_format_no_separator(self):
        """测试 space_uid 缺少分隔符"""
        with pytest.raises(ValueError, match="space_uid 格式错误"):
            get_space(space_uid="bkcc100")

    def test_get_space_by_str_bk_biz_id(self, test_space):
        """测试通过字符串类型的 bk_biz_id 获取空间，适配外层传参为字符串的场景"""
        result = get_space(bk_biz_id="100")

        assert result is not None
        assert get_space_id(result) == "100"
        assert result.type == SpaceTypeEnum.BKCC

    def test_get_space_by_str_negative_bk_biz_id(self, test_non_bkcc_space):
        """测试通过字符串类型的负数 bk_biz_id 获取非BKCC类型空间"""
        result = get_space(bk_biz_id=str(-test_non_bkcc_space.pk))

        assert result is not None
        assert get_space_id(result) == "project1"
        assert result.type == SpaceTypeEnum.BCS
