from . import NodeManV3RequestContext, NodeManV3ServiceClient


class HostClient(NodeManV3ServiceClient):
    PREFIX = "api/v3/topo/host"

    def list(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._read(f"{self.PREFIX}/list", payload, context=context)

    def distinct(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._read(f"{self.PREFIX}/distinct", payload, context=context)

    def select_host_id(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._read(f"{self.PREFIX}/scenario/select_host_id", payload, context=context)

    def select_inner_ip(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._read(f"{self.PREFIX}/scenario/select_inner_ip", payload, context=context)

    def select_inner_ipv6(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._read(f"{self.PREFIX}/scenario/select_inner_ipv6", payload, context=context)


class ProxyClient(NodeManV3ServiceClient):
    PREFIX = "api/v3/node/proxy"

    def install(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._write(f"{self.PREFIX}/install", payload, context=context)

    def reconfig(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._write(f"{self.PREFIX}/reconfig", payload, context=context)

    def restart(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._write(f"{self.PREFIX}/restart", payload, context=context)

    def uninstall(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._write(f"{self.PREFIX}/uninstall", payload, context=context)

    def update(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._write(f"{self.PREFIX}/update", payload, context=context)

    def upgrade(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._write(f"{self.PREFIX}/upgrade", payload, context=context)


class NetworkUnitClient(NodeManV3ServiceClient):
    PREFIX = "api/v3/topo/networkunit"

    def list(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._read(f"{self.PREFIX}/list", payload, context=context)

    def list_brief(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._read(f"{self.PREFIX}/list/brief", payload, context=context)

    def get(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._read(f"{self.PREFIX}/get", payload, context=context)

    def recommend_by_network_segment(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._read(f"{self.PREFIX}/recommend_by_network_segment", payload, context=context)
