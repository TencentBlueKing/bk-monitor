from . import NodeManV3RequestContext, NodeManV3ServiceClient


class DeployPolicyClient(NodeManV3ServiceClient):
    PREFIX = "api/v3/deploy_policy"

    def create(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._write(f"{self.PREFIX}/create", payload, context=context)

    def update(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._write(f"{self.PREFIX}/update", payload, context=context)

    def execute(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._write(f"{self.PREFIX}/execute", payload, context=context)

    def list(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._read(f"{self.PREFIX}/list", payload, context=context)
