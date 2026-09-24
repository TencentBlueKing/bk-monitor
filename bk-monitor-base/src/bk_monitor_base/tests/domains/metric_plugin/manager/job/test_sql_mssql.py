from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from bk_monitor_base.domains.metric_plugin.errors import ParseOsTypeError
from bk_monitor_base.domains.metric_plugin.manager.base import OSType
from bk_monitor_base.domains.metric_plugin.manager.job.base import JobPluginParamsMode, JobPluginParamsType
from bk_monitor_base.domains.metric_plugin.manager.job.mssql import MSSQLPluginManager
from bk_monitor_base.domains.metric_plugin.mock_cmdb_tools import get_host_info, get_os_type_by_collect_host
from bk_monitor_base.metric_plugin import (
    MetricPlugin,
    MetricPluginMetricField,
    MetricPluginMetricGroup,
    MetricPluginParams,
    MetricPluginStatus,
    VersionTuple,
)


class TestMSSQLPluginManager:
    """测试 MSSQLPluginManager 类"""

    def setup_method(self):
        """设置测试数据"""
        self.plugin = MetricPlugin(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            id="test_plugin",
            type="job_mssql",
            name="测试MSSQL插件",
            description_md="测试插件文档",
            version=VersionTuple(1, 0),
            status=MetricPluginStatus.DEBUG,
            created_by="admin",
            updated_by="admin",
            define={
                "linux": {},  # 标记支持 linux
                "linux_aarch64": {},  # 标记支持 linux_aarch64
                "sql_content": [
                    {
                        "classification_id": "sql1",
                        "classification_name": "SQL-111",
                        "content": "SELECT 1 as metrics_test;",
                    }
                ],
            },
            params=[
                MetricPluginParams(
                    name="user",
                    type=JobPluginParamsType.TEXT,
                    mode=JobPluginParamsMode.OPT_CMD,
                    description="用户名",
                    default="root",
                    required=True,
                ),
                MetricPluginParams(
                    name="password",
                    type=JobPluginParamsType.PASSWORD,
                    mode=JobPluginParamsMode.OPT_CMD,
                    description="密码",
                    default="",
                    required=True,
                ),
                MetricPluginParams(
                    name="host",
                    type=JobPluginParamsType.TEXT,
                    mode=JobPluginParamsMode.OPT_CMD,
                    description="服务地址",
                    default="127.0.0.1",
                    required=True,
                ),
                MetricPluginParams(
                    name="port",
                    type=JobPluginParamsType.TEXT,
                    mode=JobPluginParamsMode.OPT_CMD,
                    description="端口",
                    default="3306",
                    required=True,
                ),
                MetricPluginParams(
                    name="name",
                    type=JobPluginParamsType.TEXT,
                    mode=JobPluginParamsMode.OPT_CMD,
                    description="实例名",
                    default="dbname",
                    required=True,
                ),
                MetricPluginParams(
                    name="time",
                    type=JobPluginParamsType.TEXT,
                    mode=JobPluginParamsMode.OPT_CMD,
                    description="单条SQL超时时间(s)",
                    default="60",
                    required=True,
                ),
                MetricPluginParams(
                    name="session",
                    type=JobPluginParamsType.TEXT,
                    mode=JobPluginParamsMode.OPT_CMD,
                    description="SQL采集并发数",
                    default="10",
                    required=True,
                ),
            ],
            # 此时处于调试阶段，无需关注 metrics 定义
            metrics=[],
        )
        self.plugin_manager = MSSQLPluginManager(self.plugin)

    def test_get_binary_path(self):
        """测试获取二进制文件路径"""
        # 测试 Linux 路径
        path_linux = self.plugin_manager.get_binary_path(OSType.LINUX)
        assert path_linux == "job_plugin/job_mssql/OracleUniversalPlugin"

        # 测试 Linux AArch64 路径
        path_arm = self.plugin_manager.get_binary_path(OSType.LINUX_AARCH64)
        assert path_arm == "job_plugin/job_mssql/OracleUniversalPlugin_arm"

        # 测试不支持的系统类型
        with pytest.raises(ParseOsTypeError):
            self.plugin_manager.get_binary_path(OSType.WINDOWS)

    def test_make_package(self, mocker: MockerFixture):
        """测试制作插件包"""
        # 模拟 _download_binary
        mock_download_path = Path("/tmp/mock_binary")
        mocker.patch.object(self.plugin_manager, "_download_binary", return_value=mock_download_path)

        # 模拟 _make_package
        mock_make_package = mocker.patch.object(
            self.plugin_manager, "_make_package", return_value=Path("/tmp/mock_pkg.tgz")
        )

        self.plugin_manager.make_package(is_compress=True)

        # 验证 _download_binary 被调用
        assert self.plugin_manager._download_binary.call_count == 2  # 支持 linux 和 linux_aarch64

        # 验证 _make_package 被调用
        mock_make_package.assert_called_once()
        assert mock_make_package.call_args.kwargs["is_compress"] is True
        assert "extra_files" in mock_make_package.call_args.kwargs

    def test_start_debug(self, mocker: MockerFixture):
        """测试启动调试"""
        # 模拟 JobMetricPluginDebugInst 构造函数
        mock_debug_inst = mocker.MagicMock()
        mock_debug_inst.id = 123
        mock_debug_inst.debug_params = {}

        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.job.base.JobMetricPluginDebugInst",
            return_value=mock_debug_inst,
        )

        # 模拟 JobMetricPluginDebugInst.get (用于 _start_debug)
        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.job.base.JobMetricPluginDebugInst.get",
            return_value=mock_debug_inst,
        )

        # 模拟 _generate_debug_yaml
        mocker.patch.object(self.plugin_manager, "_generate_debug_yaml", return_value="mock_config_path")

        # 模拟 submit_debug_task
        mock_submit_task = mocker.patch("bk_monitor_base.domains.metric_plugin.manager.job.base.submit_debug_task")

        # 模拟 parse_target_server
        mocker.patch.object(self.plugin_manager, "parse_target_server", return_value={"ip": "127.0.0.1"})

        # 模拟 make_package (因为 _start_debug 会调用它)
        mocker.patch.object(self.plugin_manager, "make_package", return_value=Path("/tmp/mock_pkg.tgz"))

        # 模拟 get_storage
        mock_storage = mocker.MagicMock()
        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.job.base.get_storage",
            return_value=mock_storage,
        )

        # 模拟 open
        mocker.patch("builtins.open", mocker.mock_open())

        # 模拟 os.path.basename, os.path.join
        mocker.patch("os.path.basename", side_effect=lambda p: Path(p).name)
        mocker.patch("os.path.join", side_effect=lambda *args: "/".join(args))

        collect_params = {"period": 60}
        plugin_params = {"user": "root"}
        collect_host = {"bk_host_id": 1, "bk_cloud_id": 0, "ip": "127.0.0.1"}  # 提供足够信息以解析 os_type
        operator = "admin"

        # 模拟 get_os_type_by_collect_host
        # 注意：需要 patch 函数被使用的位置（base.py），而不是定义的位置（mock_cmdb_tools.py）
        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.job.base.get_os_type_by_collect_host",
            return_value=OSType.LINUX,
        )

        # 模拟 _get_debug_os_target_path
        mocker.patch.object(self.plugin_manager, "_get_debug_os_target_path", return_value="/tmp/bk_monitor_debug/123")

        self.plugin_manager.start_debug(collect_params, plugin_params, collect_host, operator)

        # 验证 submit_debug_task 调用参数
        mock_submit_task.assert_called_once()
        call_args = mock_submit_task.call_args
        assert call_args[1]["debug_task_inst_id"] == 123
        context = call_args[1]["context"]
        assert context["target_server"] == {"ip": "127.0.0.1"}
        assert context["binary_path"] == "job_plugin/job_mssql/OracleUniversalPlugin"
        assert context["debug_yaml_file_path"] == "mock_config_path"
        assert context["target_path"] == "/tmp/bk_monitor_debug/123"

    def test_stop_debug(self, mocker: MockerFixture):
        """测试停止调试"""
        # 模拟 JobMetricPluginDebugInst.get
        mock_debug_inst = mocker.MagicMock()
        mock_debug_inst.debug_params = {"collect_host": {"bk_host_id": 1}}
        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.job.base.JobMetricPluginDebugInst.get",
            return_value=mock_debug_inst,
        )

        self.plugin_manager.stop_debug(123, "admin")

        # 验证状态更新
        assert mock_debug_inst.debug_status == "canceled"  # JobStatus.CANCELED assuming string or enum
        assert mock_debug_inst.updated_by == "admin"
        mock_debug_inst.save.assert_called_once()

    def test_generate_debug_yaml(self, mocker: MockerFixture):
        """测试生成调试 YAML 配置文件"""
        # 模拟 debug_inst
        mock_debug_inst = mocker.MagicMock()
        mock_debug_inst.id = 123
        mock_debug_inst.debug_params = {
            "plugin_params": {
                "user": "root",
                "password": "password",
                "host": "localhost",
                "port": 3306,
                "unknown_param": "value",  # 应该被过滤
            }
        }

        # 模拟 tempfile.mkdtemp
        mock_temp_dir = Path("/tmp/mock_temp")
        mocker.patch("tempfile.mkdtemp", return_value=str(mock_temp_dir))
        mocker.patch.object(Path, "mkdir")

        # 模拟 open
        mocker.patch("builtins.open", mocker.mock_open())

        # 模拟 yaml.safe_dump
        mock_yaml_dump = mocker.patch("yaml.safe_dump")

        # 模拟 storage
        mock_storage = mocker.MagicMock()
        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.job.base.get_storage",
            return_value=mock_storage,
        )

        remote_path = self.plugin_manager._generate_debug_yaml(mock_debug_inst)

        # 验证返回路径
        assert remote_path == "job_plugin/job_mssql/debug_123/sql_config.yml"

        # 验证 yaml dump 内容
        mock_yaml_dump.assert_called_once()
        dump_data = mock_yaml_dump.call_args[0][0]

        # 验证参数过滤
        assert "user" in dump_data
        assert "password" in dump_data
        assert "unknown_param" not in dump_data

        # 验证 sql_content
        assert "sql_content" in dump_data
        assert dump_data["sql_content"] == ["SELECT 1 as metrics_test;"]

    def test_get_debug_log(self, mocker: MockerFixture):
        """测试获取调试日志"""
        # 模拟 JobMetricPluginDebugInst.get
        mock_debug_inst = mocker.MagicMock()
        mock_debug_inst.id = 123
        mock_debug_inst.created_by = "admin"
        mock_debug_inst.debug_status = "success"
        mock_debug_inst.job_type = "job_mssql"
        mock_debug_inst.debug_params = {"collect_host": {"bk_host_id": 1}}
        mock_debug_inst.task_log = [
            {"task_step": "step1", "messages": "日志内容1"},
            {
                "task_step": "step2",
                "messages": "日志内容2",
                "log_content": "模拟作业平台返回内容",
                "job_instance": "12345",
            },
        ]
        mock_debug_inst.metrics = [
            group.model_dump()
            for group in [
                MetricPluginMetricGroup(
                    table_name="sql1",
                    fields=[
                        MetricPluginMetricField(
                            name="metrics_test", type="double", monitor_type="metric", description="metrics_test"
                        )
                    ],
                )
            ]
        ]
        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.job.base.JobMetricPluginDebugInst.get",
            return_value=mock_debug_inst,
        )

        task_log, status, metrics_json = self.plugin_manager.get_debug_log(123)

        # 验证返回日志内容
        assert task_log == [
            {
                "step": "step1",
                "status": "",
                "messages": "日志内容1",
                "job_instance_id": None,
                "timestamp": "",
                "extra": {},
            },
            {
                "step": "step2",
                "status": "",
                "messages": "日志内容2\n模拟作业平台返回内容",
                "job_instance_id": 12345,
                "timestamp": "",
                "extra": {},
            },
        ]

        # 验证返回状态
        assert status == "success"
        # 验证返回的指标解析是否正确
        assert isinstance(metrics_json, list)
        assert len(metrics_json) == 1
        assert metrics_json[0]["table_name"] == "sql1"
        assert metrics_json[0]["fields"][0]["name"] == "metrics_test"
        assert metrics_json[0]["fields"][0]["type"] == "double"
        assert metrics_json[0]["fields"][0]["monitor_type"] == "metric"
        assert metrics_json[0]["fields"][0]["unit"] == "none"
        assert metrics_json[0]["fields"][0]["description"] == "metrics_test"

        assert metrics_json[0]["table_name"] == self.plugin.define["sql_content"][0]["classification_id"]

    def test_get_debug_log_task_not_found(self, mocker: MockerFixture):
        """测试获取调试日志 - 任务不存在"""
        from bk_monitor_base.domains.metric_plugin.errors import ParsePluginDebugContentError

        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.job.base.JobMetricPluginDebugInst.get",
            return_value=None,
        )

        with pytest.raises(ParsePluginDebugContentError):
            self.plugin_manager.get_debug_log(999)

    def test_get_debug_log_failed_status(self, mocker: MockerFixture):
        """测试获取调试日志 - 调试失败状态"""
        mock_debug_inst = mocker.MagicMock()
        mock_debug_inst.id = 123
        mock_debug_inst.debug_status = "failed"
        mock_debug_inst.task_log = [{"messages": "执行失败", "log_content": "错误信息"}]
        mock_debug_inst.metrics = []
        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.job.base.JobMetricPluginDebugInst.get",
            return_value=mock_debug_inst,
        )

        task_log, status, metrics_json = self.plugin_manager.get_debug_log(123)

        assert status == "failed"
        assert metrics_json == []
        assert task_log[0]["status"] == "failed"
        assert "执行失败" in task_log[0]["messages"]

    def test_get_supported_os_types(self):
        """测试获取支持的操作系统类型"""
        supported_types = self.plugin_manager.get_supported_os_types()

        assert OSType.LINUX in supported_types
        assert OSType.LINUX_AARCH64 in supported_types
        assert OSType.WINDOWS not in supported_types
        assert OSType.AIX not in supported_types

    def test_get_supported_os_types_uses_binary_paths_when_define_has_no_os_markers(self):
        """测试支持的操作系统类型由插件二进制能力声明决定"""
        plugin = MetricPlugin(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            id="test_plugin_empty",
            type="job_mssql",
            name="测试MSSQL插件",
            description_md="测试插件文档",
            version=VersionTuple(1, 0),
            status=MetricPluginStatus.DEBUG,
            created_by="admin",
            updated_by="admin",
            define={"sql_content": []},
            params=[],
            metrics=[],
        )
        manager = MSSQLPluginManager(plugin)

        supported_types = manager.get_supported_os_types()
        assert supported_types == list(MSSQLPluginManager.BINARY_PATHS)

    def test_get_supported_os_types_matches_binary_paths_order(self):
        """测试支持系统列表与二进制路径声明顺序保持一致"""
        assert self.plugin_manager.get_supported_os_types() == list(MSSQLPluginManager.BINARY_PATHS)

    def test_get_sql_content_json(self):
        """测试获取SQL内容JSON"""
        sql_content = self.plugin_manager.get_sql_content_json()

        assert len(sql_content) == 1
        assert sql_content[0]["classification_id"] == "sql1"
        assert sql_content[0]["classification_name"] == "SQL-111"
        assert sql_content[0]["content"] == "SELECT 1 as metrics_test;"

    def test_get_parse_rules_json_empty_metrics(self):
        """测试获取解析规则JSON - 空指标配置

        当插件没有配置指标时，应返回空列表。
        """
        # setup_method 中的插件 metrics 为空列表
        parse_rules = self.plugin_manager.get_parse_rules_json()

        assert parse_rules == []

    def test_get_parse_rules_json_with_metrics(self):
        """测试获取解析规则JSON - 有指标配置

        验证 parse_rules 的结构正确，包含 sql 和 variate 字段，
        且 variate 中的字段映射正确。
        """
        # 创建带有指标配置的插件
        plugin_with_metrics = MetricPlugin(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            id="test_plugin_with_metrics",
            type="job_mssql",
            name="测试MSSQL插件",
            description_md="测试插件文档",
            version=VersionTuple(1, 0),
            status=MetricPluginStatus.DEBUG,
            created_by="admin",
            updated_by="admin",
            define={
                "linux": {},
                "sql_content": [
                    {
                        "classification_id": "sql1",
                        "classification_name": "SQL-111",
                        "content": "SELECT osuser, count(*) as session_count FROM v$session;",
                    },
                    {
                        "classification_id": "sql2",
                        "classification_name": "SQL-222",
                        "content": "SELECT tablespace_name, bytes FROM dba_data_files;",
                    },
                ],
            },
            params=[],
            metrics=[
                MetricPluginMetricGroup(
                    table_name="sql1",
                    table_desc="会话统计",
                    fields=[
                        MetricPluginMetricField(
                            name="osuser",
                            type="string",
                            monitor_type="dimension",
                            description="操作系统用户",
                        ),
                        MetricPluginMetricField(
                            name="session_count",
                            type="double",
                            monitor_type="metric",
                            description="会话数量",
                        ),
                    ],
                ),
                MetricPluginMetricGroup(
                    table_name="sql2",
                    table_desc="表空间统计",
                    fields=[
                        MetricPluginMetricField(
                            name="tablespace_name",
                            type="string",
                            monitor_type="dimension",
                            description="表空间名称",
                        ),
                        MetricPluginMetricField(
                            name="bytes",
                            type="double",
                            monitor_type="metric",
                            description="字节数",
                        ),
                    ],
                ),
            ],
        )
        manager = MSSQLPluginManager(plugin_with_metrics)

        parse_rules = manager.get_parse_rules_json()

        # 验证返回列表长度
        assert len(parse_rules) == 2

        # 验证第一个规则（sql1）
        rule1 = parse_rules[0]
        assert "sql" in rule1
        assert "variate" in rule1
        assert rule1["sql"] == "SELECT osuser, count(*) as session_count FROM v$session;"
        assert len(rule1["variate"]) == 2

        # 验证 variate 字段结构
        variate1_names = {v["object_name"] for v in rule1["variate"]}
        assert "osuser" in variate1_names
        assert "session_count" in variate1_names

        # 验证字段类型映射
        for variate in rule1["variate"]:
            if variate["object_name"] == "osuser":
                assert variate["object_new_name"] == "osuser"
                assert variate["object_type"] == "dimension"
            elif variate["object_name"] == "session_count":
                assert variate["object_new_name"] == "session_count"
                assert variate["object_type"] == "metric"

        # 验证第二个规则（sql2）
        rule2 = parse_rules[1]
        assert rule2["sql"] == "SELECT tablespace_name, bytes FROM dba_data_files;"
        assert len(rule2["variate"]) == 2

    def test_get_parse_rules_json_field_mapping(self):
        """测试获取解析规则JSON - 验证字段映射格式

        确保每个字段的 object_name、object_new_name、object_type 都被正确设置。
        """
        plugin = MetricPlugin(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            id="test_plugin_mapping",
            type="job_mssql",
            name="测试MSSQL插件",
            description_md="测试插件文档",
            version=VersionTuple(1, 0),
            status=MetricPluginStatus.DEBUG,
            created_by="admin",
            updated_by="admin",
            define={
                "linux": {},
                "sql_content": [
                    {
                        "classification_id": "test_table",
                        "classification_name": "测试表",
                        "content": "SELECT field1, field2, field3 FROM test_table;",
                    },
                ],
            },
            params=[],
            metrics=[
                MetricPluginMetricGroup(
                    table_name="test_table",
                    fields=[
                        MetricPluginMetricField(name="field1", type="string", monitor_type="dimension"),
                        MetricPluginMetricField(name="field2", type="double", monitor_type="metric"),
                        MetricPluginMetricField(name="field3", type="string", monitor_type="dimension"),
                    ],
                ),
            ],
        )
        manager = MSSQLPluginManager(plugin)

        parse_rules = manager.get_parse_rules_json()

        assert len(parse_rules) == 1
        rule = parse_rules[0]

        # 验证所有字段都包含必要的键
        for variate in rule["variate"]:
            assert "object_name" in variate
            assert "object_new_name" in variate
            assert "object_type" in variate
            # object_name 和 object_new_name 应该相同
            assert variate["object_name"] == variate["object_new_name"]
            # object_type 应该是 dimension 或 metric
            assert variate["object_type"] in ["dimension", "metric"]

    def test_get_sql_content_json_empty(self):
        """测试获取SQL内容JSON - 无SQL内容"""
        plugin = MetricPlugin(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            id="test_plugin_empty",
            type="job_mssql",
            name="测试MSSQL插件",
            description_md="测试插件文档",
            version=VersionTuple(1, 0),
            status=MetricPluginStatus.DEBUG,
            created_by="admin",
            updated_by="admin",
            define={},  # 没有 sql_content
            params=[],
            metrics=[],
        )
        manager = MSSQLPluginManager(plugin)

        sql_content = manager.get_sql_content_json()
        assert sql_content == []

    def test_get_package_context(self):
        """测试获取插件包上下文"""
        context = self.plugin_manager._get_package_context()

        assert "metric_json" in context
        assert "plugin_id" in context
        assert context["plugin_id"] == "test_plugin"
        assert "plugin_display_name" in context
        assert context["plugin_display_name"] == "测试MSSQL插件"
        assert "version" in context
        assert context["version"] == "1.0"
        assert "config_version" in context
        assert context["config_version"] == 1
        assert "sql_content" in context
        assert len(context["sql_content"]) == 1

    def test_parse_target_server_with_ip_and_cloud_id(self):
        """测试解析目标服务器 - 使用IP和云区域ID"""
        collect_host = {"ip": "192.168.1.100", "bk_cloud_id": 0}
        target_server = self.plugin_manager.parse_target_server(collect_host)

        assert target_server is not None
        assert "ip_list" in target_server
        assert target_server["ip_list"][0]["ip"] == "192.168.1.100"
        assert target_server["ip_list"][0]["bk_cloud_id"] == 0

    def test_parse_target_server_with_host_id(self):
        """测试解析目标服务器 - 使用主机ID"""
        collect_host = {"bk_host_id": 12345}
        target_server = self.plugin_manager.parse_target_server(collect_host)

        assert target_server is not None
        assert "host_id_list" in target_server
        assert target_server["host_id_list"][0] == 12345

    def test_parse_target_server_invalid(self):
        """测试解析目标服务器 - 无效输入"""
        collect_host = {"invalid_key": "value"}
        target_server = self.plugin_manager.parse_target_server(collect_host)

        assert target_server is None

    def test_download_binary(self, mocker: MockerFixture):
        """测试下载二进制文件"""
        import tempfile

        # 模拟 tempfile.mkdtemp
        mock_temp_dir = tempfile.mkdtemp()
        mocker.patch("tempfile.mkdtemp", return_value=mock_temp_dir)

        # 模拟 storage
        mock_storage = mocker.MagicMock()
        mock_remote_file = mocker.MagicMock()
        mock_remote_file.read.return_value = b"binary_content"
        mock_storage.open.return_value.__enter__ = mocker.MagicMock(return_value=mock_remote_file)
        mock_storage.open.return_value.__exit__ = mocker.MagicMock(return_value=False)
        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.job.base.get_storage",
            return_value=mock_storage,
        )

        # 模拟 open 用于写入本地文件
        mocker.patch("builtins.open", mocker.mock_open())

        result_path = self.plugin_manager._download_binary(OSType.LINUX)

        # 验证返回路径
        assert "OracleUniversalPlugin" in str(result_path)
        # 验证 storage.open 被调用
        mock_storage.open.assert_called_once()

    def test_stop_debug_task_not_found(self, mocker: MockerFixture):
        """测试停止调试 - 任务不存在"""
        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.job.base.JobMetricPluginDebugInst.get",
            return_value=None,
        )

        # 任务不存在时应该不抛出异常，只记录日志
        self.plugin_manager.stop_debug(999, "admin")  # 不应该抛出异常

    def test_get_debug_os_target_path(self, mocker: MockerFixture):
        """测试获取调试目标路径"""

        # 模拟配置
        mock_config = mocker.MagicMock()
        mock_config.blueking.gse.gse_path_variable_linux = "/data/bkce/gse"
        mock_config.blueking.gse.gse_path_variable_windows = "C:\\gse"
        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.job.base.get_config",
            return_value=mock_config,
        )

        linux_path = self.plugin_manager._get_debug_os_target_path(123, OSType.LINUX)
        assert "/data/bkce/gse/job_plugins/debug_job_mssql_123/test_plugin" in linux_path

        windows_path = self.plugin_manager._get_debug_os_target_path(123, OSType.WINDOWS)
        assert "C:\\gse\\job_plugins\\debug_job_mssql_123\\test_plugin" in windows_path

    def test_start_debug_unsupported_os_type(self, mocker: MockerFixture):
        """测试启动调试 - 不支持的操作系统类型执行脚本"""
        # 模拟 JobMetricPluginDebugInst
        mock_debug_inst = mocker.MagicMock()
        mock_debug_inst.id = 123
        mock_debug_inst.debug_params = {}

        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.job.base.JobMetricPluginDebugInst",
            return_value=mock_debug_inst,
        )
        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.job.base.JobMetricPluginDebugInst.get",
            return_value=mock_debug_inst,
        )

        # 模拟 get_os_type_by_collect_host 返回 WINDOWS (不支持的类型)
        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.job.base.get_os_type_by_collect_host",
            return_value=OSType.WINDOWS,
        )

        # 模拟其他必要的方法
        mocker.patch.object(self.plugin_manager, "make_package", return_value=Path("/tmp/mock_pkg.tgz"))
        mocker.patch.object(self.plugin_manager, "_generate_debug_yaml", return_value="mock_config_path")
        mocker.patch.object(self.plugin_manager, "parse_target_server", return_value={"ip": "127.0.0.1"})
        mocker.patch.object(self.plugin_manager, "_get_debug_os_target_path", return_value="/tmp/bk_monitor_debug/123")

        # 模拟 storage
        mock_storage = mocker.MagicMock()
        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.job.base.get_storage",
            return_value=mock_storage,
        )
        mocker.patch("builtins.open", mocker.mock_open())

        collect_params = {"period": 60}
        plugin_params = {"user": "root"}
        collect_host = {"bk_host_id": 1}
        operator = "admin"

        with pytest.raises(ParseOsTypeError):
            # 当前仅支持Linux X86与Linux Arm
            self.plugin_manager.start_debug(collect_params, plugin_params, collect_host, operator)

    def test_get_host_info_with_valid_host(self):
        """测试获取主机信息 - 有效主机"""
        bk_host = {"bk_host_id": 1, "os_type": "linux", "os_arch": "x86_64"}
        result = get_host_info(bk_host)

        assert result["os_type"] == "linux"
        assert result["os_arch"] == "x86_64"

    def test_get_host_info_missing_os_type(self, mocker: MockerFixture):
        """测试获取主机信息 - 缺少os_type字段"""
        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.mock_cmdb_tools.search_instances",
            return_value=(0, []),
        )
        bk_host = {"bk_host_id": 1, "os_arch": "x86_64"}

        host_info = get_host_info(bk_host)
        assert host_info is None

    def test_get_host_info_missing_os_arch(self, mocker: MockerFixture):
        """测试获取主机信息 - 缺少os_arch字段"""
        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.mock_cmdb_tools.search_instances",
            return_value=(0, []),
        )

        bk_host = {"bk_host_id": 1, "os_type": "linux"}

        host_info = get_host_info(bk_host)
        assert host_info is None

    def test_get_os_type_by_collect_host_linux_x86(self, mocker: MockerFixture):
        """测试通过采集主机获取操作系统类型 - Linux x86_64"""
        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.mock_cmdb_tools.get_host_info",
            return_value={"os_type": "linux", "os_arch": "x86_64"},
        )

        collect_host = {"bk_host_id": 1}
        os_type = get_os_type_by_collect_host(collect_host)

        assert os_type == OSType.LINUX

    def test_get_os_type_by_collect_host_linux_aarch64(self, mocker: MockerFixture):
        """测试通过采集主机获取操作系统类型 - Linux aarch64"""
        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.mock_cmdb_tools.get_host_info",
            return_value={"os_type": "linux", "os_arch": "aarch64"},
        )

        collect_host = {"bk_host_id": 1}
        os_type = get_os_type_by_collect_host(collect_host)

        assert os_type == OSType.LINUX_AARCH64

    def test_get_os_type_by_collect_host_windows(self, mocker: MockerFixture):
        """测试通过采集主机获取操作系统类型 - Windows"""
        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.mock_cmdb_tools.get_host_info",
            return_value={"os_type": "windows", "os_arch": "x86_64"},
        )

        collect_host = {"bk_host_id": 1}
        os_type = get_os_type_by_collect_host(collect_host)

        assert os_type == OSType.WINDOWS

    def test_get_os_type_by_collect_host_aix(self, mocker: MockerFixture):
        """测试通过采集主机获取操作系统类型 - AIX"""
        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.mock_cmdb_tools.get_host_info",
            return_value={"os_type": "aix", "os_arch": "powerpc"},
        )

        collect_host = {"bk_host_id": 1}
        os_type = get_os_type_by_collect_host(collect_host)

        assert os_type == OSType.AIX

    def test_get_os_type_by_collect_host_unsupported(self, mocker: MockerFixture):
        """测试通过采集主机获取操作系统类型 - 不支持的类型"""
        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.mock_cmdb_tools.get_host_info",
            return_value={"os_type": "macos", "os_arch": "arm64"},
        )

        collect_host = {"bk_host_id": 1}
        # 不支持的类型返回 None
        os_type = get_os_type_by_collect_host(collect_host)
        assert os_type is None

    def test_get_extra_file_source_paths(self):
        """测试获取额外文件路径 - MSSQL不需要额外文件"""
        extra_files = self.plugin_manager.get_extra_file_source_paths(OSType.LINUX)
        assert extra_files == []

        extra_files_arm = self.plugin_manager.get_extra_file_source_paths(OSType.LINUX_AARCH64)
        assert extra_files_arm == []

    def test_type_class_variable(self):
        """测试类型类变量"""
        assert MSSQLPluginManager.type == "job_mssql"

    def test_binary_paths(self):
        """测试二进制文件路径配置"""
        assert OSType.LINUX in MSSQLPluginManager.BINARY_PATHS
        assert MSSQLPluginManager.BINARY_PATHS[OSType.LINUX] == "OracleUniversalPlugin"

        assert OSType.LINUX_AARCH64 in MSSQLPluginManager.BINARY_PATHS
        assert MSSQLPluginManager.BINARY_PATHS[OSType.LINUX_AARCH64] == "OracleUniversalPlugin_arm"
