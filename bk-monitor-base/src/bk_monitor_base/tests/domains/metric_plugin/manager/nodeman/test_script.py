import base64
import json
import shutil
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from bk_monitor_base.domains.metric_plugin.errors import (
    ExportPluginFailedError,
    ExportPluginTimeoutError,
    RegisterPluginFailedError,
)
from bk_monitor_base.domains.metric_plugin.manager.node_man.define import (
    NodemanPluginParamsMode,
    NodemanPluginParamsType,
)
from bk_monitor_base.metric_plugin import (
    MetricPlugin,
    MetricPluginMetricField,
    MetricPluginMetricGroup,
    MetricPluginParams,
    MetricPluginStatus,
    ScriptPluginManager,
    VersionTuple,
)


class TestScriptPluginManager:
    """测试 ScriptPluginManager 类"""

    def setup_method(self):
        """设置测试数据"""
        self.plugin = MetricPlugin(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            id="test_plugin",
            type="script",
            name="测试插件",
            description_md="测试插件文档",
            version=VersionTuple(1, 0),
            status=MetricPluginStatus.DEBUG,
            created_by="admin",
            updated_by="admin",
            define={
                "linux": {
                    "filename": "test.sh",
                    "script_content_base64": base64.b64encode(b"echo 'test'").decode("utf-8"),
                }
            },
            params=[
                # TEXT + ENV
                MetricPluginParams(
                    name="test_param",
                    type=NodemanPluginParamsType.TEXT,
                    mode=NodemanPluginParamsMode.ENV,
                    description="测试参数",
                    default="test",
                    required=True,
                ),
                # SWITCH + OPT_CMD
                MetricPluginParams(
                    name="--enable",
                    type=NodemanPluginParamsType.SWITCH,
                    mode=NodemanPluginParamsMode.OPT_CMD,
                    description="开关选项",
                    default="false",
                    required=False,
                ),
                # TEXT + OPT_CMD
                MetricPluginParams(
                    name="--config",
                    type=NodemanPluginParamsType.TEXT,
                    mode=NodemanPluginParamsMode.OPT_CMD,
                    description="配置选项",
                    default="",
                    required=False,
                ),
                # TEXT + POS_CMD
                MetricPluginParams(
                    name="pos_arg",
                    type=NodemanPluginParamsType.TEXT,
                    mode=NodemanPluginParamsMode.POS_CMD,
                    description="位置参数",
                    default="",
                    required=False,
                ),
                # FILE + ENV
                MetricPluginParams(
                    name="file_param",
                    type=NodemanPluginParamsType.FILE,
                    mode=NodemanPluginParamsMode.ENV,
                    description="文件参数",
                    default="",
                    required=False,
                ),
                # FILE + POS_CMD
                MetricPluginParams(
                    name="file_param2",
                    type=NodemanPluginParamsType.FILE,
                    mode=NodemanPluginParamsMode.POS_CMD,
                    description="文件参数2",
                    default="",
                    required=False,
                ),
                # ENCRYPT + ENV
                MetricPluginParams(
                    name="encrypt_param",
                    type=NodemanPluginParamsType.ENCRYPT,
                    mode=NodemanPluginParamsMode.ENV,
                    description="加密参数",
                    default="",
                    required=False,
                ),
                # HOST + DMS_INSERT
                MetricPluginParams(
                    name="host_dms",
                    type=NodemanPluginParamsType.HOST,
                    mode=NodemanPluginParamsMode.DMS_INSERT,
                    description="主机维度",
                    default="",
                    required=False,
                ),
            ],
            metrics=[
                MetricPluginMetricGroup(
                    table_name="test_metric",
                    fields=[MetricPluginMetricField(name="metric1", type="double", monitor_type="metric")],
                )
            ],
        )
        self.plugin_manager = ScriptPluginManager(self.plugin)

    def test_make_package(self):
        """测试制作插件包"""
        package_dir = self.plugin_manager.make_package(is_compress=True)
        # 检查插件压缩包
        assert package_dir.exists() and package_dir.is_file()
        # print("\n", package_dir.parent)

        # 检查插件目录
        plugin_dir = package_dir.parent / "test_plugin" / "external_plugins_linux_x86_64" / "test_plugin"
        assert plugin_dir.exists() and plugin_dir.is_dir()
        assert (plugin_dir / "test.sh").exists()

        assert (plugin_dir / "test.sh").read_text() == "echo 'test'"
        assert (plugin_dir / "info" / "description.md").read_text(encoding="utf-8") == "测试插件文档"
        assert (plugin_dir / "info" / "config.json").read_text(encoding="utf-8") == json.dumps(
            [param.model_dump() for param in self.plugin.params], ensure_ascii=False, indent=4
        )
        assert (plugin_dir / "info" / "metrics.json").read_text(encoding="utf-8") == json.dumps(
            [self.plugin.metrics[0].model_dump()], ensure_ascii=False, indent=4
        )

        # 删除插件包目录
        shutil.rmtree(package_dir.parent)

    def test_register_plugin(self, mocker: MockerFixture):
        """测试注册插件"""
        # 模拟 _make_package 返回压缩包路径
        from pathlib import Path

        mock_tar_path = Path("/tmp/test_plugin.tgz")
        make_package_mocker = mocker.patch.object(self.plugin_manager, "make_package", return_value=mock_tar_path)

        # 模拟 _upload_plugin 返回插件名称
        upload_plugin_mocker = mocker.patch.object(
            self.plugin_manager, "_upload_plugin", return_value="test_plugin_uploaded"
        )

        # 模拟 _register_plugin 方法
        register_plugin_mocker = mocker.patch.object(self.plugin_manager, "_register_plugin")

        # 模拟 _register_template 方法
        register_template_mocker = mocker.patch.object(self.plugin_manager, "_register_template")

        # 模拟 get_plugin_info API 调用返回插件信息
        mock_plugin_info = mocker.MagicMock()
        mock_plugin_info.md5 = "test_md5_hash"
        get_plugin_info_mocker = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.base.get_plugin_info",
            return_value=[mock_plugin_info],
        )

        # 模拟 shutil.rmtree 避免实际删除文件
        mocker.patch("shutil.rmtree")

        operator = "admin"

        # 调用 register 方法
        md5_list = self.plugin_manager.register(operator=operator)

        # 验证返回值
        assert md5_list == ["test_md5_hash"]

        # 验证 make_package 被调用
        assert make_package_mocker.called
        make_package_mocker.assert_called_once_with(is_compress=True)

        # 验证 _upload_plugin 被调用
        assert upload_plugin_mocker.called
        upload_plugin_mocker.assert_called_once_with(tar_file=mock_tar_path)

        # 验证 _register_plugin 被调用
        assert register_plugin_mocker.called
        register_plugin_mocker.assert_called_once_with(operator=operator, plugin_name="test_plugin_uploaded")

        # 验证 _register_template 被调用
        assert register_template_mocker.called
        register_template_mocker.assert_called_once_with(operator=operator, tar_file=mock_tar_path)

        # 验证 get_plugin_info 被调用
        assert get_plugin_info_mocker.called
        get_plugin_info_mocker.assert_called_once_with(
            bk_tenant_id="test_tenant",
            name="test_plugin",
            version="1.0",
        )

    def test_register_plugin_internal_success(self, mocker: MockerFixture):
        """测试 _register_plugin 方法 - 成功场景"""
        # 模拟 create_register_plugin_task API 调用
        create_register_plugin_task_mocker = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.base.create_register_plugin_task",
            return_value=123,
        )

        # 模拟 query_register_plugin_task API 调用 - 成功完成
        query_register_plugin_task_mocker = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.base.query_register_plugin_task",
            return_value={"status": "SUCCESS", "is_finish": True},
        )

        plugin_name = "test_plugin_v1_0"
        operator = "admin"

        # 调用 _register_plugin 方法
        self.plugin_manager._register_plugin(plugin_name=plugin_name, operator=operator)

        # 验证 create_register_plugin_task 被调用
        assert create_register_plugin_task_mocker.called
        create_register_plugin_task_mocker.assert_called_once_with(
            bk_tenant_id="test_tenant",
            file_name=plugin_name,
            is_release=False,
        )

        # 验证 query_register_plugin_task 被调用
        assert query_register_plugin_task_mocker.called
        query_register_plugin_task_mocker.assert_called_once_with(bk_tenant_id="test_tenant", job_id=123)

    def test_register_plugin_internal_failed(self, mocker: MockerFixture):
        """测试 _register_plugin 方法 - 失败场景"""
        # 模拟 create_register_plugin_task API 调用
        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.base.create_register_plugin_task",
            return_value=456,
        )

        # 模拟 query_register_plugin_task API 调用 - 任务失败
        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.base.query_register_plugin_task",
            return_value={"status": "FAILED", "message": "Plugin registration failed", "is_finish": True},
        )

        plugin_name = "test_plugin_v1_0"
        operator = "admin"

        # 调用 _register_plugin 方法应该抛出 RegisterPluginFailedError
        with pytest.raises(RegisterPluginFailedError, match="Plugin registration failed"):
            self.plugin_manager._register_plugin(plugin_name=plugin_name, operator=operator)

    def test_register_plugin_internal_timeout(self, mocker: MockerFixture):
        """测试 _register_plugin 方法 - 超时场景"""
        # 模拟 time.sleep 避免实际等待
        mocker.patch("time.sleep")

        # 模拟 create_register_plugin_task API 调用
        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.base.create_register_plugin_task",
            return_value=789,
        )

        # 模拟 query_register_plugin_task API 调用 - 任务永不完成
        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.base.query_register_plugin_task",
            return_value={"status": "RUNNING", "is_finish": False},
        )

        plugin_name = "test_plugin_v1_0"
        operator = "admin"

        # 调用 _register_plugin 方法应该抛出 RegisterPluginFailedError (超时)
        with pytest.raises(RegisterPluginFailedError, match="注册插件超时"):
            self.plugin_manager._register_plugin(plugin_name=plugin_name, operator=operator)

    def test_upload_plugin_success(self, mocker: MockerFixture):
        """测试 _upload_plugin 方法 - 成功场景"""
        # Mock dependencies
        mock_storage = mocker.Mock()
        mock_storage.save = mocker.Mock()
        mock_storage.url = mocker.Mock(return_value="http://bkrepo.example.com/path/to/plugin.tgz")
        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.base.get_storage",
            return_value=mock_storage,
        )

        mock_upload_plugin = mocker.patch("bk_monitor_base.domains.metric_plugin.manager.node_man.base.upload_plugin")
        mock_upload_plugin.return_value = {"name": "test_plugin_uploaded.tgz"}

        mock_open = mocker.patch("builtins.open", mocker.mock_open(read_data=b"test plugin content"))
        mock_hashlib_md5 = mocker.patch("hashlib.md5")
        mock_hash = mocker.Mock()
        mock_hash.hexdigest.return_value = "test_md5_hash"
        mock_hashlib_md5.return_value = mock_hash

        # Test data
        tar_file = Path("/tmp/test_plugin.tgz")

        # 调用 _upload_plugin 方法
        result = self.plugin_manager._upload_plugin(tar_file=tar_file)

        # 验证结果
        assert result == "test_plugin_uploaded.tgz"

        # 验证文件被读取用于计算MD5
        mock_open.assert_called_with(tar_file, "rb")

        # 验证上传到bkrepo
        mock_storage.save.assert_called_once()
        args, _ = mock_storage.save.call_args
        assert "nodeman_plugins/test_plugin/" in args[0]
        assert args[0].endswith("/test_plugin.tgz")

        # 验证上传到节点管理
        mock_upload_plugin.assert_called_once_with(
            bk_tenant_id=self.plugin.bk_tenant_id,
            file_name=tar_file.name,
            download_url="http://bkrepo.example.com/path/to/plugin.tgz",
            md5="test_md5_hash",
        )

    def test_upload_plugin_bkrepo_failure(self, mocker: MockerFixture):
        """测试 _upload_plugin 方法 - BkRepo上传失败场景"""
        # Mock dependencies - bkrepo上传失败
        mock_storage = mocker.Mock()
        mock_storage.save.side_effect = Exception("BkRepo upload failed")
        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.base.get_storage",
            return_value=mock_storage,
        )

        mocker.patch("builtins.open", mocker.mock_open(read_data=b"test plugin content"))
        mock_hashlib_md5 = mocker.patch("hashlib.md5")
        mock_hash = mocker.Mock()
        mock_hash.hexdigest.return_value = "test_md5_hash"
        mock_hashlib_md5.return_value = mock_hash

        # Test data
        tar_file = Path("/tmp/test_plugin.tgz")

        # 调用 _upload_plugin 方法应该抛出异常
        with pytest.raises(Exception, match="BkRepo upload failed"):
            self.plugin_manager._upload_plugin(tar_file=tar_file)

    def test_upload_plugin_nodeman_failure(self, mocker: MockerFixture):
        """测试 _upload_plugin 方法 - 节点管理上传失败场景"""
        # Mock dependencies - 节点管理上传失败
        mock_storage = mocker.Mock()
        mock_storage.save = mocker.Mock()
        mock_storage.url = mocker.Mock(return_value="http://bkrepo.example.com/path/to/plugin.tgz")
        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.base.get_storage",
            return_value=mock_storage,
        )

        mock_upload_plugin = mocker.patch("bk_monitor_base.domains.metric_plugin.manager.node_man.base.upload_plugin")
        mock_upload_plugin.side_effect = Exception("NodeMan upload failed")

        mocker.patch("builtins.open", mocker.mock_open(read_data=b"test plugin content"))
        mock_hashlib_md5 = mocker.patch("hashlib.md5")
        mock_hash = mocker.Mock()
        mock_hash.hexdigest.return_value = "test_md5_hash"
        mock_hashlib_md5.return_value = mock_hash

        # Test data
        tar_file = Path("/tmp/test_plugin.tgz")

        # 调用 _upload_plugin 方法应该抛出异常
        with pytest.raises(Exception, match="NodeMan upload failed"):
            self.plugin_manager._upload_plugin(tar_file=tar_file)

    def test_register_template_success(self, mocker: MockerFixture):
        """测试 _register_template 方法 - 成功场景"""
        # Mock dependencies
        mock_create_template = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.base.create_plugin_config_template"
        )

        # Mock file system operations
        mocker.patch("os.listdir", return_value=["linux_x86_64"])
        mock_walk = mocker.patch("os.walk")
        mock_walk.return_value = [
            (
                "/tmp/test_plugin/linux_x86_64/test_plugin/etc",
                [],
                ["config.tpl", "other_config.tpl", "not_template.conf"],
            )
        ]

        # Mock file reading with different contents for each file
        def mock_open_side_effect(filename, *args, **kwargs):
            if "config.tpl" in str(filename):
                return mocker.mock_open(read_data=b"template content 1")()
            elif "other_config.tpl" in str(filename):
                return mocker.mock_open(read_data=b"template content 2")()
            else:
                return mocker.mock_open()()

        mocker.patch("builtins.open", side_effect=mock_open_side_effect)

        # Mock base64 and hashlib
        def mock_b64encode_side_effect(content):
            if content == b"template content 1":
                return b"encoded_content1"
            elif content == b"template content 2":
                return b"encoded_content2"
            else:
                return b"encoded_content"

        mocker.patch("base64.b64encode", side_effect=mock_b64encode_side_effect)

        def mock_md5_side_effect(content):
            mock_hash = mocker.Mock()
            if content == b"template content 1":
                mock_hash.hexdigest.return_value = "hash1"
            elif content == b"template content 2":
                mock_hash.hexdigest.return_value = "hash2"
            else:
                mock_hash.hexdigest.return_value = "default_hash"
            return mock_hash

        mocker.patch("hashlib.md5", side_effect=mock_md5_side_effect)

        # Test data
        tar_file = Path("/tmp/test_plugin.tgz")
        operator = "admin"

        # 调用 _register_template 方法
        self.plugin_manager._register_template(tar_file=tar_file, operator=operator)

        # 验证模板创建至少被调用了1次
        assert mock_create_template.call_count >= 1

        # 验证调用参数
        call_args_list = mock_create_template.call_args_list
        for call in call_args_list:
            assert call[1]["bk_tenant_id"] == self.plugin.bk_tenant_id
            params = call[1]["params"]
            assert params["plugin_name"] == "test_plugin"
            assert "content" in params
            assert "md5" in params
            # 验证模板名称合理（移除.tpl后缀）
            assert params["name"] in ["config", "other_config"]

    def test_register_template_no_template_files(self, mocker: MockerFixture):
        """测试 _register_template 方法 - 无模板文件场景"""
        # Mock dependencies
        mock_create_template = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.base.create_plugin_config_template"
        )

        # Mock file system operations - 没有.tpl文件
        mocker.patch("os.listdir", return_value=["linux_x86_64"])
        mock_walk = mocker.patch("os.walk")
        mock_walk.return_value = [
            (
                "/tmp/test_plugin/linux_x86_64/test_plugin/etc",
                [],
                ["config.conf", "other.yaml"],  # 没有.tpl文件
            )
        ]

        # Test data
        tar_file = Path("/tmp/test_plugin.tgz")
        operator = "admin"

        # 调用 _register_template 方法
        self.plugin_manager._register_template(tar_file=tar_file, operator=operator)

        # 验证没有调用模板创建
        mock_create_template.assert_not_called()

    def test_register_template_api_failure(self, mocker: MockerFixture):
        """测试 _register_template 方法 - API调用失败场景"""
        # Mock dependencies - API调用失败
        mock_create_template = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.base.create_plugin_config_template"
        )
        mock_create_template.side_effect = Exception("API call failed")

        # Mock file system operations
        mocker.patch("os.listdir", return_value=["linux_x86_64"])
        mock_walk = mocker.patch("os.walk")
        mock_walk.return_value = [("/tmp/test_plugin/linux_x86_64/test_plugin/etc", [], ["config.tpl"])]

        # Mock file reading
        template_content = b"template content"
        mocker.patch("builtins.open", mocker.mock_open(read_data=template_content))

        # Mock base64 and hashlib
        mocker.patch("base64.b64encode", return_value=b"encoded_content")
        mock_hashlib_md5 = mocker.patch("hashlib.md5")
        mock_hash = mocker.Mock()
        mock_hash.hexdigest.return_value = "test_hash"
        mock_hashlib_md5.return_value = mock_hash

        # Test data
        tar_file = Path("/tmp/test_plugin.tgz")
        operator = "admin"

        # 调用 _register_template 方法应该抛出异常
        with pytest.raises(Exception, match="API call failed"):
            self.plugin_manager._register_template(tar_file=tar_file, operator=operator)

    def test_get_debug_log_success(self, mocker: MockerFixture):
        """测试 get_debug_log 方法 - 成功场景"""
        # Mock query_plugin_debug API调用
        mock_query_debug = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.base.query_plugin_debug"
        )

        # 基于实际示例的调试日志消息
        debug_message = """{"@timestamp":"2025-09-02T04:14:53.492Z","@metadata":{"beat":"bkmonitorbeat","type":"_doc","version":"3.72.3657"},"dataid":101178,"dimensions":{"status":0,"version":"","bk_host_id":"0"},"metrics":{"config_load_at":1756786493,"published":0,"errors":0,"config_error_code":111,"error_tasks":0,"uptime":0,"tasks":1},"time":1756786493}



{"@timestamp":"2025-09-02T04:15:10.503Z","@metadata":{"beat":"bkmonitorbeat","type":"_doc","version":"3.72.3657"},"usertime":"2025-09-02 04:15:10","ip":"127.0.0.1","exemplar":{},"task_id":0,"dimensions":{"disk_name":"/data","bk_biz_id":0},"task_type":"script","type":"script","message":"success","utctime":"2025-09-02 04:15:10","bk_cloud_id":0,"bk_biz_id":0,"localtime":"2025-09-02 12:15:10","group_info":[],"bk_cmdb_level":[{"bk_biz_id":2,"bk_set_id":5,"bk_module_id":15},{"bk_biz_id":2,"bk_set_id":5,"bk_module_id":19}],"error_code":0,"cost_time":7,"dataid":0,"time":1756786510,"metrics":{"disk_usage":8},"node_id":"0:127.0.0.1"}
{"@timestamp":"2025-09-02T04:15:10.504Z","@metadata":{"beat":"bkmonitorbeat","type":"_doc","version":"3.72.3657"},"type":"status","dataid":0,"data":[{"timestamp":1756786510503,"metrics":{"bkm_gather_up":2},"dimension":{"bk_collect_type":"script","bk_biz_id":"0","bkm_up_code":"0","bkm_up_code_name":"Ok","task_id":"0"}}],"node_id":"0:127.0.0.1","bk_cloud_id":0,"ip":"127.0.0.1"}"""

        mock_query_debug.return_value = {"message": debug_message, "status": "running"}

        # Test data
        task_id = 12345
        operator = "admin"

        # 调用 get_debug_log 方法
        result = self.plugin_manager.get_debug_log(task_id=task_id, operator=operator)
        metrics = result["metric_json"]
        last_time = result["last_time"]
        error_message = result["error_message"]

        # 验证API调用
        mock_query_debug.assert_called_once_with(bk_tenant_id=self.plugin.bk_tenant_id, task_id=task_id)

        # 验证解析结果
        assert isinstance(metrics, list)
        assert len(metrics) == 1  # 只有一条有效的指标数据（success message）

        # 验证指标数据结构
        metric = metrics[0]
        assert metric["metric_name"] == "disk_usage"
        assert metric["metric_value"] == 8
        assert len(metric["dimensions"]) == 1
        assert metric["dimensions"][0]["dimension_name"] == "disk_name"
        assert metric["dimensions"][0]["dimension_value"] == "/data"

        # 验证时间戳
        assert last_time == "2025-09-02 12:15:10"

        # 验证没有错误信息
        assert error_message == ""

    def test_get_debug_log_with_errors(self, mocker: MockerFixture):
        """测试 get_debug_log 方法 - 包含错误信息的场景"""
        # Mock query_plugin_debug API调用
        mock_query_debug = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.base.query_plugin_debug"
        )

        # 包含错误的调试日志消息
        debug_message = """{"@timestamp":"2025-09-02T04:15:20.504Z","@metadata":{"beat":"bkmonitorbeat","type":"_doc","version":"3.72.3657"},"time":1756786520,"exemplar":{},"dataid":0,"type":"script","task_id":0,"task_type":"script","message":"success","group_info":[],"bk_cloud_id":0,"bk_biz_id":0,"localtime":"2025-09-02 12:15:20","dimensions":{"disk_name":"/data","bk_biz_id":0},"metrics":{"disk_usage":5},"cost_time":7,"ip":"127.0.0.1","utctime":"2025-09-02 04:15:20","node_id":"0:127.0.0.1","bk_cmdb_level":[{"bk_biz_id":2,"bk_set_id":5,"bk_module_id":15}],"error_code":4001,"message":"Script execution failed"}"""

        mock_query_debug.return_value = {"message": debug_message, "status": "failed"}

        # Test data
        task_id = 12346
        operator = "admin"

        # 调用 get_debug_log 方法
        result = self.plugin_manager.get_debug_log(task_id=task_id, operator=operator)
        metrics = result["metric_json"]
        error_message = result["error_message"]

        # 验证API调用
        mock_query_debug.assert_called_once_with(bk_tenant_id=self.plugin.bk_tenant_id, task_id=task_id)

        # 验证解析结果 - 错误情况下不会有指标数据（因为message不是"success"）
        assert isinstance(metrics, list)
        assert len(metrics) == 0

        # 验证错误信息被正确解析
        assert "脚本运行报错,原因是Script execution failed" in error_message

    def test_get_debug_log_exporter_format(self, mocker: MockerFixture):
        """测试 get_debug_log 方法 - exporter格式数据"""
        # Mock query_plugin_debug API调用
        mock_query_debug = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.base.query_plugin_debug"
        )

        # exporter格式的调试日志消息
        debug_message = """{"@timestamp":"2025-09-02T04:15:30.505Z","@metadata":{"beat":"bkmonitorbeat","type":"_doc","version":"3.72.3657"},"prometheus":{"collector":{"metrics":[{"key":"cpu_usage","value":75.5,"labels":{"cpu_core":"0","mode":"user"}},{"key":"memory_usage","value":1024,"labels":{"type":"physical"}}]}},"time":1756786530,"dataid":0,"type":"prometheus"}"""

        mock_query_debug.return_value = {"message": debug_message, "status": "success"}

        # Test data
        task_id = 12347
        operator = "admin"

        # 调用 get_debug_log 方法
        result = self.plugin_manager.get_debug_log(task_id=task_id, operator=operator)
        metrics = result["metric_json"]
        last_time = result["last_time"]
        error_message = result["error_message"]

        # 验证API调用
        mock_query_debug.assert_called_once_with(bk_tenant_id=self.plugin.bk_tenant_id, task_id=task_id)

        # 验证解析结果
        assert isinstance(metrics, list)
        assert len(metrics) == 2  # cpu_usage 和 memory_usage

        # 验证第一个指标（cpu_usage）
        cpu_metric = next(m for m in metrics if m["metric_name"] == "cpu_usage")
        assert cpu_metric["metric_value"] == 75.5
        assert len(cpu_metric["dimensions"]) == 2

        # 验证第二个指标（memory_usage）
        memory_metric = next(m for m in metrics if m["metric_name"] == "memory_usage")
        assert memory_metric["metric_value"] == 1024
        assert len(memory_metric["dimensions"]) == 1

        # 验证时间戳
        assert last_time == "2025-09-02 12:15:30"

        # 验证没有错误信息
        assert error_message == ""

    def test_get_debug_log_api_failure(self, mocker: MockerFixture):
        """测试 get_debug_log 方法 - API调用失败场景"""
        # Mock query_plugin_debug API调用失败
        mock_query_debug = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.base.query_plugin_debug"
        )
        mock_query_debug.side_effect = Exception("API call failed")

        # Test data
        task_id = 12348
        operator = "admin"

        # 调用 get_debug_log 方法应该抛出异常
        with pytest.raises(Exception, match="API call failed"):
            self.plugin_manager.get_debug_log(task_id=task_id, operator=operator)

    def test_get_debug_log_parse_error(self, mocker: MockerFixture):
        """测试 get_debug_log 方法 - 解析错误场景"""
        # Mock query_plugin_debug API调用
        mock_query_debug = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.base.query_plugin_debug"
        )

        # 包含无效JSON但包含"beat"的调试日志消息
        debug_message = """{"@metadata":{"beat":"bkmonitorbeat","type":"_doc"},"invalid": json data}
{"@metadata":{"beat":"bkmonitorbeat"invalid json line"""

        mock_query_debug.return_value = {"message": debug_message, "status": "failed"}

        # Test data
        task_id = 12349
        operator = "admin"

        # 调用 get_debug_log 方法应该抛出解析错误
        from bk_monitor_base.domains.metric_plugin.errors import ParsePluginDebugContentError

        with pytest.raises(ParsePluginDebugContentError):
            self.plugin_manager.get_debug_log(task_id=task_id, operator=operator)

    def test_debug_context(self):
        """测试调试上下文"""
        collect_params = {"period": 300, "timeout": 30}
        plugin_params = {
            "test_param": "debug_value",
            "--enable": "true",
            "--config": "config.yaml",
            "pos_arg": "arg1",
            "file_param": {"filename": "test.conf", "file_base64": base64.b64encode(b"content").decode()},
            "file_param2": {"filename": "test2.conf", "file_base64": base64.b64encode(b"content2").decode()},
            "encrypt_param": "secret",
            "host_dms": {"host_ip": "bk_host_innerip"},
        }

        # 测试_get_debug_config_context方法
        debug_context = self.plugin_manager._get_debug_config_context(
            collect_params=collect_params,
            plugin_params=plugin_params,
            target_nodes=[],
        )

        expected_debug_context = {
            "env.yaml": {
                "test_param": "debug_value",
                "file_param": "etc/test.conf",
                "encrypt_param": "secret",
                "cmd_args": "--enable --config config.yaml arg1 etc/test2.conf ",
            },
            "bkmonitorbeat_debug.yaml": {
                "labels": {
                    "$for": "cmdb_instance.scope",
                    "$item": "scope",
                    "$body": {"host_ip": "{{ cmdb_instance.host.bk_host_innerip or 'bk_host_innerip' or '-' }}"},
                },
                "period": 300,
                "timeout": 30,
            },
            "{{file1}}": {"file1": "test.conf", "file1_content": "$NODEMAN_BASE64_PREFIX$Y29udGVudA=="},
            "{{file2}}": {"file2": "test2.conf", "file2_content": "$NODEMAN_BASE64_PREFIX$Y29udGVudDI="},
        }

        # 校验调试配置上下文结果
        assert debug_context == expected_debug_context, f"调试配置上下文不匹配: {debug_context}"

    def test_process_plugin_params_host_dms_insert_with_legacy_literal_value(self):
        """测试 host 维度注入兼容老版本将字面量误传为 host 字段名的场景。"""
        collect_params = {"period": 300, "timeout": 30}
        plugin_params = {
            "host_dms": {"legacy_host_dimension": "custom-host-value"},
        }

        env_vars, user_files, extra_dimensions = self.plugin_manager._process_plugin_params(
            collect_params=collect_params,
            plugin_params=plugin_params,
        )

        assert env_vars == {"cmd_args": ""}
        assert user_files == []
        assert extra_dimensions == {
            "legacy_host_dimension": "{{ cmdb_instance.host.custom-host-value or 'custom-host-value' or '-' }}"
        }

    def test_start_debug(self, mocker: MockerFixture):
        """测试启动调试"""
        # 模拟 render_plugin_config_template 返回配置ID
        render_plugin_config_template_mocker = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.base.render_plugin_config_template",
            return_value={"id": 100},
        )

        # 模拟 start_plugin_debug 返回调试任务ID
        start_plugin_debug_mocker = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.base.start_plugin_debug",
            return_value=1,
        )

        collect_params = {"period": 300, "timeout": 30}
        plugin_params = {
            "test_param": "debug_value",
            "--enable": "true",
            "--config": "config.yaml",
            "pos_arg": "arg1",
            "file_param": {"filename": "test.conf", "file_base64": base64.b64encode(b"content").decode()},
            "file_param2": {"filename": "test2.conf", "file_base64": base64.b64encode(b"content2").decode()},
            "encrypt_param": "secret",
            "host_dms": {"host_ip": "bk_host_innerip"},
        }

        debug_id = self.plugin_manager.start_debug(
            collect_params=collect_params,
            plugin_params=plugin_params,
            collect_host={"bk_host_id": 1},
            target_nodes=[],
            operator="admin",
        )

        # 验证返回值
        assert isinstance(debug_id, int) and debug_id > 0

        # 验证 render_plugin_config_template 被调用
        assert render_plugin_config_template_mocker.called
        assert render_plugin_config_template_mocker.call_count == 4  # 4个配置文件

        # 验证 render_plugin_config_template 调用参数
        expected_render_calls = [
            # env.yaml
            {
                "bk_tenant_id": "test_tenant",
                "plugin_name": "test_plugin",
                "plugin_version": "*",
                "name": "env.yaml",
                "version": "1",
                "data": {
                    "cmd_args": "--enable --config config.yaml arg1 etc/test2.conf ",
                    "test_param": "debug_value",
                    "file_param": "etc/test.conf",
                    "encrypt_param": "secret",
                },
            },
            # bkmonitorbeat_debug.yaml
            {
                "bk_tenant_id": "test_tenant",
                "plugin_name": "test_plugin",
                "plugin_version": "*",
                "name": "bkmonitorbeat_debug.yaml",
                "version": "1",
                "data": {
                    "labels": {
                        "$for": "cmdb_instance.scope",
                        "$item": "scope",
                        "$body": {"host_ip": "{{ cmdb_instance.host.bk_host_innerip or 'bk_host_innerip' or '-' }}"},
                    },
                    "period": 300,
                    "timeout": 30,
                },
            },
            # {{file1}}
            {
                "bk_tenant_id": "test_tenant",
                "plugin_name": "test_plugin",
                "plugin_version": "*",
                "name": "{{file1}}",
                "version": "1",
                "data": {"file1": "test.conf", "file1_content": "$NODEMAN_BASE64_PREFIX$Y29udGVudA=="},
            },
            # {{file2}}
            {
                "bk_tenant_id": "test_tenant",
                "plugin_name": "test_plugin",
                "plugin_version": "*",
                "name": "{{file2}}",
                "version": "1",
                "data": {"file2": "test2.conf", "file2_content": "$NODEMAN_BASE64_PREFIX$Y29udGVudDI="},
            },
        ]

        for i, expected_call in enumerate(expected_render_calls):
            actual_call = render_plugin_config_template_mocker.call_args_list[i][1]
            assert actual_call == expected_call, f"第{i + 1}次render调用参数不匹配: {actual_call}"

        # 验证 start_plugin_debug 被调用
        assert start_plugin_debug_mocker.called
        assert start_plugin_debug_mocker.call_count == 1

        # 验证 start_plugin_debug 调用参数
        expected_start_debug_call = {
            "bk_tenant_id": "test_tenant",
            "params": {
                "plugin_name": "test_plugin",
                "version": "1.0",
                "config_ids": [100, 100, 100, 100],  # 4个配置文件，每个返回id=100
                "host_info": {"bk_host_id": 1},
            },
        }
        actual_start_debug_call = start_plugin_debug_mocker.call_args[1]
        assert actual_start_debug_call == expected_start_debug_call, (
            f"start_plugin_debug调用参数不匹配: {actual_start_debug_call}"
        )

    def test_stop_debug(self, mocker: MockerFixture):
        """测试停止调试"""
        # 模拟 stop_plugin_debug API 调用
        stop_plugin_debug_mocker = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.base.stop_plugin_debug"
        )

        task_id = 12345
        operator = "admin"

        # 调用 stop_debug 方法
        self.plugin_manager.stop_debug(task_id=task_id, operator=operator)

        # 验证 stop_plugin_debug 被调用
        assert stop_plugin_debug_mocker.called
        assert stop_plugin_debug_mocker.call_count == 1

        # 验证 stop_plugin_debug 调用参数
        expected_call = {
            "bk_tenant_id": "test_tenant",
            "task_id": 12345,
        }
        actual_call = stop_plugin_debug_mocker.call_args[1]
        assert actual_call == expected_call, f"stop_plugin_debug调用参数不匹配: {actual_call}"

    def test_export(self, mocker: MockerFixture):
        """测试导出插件"""
        # 模拟 create_export_plugin_task API 调用
        create_export_plugin_task_mocker = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.base.create_export_plugin_task", return_value=999
        )

        # 模拟 query_export_plugin_task API 调用 - 成功情况
        query_export_plugin_task_mocker = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.base.query_export_plugin_task",
            return_value={
                "is_finish": True,
                "is_failed": False,
                "download_url": "https://example.com/download/plugin.tgz",
            },
        )

        # 设置插件状态为 RELEASE（导出所需）
        self.plugin.status = MetricPluginStatus.RELEASE
        operator = "admin"

        # 调用 export 方法
        download_url = self.plugin_manager.export_package(operator=operator)

        # 验证返回值
        assert download_url == "https://example.com/download/plugin.tgz"

        # 验证 create_export_plugin_task 被调用
        assert create_export_plugin_task_mocker.called
        assert create_export_plugin_task_mocker.call_count == 1

        # 验证 create_export_plugin_task 调用参数
        expected_create_call = {
            "bk_tenant_id": "test_tenant",
            "category": "gse_plugin",
            "query_params": {"project": "test_plugin", "version": "1.0"},
            "creator": "admin",
            "bk_app_code": "bk_monitorv3",
        }
        actual_create_call = create_export_plugin_task_mocker.call_args[1]
        assert actual_create_call == expected_create_call, (
            f"create_export_plugin_task调用参数不匹配: {actual_create_call}"
        )

        # 验证 query_export_plugin_task 被调用
        assert query_export_plugin_task_mocker.called
        assert query_export_plugin_task_mocker.call_count == 1

        # 验证 query_export_plugin_task 调用参数
        expected_query_call = {"bk_tenant_id": "test_tenant", "job_id": 999}
        actual_query_call = query_export_plugin_task_mocker.call_args[1]
        assert actual_query_call == expected_query_call, f"query_export_plugin_task调用参数不匹配: {actual_query_call}"

    def test_export_failed_not_released(self):
        """测试导出插件失败 - 插件未发布"""
        # 插件状态默认为 DEBUG（非 RELEASE）
        operator = "admin"

        # 调用 export 方法应该抛出 ExportPluginFailedError
        with pytest.raises(ExportPluginFailedError, match="plugin test_plugin\\(1\\.0\\) is not released"):
            self.plugin_manager.export_package(operator=operator)

    def test_export_failed_task_error(self, mocker: MockerFixture):
        """测试导出插件失败 - 任务执行失败"""
        # 模拟 create_export_plugin_task API 调用
        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.base.create_export_plugin_task", return_value=999
        )

        # 模拟 query_export_plugin_task API 调用 - 失败情况
        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.base.query_export_plugin_task",
            return_value={"is_finish": True, "is_failed": True, "error_message": "Export task failed"},
        )

        # 设置插件状态为 RELEASE
        self.plugin.status = MetricPluginStatus.RELEASE
        operator = "admin"

        # 调用 export 方法应该抛出 ExportPluginFailedError
        with pytest.raises(ExportPluginFailedError, match="Export task failed"):
            self.plugin_manager.export_package(operator=operator)

    def test_export_timeout(self, mocker: MockerFixture):
        """测试导出插件超时"""
        # 模拟 time.sleep 避免实际等待
        mocker.patch("time.sleep")

        # 模拟 create_export_plugin_task API 调用
        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.base.create_export_plugin_task", return_value=999
        )

        # 模拟 query_export_plugin_task API 调用 - 永不完成
        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.base.query_export_plugin_task",
            return_value={"is_finish": False, "is_failed": False},
        )

        # 设置插件状态为 RELEASE
        self.plugin.status = MetricPluginStatus.RELEASE
        operator = "admin"

        # 调用 export 方法应该抛出 ExportPluginTimeoutError
        with pytest.raises(ExportPluginTimeoutError):
            self.plugin_manager.export_package(operator=operator)

    def test_get_deploy_steps_params(self, mocker):
        collect_params = {"period": 300, "timeout": 30, "exclude_metrics": ["metric1", "metric2"]}
        plugin_params = {
            "test_param": "debug_value",
            "--enable": "true",
            "--config": "config.yaml",
            "pos_arg": "arg1",
            "file_param": {"filename": "test.conf", "file_base64": base64.b64encode(b"content").decode()},
            "file_param2": {"filename": "test2.conf", "file_base64": base64.b64encode(b"content2").decode()},
            "encrypt_param": "secret",
            "host_dms": {"host_ip": "bk_host_innerip"},
        }

        steps_params = self.plugin_manager.get_deploy_steps_params(
            bk_biz_id=1,
            collect_task_id=2,
            bk_data_ids={"bk_data_id": 3},
            collect_params=collect_params,
            plugin_params=plugin_params,
            target_nodes=[{"host_ip": "127.0.0.1"}],
        )

        expected_steps_params = [
            {
                "id": "test_plugin",
                "type": "PLUGIN",
                "config": {
                    "plugin_name": "test_plugin",
                    "plugin_version": "1.0",
                    "config_templates": [
                        {"name": "env.yaml", "version": "1"},
                        {"name": "{{file1}}", "version": "1", "content": "{{file1_content}}"},
                        {"name": "{{file2}}", "version": "1", "content": "{{file2_content}}"},
                    ],
                },
                "params": {
                    "context": {
                        "test_param": "debug_value",
                        "file_param": "etc/test.conf",
                        "encrypt_param": "secret",
                        "cmd_args": "--enable --config config.yaml arg1 etc/test2.conf ",
                        "file1": "test.conf",
                        "file1_content": "$NODEMAN_BASE64_PREFIX$Y29udGVudA==",
                        "file2": "test2.conf",
                        "file2_content": "$NODEMAN_BASE64_PREFIX$Y29udGVudDI=",
                    }
                },
            },
            {
                "id": "bkmonitorbeat",
                "type": "PLUGIN",
                "config": {
                    "plugin_name": "bkmonitorbeat",
                    "plugin_version": "latest",
                    "config_templates": [{"name": "bkmonitorbeat_script.conf", "version": "latest"}],
                },
                "params": {
                    "context": {
                        "period": "300",
                        "task_id": "2",
                        "bk_biz_id": "1",
                        "config_name": "test_plugin",
                        "config_version": "1.0",
                        "namespace": "test_plugin",
                        "timeout": "30",
                        "max_timeout": "30",
                        "dataid": 3,
                        "labels": {
                            "$for": "cmdb_instance.scope",
                            "$item": "scope",
                            "$body": {
                                "bk_target_host_id": "{{ cmdb_instance.host.bk_host_id }}",
                                "bk_target_ip": "{{ cmdb_instance.host.bk_host_innerip }}",
                                "bk_target_cloud_id": "{{ cmdb_instance.host.bk_cloud_id[0].id if cmdb_instance.host.bk_cloud_id is iterable and cmdb_instance.host.bk_cloud_id is not string else cmdb_instance.host.bk_cloud_id }}",
                                "bk_target_topo_level": "{{ scope.bk_obj_id }}",
                                "bk_target_topo_id": "{{ scope.bk_inst_id }}",
                                "bk_target_service_category_id": "{{ cmdb_instance.service.service_category_id | default('', true) }}",
                                "bk_target_service_instance_id": "{{ cmdb_instance.service.id }}",
                                "bk_collect_config_id": "2",
                                "host_ip": "{{ cmdb_instance.host.bk_host_innerip or 'bk_host_innerip' or '-' }}",
                            },
                        },
                        "command": "{{ step_data.test_plugin.control_info.setup_path }}/{{ step_data.test_plugin.control_info.start_cmd }}",
                        "metric_relabel_configs": [
                            {"source_labels": ["__name__"], "action": "drop", "regex": "metric1|metric2"}
                        ],
                    }
                },
            },
        ]
        assert steps_params == expected_steps_params

    def test_get_deploy_steps_params_without_exclude_metrics(self):
        """测试 exclude_metrics 为空时不生成 metric_relabel_configs。"""
        collect_params = {"period": 300, "timeout": 30, "exclude_metrics": []}
        plugin_params = {
            "test_param": "debug_value",
            "--enable": "true",
            "--config": "config.yaml",
            "pos_arg": "arg1",
            "file_param": {"filename": "test.conf", "file_base64": base64.b64encode(b"content").decode()},
            "file_param2": {"filename": "test2.conf", "file_base64": base64.b64encode(b"content2").decode()},
            "encrypt_param": "secret",
            "host_dms": {"host_ip": "bk_host_innerip"},
        }

        steps_params = self.plugin_manager.get_deploy_steps_params(
            bk_biz_id=1,
            collect_task_id=2,
            bk_data_ids={"bk_data_id": 3},
            collect_params=collect_params,
            plugin_params=plugin_params,
            target_nodes=[{"host_ip": "127.0.0.1"}],
        )

        expected_steps_params = [
            {
                "id": "test_plugin",
                "type": "PLUGIN",
                "config": {
                    "plugin_name": "test_plugin",
                    "plugin_version": "1.0",
                    "config_templates": [
                        {"name": "env.yaml", "version": "1"},
                        {"name": "{{file1}}", "version": "1", "content": "{{file1_content}}"},
                        {"name": "{{file2}}", "version": "1", "content": "{{file2_content}}"},
                    ],
                },
                "params": {
                    "context": {
                        "test_param": "debug_value",
                        "file_param": "etc/test.conf",
                        "encrypt_param": "secret",
                        "cmd_args": "--enable --config config.yaml arg1 etc/test2.conf ",
                        "file1": "test.conf",
                        "file1_content": "$NODEMAN_BASE64_PREFIX$Y29udGVudA==",
                        "file2": "test2.conf",
                        "file2_content": "$NODEMAN_BASE64_PREFIX$Y29udGVudDI=",
                    }
                },
            },
            {
                "id": "bkmonitorbeat",
                "type": "PLUGIN",
                "config": {
                    "plugin_name": "bkmonitorbeat",
                    "plugin_version": "latest",
                    "config_templates": [{"name": "bkmonitorbeat_script.conf", "version": "latest"}],
                },
                "params": {
                    "context": {
                        "period": "300",
                        "task_id": "2",
                        "bk_biz_id": "1",
                        "config_name": "test_plugin",
                        "config_version": "1.0",
                        "namespace": "test_plugin",
                        "timeout": "30",
                        "max_timeout": "30",
                        "dataid": 3,
                        "labels": {
                            "$for": "cmdb_instance.scope",
                            "$item": "scope",
                            "$body": {
                                "bk_target_host_id": "{{ cmdb_instance.host.bk_host_id }}",
                                "bk_target_ip": "{{ cmdb_instance.host.bk_host_innerip }}",
                                "bk_target_cloud_id": "{{ cmdb_instance.host.bk_cloud_id[0].id if cmdb_instance.host.bk_cloud_id is iterable and cmdb_instance.host.bk_cloud_id is not string else cmdb_instance.host.bk_cloud_id }}",
                                "bk_target_topo_level": "{{ scope.bk_obj_id }}",
                                "bk_target_topo_id": "{{ scope.bk_inst_id }}",
                                "bk_target_service_category_id": "{{ cmdb_instance.service.service_category_id | default('', true) }}",
                                "bk_target_service_instance_id": "{{ cmdb_instance.service.id }}",
                                "bk_collect_config_id": "2",
                                "host_ip": "{{ cmdb_instance.host.bk_host_innerip or 'bk_host_innerip' or '-' }}",
                            },
                        },
                        "command": "{{ step_data.test_plugin.control_info.setup_path }}/{{ step_data.test_plugin.control_info.start_cmd }}",
                    }
                },
            },
        ]

        assert steps_params == expected_steps_params

    def test_get_supported_os_types(self):
        """测试获取支持的操作系统类型"""
        supported_os_types = self.plugin_manager.get_supported_os_types()
        actual_os_types = [os_type.value for os_type in supported_os_types]

        # 根据测试数据，应该支持linux
        expected_os_types = ["linux"]

        assert set(actual_os_types) == set(expected_os_types)

    def test_get_supported_os_types_multiple(self):
        """测试获取支持的操作系统类型 - 多个操作系统"""
        plugin = MetricPlugin(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            id="test_plugin",
            type="script",
            name="测试插件",
            description_md="测试",
            version=VersionTuple(1, 0),
            status=MetricPluginStatus.DEBUG,
            created_by="admin",
            updated_by="admin",
            define={
                "linux": {
                    "type": "shell",
                    "filename": "test.sh",
                    "script_content_base64": base64.b64encode(b"echo 'linux'").decode("utf-8"),
                },
                "windows": {
                    "type": "bat",
                    "filename": "test.bat",
                    "script_content_base64": base64.b64encode(b"echo 'windows'").decode("utf-8"),
                },
            },
        )
        plugin_manager = ScriptPluginManager(plugin)

        supported_os_types = plugin_manager.get_supported_os_types()
        actual_os_types = [os_type.value for os_type in supported_os_types]

        expected_os_types = ["linux", "windows"]
        assert set(actual_os_types) == set(expected_os_types)

    def test_get_supported_os_types_empty(self):
        """测试获取支持的操作系统类型 - 空define"""
        plugin = MetricPlugin(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            id="test_plugin",
            type="script",
            name="测试插件",
            description_md="测试",
            version=VersionTuple(1, 0),
            status=MetricPluginStatus.DEBUG,
            created_by="admin",
            updated_by="admin",
            define={},
        )
        plugin_manager = ScriptPluginManager(plugin)
        supported_os_types = plugin_manager.get_supported_os_types()
        assert len(supported_os_types) == 0

    @pytest.mark.django_db(databases=["default"])
    def test_parse_define_success(self, tmp_path: Path):
        """测试 _parse_define 方法 - 成功场景"""
        plugin_id = "test_script_plugin"
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        # 创建多个操作系统目录和脚本文件
        os_configs = [
            ("external_plugins_linux_x86_64", "linux", "shell", "test.sh", "#!/bin/bash\necho 'test'"),
            ("external_plugins_windows_x86_64", "windows", "bat", "test.bat", "@echo off\necho test"),
            ("external_plugins_aix_powerpc", "aix", "ksh", "test.ksh", "#!/bin/ksh\necho 'test'"),
        ]

        meta_scripts = {}

        for _os_dir_name, os_type_str, script_type, filename, script_content in os_configs:
            plugin_dir = extract_dir / _os_dir_name / plugin_id
            plugin_dir.mkdir(parents=True)

            # 创建脚本文件
            script_file = plugin_dir / filename
            script_file.write_text(script_content, encoding="utf-8")

            # 添加到meta_scripts
            meta_scripts[os_type_str] = {
                "type": script_type,
                "filename": filename,
            }

        meta_data = {
            "plugin_id": plugin_id,
            "plugin_display_name": "测试脚本插件",
            "plugin_type": "Script",
            "scripts": meta_scripts,
        }

        # 调用 _parse_define
        result = ScriptPluginManager._parse_define(
            bk_tenant_id="test_tenant",
            operator="test_user",
            extract_dir=extract_dir,
            plugin_id=plugin_id,
            meta_data=meta_data,
        )

        # 验证结果
        for _os_dir_name, os_type_str, script_type, filename, script_content in os_configs:
            assert os_type_str in result
            assert result[os_type_str]["type"] == script_type
            assert result[os_type_str]["filename"] == filename
            assert "script_content_base64" in result[os_type_str]

            # 验证base64编码的内容
            import base64

            decoded_content = base64.b64decode(result[os_type_str]["script_content_base64"]).decode("utf-8")
            assert decoded_content == script_content

    def test_parse_define_missing_scripts(self, tmp_path: Path):
        """测试 _parse_define 方法 - meta.yaml 缺少 scripts 配置"""
        plugin_id = "test_plugin"
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        meta_data = {
            "plugin_id": plugin_id,
            "plugin_display_name": "测试插件",
            "plugin_type": "Script",
            # 缺少 scripts
        }

        with pytest.raises(ValueError, match="meta.yaml 中未找到 scripts 配置"):
            ScriptPluginManager._parse_define(
                bk_tenant_id="test_tenant",
                operator="test_user",
                extract_dir=extract_dir,
                plugin_id=plugin_id,
                meta_data=meta_data,
            )

    def test_parse_define_empty_scripts(self, tmp_path: Path):
        """测试 _parse_define 方法 - scripts 配置为空"""
        plugin_id = "test_plugin"
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        meta_data = {
            "plugin_id": plugin_id,
            "plugin_display_name": "测试插件",
            "plugin_type": "Script",
            "scripts": {},  # 空字典
        }

        with pytest.raises(ValueError, match="meta.yaml 中未找到 scripts 配置"):
            ScriptPluginManager._parse_define(
                bk_tenant_id="test_tenant",
                operator="test_user",
                extract_dir=extract_dir,
                plugin_id=plugin_id,
                meta_data=meta_data,
            )

    def test_parse_define_invalid_script_info_type(self, tmp_path: Path):
        """测试 _parse_define 方法 - scripts 配置中值不是字典类型"""
        plugin_id = "test_plugin"
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        meta_data = {
            "plugin_id": plugin_id,
            "plugin_display_name": "测试插件",
            "plugin_type": "Script",
            "scripts": {
                "linux": "not_a_dict",  # 应该是字典
            },
        }

        with pytest.raises(ValueError, match="scripts 配置中.*的值必须是字典类型"):
            ScriptPluginManager._parse_define(
                bk_tenant_id="test_tenant",
                operator="test_user",
                extract_dir=extract_dir,
                plugin_id=plugin_id,
                meta_data=meta_data,
            )

    def test_parse_define_missing_type_field(self, tmp_path: Path):
        """测试 _parse_define 方法 - scripts 配置中缺少 type 字段"""
        plugin_id = "test_plugin"
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        meta_data = {
            "plugin_id": plugin_id,
            "plugin_display_name": "测试插件",
            "plugin_type": "Script",
            "scripts": {
                "linux": {
                    "filename": "test.sh",
                    # 缺少 type
                },
            },
        }

        with pytest.raises(ValueError, match="scripts 配置中.*缺少 type 字段或类型不正确"):
            ScriptPluginManager._parse_define(
                bk_tenant_id="test_tenant",
                operator="test_user",
                extract_dir=extract_dir,
                plugin_id=plugin_id,
                meta_data=meta_data,
            )

    def test_parse_define_missing_filename_field(self, tmp_path: Path):
        """测试 _parse_define 方法 - scripts 配置中缺少 filename 字段"""
        plugin_id = "test_plugin"
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        meta_data = {
            "plugin_id": plugin_id,
            "plugin_display_name": "测试插件",
            "plugin_type": "Script",
            "scripts": {
                "linux": {
                    "type": "shell",
                    # 缺少 filename
                },
            },
        }

        with pytest.raises(ValueError, match="scripts 配置中.*缺少 filename 字段或类型不正确"):
            ScriptPluginManager._parse_define(
                bk_tenant_id="test_tenant",
                operator="test_user",
                extract_dir=extract_dir,
                plugin_id=plugin_id,
                meta_data=meta_data,
            )

    def test_parse_define_unsupported_os_type(self, tmp_path: Path):
        """测试 _parse_define 方法 - 不支持的操作系统类型"""
        plugin_id = "test_plugin"
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        meta_data = {
            "plugin_id": plugin_id,
            "plugin_display_name": "测试插件",
            "plugin_type": "Script",
            "scripts": {
                "unsupported_os": {  # 不支持的操作系统
                    "type": "shell",
                    "filename": "test.sh",
                },
            },
        }

        with pytest.raises(ValueError, match="不支持的操作系统类型"):
            ScriptPluginManager._parse_define(
                bk_tenant_id="test_tenant",
                operator="test_user",
                extract_dir=extract_dir,
                plugin_id=plugin_id,
                meta_data=meta_data,
            )

    def test_parse_define_missing_script_file(self, tmp_path: Path):
        """测试 _parse_define 方法 - 脚本文件不存在"""
        plugin_id = "test_plugin"
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        # 创建目录但不创建脚本文件
        os_dir_name = "external_plugins_linux_x86_64"
        plugin_dir = extract_dir / os_dir_name / plugin_id
        plugin_dir.mkdir(parents=True)
        # 不创建脚本文件

        meta_data = {
            "plugin_id": plugin_id,
            "plugin_display_name": "测试插件",
            "plugin_type": "Script",
            "scripts": {
                "linux": {
                    "type": "shell",
                    "filename": "test.sh",
                },
            },
        }

        with pytest.raises(ValueError, match="脚本文件不存在"):
            ScriptPluginManager._parse_define(
                bk_tenant_id="test_tenant",
                operator="test_user",
                extract_dir=extract_dir,
                plugin_id=plugin_id,
                meta_data=meta_data,
            )
