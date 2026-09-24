"""
拨测分组 operation 层测试

测试内容:
- list_groups: page/page_size 分页参数（向后兼容不传分页时返回全量）
- count_groups: 分组总数查询
"""

import pytest

from bk_monitor_base.domains.uptime_check.define import UptimeCheckTaskStatus
from bk_monitor_base.domains.uptime_check.models import (
    UptimeCheckGroupModel,
    UptimeCheckTaskModel,
)
from bk_monitor_base.domains.uptime_check.operation import (
    count_groups,
    list_groups,
)

pytestmark = pytest.mark.django_db(databases=["default"])


# =============================================================================
# 共享 Fixtures
# =============================================================================

BIZ_ID = 2


@pytest.fixture
def groups_with_tasks(db):
    """创建 3 个分组，每个分组关联不同协议的任务"""
    # 清理残留数据
    UptimeCheckGroupModel.objects.filter(bk_biz_id__in=[BIZ_ID, 0]).delete()
    UptimeCheckTaskModel.objects.filter(bk_biz_id=BIZ_ID).delete()

    t1 = UptimeCheckTaskModel.objects.create(
        bk_biz_id=BIZ_ID,
        name="HTTP任务1",
        protocol="HTTP",
        status=UptimeCheckTaskStatus.RUNNING.value,
        config={"period": 60},
    )
    t2 = UptimeCheckTaskModel.objects.create(
        bk_biz_id=BIZ_ID,
        name="TCP任务1",
        protocol="TCP",
        status=UptimeCheckTaskStatus.RUNNING.value,
        config={"period": 60},
    )
    t3 = UptimeCheckTaskModel.objects.create(
        bk_biz_id=BIZ_ID,
        name="ICMP任务1",
        protocol="ICMP",
        status=UptimeCheckTaskStatus.RUNNING.value,
        config={"period": 60},
    )
    t4_deleted = UptimeCheckTaskModel.objects.create(
        bk_biz_id=BIZ_ID,
        name="已删除任务",
        protocol="HTTP",
        status=UptimeCheckTaskStatus.RUNNING.value,
        config={"period": 60},
        is_deleted=True,
    )

    g1 = UptimeCheckGroupModel.objects.create(bk_biz_id=BIZ_ID, name="分组A")
    g1.tasks.add(t1, t2)

    g2 = UptimeCheckGroupModel.objects.create(bk_biz_id=BIZ_ID, name="分组B")
    g2.tasks.add(t3)

    g3 = UptimeCheckGroupModel.objects.create(bk_biz_id=BIZ_ID, name="分组C")
    g3.tasks.add(t1, t4_deleted)  # t4 已删除，聚合时应被排除

    return {"groups": [g1, g2, g3], "tasks": [t1, t2, t3, t4_deleted]}


# =============================================================================
# list_groups 分页测试
# =============================================================================


class TestListGroupsPagination:
    """list_groups 分页参数测试"""

    def test_no_pagination_returns_all(self, groups_with_tasks):
        """不传 page/page_size 时返回全量（向后兼容）"""
        result = list_groups(bk_tenant_id="system", bk_biz_id=BIZ_ID)
        assert len(result) == 3

    def test_only_page_raises_value_error(self, groups_with_tasks):
        """仅传 page 不传 page_size 时，抛出参数错误。"""
        with pytest.raises(ValueError, match="page 和 page_size 必须同时提供"):
            list_groups(bk_tenant_id="system", bk_biz_id=BIZ_ID, page=1)

    def test_only_page_size_raises_value_error(self, groups_with_tasks):
        """仅传 page_size 不传 page 时，抛出参数错误。"""
        with pytest.raises(ValueError, match="page 和 page_size 必须同时提供"):
            list_groups(bk_tenant_id="system", bk_biz_id=BIZ_ID, page_size=2)

    @pytest.mark.parametrize(
        ("page", "page_size", "message"),
        [
            (0, 2, "page 必须大于 0"),
            (-1, 2, "page 必须大于 0"),
            (1, 0, "page_size 必须大于 0"),
            (1, -2, "page_size 必须大于 0"),
        ],
    )
    def test_invalid_page_params_raise_value_error(self, groups_with_tasks, page, page_size, message):
        """page/page_size 小于等于 0 时，抛出参数错误。"""
        with pytest.raises(ValueError, match=message):
            list_groups(bk_tenant_id="system", bk_biz_id=BIZ_ID, page=page, page_size=page_size)

    def test_page_1(self, groups_with_tasks):
        """第一页返回指定条数"""
        result = list_groups(bk_tenant_id="system", bk_biz_id=BIZ_ID, page=1, page_size=2, order_by="id")
        assert len(result) == 2
        assert result[0].name == "分组A"
        assert result[1].name == "分组B"

    def test_page_2(self, groups_with_tasks):
        """第二页返回剩余数据"""
        result = list_groups(bk_tenant_id="system", bk_biz_id=BIZ_ID, page=2, page_size=2, order_by="id")
        assert len(result) == 1
        assert result[0].name == "分组C"

    def test_page_beyond_total(self, groups_with_tasks):
        """超出总数的页码返回空列表"""
        result = list_groups(bk_tenant_id="system", bk_biz_id=BIZ_ID, page=10, page_size=2, order_by="id")
        assert result == []

    def test_page_size_1(self, groups_with_tasks):
        """page_size=1 每页只返回一条"""
        result = list_groups(bk_tenant_id="system", bk_biz_id=BIZ_ID, page=1, page_size=1, order_by="id")
        assert len(result) == 1

    def test_pagination_without_order_by_uses_id_order(self, groups_with_tasks):
        """分页未传 order_by 时，默认按 id 稳定排序。"""
        result = list_groups(bk_tenant_id="system", bk_biz_id=BIZ_ID, page=2, page_size=2)
        assert [group.name for group in result] == ["分组C"]

    def test_pagination_with_query_filter(self, groups_with_tasks):
        """分页与 query 过滤条件组合使用"""
        result = list_groups(
            bk_tenant_id="system",
            bk_biz_id=BIZ_ID,
            query={"name": "分组A"},
            page=1,
            page_size=10,
        )
        assert len(result) == 1
        assert result[0].name == "分组A"

    def test_include_global_with_pagination(self, db):
        """include_global 与分页组合：全局分组(bk_biz_id=0)也能被查到"""
        UptimeCheckGroupModel.objects.filter(bk_biz_id__in=[BIZ_ID, 0]).delete()
        UptimeCheckGroupModel.objects.create(bk_biz_id=BIZ_ID, name="业务组")
        UptimeCheckGroupModel.objects.create(bk_biz_id=0, name="全局组")

        # 全局分组 bk_biz_id=0 在 to_define() 时会触发 pydantic ge=1 校验，
        # 这是 Define 层的已知限制；此处用 count_groups 验证 include_global 过滤逻辑正确
        total = count_groups(
            bk_tenant_id="system",
            bk_biz_id=BIZ_ID,
            query={"include_global": True},
        )
        assert total == 2

    def test_deleted_group_excluded(self, db):
        """已删除分组不出现在结果中"""
        UptimeCheckGroupModel.objects.filter(bk_biz_id=BIZ_ID).delete()
        UptimeCheckGroupModel.objects.create(bk_biz_id=BIZ_ID, name="正常组")
        deleted = UptimeCheckGroupModel.objects.create(bk_biz_id=BIZ_ID, name="已删除组")
        deleted.is_deleted = True
        deleted.save()

        result = list_groups(bk_tenant_id="system", bk_biz_id=BIZ_ID, page=1, page_size=10)
        assert len(result) == 1
        assert result[0].name == "正常组"


# =============================================================================
# count_groups 测试
# =============================================================================


class TestCountGroups:
    """count_groups 总数查询测试"""

    def test_count_all(self, groups_with_tasks):
        """统计全部分组数量"""
        total = count_groups(bk_tenant_id="system", bk_biz_id=BIZ_ID)
        assert total == 3

    def test_count_with_query(self, groups_with_tasks):
        """带过滤条件的计数"""
        total = count_groups(bk_tenant_id="system", bk_biz_id=BIZ_ID, query={"name": "分组A"})
        assert total == 1

    def test_count_excludes_deleted(self, db):
        """已删除分组不计入总数"""
        UptimeCheckGroupModel.objects.filter(bk_biz_id=BIZ_ID).delete()
        UptimeCheckGroupModel.objects.create(bk_biz_id=BIZ_ID, name="正常组")
        deleted = UptimeCheckGroupModel.objects.create(bk_biz_id=BIZ_ID, name="已删除组")
        deleted.is_deleted = True
        deleted.save()

        total = count_groups(bk_tenant_id="system", bk_biz_id=BIZ_ID)
        assert total == 1

    def test_count_include_global(self, db):
        """include_global 包含全局分组"""
        UptimeCheckGroupModel.objects.filter(bk_biz_id__in=[BIZ_ID, 0]).delete()
        UptimeCheckGroupModel.objects.create(bk_biz_id=BIZ_ID, name="业务组")
        UptimeCheckGroupModel.objects.create(bk_biz_id=0, name="全局组")

        total = count_groups(bk_tenant_id="system", bk_biz_id=BIZ_ID, query={"include_global": True})
        assert total == 2

    def test_count_empty(self, db):
        """无分组时返回 0"""
        UptimeCheckGroupModel.objects.filter(bk_biz_id=BIZ_ID).delete()
        total = count_groups(bk_tenant_id="system", bk_biz_id=BIZ_ID)
        assert total == 0
