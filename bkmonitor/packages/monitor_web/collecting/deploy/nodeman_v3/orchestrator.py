from bkmonitor.nodeman_integration.v3.exceptions import NodeManV3AdapterPending

from .deploy_policy import NodeManV3DeployPolicyGateway
from .validation import NodeManV3CapabilityBlocked


class NodeManV3Orchestrator:
    def __init__(self, *, gateway=None):
        self.gateway = gateway

    def stop_targets(self, targets, *, context=None) -> None:
        del context, targets
        raise NodeManV3CapabilityBlocked(
            "deploy-policy does not define exact sub-config removal and exporter stop semantics"
        )

    def uninstall_targets(self, targets, *, context=None) -> None:
        del context, targets
        raise NodeManV3CapabilityBlocked(
            "deploy-policy does not define target removal and generated resource cleanup semantics"
        )

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
        self._adapter_pending("E1-E6 install and configuration lifecycle", kwargs)

    def upgrade(self, **kwargs):
        self._adapter_pending("E1-E6 upgrade and configuration lifecycle", kwargs)

    def uninstall(self, **kwargs):
        del kwargs
        raise NodeManV3CapabilityBlocked(
            "deploy-policy does not define policy deletion and generated resource cleanup semantics"
        )

    def rollback(self, **kwargs):
        del kwargs
        raise NodeManV3CapabilityBlocked(
            "deploy-policy rollback and replacement semantics are absent from the NodeMan V3 protocol"
        )

    def stop(self, **kwargs):
        del kwargs
        raise NodeManV3CapabilityBlocked(
            "deploy-policy does not define exact sub-config removal and exporter stop semantics"
        )

    def start(self, **kwargs):
        self._adapter_pending("E7 independent start operation", kwargs)

    def run(self, **kwargs):
        self._adapter_pending("E1-E7 explicit execution lifecycle", kwargs)

    def retry(self, **kwargs):
        self._adapter_pending("E1 retry workflow contract", kwargs)

    def revoke(self, **kwargs):
        self._adapter_pending("E1 terminate workflow contract", kwargs)

    def status(self, **kwargs):
        self._adapter_pending("E1-E3 status identity contract", kwargs)

    def instance_status(self, **kwargs):
        self._adapter_pending("E1-E3 instance status identity contract", kwargs)

    @staticmethod
    def _single_target(targets):
        targets = tuple(targets)
        if len(targets) != 1:
            raise ValueError("each deploy-policy execution batch must contain exactly one target")
        return targets[0]

    @staticmethod
    def _adapter_pending(capability: str, request) -> None:
        del request
        raise NodeManV3AdapterPending(f"NodeMan protocol is available but monitor adapter is pending: {capability}")
