import tarfile
from types import SimpleNamespace

import pytest
import yaml

from bkmonitor.nodeman_integration.v3.client import NodeManV3UnknownResultError
from monitor_web.models.node_man import (
    MonitorNodeManOperation,
    MonitorNodeManWorkflow,
    NodeManOperationStatus,
    NodeManOperationType,
    NodeManWorkflowDispatchStatus,
)
from monitor_web.models.plugin import CollectorPluginMeta
from monitor_web.plugin.constant import DebugStatus, PluginType
from monitor_web.plugin.nodeman_v3 import (
    NodeManV3PackageBuilder,
    NodeManV3PackageWorkflowService,
    NodeManV3PluginDebugService,
)


class FakeStorage:
    def __init__(self):
        self.saved = []

    def save(self, name, content):
        self.saved.append((name, content.read()))
        return name

    @staticmethod
    def url(name):
        return f"https://files.example/{name}"


class FakePackageWorkflowClient:
    def __init__(self, *, unknown=False):
        self.unknown = unknown
        self.calls = []

    def import_plugin_v3(self, payload, *, context):
        self.calls.append(("import", payload, context))
        if self.unknown:
            raise NodeManV3UnknownResultError("timeout")
        return {"workflow_id": "package-workflow"}

    def import_result(self, payload, *, context):
        self.calls.append(("import_result", payload, context))
        return {"status": "success", "is_finish": True, "operations": []}

    def export_plugin(self, payload, *, context):
        self.calls.append(("export", payload, context))
        return {"workflow_id": "export-workflow"}

    def export_result(self, payload, *, context):
        self.calls.append(("export_result", payload, context))
        return {"status": "success", "is_finish": True, "download_url": "https://files.example/export.tgz"}


class FakePackageClient:
    def __init__(self):
        self.calls = []

    def list_plugin_releases(self, payload, *, context):
        self.calls.append((payload, context))
        return {
            "total": 1,
            "items": [
                {
                    "release": {
                        "name": "mysql_exporter",
                        "version": "1.2",
                        "os_type": "linux",
                        "cpu_arch": "x86_64",
                        "enabled": True,
                    }
                }
            ],
        }


class FakeLogicalPluginClient:
    def __init__(self):
        self.calls = []

    def list(self, payload, *, context):
        self.calls.append((payload, context))
        return {"total": 1, "items": [{"name": "mysql_exporter", "pkg_name": "mysql_exporter"}]}


@pytest.fixture
def plugin(db):
    return CollectorPluginMeta.objects.create(
        bk_tenant_id="tenant-a",
        bk_biz_id=2,
        plugin_id="mysql_exporter",
        plugin_type=PluginType.EXPORTER,
    )


def test_v3_package_builder_translates_layout_and_keeps_jinja2_templates(tmp_path):
    plugin = SimpleNamespace(plugin_id="mysql_exporter")
    manager = SimpleNamespace(plugin=plugin, tmp_path=str(tmp_path))

    def make_package():
        source = tmp_path / plugin.plugin_id / "external_plugins_linux_x86_64" / plugin.plugin_id
        (source / "etc").mkdir(parents=True)
        (source / "project.yaml").write_text(
            yaml.safe_dump(
                {
                    "name": plugin.plugin_id,
                    "version": "1.2",
                    "description": "MySQL exporter",
                    "description_en": "MySQL exporter",
                    "launch_node": "all",
                    "port_range": "9102,10000-65535",
                    "control": {"start": "./start.sh", "stop": "./stop.sh"},
                    "config_templates": [
                        {
                            "name": "env.yaml",
                            "file_path": "etc",
                            "source_path": "etc/env.yaml.tpl",
                        },
                        {
                            "name": "config.yaml",
                            "file_path": "etc",
                            "source_path": "etc/config.yaml.tpl",
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        (source / "etc" / "env.yaml.tpl").write_text("port: {{ port }}", encoding="utf-8")
        (source / "etc" / "config.yaml.tpl").write_text("modules: {{ modules }}", encoding="utf-8")
        (source / "etc" / "bkmonitorbeat_debug.yaml.tpl").write_text("period: {{ period }}", encoding="utf-8")
        (source / "start.sh").write_text("#!/bin/sh\n", encoding="utf-8")

    manager.make_package = make_package
    archive = NodeManV3PackageBuilder().build(manager)

    with tarfile.open(archive) as package:
        names = set(package.getnames())
        project = yaml.safe_load(package.extractfile("mysql_exporter/project.yaml"))
        definition = yaml.safe_load(package.extractfile("mysql_exporter/plugins_linux_x86_64/definition.yaml"))

    assert project["templateRenderer"] == "jinja2"
    assert project["name"] == "mysql_exporter"
    assert definition["bindAddressAllocated"] == {
        "enable": True,
        "bindIP": "127.0.0.1",
        "bindPortAvailableRange": "9102,10000-65535",
    }
    assert definition["configTemplates"] == [
        {
            "name": "bkmonitorbeat_debug.yaml",
            "isMainConfig": False,
            "filePath": "etc",
            "sourcePath": "templates/bkmonitorbeat_debug.yaml.template",
            "variables": [],
        },
        {
            "name": "config.yaml",
            "isMainConfig": False,
            "filePath": "etc",
            "sourcePath": "templates/config.yaml.template",
            "variables": [],
        },
        {
            "name": "env.yaml",
            "isMainConfig": True,
            "filePath": "etc",
            "sourcePath": "templates/env.yaml.template",
            "variables": [],
        },
    ]
    assert "mysql_exporter/plugins_linux_x86_64/bin/start.sh" in names
    assert "mysql_exporter/plugins_linux_x86_64/templates/env.yaml.template" in names


@pytest.mark.django_db(transaction=True)
def test_package_import_uses_v3_workflow_and_persists_success(plugin, tmp_path):
    archive = tmp_path / "mysql_exporter.tgz"
    archive.write_bytes(b"package")
    workflow_client = FakePackageWorkflowClient()
    package_client = FakePackageClient()
    plugin_client = FakeLogicalPluginClient()
    manager = SimpleNamespace(plugin=plugin, version=SimpleNamespace(version="1.2"))
    package_builder = SimpleNamespace(
        build=lambda plugin_manager: str(archive),
        expected_platforms=lambda path: {("linux", "x86_64")},
    )
    service = NodeManV3PackageWorkflowService(
        workflow_client=workflow_client,
        package_client=package_client,
        plugin_client=plugin_client,
        package_builder=package_builder,
        storage=FakeStorage(),
        sleeper=lambda _: None,
    )

    assert service.register(manager) == {"status": "success", "is_finish": True, "operations": []}

    operation = MonitorNodeManOperation.objects.get(operation_type=NodeManOperationType.PACKAGE_IMPORT)
    workflow = operation.workflows.get()
    assert operation.status == NodeManOperationStatus.SUCCESS
    assert workflow.workflow_id == "package-workflow"
    assert workflow.dispatch_status == NodeManWorkflowDispatchStatus.SUBMITTED
    assert workflow_client.calls[0][1] == {
        "filename": "mysql_exporter.tgz",
        "download_url": workflow_client.calls[0][1]["download_url"],
        "md5": "efe90a8e604a7c840e88d03a67f6b7d8",
    }
    assert package_client.calls[0][0]["exact_include_conditions"] == {
        "name": ["mysql_exporter"],
        "version": ["1.2"],
        "platform": [{"os_type": "linux", "cpu_arch": "x86_64"}],
        "enabled": [True],
    }
    assert plugin_client.calls[0][0]["exact_include_conditions"] == {"name": ["mysql_exporter"]}


@pytest.mark.django_db(transaction=True)
def test_package_import_preserves_unknown_write_result(plugin, tmp_path):
    archive = tmp_path / "mysql_exporter.tgz"
    archive.write_bytes(b"package")
    manager = SimpleNamespace(plugin=plugin, version=SimpleNamespace(version="1.2"))
    package_builder = SimpleNamespace(
        build=lambda plugin_manager: str(archive),
        expected_platforms=lambda path: {("linux", "x86_64")},
    )
    service = NodeManV3PackageWorkflowService(
        workflow_client=FakePackageWorkflowClient(unknown=True),
        package_client=FakePackageClient(),
        plugin_client=FakeLogicalPluginClient(),
        package_builder=package_builder,
        storage=FakeStorage(),
    )

    with pytest.raises(NodeManV3UnknownResultError):
        service.register(manager)

    operation = MonitorNodeManOperation.objects.get(operation_type=NodeManOperationType.PACKAGE_IMPORT)
    workflow = operation.workflows.get()
    assert operation.status == NodeManOperationStatus.UNKNOWN
    assert workflow.dispatch_status == NodeManWorkflowDispatchStatus.UNKNOWN
    assert operation.result_state == "write_result_unknown"


@pytest.mark.django_db(transaction=True)
def test_package_export_uses_v3_workflow(plugin):
    service = NodeManV3PackageWorkflowService(
        workflow_client=FakePackageWorkflowClient(),
        package_client=FakePackageClient(),
        plugin_client=FakeLogicalPluginClient(),
        sleeper=lambda _: None,
    )

    assert service.export(plugin, "1.2") == "https://files.example/export.tgz"
    operation = MonitorNodeManOperation.objects.get(operation_type=NodeManOperationType.PLUGIN_EXPORT)
    assert operation.status == NodeManOperationStatus.SUCCESS
    assert operation.workflows.get().workflow_id == "export-workflow"


class FakePluginClient:
    def __init__(self):
        self.calls = []

    def start_debug(self, payload, *, context):
        self.calls.append(("start", payload, context))
        return {"workflow_id": "debug-workflow"}

    def stop_debug(self, payload, *, context):
        self.calls.append(("stop", payload, context))
        return {}


class FakeWorkflowClient:
    def list_workflows(self, payload, *, context):
        return {"total": 1, "items": [{"workflow_id": "debug-workflow", "status": "success"}]}

    def list_operations(self, payload, *, context):
        return {
            "total": 1,
            "operations": [
                {
                    "instance_ids": ["instance-1"],
                    "latest_oper_inst_brief_data": {"life_cycle": {"state": "success"}},
                }
            ],
        }

    def get_operation_instance_log(self, payload, *, context):
        return {
            "oper_inst_logs": {"debug": {"message": {"logs": [{"text_zh": '{"beat": true, "type": "status"}'}]}}},
            "extra_execution_logs": {"logs": [{"text_en": "debug complete"}]},
        }


@pytest.mark.django_db(transaction=True)
def test_plugin_debug_uses_host_scope_and_direct_workflow_query(plugin):
    plugin_client = FakePluginClient()
    scheduled = []
    service = NodeManV3PluginDebugService(
        plugin_client=plugin_client,
        workflow_client=FakeWorkflowClient(),
        poll_scheduler=scheduled.append,
    )
    manager = SimpleNamespace(
        plugin=plugin,
        _get_debug_config_context=lambda *args: {
            "env.yaml": {"port": 9102},
            "bkmonitorbeat_debug.yaml": {"period": 60},
        },
    )
    plugin.get_debug_version = lambda config_version: SimpleNamespace(version="1.2")

    workflow_id = service.start(
        manager,
        config_version=1,
        info_version=2,
        param={},
        host_info={"bk_biz_id": 2, "bk_host_id": 101},
    )
    assert workflow_id == "debug-workflow"
    assert plugin_client.calls[0][1] == {
        "debug_info": {
            "scope": {"granularity": "host", "bk_biz_id": 2, "instance_ids": [101]},
            "plugin_name": "mysql_exporter",
            "version": "1.2",
            "config_template_name": ["env.yaml", "bkmonitorbeat_debug.yaml"],
            "custom_config_context": {"port": 9102, "period": 60},
        }
    }
    assert service.query(plugin, workflow_id) == {
        "status": DebugStatus.SUCCESS,
        "message": '{"beat": true, "type": "status"}\ndebug complete',
        "step": "DEBUG_PROCESS",
    }
    service.stop(plugin, workflow_id)
    assert plugin_client.calls[-1][0:2] == ("stop", {"workflow_id": "debug-workflow"})
    assert MonitorNodeManWorkflow.objects.filter(workflow_id="debug-workflow").count() == 2
    terminate = MonitorNodeManOperation.objects.get(operation_type=NodeManOperationType.TERMINATE)
    assert terminate.status == NodeManOperationStatus.RUNNING
    assert scheduled == [str(terminate.pk)]
