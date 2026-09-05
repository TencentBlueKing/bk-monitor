from . import NodeManV3RequestContext, NodeManV3ServiceClient


class PackageClient(NodeManV3ServiceClient):
    def upload_plugin_v3(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._write("api/v3/package/upload/origin/v3/plugin", payload, context=context)

    def publish_plugin_v3(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._write("api/v3/package/publish/release/v3/plugin", payload, context=context)

    def list_plugin_releases(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._read("api/v3/package/release/plugin/list", payload, context=context)

    def enable_plugin_release(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._write("api/v3/package/release/plugin/enable", payload, context=context)

    def disable_plugin_release(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._write("api/v3/package/release/plugin/disable", payload, context=context)

    def delete_plugin_release(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._write("api/v3/package/release/plugin/delete", payload, context=context)

    def download_plugin_release(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._read("api/v3/package/release/plugin/download", payload, context=context)


class PackageWorkflowClient(NodeManV3ServiceClient):
    PREFIX = "api/v3/package/workflow"

    def import_plugin_v3(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._write(f"{self.PREFIX}/import/v3/plugin", payload, context=context)

    def import_result(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._read(f"{self.PREFIX}/import_result", payload, context=context)

    def export_plugin(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._write(f"{self.PREFIX}/export/plugin", payload, context=context)

    def export_result(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._read(f"{self.PREFIX}/export_result", payload, context=context)


class PluginClient(NodeManV3ServiceClient):
    def install(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._write("api/v3/plugin/install", payload, context=context)

    def upgrade(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._write("api/v3/plugin/upgrade", payload, context=context)

    def apply_subconfig(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._write("api/v3/plugin/apply_subconfig", payload, context=context)

    def remove_subconfig(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._write("api/v3/plugin/remove_subconfig", payload, context=context)

    def start(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._write("api/v3/plugin/start", payload, context=context)

    def restart(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._write("api/v3/plugin/restart", payload, context=context)

    def stop(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._write("api/v3/plugin/stop", payload, context=context)

    def uninstall(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._write("api/v3/plugin/uninstall", payload, context=context)

    def list(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._read("api/v3/plugin/list", payload, context=context)

    def list_config_files(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._read("api/v3/plugin/list_config_files", payload, context=context)

    def list_permitted_operations(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._read("api/v3/plugin/list_permitted_operations", payload, context=context)

    def set_memo(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._write("api/v3/plugin/set_memo", payload, context=context)

    def start_debug(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._write("api/v3/plugin/start_debug", payload, context=context)

    def stop_debug(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._write("api/v3/plugin/stop_debug", payload, context=context)
