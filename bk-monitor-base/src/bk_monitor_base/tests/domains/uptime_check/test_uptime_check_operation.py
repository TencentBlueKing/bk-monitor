"""
拨测模块 operation 层测试

测试内容:
- list_tasks: fields 参数字段裁剪、虚拟关联字段、必要字段自动补全
- list_tasks: page/page_size 分页参数
- count_tasks: 任务总数查询
- UptimeCheckTaskModel.to_define: include_node_ids/include_group_ids 参数控制
- refresh_task_status: 含公共节点的多订阅场景下的状态聚合与业务隔离
"""

from unittest.mock import patch

import pytest

from bk_monitor_base.domains.uptime_check.constants import CollectStatus
from bk_monitor_base.domains.uptime_check.define import (
    UptimeCheckTask,
    UptimeCheckTaskProtocol,
    UptimeCheckTaskStatus,
)
from bk_monitor_base.domains.uptime_check.models import (
    UptimeCheckGroupModel,
    UptimeCheckNodeModel,
    UptimeCheckTaskCollectorLog,
    UptimeCheckTaskModel,
    UptimeCheckTaskSubscription,
)
from bk_monitor_base.domains.uptime_check.operation import count_tasks, list_nodes, list_tasks, refresh_task_status

pytestmark = pytest.mark.django_db(databases=["default"])


# =============================================================================
# 共享 Fixtures
# =============================================================================


@pytest.fixture
def biz_id() -> int:
    """测试使用的业务ID"""
    return 2


@pytest.fixture
def task_full(db, biz_id: int) -> UptimeCheckTaskModel:
    """创建带完整配置的拨测任务（含 config、labels、location 等可选字段）"""
    return UptimeCheckTaskModel.objects.create(
        bk_biz_id=biz_id,
        name="完整任务",
        protocol=UptimeCheckTaskModel.Protocol.HTTP,
        status=UptimeCheckTaskStatus.RUNNING.value,
        config={"url_list": ["https://example.com"], "method": "GET", "period": 60},
        labels={"env": "prod"},
        check_interval=3,
        location={"country": "中国", "city": "深圳"},
    )


@pytest.fixture
def node(db, biz_id: int) -> UptimeCheckNodeModel:
    """创建拨测节点"""
    return UptimeCheckNodeModel.objects.create(
        bk_tenant_id="default",
        bk_biz_id=biz_id,
        name="测试节点",
        ip="192.168.1.1",
        bk_host_id=10001,
        plat_id=0,
    )


@pytest.fixture
def group(db, biz_id: int) -> UptimeCheckGroupModel:
    """创建拨测分组"""
    return UptimeCheckGroupModel.objects.create(
        bk_biz_id=biz_id,
        name="测试分组",
    )


@pytest.fixture
def task_with_relations(task_full: UptimeCheckTaskModel, node: UptimeCheckNodeModel, group: UptimeCheckGroupModel):
    """创建关联了节点和分组的完整任务"""
    task_full.nodes.add(node)
    group.tasks.add(task_full)
    return task_full


# =============================================================================
# list_tasks fields 参数测试
# =============================================================================


class TestListTasksFields:
    """list_tasks fields 参数的字段裁剪行为测试。

    验证以下核心逻辑：
    1. 不传 fields 时，返回完整字段 + node_ids/group_ids
    2. 传入 fields 时，未指定的普通字段在 define 中返回默认值，不触发额外 SQL
    3. 核心字段（id/bk_biz_id/name/protocol/status）始终被加载，即使未显式指定
    4. 虚拟字段 "node_ids"/"group_ids" 控制 M2M 关联是否加载
    """

    def test_default_returns_full_fields(self, task_with_relations: UptimeCheckTaskModel, biz_id: int) -> None:
        """不传 fields 时，返回完整字段，包含真实 config 和关联 ID 列表。"""
        # Act
        tasks = list_tasks(bk_biz_id=biz_id)

        # Assert
        assert len(tasks) == 1
        task = tasks[0]
        assert isinstance(task, UptimeCheckTask)
        assert task.config == {"url_list": ["https://example.com"], "method": "GET", "period": 60}
        assert task.labels == {"env": "prod"}
        assert task.check_interval == 3
        assert task.location == {"country": "中国", "city": "深圳"}
        assert len(task.node_ids) == 1
        assert len(task.group_ids) == 1

    def test_fields_without_relations_skips_m2m(self, task_with_relations: UptimeCheckTaskModel, biz_id: int) -> None:
        """指定 fields 且不含 node_ids/group_ids 时，关联列表为空，不发起 Prefetch 查询。"""
        # Act
        tasks = list_tasks(bk_biz_id=biz_id, fields=["id", "name", "status"])

        # Assert：关联字段为空列表（未查询 M2M）
        assert len(tasks) == 1
        task = tasks[0]
        assert task.node_ids == []
        assert task.group_ids == []

    def test_fields_with_node_ids_loads_nodes(self, task_with_relations: UptimeCheckTaskModel, biz_id: int) -> None:
        """fields 中包含虚拟字段 'node_ids' 时，节点关联正常加载。"""
        # Act
        tasks = list_tasks(bk_biz_id=biz_id, fields=["id", "node_ids"])

        # Assert
        assert len(tasks) == 1
        assert len(tasks[0].node_ids) == 1
        assert tasks[0].group_ids == []  # 未指定 group_ids，不加载

    def test_fields_with_group_ids_loads_groups(self, task_with_relations: UptimeCheckTaskModel, biz_id: int) -> None:
        """fields 中包含虚拟字段 'group_ids' 时，分组关联正常加载。"""
        # Act
        tasks = list_tasks(bk_biz_id=biz_id, fields=["id", "group_ids"])

        # Assert
        assert len(tasks) == 1
        assert tasks[0].node_ids == []
        assert len(tasks[0].group_ids) == 1

    def test_fields_with_both_relations(self, task_with_relations: UptimeCheckTaskModel, biz_id: int) -> None:
        """fields 中同时包含 'node_ids' 和 'group_ids' 时，两个关联均正常加载。"""
        # Act
        tasks = list_tasks(bk_biz_id=biz_id, fields=["id", "node_ids", "group_ids"])

        # Assert
        assert len(tasks) == 1
        assert len(tasks[0].node_ids) == 1
        assert len(tasks[0].group_ids) == 1

    def test_deferred_config_returns_default(self, task_full: UptimeCheckTaskModel, biz_id: int) -> None:
        """config 字段未在 fields 中指定时，define 中 config 返回空字典默认值，不触发额外 SQL。"""
        # Act：不包含 config
        tasks = list_tasks(bk_biz_id=biz_id, fields=["id", "name", "status"])

        # Assert
        assert len(tasks) == 1
        assert tasks[0].config == {}  # deferred 字段的 define 默认值

    def test_deferred_labels_returns_default(self, task_full: UptimeCheckTaskModel, biz_id: int) -> None:
        """labels 字段未在 fields 中指定时，define 中返回空字典默认值。"""
        tasks = list_tasks(bk_biz_id=biz_id, fields=["id"])

        assert tasks[0].labels == {}

    def test_deferred_optional_fields_return_defaults(self, task_full: UptimeCheckTaskModel, biz_id: int) -> None:
        """一次性验证所有可选 deferred 字段均返回 define 中的默认值，而非数据库值。

        覆盖字段：config / labels / check_interval / location / create_user / update_user
        """
        # Act：仅加载核心字段，其余全部 deferred
        tasks = list_tasks(bk_biz_id=biz_id, fields=["id"])

        assert len(tasks) == 1
        task = tasks[0]

        # 表驱动：(字段名, 实际值, 期望默认值)
        deferred_defaults = [
            ("config", task.config, {}),
            ("labels", task.labels, {}),
            ("check_interval", task.check_interval, 5),
            ("location", task.location, {}),
            ("create_user", task.create_user, None),
            ("update_user", task.update_user, None),
        ]
        for field_name, actual, expected in deferred_defaults:
            assert actual == expected, f"字段 {field_name} deferred 时应返回默认值 {expected!r}，实际为 {actual!r}"

    def test_required_fields_always_loaded(self, task_full: UptimeCheckTaskModel, biz_id: int) -> None:
        """核心字段（id/bk_biz_id/name/protocol/status）始终被加载，即使 fields 中未显式指定。

        验证核心字段的真实数据库值可正确获取，而非 deferred 默认值。
        """
        # Act：只传 "config"，但核心字段应被自动补充
        tasks = list_tasks(bk_biz_id=biz_id, fields=["config"])

        assert len(tasks) == 1
        task = tasks[0]

        # 核心字段应为真实值（非默认值）
        assert task.id is not None
        assert task.bk_biz_id == biz_id
        assert task.name == "完整任务"
        assert task.protocol == UptimeCheckTaskProtocol.HTTP
        assert task.status == UptimeCheckTaskStatus.RUNNING
        # config 字段因在 fields 中指定，也应为真实值
        assert task.config != {}

    def test_fields_only_id_name_status(self, task_full: UptimeCheckTaskModel, biz_id: int) -> None:
        """典型轻量查询场景：只关心 id/name/status，跳过大字段和关联。"""
        tasks = list_tasks(bk_biz_id=biz_id, fields=["id", "name", "status"])

        assert len(tasks) == 1
        task = tasks[0]
        # 核心字段正确
        assert task.id == task_full.pk
        assert task.name == "完整任务"
        assert task.status == UptimeCheckTaskStatus.RUNNING
        # 未加载的关联
        assert task.node_ids == []
        assert task.group_ids == []
        # 未加载的大字段返回默认值
        assert task.config == {}

    def test_empty_result(self, db, biz_id: int) -> None:
        """业务下无任务时返回空列表。"""
        tasks = list_tasks(bk_biz_id=biz_id)

        assert tasks == []

    def test_multiple_tasks_all_returned(self, db, biz_id: int) -> None:
        """多条任务场景下，所有任务均被返回。"""
        # Arrange
        for i in range(3):
            UptimeCheckTaskModel.objects.create(
                bk_biz_id=biz_id,
                name=f"任务{i}",
                protocol=UptimeCheckTaskModel.Protocol.TCP,
            )

        # Act
        tasks = list_tasks(bk_biz_id=biz_id)

        # Assert
        assert len(tasks) == 3

    def test_deleted_tasks_excluded(self, db, biz_id: int) -> None:
        """软删除的任务不出现在结果中。"""
        # Arrange
        active = UptimeCheckTaskModel.objects.create(
            bk_biz_id=biz_id, name="活跃任务", protocol=UptimeCheckTaskModel.Protocol.TCP
        )
        UptimeCheckTaskModel.objects.create(
            bk_biz_id=biz_id,
            name="已删除任务",
            protocol=UptimeCheckTaskModel.Protocol.TCP,
            is_deleted=True,
        )

        # Act
        tasks = list_tasks(bk_biz_id=biz_id)

        # Assert
        assert len(tasks) == 1
        assert tasks[0].id == active.pk

    def test_query_with_multiple_nodes_and_groups_returns_distinct_tasks(self, db, biz_id: int) -> None:
        """同一任务命中多个节点和分组过滤条件时，列表结果应去重。

        这个场景会同时触发任务到节点、任务到分组的 M2M Join。
        如果没有 distinct()，同一任务会因为匹配多条关联记录而重复返回。
        """
        # Arrange
        task = UptimeCheckTaskModel.objects.create(
            bk_biz_id=biz_id,
            name="去重任务",
            protocol=UptimeCheckTaskModel.Protocol.HTTP,
        )
        nodes = [
            UptimeCheckNodeModel.objects.create(
                bk_tenant_id="default",
                bk_biz_id=biz_id,
                name=f"去重节点{i}",
                ip=f"192.168.2.{i}",
                bk_host_id=20000 + i,
                plat_id=0,
            )
            for i in range(1, 3)
        ]
        groups = [UptimeCheckGroupModel.objects.create(bk_biz_id=biz_id, name=f"去重分组{i}") for i in range(1, 3)]
        task.nodes.add(*nodes)
        for group in groups:
            group.tasks.add(task)

        # Act
        tasks = list_tasks(
            bk_biz_id=biz_id,
            query={
                "node_ids": [node.pk for node in nodes],
                "group_ids": [group.pk for group in groups],
            },
        )

        # Assert
        assert len(tasks) == 1
        assert tasks[0].id == task.pk


# =============================================================================
# list_tasks 分页 和 count_tasks 测试
# =============================================================================


@pytest.fixture
def ten_tasks(db, biz_id: int) -> list[UptimeCheckTaskModel]:
    """创建 10 个拨测任务，用于分页和计数测试。"""
    return [
        UptimeCheckTaskModel.objects.create(
            bk_biz_id=biz_id,
            name=f"分页任务{i}",
            protocol=UptimeCheckTaskModel.Protocol.TCP,
        )
        for i in range(10)
    ]


class TestListTasksPagination:
    """list_tasks page/page_size 分页参数和 count_tasks 的测试。

    验证以下核心逻辑：
    1. 不传 page/page_size 时，返回全部任务（向后兼容）
    2. 仅传 page 或仅传 page_size 时，抛出参数错误
    3. page/page_size 小于等于 0 时，抛出参数错误
    4. page=1, page_size=3 时，返回前 3 条
    5. page=2, page_size=3 时，返回第 4-6 条
    6. page 超出范围时，返回空列表
    7. page/page_size 不影响 fields / order_by 等其他参数
    8. count_tasks 返回过滤后的任务总数
    """

    def test_no_pagination_returns_all(self, ten_tasks: list, biz_id: int) -> None:
        """不传 page/page_size 时返回全部任务。"""
        tasks = list_tasks(bk_biz_id=biz_id)
        assert len(tasks) == 10

    def test_only_page_raises_value_error(self, ten_tasks: list, biz_id: int) -> None:
        """仅传 page 不传 page_size 时，抛出参数错误。"""
        with pytest.raises(ValueError, match="page 和 page_size 必须同时提供"):
            list_tasks(bk_biz_id=biz_id, page=1)

    def test_only_page_size_raises_value_error(self, ten_tasks: list, biz_id: int) -> None:
        """仅传 page_size 不传 page 时，抛出参数错误。"""
        with pytest.raises(ValueError, match="page 和 page_size 必须同时提供"):
            list_tasks(bk_biz_id=biz_id, page_size=3)

    @pytest.mark.parametrize(
        ("page", "page_size", "message"),
        [
            (0, 3, "page 必须大于 0"),
            (-1, 3, "page 必须大于 0"),
            (1, 0, "page_size 必须大于 0"),
            (1, -3, "page_size 必须大于 0"),
        ],
    )
    def test_invalid_page_params_raise_value_error(
        self,
        ten_tasks: list,
        biz_id: int,
        page: int,
        page_size: int,
        message: str,
    ) -> None:
        """page/page_size 小于等于 0 时，抛出参数错误。"""
        with pytest.raises(ValueError, match=message):
            list_tasks(bk_biz_id=biz_id, page=page, page_size=page_size)

    def test_page1_size3_returns_first_3(self, ten_tasks: list, biz_id: int) -> None:
        """page=1, page_size=3 返回前 3 条。"""
        tasks = list_tasks(bk_biz_id=biz_id, page=1, page_size=3)
        assert len(tasks) == 3
        assert [t.name for t in tasks] == [f"分页任务{i}" for i in range(3)]

    def test_page2_size3_returns_4_to_6(self, ten_tasks: list, biz_id: int) -> None:
        """page=2, page_size=3 返回第 4-6 条。"""
        tasks = list_tasks(bk_biz_id=biz_id, page=2, page_size=3, order_by="id")
        assert len(tasks) == 3
        assert {t.name for t in tasks} == {f"分页任务{i}" for i in range(3, 6)}

    def test_page_exceeds_total_returns_empty(self, ten_tasks: list, biz_id: int) -> None:
        """page 超出范围时返回空列表。"""
        tasks = list_tasks(bk_biz_id=biz_id, page=10, page_size=3)
        assert tasks == []

    def test_pagination_different_page_sizes(self, ten_tasks: list, biz_id: int) -> None:
        """验证不同 page_size 下分页结果条数正确。"""
        for size in [1, 5, 10, 20]:
            tasks = list_tasks(bk_biz_id=biz_id, page=1, page_size=size)
            assert len(tasks) == min(size, 10)

    def test_pagination_with_fields(self, ten_tasks: list, biz_id: int) -> None:
        """分页 + fields 参数组合使用，大字段被 deferred。"""
        tasks = list_tasks(bk_biz_id=biz_id, page=1, page_size=2, fields=["id", "name"])
        assert len(tasks) == 2
        assert tasks[0].config == {}  # config 未加载，返回默认值

    def test_pagination_with_query(self, ten_tasks: list, biz_id: int) -> None:
        """分页 + task_ids 筛选组合使用，验证分页在过滤后再切片。"""
        target_ids = [ten_tasks[0].pk, ten_tasks[3].pk, ten_tasks[7].pk]  # 3 个任务
        tasks = list_tasks(
            bk_biz_id=biz_id,
            page=1,
            page_size=2,
            query={"task_ids": target_ids},
        )
        assert len(tasks) == 2  # 过滤后 3 个，但分页只取 2 个

    def test_pagination_with_order_by(self, ten_tasks: list, biz_id: int) -> None:
        """分页 + 排序组合使用，第二页不应与第一页重复。"""
        page1 = list_tasks(bk_biz_id=biz_id, page=1, page_size=3, order_by="id")
        page2 = list_tasks(bk_biz_id=biz_id, page=2, page_size=3, order_by="id")
        page1_ids = {t.id for t in page1}
        page2_ids = {t.id for t in page2}
        assert page1_ids.isdisjoint(page2_ids)

    def test_pagination_without_order_by_uses_id_order(self, ten_tasks: list, biz_id: int) -> None:
        """分页未传 order_by 时，默认按 id 稳定排序。"""
        tasks = list_tasks(bk_biz_id=biz_id, page=2, page_size=3)
        assert [t.name for t in tasks] == [f"分页任务{i}" for i in range(3, 6)]


class TestCountTasks:
    """count_tasks 函数测试。

    验证以下核心逻辑：
    1. 无过滤条件时返回业务下所有未删除任务数
    2. 支持 query 过滤条件
    3. 已删除任务不计入
    """

    def test_returns_total_count(self, ten_tasks: list, biz_id: int) -> None:
        """无过滤条件时返回任务总数。"""
        assert count_tasks(bk_biz_id=biz_id) == 10

    def test_empty_biz_returns_zero(self, db) -> None:
        """无任务的业务返回 0。"""
        assert count_tasks(bk_biz_id=99999) == 0

    def test_excludes_deleted(self, db, biz_id: int) -> None:
        """已删除任务不计入 count。"""
        UptimeCheckTaskModel.objects.create(
            bk_biz_id=biz_id,
            name="活跃",
            protocol=UptimeCheckTaskModel.Protocol.TCP,
        )
        UptimeCheckTaskModel.objects.create(
            bk_biz_id=biz_id, name="删除", protocol=UptimeCheckTaskModel.Protocol.TCP, is_deleted=True
        )
        assert count_tasks(bk_biz_id=biz_id) == 1

    def test_with_name_query(self, ten_tasks: list, biz_id: int) -> None:
        """name 过滤条件生效。"""
        assert count_tasks(bk_biz_id=biz_id, query={"name": "分页任务1"}) == 1  # icontains 匹配 "分页任务1"

    def test_with_task_id_query(self, ten_tasks: list, biz_id: int) -> None:
        """task_id 精确匹配。"""
        target = ten_tasks[0]
        assert count_tasks(bk_biz_id=biz_id, query={"task_id": target.pk}) == 1

    def test_count_and_list_consistent(self, ten_tasks: list, biz_id: int) -> None:
        """count_tasks 与 list_tasks 无分页时的结果数一致。"""
        total = count_tasks(bk_biz_id=biz_id)
        tasks = list_tasks(bk_biz_id=biz_id)
        assert total == len(tasks)


# =============================================================================
# list_nodes include_common 过滤测试
# =============================================================================


class TestListNodesIncludeCommonFilters:
    """list_nodes 在 include_common 场景下的过滤行为测试。"""

    def test_include_common_should_apply_filters_to_common_nodes(self, db, monkeypatch) -> None:
        """include_common=True 时，公共节点也应应用 name/carrieroperator 等过滤条件。"""
        # Arrange: 固定业务与租户映射，避免依赖空间域数据
        monkeypatch.setattr(
            "bk_monitor_base.domains.uptime_check.operation.bk_biz_id_to_bk_tenant_id",
            lambda _: "default",
        )
        bk_tenant_id = "default"
        bk_biz_id = 2

        biz_node = UptimeCheckNodeModel.objects.create(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            is_common=False,
            name="深圳移动业务节点",
            ip="10.0.0.1",
            carrieroperator="移动",
        )
        common_node_match = UptimeCheckNodeModel.objects.create(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=0,
            is_common=True,
            biz_scope=[bk_biz_id],
            name="深圳移动公共节点",
            ip="10.0.0.2",
            carrieroperator="移动",
        )
        UptimeCheckNodeModel.objects.create(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=0,
            is_common=True,
            biz_scope=[bk_biz_id],
            name="深圳联通公共节点",
            ip="10.0.0.3",
            carrieroperator="联通",
        )
        UptimeCheckNodeModel.objects.create(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=0,
            is_common=True,
            biz_scope=[3],
            name="深圳移动其他业务公共节点",
            ip="10.0.0.4",
            carrieroperator="移动",
        )

        # Act
        nodes = list_nodes(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            query={
                "include_common": True,
                "name": "深圳",
                "carrieroperator": "移动",
            },
        )

        # Assert
        node_ids = {node.id for node in nodes}
        assert node_ids == {biz_node.pk, common_node_match.pk}

    def test_include_common_with_is_common_false_keeps_common_nodes(self, db, monkeypatch) -> None:
        """include_common=True 且 is_common=False 时，仍返回公共节点（兼容历史行为）。"""
        # Arrange: 固定业务与租户映射，避免依赖空间域数据
        monkeypatch.setattr(
            "bk_monitor_base.domains.uptime_check.operation.bk_biz_id_to_bk_tenant_id",
            lambda _: "default",
        )
        bk_tenant_id = "default"
        bk_biz_id = 2

        biz_node = UptimeCheckNodeModel.objects.create(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            is_common=False,
            name="深圳移动业务节点",
            ip="10.0.1.1",
            carrieroperator="移动",
        )
        common_node = UptimeCheckNodeModel.objects.create(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=0,
            is_common=True,
            biz_scope=[bk_biz_id],
            name="深圳移动公共节点",
            ip="10.0.1.2",
            carrieroperator="移动",
        )

        # Act
        nodes = list_nodes(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            query={
                "include_common": True,
                "is_common": False,
                "name": "深圳",
                "carrieroperator": "移动",
            },
        )

        # Assert
        node_ids = {node.id for node in nodes}
        assert node_ids == {biz_node.pk, common_node.pk}


# =============================================================================
# to_define 参数测试
# =============================================================================


class TestToDefineParams:
    """UptimeCheckTaskModel.to_define() 的 include_node_ids/include_group_ids 参数测试。

    验证以下核心逻辑：
    1. 默认行为与改动前一致（向后兼容）
    2. include_node_ids=False 时直接返回空列表，不访问 nodes M2M
    3. include_group_ids=False 时直接返回空列表，不访问 groups M2M
    4. only() 产生的 deferred 字段由 get_deferred_fields() 感知并返回默认值
    """

    def test_default_includes_both_relations(self, task_with_relations: UptimeCheckTaskModel) -> None:
        """默认调用（无参数）时，node_ids 和 group_ids 均正常加载（向后兼容）。"""
        define = task_with_relations.to_define()

        assert len(define.node_ids) == 1
        assert len(define.group_ids) == 1

    def test_include_node_ids_false_returns_empty(self, task_with_relations: UptimeCheckTaskModel) -> None:
        """include_node_ids=False 时，node_ids 返回空列表，不查询 M2M。"""
        define = task_with_relations.to_define(include_node_ids=False)

        assert define.node_ids == []
        assert len(define.group_ids) == 1  # group_ids 不受影响

    def test_include_group_ids_false_returns_empty(self, task_with_relations: UptimeCheckTaskModel) -> None:
        """include_group_ids=False 时，group_ids 返回空列表，不查询 M2M。"""
        define = task_with_relations.to_define(include_group_ids=False)

        assert len(define.node_ids) == 1  # node_ids 不受影响
        assert define.group_ids == []

    def test_both_relations_disabled(self, task_with_relations: UptimeCheckTaskModel) -> None:
        """两个关联均禁用时，define 中均为空列表。"""
        define = task_with_relations.to_define(include_node_ids=False, include_group_ids=False)

        assert define.node_ids == []
        assert define.group_ids == []

    def test_task_without_relations_returns_empty_by_default(self, task_full: UptimeCheckTaskModel) -> None:
        """无关联数据的任务，默认调用时关联列表为空。"""
        define = task_full.to_define()

        assert define.node_ids == []
        assert define.group_ids == []

    @pytest.mark.parametrize(
        "fields, expected_config, expected_labels, expected_check_interval, expected_location",
        [
            # 仅加载核心字段，所有可选字段均 deferred
            (
                ["id", "name", "status", "bk_biz_id", "protocol"],
                {},
                {},
                5,
                {},
            ),
            # 加载 config，其余可选字段 deferred
            (
                ["id", "name", "status", "bk_biz_id", "protocol", "config"],
                {"url_list": ["https://example.com"], "method": "GET", "period": 60},
                {},
                5,
                {},
            ),
            # 加载 config + labels，其余可选字段 deferred
            (
                ["id", "name", "status", "bk_biz_id", "protocol", "config", "labels"],
                {"url_list": ["https://example.com"], "method": "GET", "period": 60},
                {"env": "prod"},
                5,
                {},
            ),
        ],
        ids=["仅核心字段", "含config", "含config和labels"],
    )
    def test_deferred_fields_via_only(
        self,
        task_full: UptimeCheckTaskModel,
        fields: list[str],
        expected_config: dict,
        expected_labels: dict,
        expected_check_interval: int,
        expected_location: dict,
    ) -> None:
        """通过 only() 产生 deferred 字段，to_define() 应返回 define 默认值而非触发额外 SQL。

        表驱动测试：验证不同 fields 组合下 deferred 字段的默认值填充是否正确。
        """
        # Arrange：用 only() 模拟 list_tasks 中的字段裁剪行为
        task = UptimeCheckTaskModel.objects.only(*fields).get(pk=task_full.pk)

        # Act
        define = task.to_define(include_node_ids=False, include_group_ids=False)

        # Assert
        assert define.config == expected_config
        assert define.labels == expected_labels
        assert define.check_interval == expected_check_interval
        assert define.location == expected_location

    def test_non_deferred_fields_return_real_values(self, task_full: UptimeCheckTaskModel) -> None:
        """未被 only() 裁剪的字段应返回真实数据库值，而非默认值。"""
        # Arrange：加载所有字段（无 only 裁剪）
        task = UptimeCheckTaskModel.objects.get(pk=task_full.pk)

        # Act
        define = task.to_define(include_node_ids=False, include_group_ids=False)

        # Assert：真实值应与 fixtures 中的设置一致
        assert define.config == {"url_list": ["https://example.com"], "method": "GET", "period": 60}
        assert define.labels == {"env": "prod"}
        assert define.check_interval == 3
        assert define.location == {"country": "中国", "city": "深圳"}
        assert define.status == UptimeCheckTaskStatus.RUNNING

    def test_to_define_returns_uptime_check_task_type(self, task_full: UptimeCheckTaskModel) -> None:
        """to_define() 始终返回 UptimeCheckTask 类型。"""
        define = task_full.to_define()

        assert isinstance(define, UptimeCheckTask)


# =============================================================================
# refresh_task_status 多订阅状态聚合测试
# =============================================================================


# 公共节点所属的公共业务ID（与任务的业务ID不同）
PUBLIC_BIZ_ID = 100


class TestRefreshTaskStatusMultiSubscription:
    """``refresh_task_status`` 在含公共节点的多订阅场景下的核心行为测试。

    背景：当拨测任务包含公共节点时，订阅服务会按节点 ``bk_biz_id`` 拆分订阅，
    ``UptimeCheckTaskSubscription`` 表中会出现多条记录，且 ``bk_biz_id`` 是
    节点的业务ID（公共节点为公共业务ID），与任务 ``bk_biz_id`` 不一致。

    本测试套件验证：
    1. 业务隔离基于任务而非订阅，能正确拉取公共节点订阅
    2. 多订阅状态按 ``FAILED > STARTING > RUNNING`` 优先级聚合
    3. 失败时所有失败订阅的错误日志均被记录
    4. 跨业务的任务不会被误更新
    """

    # --- Fixtures -----------------------------------------------------------

    @pytest.fixture(autouse=True)
    def _mock_tenant_check(self):
        """绕过 ``_check_bk_biz_id_tenant_id`` 对 SpaceModel 的依赖。

        ``operation`` 模块顶层 ``from ... import bk_biz_id_to_bk_tenant_id`` 后，
        必须 patch ``operation`` 模块自身的引用才能生效。
        """
        with patch(
            "bk_monitor_base.domains.uptime_check.operation.bk_biz_id_to_bk_tenant_id",
            return_value="default",
        ):
            yield

    @pytest.fixture
    def task_with_subs(self, task_full: UptimeCheckTaskModel) -> UptimeCheckTaskModel:
        """构造一条拨测任务 + 两条订阅（业务订阅 + 公共节点订阅）。

        - 订阅 1001：与任务同业务（普通节点）
        - 订阅 1002：归属公共业务 ``PUBLIC_BIZ_ID``（公共节点），用于复现 Bug 场景
        """
        UptimeCheckTaskSubscription.objects.create(
            uptimecheck_id=task_full.pk,
            subscription_id=1001,
            bk_biz_id=task_full.bk_biz_id,
        )
        UptimeCheckTaskSubscription.objects.create(
            uptimecheck_id=task_full.pk,
            subscription_id=1002,
            bk_biz_id=PUBLIC_BIZ_ID,
        )
        return task_full

    @staticmethod
    def _mock_status(status: str) -> tuple[list[dict[str, str]], int]:
        """构造 ``batch_get_subscription_task_result`` 的最小返回值。

        节点管理返回 ``(tasks, total_count)`` 元组，``tasks`` 元素只需要 ``status`` 字段。
        """
        return [{"status": status}], 1

    # --- 业务隔离与订阅查询 -------------------------------------------------

    @patch("bk_monitor_base.domains.uptime_check.operation.node_man_v2_api.batch_get_subscription_task_result")
    def test_fetch_includes_public_node_subscription(
        self,
        mock_batch_result,
        task_with_subs: UptimeCheckTaskModel,
        biz_id: int,
    ) -> None:
        """Bug 1 回归：含公共节点的任务，公共节点订阅必须被拉取并参与状态聚合。

        构造两条订阅都返回 SUCCESS，期望任务被更新为 RUNNING；
        若公共节点订阅被漏掉，状态映射会因订阅数不全而表现异常。
        """
        # Arrange
        mock_batch_result.return_value = self._mock_status(CollectStatus.SUCCESS)

        # Act
        result = refresh_task_status(
            bk_tenant_id="default",
            bk_biz_id=biz_id,
            task_ids=[task_with_subs.pk],
        )

        # Assert：两条订阅都被请求，任务最终状态为 RUNNING
        called_sub_ids = sorted(call.kwargs["params"]["subscription_id"] for call in mock_batch_result.call_args_list)
        assert called_sub_ids == [1001, 1002]
        assert result == {task_with_subs.pk: UptimeCheckTaskStatus.RUNNING.value}

    @patch("bk_monitor_base.domains.uptime_check.operation.node_man_v2_api.batch_get_subscription_task_result")
    def test_cross_biz_task_is_isolated(
        self,
        mock_batch_result,
        task_with_subs: UptimeCheckTaskModel,
        biz_id: int,
    ) -> None:
        """业务隔离基于任务侧 ``bk_biz_id``，跨业务调用时不应返回任何更新。"""
        # Arrange
        mock_batch_result.return_value = self._mock_status(CollectStatus.SUCCESS)

        # Act：用不同的业务ID尝试刷新该任务
        result = refresh_task_status(
            bk_tenant_id="default",
            bk_biz_id=biz_id + 999,
            task_ids=[task_with_subs.pk],
        )

        # Assert：跨业务读取被阻断，节点管理接口不应被调用
        assert result == {}
        mock_batch_result.assert_not_called()

    # --- 多订阅状态聚合（表驱动）------------------------------------------

    @pytest.mark.parametrize(
        "sub_statuses, expected_task_status, expect_failed_sub_ids",
        [
            # 全部完成 -> RUNNING
            (
                {1001: CollectStatus.SUCCESS, 1002: CollectStatus.SUCCESS},
                UptimeCheckTaskStatus.RUNNING.value,
                [],
            ),
            # 公共节点订阅仍在 RUNNING（节点管理任务未完成）-> STARTING
            (
                {1001: CollectStatus.SUCCESS, 1002: CollectStatus.RUNNING},
                UptimeCheckTaskStatus.STARTING.value,
                [],
            ),
            (
                {1001: CollectStatus.PENDING, 1002: CollectStatus.SUCCESS},
                UptimeCheckTaskStatus.STARTING.value,
                [],
            ),
            # 任一订阅 FAILED -> START_FAILED，并记录所有失败订阅日志
            (
                {1001: CollectStatus.SUCCESS, 1002: CollectStatus.FAILED},
                UptimeCheckTaskStatus.START_FAILED.value,
                [1002],
            ),
            (
                {1001: CollectStatus.FAILED, 1002: CollectStatus.FAILED},
                UptimeCheckTaskStatus.START_FAILED.value,
                [1001, 1002],
            ),
            # FAILED 优先级高于 STARTING
            (
                {1001: CollectStatus.RUNNING, 1002: CollectStatus.FAILED},
                UptimeCheckTaskStatus.START_FAILED.value,
                [1002],
            ),
        ],
        ids=[
            "全部成功-RUNNING",
            "含运行中-STARTING",
            "含等待中-STARTING",
            "单失败-START_FAILED",
            "双失败-START_FAILED",
            "失败优先级高于运行中",
        ],
    )
    @patch("bk_monitor_base.infras.third_party_api.nodeman.api.get_subscription_task_result")
    @patch("bk_monitor_base.infras.third_party_api.nodeman.api.get_subscription_task_result_detail")
    @patch("bk_monitor_base.domains.uptime_check.operation.node_man_v2_api.batch_get_subscription_task_result")
    def test_aggregate_status_across_subscriptions(
        self,
        mock_batch_result,
        mock_detail,
        mock_result,
        task_with_subs: UptimeCheckTaskModel,
        biz_id: int,
        sub_statuses: dict[int, str],
        expected_task_status: str,
        expect_failed_sub_ids: list[int],
    ) -> None:
        """跨订阅聚合规则验证：FAILED > STARTING > RUNNING。

        - ``batch_get_subscription_task_result`` 根据订阅ID返回不同状态
        - 当存在失败订阅时，应对每个失败订阅调用错误日志记录链路
        """

        # Arrange：按订阅ID动态返回不同状态
        def _side_effect(*, bk_tenant_id: str, params: dict):
            sub_id = params["subscription_id"]
            return self._mock_status(sub_statuses[sub_id])

        mock_batch_result.side_effect = _side_effect
        # 错误日志链路用空 list 短路掉，避免污染断言
        mock_result.return_value = {"list": []}
        mock_detail.return_value = {"steps": []}

        # Act
        result = refresh_task_status(
            bk_tenant_id="default",
            bk_biz_id=biz_id,
            task_ids=[task_with_subs.pk],
        )

        # Assert：任务状态聚合正确
        assert result == {task_with_subs.pk: expected_task_status}
        task_with_subs.refresh_from_db()
        assert task_with_subs.status == expected_task_status

        # Assert：所有失败订阅都触发了错误日志查询（按 subscription_id 维度）
        called_sub_ids_for_logs = sorted(
            call.kwargs["params"]["subscription_id"] for call in mock_result.call_args_list
        )
        assert called_sub_ids_for_logs == sorted(expect_failed_sub_ids)

    # --- 缺失 / 异常订阅状态聚合 -------------------------------------------

    @patch("bk_monitor_base.domains.uptime_check.operation.node_man_v2_api.batch_get_subscription_task_result")
    def test_partial_missing_result_keeps_task_starting(
        self,
        mock_batch_result,
        task_with_subs: UptimeCheckTaskModel,
        biz_id: int,
    ) -> None:
        """P1 回归：业务订阅已 SUCCESS、公共节点订阅暂无结果时，任务必须保持 STARTING。

        这是当前 ``refresh_task_status`` 的核心保护机制：``_fetch_subscription_statuses``
        会把空结果统一标记为 ``PENDING``，避免任务被已完成订阅误推进到 ``RUNNING``。
        """

        # Arrange：订阅 1001 SUCCESS、订阅 1002（公共节点）返回空结果
        def _side_effect(*, bk_tenant_id: str, params: dict):
            sub_id = params["subscription_id"]
            if sub_id == 1001:
                return [{"status": CollectStatus.SUCCESS}], 1
            return [], 0  # 节点管理返回空 tasks，代表订阅尚未产生执行实例

        mock_batch_result.side_effect = _side_effect

        # Act
        result = refresh_task_status(
            bk_tenant_id="default",
            bk_biz_id=biz_id,
            task_ids=[task_with_subs.pk],
        )

        # Assert：任务仍保持启用中状态，而不是被错误地推进到 RUNNING
        assert result == {task_with_subs.pk: UptimeCheckTaskStatus.STARTING.value}

    @patch("bk_monitor_base.domains.uptime_check.operation.node_man_v2_api.batch_get_subscription_task_result")
    def test_api_exception_keeps_task_starting(
        self,
        mock_batch_result,
        task_with_subs: UptimeCheckTaskModel,
        biz_id: int,
    ) -> None:
        """节点管理接口异常时，相应订阅按启用中处理，任务不应被误判为 RUNNING。"""

        # Arrange：订阅 1001 SUCCESS、订阅 1002 调用节点管理抛异常
        def _side_effect(*, bk_tenant_id: str, params: dict):
            sub_id = params["subscription_id"]
            if sub_id == 1001:
                return [{"status": CollectStatus.SUCCESS}], 1
            raise RuntimeError("nodeman api timeout")

        mock_batch_result.side_effect = _side_effect

        # Act
        result = refresh_task_status(
            bk_tenant_id="default",
            bk_biz_id=biz_id,
            task_ids=[task_with_subs.pk],
        )

        # Assert：异常订阅折算为 PENDING，任务整体停留在 STARTING
        assert result == {task_with_subs.pk: UptimeCheckTaskStatus.STARTING.value}

    @patch("bk_monitor_base.infras.third_party_api.nodeman.api.get_subscription_task_result_detail")
    @patch("bk_monitor_base.infras.third_party_api.nodeman.api.get_subscription_task_result")
    @patch("bk_monitor_base.domains.uptime_check.operation.node_man_v2_api.batch_get_subscription_task_result")
    def test_failed_priority_over_missing_subscription(
        self,
        mock_batch_result,
        mock_result,
        mock_detail,
        task_with_subs: UptimeCheckTaskModel,
        biz_id: int,
    ) -> None:
        """``FAILED`` 优先级高于"无结果"：即便有订阅暂无结果，也不应掩盖另一订阅的失败。"""

        # Arrange：订阅 1001 FAILED、订阅 1002 空结果
        def _side_effect(*, bk_tenant_id: str, params: dict):
            sub_id = params["subscription_id"]
            if sub_id == 1001:
                return [{"status": CollectStatus.FAILED}], 1
            return [], 0

        mock_batch_result.side_effect = _side_effect
        mock_result.return_value = {"list": []}
        mock_detail.return_value = {"steps": []}

        # Act
        result = refresh_task_status(
            bk_tenant_id="default",
            bk_biz_id=biz_id,
            task_ids=[task_with_subs.pk],
        )

        # Assert：任务被判为 START_FAILED，且仅失败订阅触发错误日志查询
        assert result == {task_with_subs.pk: UptimeCheckTaskStatus.START_FAILED.value}
        called_sub_ids_for_logs = [call.kwargs["params"]["subscription_id"] for call in mock_result.call_args_list]
        assert called_sub_ids_for_logs == [1001]

    @patch("bk_monitor_base.domains.uptime_check.operation.node_man_v2_api.batch_get_subscription_task_result")
    def test_all_subscriptions_missing_keeps_task_starting(
        self,
        mock_batch_result,
        task_with_subs: UptimeCheckTaskModel,
        biz_id: int,
    ) -> None:
        """所有订阅都没有节点管理结果时，任务整体仍保持 STARTING。"""
        # Arrange：所有订阅都返回空结果
        mock_batch_result.return_value = ([], 0)

        # Act
        result = refresh_task_status(
            bk_tenant_id="default",
            bk_biz_id=biz_id,
            task_ids=[task_with_subs.pk],
        )

        # Assert
        assert result == {task_with_subs.pk: UptimeCheckTaskStatus.STARTING.value}

    # --- 错误日志记录 -------------------------------------------------------

    @patch("bk_monitor_base.infras.third_party_api.nodeman.api.get_subscription_task_result_detail")
    @patch("bk_monitor_base.infras.third_party_api.nodeman.api.get_subscription_task_result")
    @patch("bk_monitor_base.domains.uptime_check.operation.node_man_v2_api.batch_get_subscription_task_result")
    def test_failed_subscription_writes_collector_log(
        self,
        mock_batch_result,
        mock_result,
        mock_detail,
        task_with_subs: UptimeCheckTaskModel,
        biz_id: int,
    ) -> None:
        """失败订阅应落库 ``UptimeCheckTaskCollectorLog``，并带上 subscription_id。"""

        # Arrange：订阅 1001 成功，订阅 1002（公共节点）失败
        def _batch_side_effect(*, bk_tenant_id: str, params: dict):
            sub_id = params["subscription_id"]
            status = CollectStatus.SUCCESS if sub_id == 1001 else CollectStatus.FAILED
            return self._mock_status(status)

        mock_batch_result.side_effect = _batch_side_effect
        mock_result.return_value = {
            "list": [{"status": CollectStatus.FAILED, "instance_id": "host|host|1|0", "task_id": 9999}]
        }
        mock_detail.return_value = {
            "steps": [
                {
                    "status": CollectStatus.FAILED,
                    "target_hosts": [
                        {
                            "sub_steps": [
                                {"ex_data": {"err": "公共节点采集失败"}},
                            ]
                        }
                    ],
                }
            ]
        }

        # Act
        refresh_task_status(bk_tenant_id="default", bk_biz_id=biz_id, task_ids=[task_with_subs.pk])

        # Assert：日志记录仅来自失败订阅 1002
        logs = list(UptimeCheckTaskCollectorLog.objects.filter(task_id=task_with_subs.pk))
        assert len(logs) == 1
        assert logs[0].subscription_id == 1002
        assert logs[0].error_log == {"err": "公共节点采集失败"}
