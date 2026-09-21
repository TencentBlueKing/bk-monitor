"""
拨测模块服务测试

测试内容:
- ConfigGeneratorService: 配置生成器服务
- DataAccessService: 数据接入服务
- GetHTTPConfig: HTTP配置辅助类
- url_join_args: URL参数拼接函数
"""

from base64 import b64decode
from unittest.mock import MagicMock, patch

import pytest

from bk_monitor_base.domains.uptime_check.constants import DEFAULT_MAX_TIMEOUT, UptimeCheckProtocol
from bk_monitor_base.domains.uptime_check.services.config_generator import ConfigGeneratorService
from bk_monitor_base.domains.uptime_check.services.data_access import DataAccessService
from bk_monitor_base.domains.uptime_check.services.http_helper import GetHTTPConfig, url_join_args
from bk_monitor_base.domains.uptime_check.services.subscription import SubscriptionService
from bk_monitor_base.infras.third_party_api.errors import BkApiError

pytestmark = pytest.mark.django_db(databases=["default"])

# =============================================================================
# ConfigGeneratorService 测试
# =============================================================================


class TestConfigGeneratorService:
    """ConfigGeneratorService测试"""

    @pytest.fixture
    def config_generator(self):
        """创建配置生成器实例"""
        return ConfigGeneratorService()

    def test_init_with_default_template_dir(self, config_generator):
        """测试使用默认模板目录初始化"""
        assert config_generator.template_dir.exists()
        assert config_generator.template_dir.name == "templates"

    def test_init_with_custom_template_dir(self, tmp_path):
        """测试使用自定义模板目录初始化"""
        generator = ConfigGeneratorService(template_dir=tmp_path)
        assert generator.template_dir == tmp_path

    def test_template_map(self, config_generator):
        """测试协议与模板文件映射"""
        assert UptimeCheckProtocol.HTTP in config_generator.TEMPLATE_MAP
        assert UptimeCheckProtocol.TCP in config_generator.TEMPLATE_MAP
        assert UptimeCheckProtocol.UDP in config_generator.TEMPLATE_MAP
        assert UptimeCheckProtocol.ICMP in config_generator.TEMPLATE_MAP

    def test_default_dataid_map(self, config_generator):
        """测试协议与默认DataID映射"""
        assert config_generator.DEFAULT_DATAID_MAP[UptimeCheckProtocol.HTTP] == 1011
        assert config_generator.DEFAULT_DATAID_MAP[UptimeCheckProtocol.TCP] == 1009
        assert config_generator.DEFAULT_DATAID_MAP[UptimeCheckProtocol.UDP] == 1010
        assert config_generator.DEFAULT_DATAID_MAP[UptimeCheckProtocol.ICMP] == 1100003


class TestRenderTemplate:
    """测试模板渲染功能"""

    @pytest.fixture
    def config_generator(self):
        return ConfigGeneratorService()

    def test_render_template_file_not_found(self, config_generator):
        """测试渲染不存在的模板文件"""
        with pytest.raises(FileNotFoundError):
            config_generator.render_template("nonexistent.tpl", {})

    def test_render_http_template(self, config_generator):
        """测试渲染HTTP模板"""
        context = {
            "data_id": 1011,
            "max_timeout": "30000ms",
            "tasks": [{"task_id": 1, "bk_biz_id": 2, "period": "60s"}],
        }

        result = config_generator.render_template(
            "bkmonitorbeat_http_global.conf.tpl",
            context,
        )

        assert "1011" in result
        assert "30000ms" in result


class TestGenerateConfig:
    """测试配置生成功能"""

    @pytest.fixture
    def config_generator(self):
        return ConfigGeneratorService()

    def test_generate_http_config(self, config_generator):
        """测试生成HTTP配置"""
        config = {
            "period": 60,
            "url_list": ["https://www.example.com"],
            "method": "GET",
        }

        result = config_generator.generate_config(
            protocol="HTTP",
            config=config,
            data_id=1011,
        )

        assert isinstance(result, str)
        assert "1011" in result

    def test_generate_tcp_config(self, config_generator):
        """测试生成TCP配置"""
        config = {
            "period": 60,
            "ip_list": ["192.168.1.1"],
            "port": 80,
        }

        result = config_generator.generate_config(
            protocol="TCP",
            config=config,
            data_id=1009,
        )

        assert isinstance(result, str)
        assert "1009" in result

    def test_generate_config_with_default_data_id(self, config_generator):
        """测试使用默认DataID生成配置"""
        config = {"period": 60}

        result = config_generator.generate_config(
            protocol="HTTP",
            config=config,
        )

        assert "1011" in result

    def test_generate_config_unsupported_protocol(self, config_generator):
        """测试不支持的协议类型"""
        with pytest.raises(ValueError):
            config_generator.generate_config(
                protocol="INVALID",
                config={},
            )


class TestGenerateSubConfig:
    """测试生成beat任务配置"""

    @pytest.fixture
    def config_generator(self):
        return ConfigGeneratorService()

    def test_generate_tcp_sub_config(self, config_generator):
        """测试生成TCP子配置"""
        config = {
            "period": 60,
            "ip_list": ["192.168.1.1"],
            "port": 80,
            "timeout": 3000,
            "response": "OK",
            "response_format": "in",
        }

        tasks = config_generator.generate_sub_config(
            protocol=UptimeCheckProtocol.TCP,
            config=config,
            task_id=1,
            bk_biz_id=2,
        )

        assert len(tasks) == 1
        task = tasks[0]
        assert task["task_id"] == 1
        assert task["bk_biz_id"] == 2
        assert task["period"] == "60s"
        assert task["target_port"] == 80
        assert "ms" in task["available_duration"]
        assert "ms" in task["timeout"]

    def test_generate_udp_sub_config(self, config_generator):
        """测试生成UDP子配置"""
        config = {
            "period": 60,
            "ip_list": ["192.168.1.1"],
            "port": 53,
            "request": "test",
            "response": "test",
            "request_format": "hex",
            "response_format": "hex|eq",
            "wait_empty_response": True,
        }

        tasks = config_generator.generate_sub_config(
            protocol=UptimeCheckProtocol.UDP,
            config=config,
            task_id=1,
            bk_biz_id=2,
        )

        assert len(tasks) == 1
        task = tasks[0]
        assert task["target_port"] == 53
        assert task["request_format"] == "hex"
        assert task["response_format"] == "hex|eq"
        assert task["wait_empty_response"] == "true"

    @patch("bk_monitor_base.domains.uptime_check.services.http_helper.GetHTTPConfig")
    def test_generate_http_sub_config(self, mock_http_config, config_generator):
        """测试生成HTTP子配置"""
        mock_instance = MagicMock()
        mock_instance.get_body.return_value = ""
        mock_instance.get_authorization.return_value = {}
        mock_http_config.return_value = mock_instance

        config = {
            "period": 60,
            "url_list": ["https://www.example.com"],
            "method": "GET",
            "timeout": 3000,
            "headers": [],
            "body": {"data_type": "default"},
            "authorize": {},
        }

        tasks = config_generator.generate_sub_config(
            protocol=UptimeCheckProtocol.HTTP,
            config=config,
            task_id=1,
            bk_biz_id=2,
        )

        assert len(tasks) == 1
        task = tasks[0]
        assert task["task_id"] == 1
        assert task["bk_biz_id"] == 2
        assert "steps" in task
        assert len(task["steps"]) == 1
        assert task["steps"][0]["method"] == "GET"

    def test_generate_icmp_sub_config(self, config_generator):
        """测试生成ICMP子配置"""
        config = {
            "period": 60,
            "ip_list": ["192.168.1.1"],
            "url_list": ["www.example.com"],
            "max_rtt": 3000,
            "total_num": 3,
            "size": 56,
        }

        tasks = config_generator.generate_sub_config(
            protocol=UptimeCheckProtocol.ICMP,
            config=config,
            task_id=1,
            bk_biz_id=2,
        )

        assert len(tasks) == 1
        task = tasks[0]
        assert task["size"] == 56
        assert task["total_num"] == 3
        assert task["max_rtt"] == "3000ms"
        assert len(task["target_host_list"]) == 2

    def test_generate_sub_config_test_mode(self, config_generator):
        """测试测试模式生成配置"""
        config = {
            "period": 60,
            "ip_list": ["192.168.1.1"],
            "port": 80,
        }

        tasks = config_generator.generate_sub_config(
            protocol=UptimeCheckProtocol.TCP,
            config=config,
            task_id=1,
            bk_biz_id=2,
            test=True,
        )

        assert len(tasks) == 1
        task = tasks[0]
        assert task["task_id"] == 0
        assert task["bk_biz_id"] == 0

    def test_generate_sub_config_with_labels(self, config_generator):
        """测试带标签的配置生成"""
        config = {
            "period": 60,
            "ip_list": ["192.168.1.1"],
            "port": 80,
        }
        labels = {"env": "test", "app": "demo"}

        tasks = config_generator.generate_sub_config(
            protocol=UptimeCheckProtocol.TCP,
            config=config,
            task_id=1,
            bk_biz_id=2,
            labels=labels,
        )

        assert tasks[0]["labels"] == labels

    def test_generate_sub_config_empty_config(self, config_generator):
        """测试空配置应该抛出ValueError"""
        with pytest.raises(ValueError, match="任务配置为空"):
            config_generator.generate_sub_config(
                protocol=UptimeCheckProtocol.TCP,
                config={},
                task_id=None,  # 不传task_id避免数据库查询
                bk_biz_id=2,
            )


class TestEncodeHelpers:
    """测试编码辅助方法"""

    @pytest.fixture
    def config_generator(self):
        return ConfigGeneratorService()

    def test_add_escape_normal_string(self, config_generator):
        """测试普通字符串转义"""
        result = config_generator.add_escape("hello")
        assert result == "'hello'"

    def test_add_escape_with_single_quote(self, config_generator):
        """测试带单引号的字符串转义"""
        result = config_generator.add_escape("it's")
        assert result == "'it''s'"

    def test_add_escape_empty_string(self, config_generator):
        """测试空字符串转义"""
        result = config_generator.add_escape("")
        assert result == ""

    @patch.object(ConfigGeneratorService, "add_escape")
    def test_encode_data_with_prefix_empty(self, mock_add_escape, config_generator):
        """测试空数据编码"""
        mock_add_escape.return_value = ""
        config_generator.encode_data_with_prefix("")
        mock_add_escape.assert_called_once_with("")

    @patch("bk_monitor_base.domains.uptime_check.services.config_generator.get_config")
    def test_encode_data_with_prefix_no_trigger_chars(self, mock_get_config, config_generator):
        """测试没有触发字符时（base64_encode_trigger_chars 为空）走转义路径"""
        mock_config = MagicMock()
        mock_config.domains.uptime_check.base64_encode_trigger_chars = []
        mock_get_config.return_value = mock_config

        result = config_generator.encode_data_with_prefix("hello")
        assert result == "'hello'"

    @patch("bk_monitor_base.domains.uptime_check.services.config_generator.get_config")
    def test_encode_data_with_prefix_with_trigger_chars(self, mock_get_config, config_generator):
        """测试包含触发字符时走 UptimeCheckConfig.base64_encode_trigger_chars 触发的 Base64 编码"""
        mock_config = MagicMock()
        mock_config.domains.uptime_check.base64_encode_trigger_chars = ["\n", "\r", "'"]
        mock_get_config.return_value = mock_config

        result = config_generator.encode_data_with_prefix("hello\nworld")

        assert result.startswith("base64://")


# =============================================================================
# SubscriptionService 测试
# =============================================================================


class TestSubscriptionService:
    """SubscriptionService测试"""

    @pytest.fixture
    def subscription_service(self):
        """创建订阅服务实例"""
        return SubscriptionService(bk_biz_id=2)

    @patch("bk_monitor_base.domains.uptime_check.services.config_generator.ConfigGeneratorService.generate_sub_config")
    def test_generate_subscription_config_keep_legacy_context(self, mock_generate_sub_config, subscription_service):
        """测试订阅上下文字段与历史逻辑保持一致"""
        mock_generate_sub_config.return_value = [{"task_id": 1001, "labels": {"env": "prod"}}]
        config = {
            "period": 60,
            "timeout": 3000,
            "port": 8080,
            "request": "ping",
            "response": "pong",
            "response_format": "nin",
        }
        nodes = [
            {"bk_biz_id": 2, "bk_host_id": 101, "ip": "127.0.0.1", "plat_id": 0},
            {"bk_biz_id": 3, "bk_host_id": 102, "ip": "127.0.0.2", "plat_id": 0},
        ]

        configs = subscription_service.generate_subscription_config(
            task_id=1001,
            protocol=UptimeCheckProtocol.TCP,
            config=config,
            nodes=nodes,
            data_id=1009,
            labels={"env": "prod"},
            task_group_id="1,2",
            use_custom_report=False,
        )

        assert len(configs) == 2
        assert {item["scope"]["bk_biz_id"] for item in configs} == {2, 3}

        for item in configs:
            context = item["steps"][0]["params"]["context"]
            assert context["bk_biz_id"] == 2
            assert context["max_timeout"] == f"{DEFAULT_MAX_TIMEOUT}ms"
            assert context["timeout"] == f"{DEFAULT_MAX_TIMEOUT}ms"
            assert context["period"] == "60s"
            assert context["available_duration"] == "3000ms"
            assert context["target_port"] == 8080
            assert context["request"] == "'ping'"
            assert context["response"] == "'pong'"
            assert context["response_format"] == "nin"
            assert context["labels"]["$body"] == {"task_group_id": "1,2"}

    @patch("bk_monitor_base.domains.uptime_check.services.config_generator.ConfigGeneratorService.generate_sub_config")
    def test_generate_subscription_config_timeout_overflow(self, mock_generate_sub_config, subscription_service):
        """测试超时超过阈值时按历史规则扩容"""
        mock_generate_sub_config.return_value = [{"task_id": 1002}]
        config = {"period": 60, "timeout": 20001}
        nodes = [{"bk_biz_id": 2, "bk_host_id": 103, "ip": "127.0.0.3", "plat_id": 0}]

        configs = subscription_service.generate_subscription_config(
            task_id=1002,
            protocol=UptimeCheckProtocol.HTTP,
            config=config,
            nodes=nodes,
            data_id=1011,
        )

        context = configs[0]["steps"][0]["params"]["context"]
        assert context["max_timeout"] == "25001ms"
        assert context["timeout"] == "25001ms"
        assert context["available_duration"] == "20001ms"

    @patch("bk_monitor_base.domains.uptime_check.services.config_generator.ConfigGeneratorService.generate_sub_config")
    def test_generate_subscription_config_icmp_fields(self, mock_generate_sub_config, subscription_service):
        """测试ICMP协议附加字段与node_id注入"""
        mock_generate_sub_config.return_value = [{"task_id": 1003}]
        config = {"period": 60, "timeout": 3000, "size": 128, "total_num": 5, "max_rtt": 4500}
        nodes = [{"bk_biz_id": 2, "bk_host_id": 104, "ip": "127.0.0.4", "plat_id": 0}]

        configs = subscription_service.generate_subscription_config(
            task_id=1003,
            protocol=UptimeCheckProtocol.ICMP,
            config=config,
            nodes=nodes,
            data_id=1100003,
            task_group_id="9",
        )

        context = configs[0]["steps"][0]["params"]["context"]
        assert context["size"] == 128
        assert context["total_num"] == 5
        assert context["max_rtt"] == "4500ms"
        assert context["target_port"] is None
        assert context["request"] == ""
        assert context["response"] == ""
        assert "node_id" in context["labels"]["$body"]
        assert context["labels"]["$body"]["task_group_id"] == "9"


# =============================================================================
# DataAccessService 测试
# =============================================================================


class TestDataAccessService:
    """DataAccessService测试"""

    @pytest.fixture
    def data_access_service(self):
        return DataAccessService(
            bk_tenant_id="default",
            bk_biz_id=2,
            protocol="HTTP",
        )

    def test_init(self, data_access_service):
        """测试初始化"""
        assert data_access_service.bk_tenant_id == "default"
        assert data_access_service.bk_biz_id == 2
        assert data_access_service.protocol == "HTTP"

    def test_db_name(self, data_access_service):
        """测试数据库名称属性"""
        assert data_access_service.db_name == "uptimecheck_http_2"

    def test_data_label(self, data_access_service):
        """测试数据标签属性"""
        assert data_access_service.data_label == "uptimecheck_http"

    def test_default_dataid_map(self):
        """测试默认DataID映射"""
        assert DataAccessService.DATAID_MAP[UptimeCheckProtocol.HTTP] == 1011
        assert DataAccessService.DATAID_MAP[UptimeCheckProtocol.TCP] == 1009
        assert DataAccessService.DATAID_MAP[UptimeCheckProtocol.UDP] == 1010
        assert DataAccessService.DATAID_MAP[UptimeCheckProtocol.ICMP] == 1100003


class TestUseCustomReport:
    """测试是否使用自定义上报"""

    @pytest.fixture
    def data_access_service(self):
        return DataAccessService(
            bk_tenant_id="default",
            bk_biz_id=2,
            protocol="HTTP",
        )

    def test_use_custom_report_true(self, data_access_service):
        """测试使用独立DataID"""
        assert data_access_service.use_custom_report(independent=True) is True

    def test_use_custom_report_false(self, data_access_service):
        """测试不使用独立DataID"""
        assert data_access_service.use_custom_report(independent=False) is False


class TestGetDataId:
    """测试获取DataID"""

    @pytest.fixture
    def data_access_service(self):
        return DataAccessService(
            bk_tenant_id="default",
            bk_biz_id=2,
            protocol="HTTP",
        )

    def test_get_default_data_id(self, data_access_service):
        """测试获取默认DataID"""
        use_custom, data_id = data_access_service.get_data_id(independent=False)

        assert use_custom is False
        assert data_id == 1011

    @patch("bk_monitor_base.domains.uptime_check.services.data_access.api.metadata.get_data_source")
    def test_get_custom_data_id(self, mock_get_data_source, data_access_service):
        """测试获取自定义DataID"""
        mock_get_data_source.return_value = {"bk_data_id": 99999}

        use_custom, data_id = data_access_service.get_data_id(independent=True)

        assert use_custom is True
        assert data_id == 99999
        mock_get_data_source.assert_called_once_with(
            bk_tenant_id="default",
            data_name="uptimecheck_http_2",
        )


class TestCreateDataId:
    """测试创建DataID"""

    @pytest.fixture
    def data_access_service(self):
        return DataAccessService(
            bk_tenant_id="default",
            bk_biz_id=2,
            protocol="HTTP",
        )

    @patch("bk_monitor_base.domains.uptime_check.services.data_access.api.metadata.get_data_source")
    def test_create_data_id_already_exists(self, mock_get_data_source, data_access_service):
        """测试DataID已存在时直接返回"""
        mock_get_data_source.return_value = {"bk_data_id": 88888}

        result = data_access_service.create_data_id()

        assert result == 88888

    @patch("bk_monitor_base.domains.uptime_check.services.data_access.api.metadata.create_data_source")
    @patch("bk_monitor_base.domains.uptime_check.services.data_access.api.metadata.get_data_source")
    def test_create_data_id_new(self, mock_get_data_source, mock_create_data_source, data_access_service):
        """测试创建新DataID"""
        mock_get_data_source.side_effect = Exception("数据源不存在")
        mock_create_data_source.return_value = 77777

        result = data_access_service.create_data_id()

        assert result == 77777
        mock_create_data_source.assert_called_once()

        call_kwargs = mock_create_data_source.call_args[1]
        assert call_kwargs["bk_tenant_id"] == "default"
        assert call_kwargs["data_name"] == "uptimecheck_http_2"
        assert call_kwargs["bk_biz_id"] == 2


class TestAccess:
    """测试数据接入"""

    @pytest.fixture
    def data_access_service(self):
        return DataAccessService(
            bk_tenant_id="default",
            bk_biz_id=2,
            protocol="HTTP",
        )

    @patch("bk_monitor_base.domains.uptime_check.services.data_access.api.metadata.create_time_series_group")
    @patch(
        "bk_monitor_base.domains.uptime_check.services.data_access.DataAccessService.get_data_id",
        side_effect=BkApiError(
            module="metadata", action="create_data_source", method="POST", url="", message="", status_code=500
        ),
    )
    @patch("bk_monitor_base.domains.uptime_check.services.data_access.DataAccessService.create_data_id")
    def test_access_new(self, mock_get_data_id, mock_create_data_id, mock_create_ts_group, data_access_service, db):
        """测试新数据接入"""
        mock_create_data_id.return_value = 66666

        data_access_service.access()

        mock_create_data_id.assert_called_once()
        mock_create_ts_group.assert_called_once()

    @patch("bk_monitor_base.domains.uptime_check.services.data_access.api.metadata.create_time_series_group")
    @patch(
        "bk_monitor_base.domains.uptime_check.services.data_access.DataAccessService.get_data_id",
        return_value=(True, 66666),
    )
    @patch("bk_monitor_base.domains.uptime_check.services.data_access.DataAccessService.create_data_id")
    def test_access_already_done(self, mock_create_data_id, mock_create_ts_group, data_access_service, db):
        """测试已完成数据接入（幂等性）"""

        data_access_service.access()

        mock_create_data_id.assert_not_called()
        mock_create_ts_group.assert_not_called()


class TestGetOrCreateDataId:
    """测试获取或创建DataID"""

    @pytest.fixture
    def data_access_service(self):
        return DataAccessService(
            bk_tenant_id="default",
            bk_biz_id=2,
            protocol="HTTP",
        )

    def test_get_or_create_default_data_id(self, data_access_service):
        """测试获取默认DataID（不使用独立DataID）"""
        use_custom, data_id = data_access_service.get_or_create_data_id(independent=False)

        assert use_custom is False
        assert data_id == 1011

    @patch("bk_monitor_base.domains.uptime_check.services.data_access.DataAccessService.get_data_id")
    def test_get_or_create_custom_data_id(self, mock_get_data_id, data_access_service):
        """测试获取或创建自定义DataID"""
        mock_get_data_id.return_value = (True, 44444)

        use_custom, data_id = data_access_service.get_or_create_data_id(independent=True)

        assert use_custom is True
        assert data_id == 44444
        mock_get_data_id.assert_called_once_with(independent=True)


class TestDifferentProtocols:
    """测试不同协议的DataID"""

    def test_tcp_default_data_id(self):
        """测试TCP默认DataID"""
        service = DataAccessService(
            bk_tenant_id="default",
            bk_biz_id=2,
            protocol="TCP",
        )

        use_custom, data_id = service.get_or_create_data_id(independent=False)

        assert data_id == 1009

    def test_udp_default_data_id(self):
        """测试UDP默认DataID"""
        service = DataAccessService(
            bk_tenant_id="default",
            bk_biz_id=2,
            protocol="UDP",
        )

        use_custom, data_id = service.get_or_create_data_id(independent=False)

        assert data_id == 1010

    def test_icmp_default_data_id(self):
        """测试ICMP默认DataID"""
        service = DataAccessService(
            bk_tenant_id="default",
            bk_biz_id=2,
            protocol="ICMP",
        )

        use_custom, data_id = service.get_or_create_data_id(independent=False)

        assert data_id == 1100003

    def test_db_name_different_protocols(self):
        """测试不同协议的数据库名称"""
        tcp_service = DataAccessService("default", 2, "TCP")
        udp_service = DataAccessService("default", 2, "UDP")

        assert tcp_service.db_name == "uptimecheck_tcp_2"
        assert udp_service.db_name == "uptimecheck_udp_2"


# =============================================================================
# HTTP Helper 测试
# =============================================================================


class TestGetHTTPConfig:
    """GetHTTPConfig测试"""

    def test_init_with_headers(self):
        """测试带请求头初始化"""
        headers = {"Content-Type": "application/json"}
        config = GetHTTPConfig(headers=headers)

        assert config.headers == headers

    def test_init_without_headers(self):
        """测试不带请求头初始化"""
        config = GetHTTPConfig()

        assert config.headers == {}


class TestGetAuthorization:
    """测试HTTP认证处理"""

    def test_basic_auth(self):
        """测试HTTP基础认证"""
        config = GetHTTPConfig()
        authorize = {
            "auth_type": "basic_auth",
            "auth_config": {"username": "admin", "password": "password123"},
        }

        headers = config.get_authorization(authorize)

        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")
        encoded_part = headers["Authorization"].replace("Basic ", "")
        decoded = b64decode(encoded_part).decode("utf-8")
        assert decoded == "admin:password123"

    def test_bearer_token(self):
        """测试Bearer Token认证"""
        config = GetHTTPConfig()
        authorize = {
            "auth_type": "bearer_token",
            "auth_config": {"token": "my-secret-token"},
        }

        headers = config.get_authorization(authorize)

        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer my-secret-token"

    def test_no_auth(self):
        """测试无认证"""
        config = GetHTTPConfig()
        authorize = {}

        headers = config.get_authorization(authorize)

        assert "Authorization" not in headers

    def test_unknown_auth_type(self):
        """测试未知认证类型"""
        config = GetHTTPConfig()
        authorize = {"auth_type": "unknown", "auth_config": {}}

        headers = config.get_authorization(authorize)

        assert "Authorization" not in headers


class TestGetBody:
    """测试HTTP请求体处理"""

    def test_default_body(self):
        """测试默认请求体（空）"""
        config = GetHTTPConfig()
        body = {"data_type": "default"}

        result = config.get_body(body)

        assert result == ""

    def test_raw_json_body(self):
        """测试raw JSON请求体"""
        config = GetHTTPConfig()
        body = {
            "data_type": "raw",
            "content_type": "json",
            "content": '{"key": "value"}',
        }

        result = config.get_body(body)

        assert result == '{"key": "value"}'
        assert config.headers["Content-Type"] == "application/json"

    def test_raw_text_body(self):
        """测试raw文本请求体"""
        config = GetHTTPConfig()
        body = {
            "data_type": "raw",
            "content_type": "text",
            "content": "Hello World",
        }

        result = config.get_body(body)

        assert result == "Hello World"
        assert config.headers["Content-Type"] == "text/plain"

    def test_form_data_body(self):
        """测试form-data请求体"""
        config = GetHTTPConfig()
        body = {
            "data_type": "form_data",
            "params": [
                {"key": "name", "value": "test", "is_enabled": True},
                {"key": "age", "value": "18", "is_enabled": True},
                {"key": "disabled", "value": "no", "is_enabled": False},
            ],
        }

        result = config.get_body(body)

        assert "name=test" in result
        assert "age=18" in result
        assert "disabled" not in result

    def test_x_www_form_urlencoded_body(self):
        """测试x-www-form-urlencoded请求体"""
        config = GetHTTPConfig()
        body = {
            "data_type": "x_www_form_urlencoded",
            "params": [
                {"key": "username", "value": "admin", "is_enabled": True},
                {"key": "password", "value": "secret", "is_enabled": True},
            ],
        }

        result = config.get_body(body)

        assert "username=admin" in result
        assert "password=secret" in result
        assert config.headers["Content-Type"] == "application/x-www-form-urlencoded;charset=utf-8"

    def test_empty_body(self):
        """测试空请求体"""
        config = GetHTTPConfig()

        result = config.get_body({})

        assert result == ""

    def test_none_body(self):
        """测试None请求体"""
        config = GetHTTPConfig()

        result = config.get_body(None)

        assert result == ""


class TestUrlJoinArgs:
    """测试URL参数拼接"""

    def test_url_without_params(self):
        """测试无参数的URL"""
        url_list = ["http://example.com"]

        result = url_join_args(url_list)

        assert result == ["http://example.com"]

    def test_url_with_query_dict(self):
        """测试带query字典的URL"""
        url_list = ["http://example.com"]
        query = {"key": "value"}

        result = url_join_args(url_list, query)

        assert result == ["http://example.com?key=value"]

    def test_url_ending_with_question_mark(self):
        """测试以问号结尾的URL"""
        url_list = ["http://example.com?"]
        query = {"key": "value"}

        result = url_join_args(url_list, query)

        assert result == ["http://example.com?key=value"]

    def test_url_with_existing_params(self):
        """测试已有参数的URL"""
        url_list = ["http://example.com?a=1"]
        query = {"b": "2"}

        result = url_join_args(url_list, query)

        assert result == ["http://example.com?a=1?b=2"]

    def test_url_with_kwargs(self):
        """测试使用kwargs"""
        url_list = ["http://example.com"]

        result = url_join_args(url_list, key1="value1", key2="value2")

        assert "key1=value1" in result[0]
        assert "key2=value2" in result[0]

    def test_multiple_urls(self):
        """测试多个URL"""
        url_list = ["http://example1.com", "http://example2.com"]
        query = {"key": "value"}

        result = url_join_args(url_list, query)

        assert len(result) == 2
        assert result[0] == "http://example1.com?key=value"
        assert result[1] == "http://example2.com?key=value"

    def test_special_characters_encoding(self):
        """测试特殊字符编码"""
        url_list = ["http://example.com"]
        query = {"name": "测试", "space": "hello world"}

        result = url_join_args(url_list, query)

        assert "%E6%B5%8B%E8%AF%95" in result[0] or "测试" in result[0]
        assert "hello+world" in result[0] or "hello%20world" in result[0]


class TestEncodeBody:
    """测试请求体编码"""

    def test_encode_raw_body_with_dict_content(self):
        """测试编码字典类型的内容"""
        config = GetHTTPConfig()
        body = {
            "data_type": "raw",
            "content_type": "json",
            "content": {"key": "value"},
        }

        result = config.encode_body(body)

        assert '"key"' in result
        assert '"value"' in result

    def test_encode_body_empty_params(self):
        """测试编码空参数列表"""
        config = GetHTTPConfig()
        body = {
            "data_type": "x_www_form_urlencoded",
            "params": [],
        }

        result = config.encode_body(body)

        assert result == b""

    def test_encode_body_filtered_params(self):
        """测试编码过滤禁用参数后为空"""
        config = GetHTTPConfig()
        body = {
            "data_type": "x_www_form_urlencoded",
            "params": [{"key": "disabled", "value": "no", "is_enabled": False}],
        }

        result = config.encode_body(body)

        assert result == b""
