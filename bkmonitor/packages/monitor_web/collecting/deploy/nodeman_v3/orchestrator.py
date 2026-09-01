from .deploy_policy import NodeManV3DeployPolicyGateway
from .validation import NodeManV3CapabilityBlocked


class NodeManV3Orchestrator:
    def __init__(self, *, gateway=None):
        self.gateway = gateway

    def stop_targets(self, targets, *, context=None) -> None:
        del context
        self._blocked("deploy-policy stop semantics", targets)

    def uninstall_targets(self, targets, *, context=None) -> None:
        del context
        self._blocked("deploy-policy delete semantics", targets)

    def ensure_targets(self, targets, *, context=None):
        target = self._single_target(targets)
        return self._gateway().ensure_target(target, context=context)

    def update_targets(self, targets, *, context=None):
        target = self._single_target(targets)
        return self._gateway().update_target(target, context=context)

    def _gateway(self):
        if self.gateway is None:
            self.gateway = NodeManV3DeployPolicyGateway()
        return self.gateway

    def install(self, **kwargs):
        self._blocked("E1-E6 install and configuration lifecycle", kwargs)

    def upgrade(self, **kwargs):
        self._blocked("E1-E6 upgrade and configuration lifecycle", kwargs)

    def uninstall(self, **kwargs):
        self._blocked("E2/E3/E6 uninstall lifecycle", kwargs)

    def rollback(self, **kwargs):
        self._blocked("E2-E6 rollback lifecycle", kwargs)

    def stop(self, **kwargs):
        self._blocked("E2/E3 exact stop lifecycle", kwargs)

    def start(self, **kwargs):
        self._blocked("E7 independent start operation", kwargs)

    def run(self, **kwargs):
        self._blocked("E1-E7 explicit execution lifecycle", kwargs)

    def retry(self, **kwargs):
        self._blocked("E1 retry workflow contract", kwargs)

    def revoke(self, **kwargs):
        self._blocked("E1 terminate workflow contract", kwargs)

    def status(self, **kwargs):
        self._blocked("E1-E3 status identity contract", kwargs)

    def instance_status(self, **kwargs):
        self._blocked("E1-E3 instance status identity contract", kwargs)

    @staticmethod
    def _single_target(targets):
        targets = tuple(targets)
        if len(targets) != 1:
            raise ValueError("each deploy-policy execution batch must contain exactly one target")
        return targets[0]

    @staticmethod
    def _blocked(capability: str, request) -> None:
        del request
        raise NodeManV3CapabilityBlocked(f"NodeMan external capability is not closed: {capability}")
