from . import NodeManV3RequestContext, NodeManV3ServiceClient


class ProcessClient(NodeManV3ServiceClient):
    PREFIX = "api/v3/process"

    def list(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._read(f"{self.PREFIX}/list", payload, context=context)

    def distinct(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._read(f"{self.PREFIX}/distinct", payload, context=context)

    def get_distribution_by_host_id(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._read(f"{self.PREFIX}/get_distribution_by_host_id", payload, context=context)

    def get_distribution_by_plugin_name(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._read(f"{self.PREFIX}/get_distribution_by_plugin_name", payload, context=context)
