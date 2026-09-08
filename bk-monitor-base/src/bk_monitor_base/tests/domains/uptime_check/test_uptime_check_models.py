"""
拨测模块常量和模型测试

测试内容:
- UptimeCheckProtocol: 协议类型枚举
- CollectorInstallWay: 采集器安装方式枚举
- 常量值测试
- UptimeCheckNodeModel: 拨测节点模型
- UptimeCheckTaskModel: 拨测任务模型
- UptimeCheckGroup: 拨测任务分组模型
- UptimeCheckTaskSubscription: 拨测任务订阅关系模型
"""

import pytest

from bk_monitor_base.domains.uptime_check.constants import (
    CollectorInstallWay,
    UptimeCheckProtocol,
)
from bk_monitor_base.domains.uptime_check.define import UptimeCheckTaskStatus
from bk_monitor_base.domains.uptime_check.models import (
    NODE_IP_TYPE_CHOICES,
    NODE_IP_TYPE_DICT,
    UptimeCheckGroupModel,
    UptimeCheckNodeModel,
    UptimeCheckTaskCollectorLog,
    UptimeCheckTaskModel,
    UptimeCheckTaskSubscription,
)

pytestmark = pytest.mark.django_db(databases=["default"])

# =============================================================================
# 常量测试
# =============================================================================


class TestUptimeCheckProtocol:
    """UptimeCheckProtocol枚举测试"""

    def test_protocol_values(self):
        """测试协议类型值"""
        assert UptimeCheckProtocol.HTTP == "HTTP"
        assert UptimeCheckProtocol.TCP == "TCP"
        assert UptimeCheckProtocol.UDP == "UDP"
        assert UptimeCheckProtocol.ICMP == "ICMP"

    def test_protocol_is_string_enum(self):
        """测试协议是字符串枚举"""
        assert isinstance(UptimeCheckProtocol.HTTP, str)
        assert UptimeCheckProtocol.HTTP.lower() == "http"

    def test_protocol_membership(self):
        """测试协议成员检查"""
        assert "HTTP" in [p.value for p in UptimeCheckProtocol]
        assert "TCP" in [p.value for p in UptimeCheckProtocol]
        assert "UDP" in [p.value for p in UptimeCheckProtocol]
        assert "ICMP" in [p.value for p in UptimeCheckProtocol]

    def test_protocol_from_string(self):
        """测试从字符串创建协议"""
        assert UptimeCheckProtocol("HTTP") == UptimeCheckProtocol.HTTP
        assert UptimeCheckProtocol("TCP") == UptimeCheckProtocol.TCP

    def test_invalid_protocol(self):
        """测试无效协议抛出异常"""
        with pytest.raises(ValueError):
            UptimeCheckProtocol("INVALID")


class TestCollectorInstallWay:
    """CollectorInstallWay枚举测试"""

    def test_install_way_values(self):
        """测试安装方式值"""
        assert CollectorInstallWay.BUILD_IN == 0
        assert CollectorInstallWay.ZIP_FILE == 1
        assert CollectorInstallWay.EXE_FILE == 2

    def test_install_way_is_int_enum(self):
        """测试安装方式是整数枚举"""
        assert isinstance(CollectorInstallWay.BUILD_IN.value, int)


# =============================================================================
# 模型测试
# =============================================================================


class TestUptimeCheckNode:
    """UptimeCheckNode模型测试"""

    def test_create_node(self, db):
        """测试创建拨测节点"""
        node = UptimeCheckNodeModel.objects.create(
            bk_tenant_id="default",
            bk_biz_id=2,
            is_common=False,
            ip_type=4,
            name="测试节点",
            ip="192.168.1.1",
            bk_host_id=12345,
            plat_id=0,
            location={"country": "中国", "city": "北京"},
            carrieroperator="电信",
        )

        assert node.pk is not None
        assert node.bk_tenant_id == "default"
        assert node.bk_biz_id == 2
        assert node.is_common is False
        assert node.ip_type == 4
        assert node.name == "测试节点"
        assert node.ip == "192.168.1.1"
        assert node.bk_host_id == 12345
        assert node.plat_id == 0
        assert node.location["city"] == "北京"
        assert str(node) == "拨测节点(测试节点)"

    def test_create_common_node(self, db):
        """测试创建通用节点"""
        node = UptimeCheckNodeModel.objects.create(
            bk_tenant_id="default",
            bk_biz_id=0,
            is_common=True,
            biz_scope=[2, 3, 4],
            ip_type=4,
            name="通用节点",
            ip="10.0.0.1",
        )

        assert node.is_common is True
        assert node.biz_scope == [2, 3, 4]

    def test_node_ip_type_choices(self):
        """测试IP类型选项"""
        assert len(NODE_IP_TYPE_CHOICES) == 3
        assert NODE_IP_TYPE_DICT[0] == "all"
        assert NODE_IP_TYPE_DICT[4] == "IPv4"
        assert NODE_IP_TYPE_DICT[6] == "IPv6"


class TestUptimeCheckTask:
    """UptimeCheckTask模型测试"""

    def test_create_http_task(self, db, sample_node):
        """测试创建HTTP拨测任务"""
        task = UptimeCheckTaskModel.objects.create(
            bk_biz_id=2,
            name="HTTP拨测任务",
            protocol=UptimeCheckTaskModel.Protocol.HTTP,
            check_interval=5,
            status=UptimeCheckTaskStatus.NEW_DRAFT.value,
            config={
                "url_list": ["https://www.example.com"],
                "method": "GET",
                "timeout": 3000,
            },
        )
        task.nodes.add(sample_node)

        assert task.pk is not None
        assert task.bk_biz_id == 2
        assert task.name == "HTTP拨测任务"
        assert task.protocol == "HTTP"
        assert task.check_interval == 5
        assert task.status == UptimeCheckTaskStatus.NEW_DRAFT.value
        assert task.nodes.count() == 1
        assert str(task) == "拨测任务(HTTP拨测任务)"

    def test_create_tcp_task(self, db):
        """测试创建TCP拨测任务"""
        task = UptimeCheckTaskModel.objects.create(
            bk_biz_id=2,
            name="TCP拨测任务",
            protocol=UptimeCheckTaskModel.Protocol.TCP,
            check_interval=1,
            config={
                "ip_list": ["192.168.1.100"],
                "port": 80,
                "timeout": 3000,
            },
        )

        assert task.protocol == "TCP"
        assert task.config["port"] == 80

    def test_create_udp_task(self, db):
        """测试创建UDP拨测任务"""
        task = UptimeCheckTaskModel.objects.create(
            bk_biz_id=2,
            name="UDP拨测任务",
            protocol=UptimeCheckTaskModel.Protocol.UDP,
            config={
                "ip_list": ["192.168.1.100"],
                "port": 53,
                "request": "test",
                "response": "test",
            },
        )

        assert task.protocol == "UDP"

    def test_create_icmp_task(self, db):
        """测试创建ICMP拨测任务"""
        task = UptimeCheckTaskModel.objects.create(
            bk_biz_id=2,
            name="ICMP拨测任务",
            protocol=UptimeCheckTaskModel.Protocol.ICMP,
            config={
                "ip_list": ["192.168.1.100"],
                "max_rtt": 3000,
                "total_num": 3,
                "size": 56,
            },
        )

        assert task.protocol == "ICMP"

    def test_task_full_table_name(self, db):
        """测试获取完整结果表名称"""
        task = UptimeCheckTaskModel.objects.create(
            bk_biz_id=2,
            name="测试任务",
            protocol=UptimeCheckTaskModel.Protocol.HTTP,
        )

        assert task.full_table_name == "2_uptimecheck_http"

    def test_task_temp_conf_name(self, db):
        """测试获取临时配置文件名"""
        task = UptimeCheckTaskModel.objects.create(
            bk_biz_id=2,
            name="测试任务",
            protocol=UptimeCheckTaskModel.Protocol.TCP,
        )

        assert task.temp_conf_name == f"2_{task.pk}_uptimecheckbeat.yml"

    def test_task_status_choices(self):
        """测试任务状态选项"""
        assert UptimeCheckTaskStatus.NEW_DRAFT.value == "new_draft"
        assert UptimeCheckTaskStatus.RUNNING.value == "running"
        assert UptimeCheckTaskStatus.STOPED.value == "stoped"
        assert UptimeCheckTaskStatus.STARTING.value == "starting"
        assert UptimeCheckTaskStatus.STOPING.value == "stoping"
        assert UptimeCheckTaskStatus.START_FAILED.value == "start_failed"
        assert UptimeCheckTaskStatus.STOP_FAILED.value == "stop_failed"

    def test_task_protocol_choices(self):
        """测试协议类型选项"""
        assert UptimeCheckTaskModel.Protocol.TCP == "TCP"
        assert UptimeCheckTaskModel.Protocol.UDP == "UDP"
        assert UptimeCheckTaskModel.Protocol.HTTP == "HTTP"
        assert UptimeCheckTaskModel.Protocol.ICMP == "ICMP"


class TestUptimeCheckTaskSubscription:
    """UptimeCheckTaskSubscription模型测试"""

    def test_create_subscription(self, db):
        """测试创建订阅关系"""
        subscription = UptimeCheckTaskSubscription.objects.create(
            uptimecheck_id=1,
            subscription_id=12345,
            bk_biz_id=2,
        )

        assert subscription.pk is not None
        assert subscription.uptimecheck_id == 1
        assert subscription.subscription_id == 12345
        assert subscription.bk_biz_id == 2

    def test_subscription_unique_constraint(self, db):
        """测试订阅关系唯一约束"""
        UptimeCheckTaskSubscription.objects.create(
            uptimecheck_id=1,
            subscription_id=12345,
            bk_biz_id=2,
        )

        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            UptimeCheckTaskSubscription.objects.create(
                uptimecheck_id=1,
                subscription_id=67890,
                bk_biz_id=2,
            )


class TestUptimeCheckGroup:
    """UptimeCheckGroup模型测试"""

    @pytest.fixture
    def sample_tasks(self, db):
        """创建示例任务"""
        task1 = UptimeCheckTaskModel.objects.create(
            bk_biz_id=2,
            name="任务1",
            protocol=UptimeCheckTaskModel.Protocol.HTTP,
            status=UptimeCheckTaskStatus.RUNNING.value,
        )
        task2 = UptimeCheckTaskModel.objects.create(
            bk_biz_id=2,
            name="任务2",
            protocol=UptimeCheckTaskModel.Protocol.TCP,
            status=UptimeCheckTaskStatus.STOPED.value,
        )
        task3 = UptimeCheckTaskModel.objects.create(
            bk_biz_id=2,
            name="任务3",
            protocol=UptimeCheckTaskModel.Protocol.ICMP,
            status=UptimeCheckTaskStatus.RUNNING.value,
        )
        return [task1, task2, task3]

    def test_create_group(self, db, sample_tasks):
        """测试创建拨测分组"""
        group = UptimeCheckGroupModel.objects.create(name="测试分组", bk_biz_id=2)
        group.tasks.add(*sample_tasks)

        assert group.pk is not None
        assert group.name == "测试分组"
        assert group.bk_biz_id == 2
        assert group.tasks.count() == 3
        assert str(group) == "拨测分组(测试分组)"


class TestUptimeCheckTaskCollectorLog:
    """UptimeCheckTaskCollectorLog模型测试"""

    def test_create_collector_log(self, db):
        """测试创建采集日志"""
        log = UptimeCheckTaskCollectorLog.objects.create(
            task_id=1,
            error_log={"message": "连接超时", "code": "TIMEOUT"},
            is_deleted=False,
            subscription_id=12345,
            nodeman_task_id=67890,
        )

        assert log.pk is not None
        assert log.task_id == 1
        assert log.error_log["message"] == "连接超时"
        assert log.is_deleted is False
        assert log.subscription_id == 12345
        assert log.nodeman_task_id == 67890
