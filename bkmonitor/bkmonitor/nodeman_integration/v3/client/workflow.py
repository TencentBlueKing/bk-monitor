from . import NodeManV3RequestContext, NodeManV3ServiceClient


class WorkflowClient(NodeManV3ServiceClient):
    PREFIX = "api/v3/plugin/workflow"

    def list_workflows(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._read(f"{self.PREFIX}/list", payload, context=context)

    def distinct_workflows(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._read(f"{self.PREFIX}/distinct", payload, context=context)

    def list_operations(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._read(f"{self.PREFIX}/operation/list", payload, context=context)

    def distinct_operations(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._read(f"{self.PREFIX}/operation/distinct", payload, context=context)

    def list_operation_instances(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._read(f"{self.PREFIX}/operation/instance/list", payload, context=context)

    def get_operation_instance_log(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._read(f"{self.PREFIX}/operation/instance/log/get", payload, context=context)

    def list_operation_instance_status_distribution(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._read(
            f"{self.PREFIX}/operation/instance/status_distribution/list",
            payload,
            context=context,
        )

    def retry_operation(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._write(f"{self.PREFIX}/operation/retry", payload, context=context)

    def terminate_operation(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._write(f"{self.PREFIX}/operation/terminate", payload, context=context)

    def statistics(self, payload: dict, *, context: NodeManV3RequestContext):
        return self._read(f"{self.PREFIX}/statistics", payload, context=context)
