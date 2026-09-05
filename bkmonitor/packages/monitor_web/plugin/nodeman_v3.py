from __future__ import annotations

import hashlib
import os
import shutil
import tarfile
import time
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

import yaml
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone

from bkmonitor.nodeman_integration.v3.client import (
    NodeManV3HTTPClient,
    NodeManV3RequestContext,
    NodeManV3UnknownResultError,
)
from bkmonitor.nodeman_integration.v3.client.package import PackageClient, PackageWorkflowClient, PluginClient
from bkmonitor.nodeman_integration.v3.client.workflow import WorkflowClient
from bkmonitor.nodeman_integration.v3.exceptions import NodeManV3PayloadError, NodeManV3ResultState
from core.errors.plugin import ExportPluginError, ExportPluginTimeout, RegisterPackageError
from monitor_web.models.node_man import (
    MonitorNodeManOperation,
    MonitorNodeManWorkflow,
    NodeManIntegrationBinding,
    NodeManOperationStatus,
    NodeManOperationType,
    NodeManResourceType,
    NodeManWorkflowDispatchStatus,
    NodeManWorkflowStatus,
    build_nodeman_resource_key,
)
from monitor_web.nodeman_integration.v3.operation import NodeManV3OperationService
from monitor_web.plugin.constant import DebugStatus


class NodeManV3PackageBuilder:
    """Convert the monitor-generated external-plugin package into the documented V3 package layout."""

    PLATFORM_PREFIX = "external_plugins_"

    def build(self, plugin_manager) -> str:
        # Keep the existing per-plugin builders as the single source for binaries,
        # scripts and rendered Jinja2 templates, then only translate the package layout.
        plugin_manager.make_package()
        source_root = Path(plugin_manager.tmp_path) / plugin_manager.plugin.plugin_id
        if not source_root.is_dir():
            raise NodeManV3PayloadError(f"generated plugin package directory is missing: {source_root}")

        package_root = Path(plugin_manager.tmp_path) / "nodeman_v3" / plugin_manager.plugin.plugin_id
        if package_root.parent.exists():
            shutil.rmtree(package_root.parent)
        package_root.mkdir(parents=True)

        project = None
        platform_count = 0
        for source_platform in sorted(source_root.iterdir()):
            if not source_platform.is_dir() or not source_platform.name.startswith(self.PLATFORM_PREFIX):
                continue
            source_plugin = source_platform / plugin_manager.plugin.plugin_id
            source_project = source_plugin / "project.yaml"
            if not source_project.is_file():
                raise NodeManV3PayloadError(f"generated plugin platform has no project.yaml: {source_platform.name}")
            with source_project.open(encoding="utf-8") as project_file:
                v2_project = yaml.safe_load(project_file) or {}
            if project is None:
                project = self._project(v2_project)

            target_platform = package_root / source_platform.name.removeprefix("external_")
            self._write_platform(source_plugin, target_platform, v2_project)
            platform_count += 1

        if project is None or platform_count == 0:
            raise NodeManV3PayloadError("generated plugin package has no supported platform")
        self._dump_yaml(package_root / "project.yaml", project)
        return self._archive(package_root)

    @staticmethod
    def _project(source: dict) -> dict:
        description = str(source.get("description") or source.get("name") or "")
        description_en = str(source.get("description_en") or description)
        return {
            "name": source.get("name"),
            "version": str(source.get("version")),
            "description": description,
            "descriptionEn": description_en,
            "scenario": str(source.get("scenario") or description),
            "scenarioEn": str(source.get("scenario_en") or description_en),
            "launchNode": str(source.get("launch_node") or "all").lower(),
            "templateRenderer": "jinja2",
        }

    def _write_platform(self, source_plugin: Path, target_platform: Path, source_project: dict) -> None:
        bin_dir = target_platform / "bin"
        templates_dir = target_platform / "templates"
        bin_dir.mkdir(parents=True)
        templates_dir.mkdir()

        config_templates = []
        declared_items = source_project.get("config_templates") or ()
        declared = {item.get("source_path"): item for item in declared_items}
        etc_dir = source_plugin / "etc"
        templates = sorted(etc_dir.rglob("*.tpl")) if etc_dir.is_dir() else []
        available_paths = {template.relative_to(source_plugin).as_posix() for template in templates}
        main_source_path = next(
            (item.get("source_path") for item in declared_items if item.get("source_path") in available_paths),
            None,
        )
        if main_source_path is None and templates:
            env_template = next((template for template in templates if template.name == "env.yaml.tpl"), None)
            main_source_path = (env_template or templates[0]).relative_to(source_plugin).as_posix()
        if etc_dir.is_dir():
            for template in templates:
                relative = template.relative_to(source_plugin).as_posix()
                metadata = declared.get(relative, {})
                source_name = f"{template.name.removesuffix('.tpl')}.template"
                shutil.copyfile(template, templates_dir / source_name)
                config_templates.append(
                    {
                        "name": metadata.get("name") or template.name.removesuffix(".tpl"),
                        "isMainConfig": relative == main_source_path,
                        "filePath": metadata.get("file_path") or "etc",
                        "sourcePath": f"templates/{source_name}",
                        "variables": [],
                    }
                )

        for child in source_plugin.iterdir():
            if child.name in {"project.yaml", "etc", "info"}:
                continue
            destination = bin_dir / child.name
            if child.is_dir():
                shutil.copytree(child, destination)
            else:
                shutil.copy2(child, destination)

        definition = {
            "configTemplates": config_templates,
            "control": source_project.get("control") or {},
        }
        port_range = source_project.get("port_range")
        if port_range:
            definition["bindAddressAllocated"] = {
                "enable": True,
                "bindIP": "127.0.0.1",
                "bindPortAvailableRange": str(port_range),
            }
        self._dump_yaml(target_platform / "definition.yaml", definition)

    @staticmethod
    def expected_platforms(archive: str) -> set[tuple[str, str]]:
        platforms = set()
        with tarfile.open(archive) as package:
            for member in package.getmembers():
                parts = Path(member.name).parts
                if len(parts) < 2 or not parts[1].startswith("plugins_"):
                    continue
                _, os_type, cpu_arch = parts[1].split("_", 2)
                platforms.add((os_type, cpu_arch))
        if not platforms:
            raise NodeManV3PayloadError("NodeMan V3 plugin package has no platform directory")
        return platforms

    @staticmethod
    def _dump_yaml(path: Path, content: dict) -> None:
        with path.open("w", encoding="utf-8") as output:
            yaml.safe_dump(content, output, allow_unicode=True, sort_keys=False)

    @staticmethod
    def _archive(package_root: Path) -> str:
        archive = package_root.parent / f"{package_root.name}.tgz"
        with tarfile.open(archive, "w:gz") as output:
            output.add(package_root, arcname=package_root.name)
        return str(archive)


class NodeManV3PluginOperationRecorder:
    def __init__(self, plugin):
        self.plugin = plugin

    def prepare(
        self, operation_type: str, request_summary: dict
    ) -> tuple[MonitorNodeManOperation, MonitorNodeManWorkflow]:
        with transaction.atomic():
            binding, _ = NodeManIntegrationBinding.objects.get_or_create(
                resource_type=NodeManResourceType.MONITOR_PLUGIN,
                resource_key=build_nodeman_resource_key(
                    NodeManResourceType.MONITOR_PLUGIN,
                    plugin_id=self.plugin.plugin_id,
                ),
                owner_bk_tenant_id=self.plugin.bk_tenant_id,
                execution_bk_tenant_id=self.plugin.bk_tenant_id,
                bk_biz_id=self.plugin.bk_biz_id,
            )
            operation = MonitorNodeManOperation.objects.create(
                binding=binding,
                operation_type=operation_type,
                generation=binding.generation,
                request_summary=request_summary,
                status=NodeManOperationStatus.DISPATCHING,
                started_at=timezone.now(),
            )
            workflow = MonitorNodeManWorkflow.objects.create(
                monitor_operation=operation,
                batch_index=0,
                target_summary={"plugin_id": self.plugin.plugin_id},
                dispatch_status=NodeManWorkflowDispatchStatus.PREPARED,
            )
        return operation, workflow

    @staticmethod
    def submit(operation, workflow, submit: Callable, *, source_workflow_id: str | None = None) -> str:
        workflow.dispatch_status = NodeManWorkflowDispatchStatus.SUBMITTING
        workflow.save(update_fields=("dispatch_status", "updated_at"))
        context = NodeManV3RequestContext(
            bk_tenant_id=operation.binding.execution_bk_tenant_id,
            bk_biz_id=operation.binding.bk_biz_id,
            monitor_operation_id=str(operation.pk),
        )
        try:
            result = submit(context)
        except NodeManV3UnknownResultError as error:
            workflow.dispatch_status = NodeManWorkflowDispatchStatus.UNKNOWN
            workflow.normalized_status = NodeManWorkflowStatus.UNKNOWN
            workflow.result_state = NodeManV3ResultState.WRITE_RESULT_UNKNOWN
            workflow.dispatch_error = str(error)
            workflow.save(
                update_fields=(
                    "dispatch_status",
                    "normalized_status",
                    "result_state",
                    "dispatch_error",
                    "updated_at",
                )
            )
            operation.status = NodeManOperationStatus.UNKNOWN
            operation.result_state = NodeManV3ResultState.WRITE_RESULT_UNKNOWN
            operation.error_summary = str(error)
            operation.save(update_fields=("status", "result_state", "error_summary", "updated_at"))
            raise
        except Exception as error:
            workflow.dispatch_status = NodeManWorkflowDispatchStatus.DEFINITE_FAILED
            workflow.normalized_status = NodeManWorkflowStatus.FAILED
            workflow.dispatch_error = str(error)
            workflow.save(update_fields=("dispatch_status", "normalized_status", "dispatch_error", "updated_at"))
            operation.error_summary = str(error)
            operation.save(update_fields=("error_summary", "updated_at"))
            operation.transition_to(NodeManOperationStatus.FAILED)
            raise

        workflow_id = source_workflow_id or (result.get("workflow_id") if isinstance(result, dict) else None)
        if not workflow_id:
            error = NodeManV3UnknownResultError("NodeMan V3 write response has no workflow_id")
            workflow.dispatch_status = NodeManWorkflowDispatchStatus.UNKNOWN
            workflow.normalized_status = NodeManWorkflowStatus.UNKNOWN
            workflow.result_state = NodeManV3ResultState.WRITE_RESULT_UNKNOWN
            workflow.dispatch_error = str(error)
            workflow.save(
                update_fields=(
                    "dispatch_status",
                    "normalized_status",
                    "result_state",
                    "dispatch_error",
                    "updated_at",
                )
            )
            operation.status = NodeManOperationStatus.UNKNOWN
            operation.result_state = NodeManV3ResultState.WRITE_RESULT_UNKNOWN
            operation.error_summary = str(error)
            operation.save(update_fields=("status", "result_state", "error_summary", "updated_at"))
            raise error

        workflow.workflow_id = str(workflow_id)
        workflow.dispatch_status = NodeManWorkflowDispatchStatus.SUBMITTED
        workflow.normalized_status = NodeManWorkflowStatus.RUNNING
        workflow.save(update_fields=("workflow_id", "dispatch_status", "normalized_status", "updated_at"))
        operation.transition_to(NodeManOperationStatus.RUNNING)
        return str(workflow_id)

    @staticmethod
    def finish(operation, workflow, *, success: bool, error: str = "") -> None:
        workflow.normalized_status = NodeManWorkflowStatus.SUCCESS if success else NodeManWorkflowStatus.FAILED
        workflow.raw_status = "success" if success else "failed"
        workflow.dispatch_error = error
        workflow.last_synced_at = timezone.now()
        workflow.save(
            update_fields=("normalized_status", "raw_status", "dispatch_error", "last_synced_at", "updated_at")
        )
        operation.error_summary = error
        operation.save(update_fields=("error_summary", "updated_at"))
        operation.transition_to(NodeManOperationStatus.SUCCESS if success else NodeManOperationStatus.FAILED)


class NodeManV3PackageWorkflowService:
    POLL_INTERVAL = 1
    MAX_POLLS = 300

    def __init__(
        self,
        *,
        workflow_client=None,
        package_client=None,
        plugin_client=None,
        package_builder=None,
        storage=None,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        self._workflow_client = workflow_client
        self._package_client = package_client
        self._plugin_client = plugin_client
        self.package_builder = package_builder or NodeManV3PackageBuilder()
        self.storage = storage or default_storage
        self.sleeper = sleeper

    @property
    def workflow_client(self):
        if self._workflow_client is None:
            self._workflow_client = PackageWorkflowClient(NodeManV3HTTPClient())
        return self._workflow_client

    @property
    def package_client(self):
        if self._package_client is None:
            self._package_client = PackageClient(NodeManV3HTTPClient())
        return self._package_client

    @property
    def plugin_client(self):
        if self._plugin_client is None:
            self._plugin_client = PluginClient(NodeManV3HTTPClient())
        return self._plugin_client

    def register(self, plugin_manager) -> dict:
        archive = self.package_builder.build(plugin_manager)
        expected_platforms = self.package_builder.expected_platforms(archive)
        storage_name = self._save_for_download(plugin_manager.plugin, archive)
        payload = {
            "filename": os.path.basename(archive),
            "download_url": self.storage.url(storage_name),
            "md5": self._md5(archive),
        }
        recorder = NodeManV3PluginOperationRecorder(plugin_manager.plugin)
        operation, workflow = recorder.prepare(
            NodeManOperationType.PACKAGE_IMPORT,
            {"filename": payload["filename"], "md5": payload["md5"], "version": plugin_manager.version.version},
        )
        workflow_id = recorder.submit(
            operation,
            workflow,
            lambda context: self.workflow_client.import_plugin_v3(payload, context=context),
        )
        try:
            result = self._wait_result(workflow_id, export=False, context=self._read_context(plugin_manager.plugin))
            self._verify_registration(plugin_manager, expected_platforms)
        except Exception as error:
            recorder.finish(operation, workflow, success=False, error=str(error))
            raise
        recorder.finish(operation, workflow, success=True)
        return result

    def export(self, plugin, version: str) -> str:
        recorder = NodeManV3PluginOperationRecorder(plugin)
        operation, workflow = recorder.prepare(
            NodeManOperationType.PLUGIN_EXPORT,
            {"plugin_pkg_name": plugin.plugin_id, "plugin_pkg_version": version},
        )
        payload = {"plugin_pkg_name": plugin.plugin_id, "plugin_pkg_version": version}
        workflow_id = recorder.submit(
            operation,
            workflow,
            lambda context: self.workflow_client.export_plugin(payload, context=context),
        )
        try:
            result = self._wait_result(workflow_id, export=True, context=self._read_context(plugin))
        except Exception as error:
            recorder.finish(operation, workflow, success=False, error=str(error))
            raise
        download_url = result.get("download_url")
        if not download_url:
            error = ExportPluginError({"msg": "NodeMan V3 export succeeded without download_url"})
            recorder.finish(operation, workflow, success=False, error=str(error))
            raise error
        recorder.finish(operation, workflow, success=True)
        return download_url

    def _wait_result(self, workflow_id: str, *, export: bool, context: NodeManV3RequestContext) -> dict:
        for _ in range(self.MAX_POLLS):
            if export:
                result = self.workflow_client.export_result({"workflow_id": workflow_id}, context=context)
            else:
                result = self.workflow_client.import_result({"workflow_id": workflow_id}, context=context)
            if result.get("is_finish"):
                if str(result.get("status", "")).lower() != "success":
                    error_type = ExportPluginError if export else RegisterPackageError
                    raise error_type({"msg": self._result_error(result)})
                return result
            self.sleeper(self.POLL_INTERVAL)
        if export:
            raise ExportPluginTimeout
        raise RegisterPackageError({"msg": "NodeMan V3 插件包导入任务轮询超时"})

    def _verify_registration(self, plugin_manager, expected_platforms: set[tuple[str, str]]) -> None:
        context = self._read_context(plugin_manager.plugin)
        platform_filter = [
            {"os_type": os_type, "cpu_arch": cpu_arch} for os_type, cpu_arch in sorted(expected_platforms)
        ]
        for _ in range(self.MAX_POLLS):
            result = self.package_client.list_plugin_releases(
                {
                    "page": {"offset": 0, "limit": 500},
                    "only_count": False,
                    "exact_include_conditions": {
                        "name": [plugin_manager.plugin.plugin_id],
                        "version": [plugin_manager.version.version],
                        "platform": platform_filter,
                        "enabled": [True],
                    },
                },
                context=context,
            )
            actual_platforms = {
                (release.get("os_type"), release.get("cpu_arch"))
                for item in (result.get("items") if isinstance(result, dict) else ()) or ()
                if (release := item.get("release", item))
            }
            plugin_result = self.plugin_client.list(
                {
                    "page": {"offset": 0, "limit": 2},
                    "only_count": False,
                    "exact_include_conditions": {"name": [plugin_manager.plugin.plugin_id]},
                },
                context=context,
            )
            logical_plugins = plugin_result.get("items") if isinstance(plugin_result, dict) else ()
            logical_plugin_ready = any(
                item.get("name") == plugin_manager.plugin.plugin_id
                and item.get("pkg_name") == plugin_manager.plugin.plugin_id
                for item in logical_plugins or ()
            )
            if actual_platforms == expected_platforms and logical_plugin_ready:
                return
            self.sleeper(self.POLL_INTERVAL)
        raise RegisterPackageError(
            {
                "msg": (
                    "NodeMan V3 import succeeded but registration is incomplete: "
                    f"expected platforms={sorted(expected_platforms)}, actual platforms={sorted(actual_platforms)}"
                )
            }
        )

    def _save_for_download(self, plugin, archive: str) -> str:
        storage_name = (
            f"plugin/nodeman_v3/{plugin.bk_tenant_id}/{plugin.plugin_id}/{uuid4().hex}-{os.path.basename(archive)}"
        )
        with open(archive, "rb") as package_file:
            return self.storage.save(storage_name, package_file)

    @staticmethod
    def _md5(path: str) -> str:
        digest = hashlib.md5()
        with open(path, "rb") as package_file:
            for chunk in iter(lambda: package_file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _result_error(result: dict) -> str:
        lines = []
        for operation in result.get("operations") or ():
            for action in (operation.get("oper_inst_logs") or {}).values():
                for item in (action.get("message") or {}).get("logs") or ():
                    text = item.get("text_zh") or item.get("text_en")
                    if text:
                        lines.append(text)
        return "\n".join(lines) or f"NodeMan V3 workflow finished with status {result.get('status')}"

    @staticmethod
    def _read_context(plugin) -> NodeManV3RequestContext:
        return NodeManV3RequestContext(bk_tenant_id=plugin.bk_tenant_id, bk_biz_id=plugin.bk_biz_id)


class NodeManV3PluginDebugService:
    def __init__(self, *, plugin_client=None, workflow_client=None, poll_scheduler=None):
        self._plugin_client = plugin_client
        self._workflow_client = workflow_client
        self.poll_scheduler = poll_scheduler or NodeManV3OperationService._schedule_poll

    @property
    def plugin_client(self):
        if self._plugin_client is None:
            self._plugin_client = PluginClient(NodeManV3HTTPClient())
        return self._plugin_client

    @property
    def workflow_client(self):
        if self._workflow_client is None:
            self._workflow_client = WorkflowClient(NodeManV3HTTPClient())
        return self._workflow_client

    def start(self, plugin_manager, *, config_version, info_version, param, host_info, target_nodes=None) -> str:
        if not host_info.get("bk_host_id"):
            raise NodeManV3PayloadError("NodeMan V3 plugin debug requires host_info.bk_host_id")
        contexts = plugin_manager._get_debug_config_context(
            config_version,
            info_version,
            param,
            target_nodes,
        )
        custom_context = {}
        for context in contexts.values():
            custom_context.update(context)
        version = plugin_manager.plugin.get_debug_version(config_version)
        payload = {
            "debug_info": {
                "scope": {
                    "granularity": "host",
                    "bk_biz_id": host_info["bk_biz_id"],
                    "instance_ids": [host_info["bk_host_id"]],
                },
                "plugin_name": plugin_manager.plugin.plugin_id,
                "version": version.version,
                "config_template_name": list(contexts),
                "custom_config_context": custom_context,
            }
        }
        recorder = NodeManV3PluginOperationRecorder(plugin_manager.plugin)
        operation, workflow = recorder.prepare(
            NodeManOperationType.PLUGIN_DEBUG,
            {"bk_host_id": host_info["bk_host_id"], "version": version.version},
        )
        return recorder.submit(
            operation,
            workflow,
            lambda context: self.plugin_client.start_debug(payload, context=context),
        )

    def stop(self, plugin, workflow_id: str):
        recorder = NodeManV3PluginOperationRecorder(plugin)
        operation, workflow = recorder.prepare(
            NodeManOperationType.TERMINATE,
            {"source_workflow_id": workflow_id},
        )
        recorder.submit(
            operation,
            workflow,
            lambda context: self.plugin_client.stop_debug({"workflow_id": workflow_id}, context=context),
            source_workflow_id=workflow_id,
        )
        self.poll_scheduler(str(operation.pk))

    def query(self, plugin, workflow_id: str) -> dict:
        context = NodeManV3RequestContext(bk_tenant_id=plugin.bk_tenant_id, bk_biz_id=plugin.bk_biz_id)
        workflows = self.workflow_client.list_workflows(
            {
                "page": {"offset": 0, "limit": 2},
                "only_count": False,
                "exact_include_conditions": {"workflow_id": [workflow_id]},
            },
            context=context,
        )
        items = workflows.get("items") or []
        if len(items) != 1:
            raise NodeManV3PayloadError(f"NodeMan V3 debug workflow {workflow_id} was not found uniquely")
        workflow_status = str(items[0].get("status") or "").lower()
        operations = (
            self.workflow_client.list_operations(
                {
                    "only_count": False,
                    "page": {"offset": 0, "limit": 500},
                    "workflow_id": workflow_id,
                },
                context=context,
            ).get("operations")
            or []
        )
        log_lines = []
        states = []
        for operation in operations:
            state = (
                ((operation.get("latest_oper_inst_brief_data") or {}).get("life_cycle") or {}).get("state") or ""
            ).lower()
            states.append(state)
            instance_ids = operation.get("instance_ids") or ()
            if not instance_ids:
                continue
            result = self.workflow_client.get_operation_instance_log(
                {"oper_inst_id": str(instance_ids[-1])},
                context=context,
            )
            log_lines.extend(self._logs(result))
        if workflow_status == "success":
            status = DebugStatus.SUCCESS
        elif workflow_status in {"failed", "partial_failed", "timeout", "terminated", "cancelled"} or any(
            state in {"failed", "timeout", "terminated"} for state in states
        ):
            status = DebugStatus.FAILED
        elif any(state == "running" for state in states):
            status = DebugStatus.FETCH_DATA
        else:
            status = DebugStatus.INSTALL
        return {"status": status, "message": "\n".join(log_lines), "step": "DEBUG_PROCESS"}

    @staticmethod
    def _logs(result: dict) -> list[str]:
        lines = []
        for action in (result.get("oper_inst_logs") or {}).values():
            for item in (action.get("message") or {}).get("logs") or ():
                text = item.get("text_zh") or item.get("text_en")
                if text:
                    lines.append(text)
        for item in (result.get("extra_execution_logs") or {}).get("logs") or ():
            text = item.get("text_zh") or item.get("text_en")
            if text:
                lines.append(text)
        return lines
