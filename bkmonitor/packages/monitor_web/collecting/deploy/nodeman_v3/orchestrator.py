from .validation import NodeManV3CapabilityBlocked


class NodeManV3Orchestrator:
    def __init__(self, *, gateway=None):
        self.gateway = gateway

    def stop_targets(self, targets) -> None:
        gateway = self._require_gateway("E2/E3 exact configuration and plugin instance lifecycle")
        targets = list(targets)
        self._require_instance_identities(targets)
        for target in targets:
            gateway.disable_config_instance(target.bkmonitorbeat_config_instance_id)
            gateway.stop_plugin_instance(target.node_man_plugin_instance_id)

    def uninstall_targets(self, targets) -> None:
        gateway = self._require_gateway("E2/E3 exact configuration and plugin instance lifecycle")
        targets = list(targets)
        self._require_instance_identities(targets)
        for target in targets:
            gateway.delete_config_instance(target.bkmonitorbeat_config_instance_id)
            gateway.uninstall_plugin_instance(target.node_man_plugin_instance_id)

    def ensure_targets(self, targets) -> None:
        self._blocked("E1-E6 target install and configuration lifecycle", targets)

    def update_targets(self, targets) -> None:
        self._blocked("E1-E6 target update and configuration lifecycle", targets)

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

    def _require_gateway(self, capability: str):
        if not self.gateway:
            raise NodeManV3CapabilityBlocked(f"NodeMan external capability is not closed: {capability}")
        return self.gateway

    @staticmethod
    def _require_instance_identities(targets) -> None:
        for target in targets:
            if not target.node_man_plugin_instance_id or not target.bkmonitorbeat_config_instance_id:
                raise NodeManV3CapabilityBlocked(
                    f"E2/E3 stable instance identity is missing for target {target.identity_key}"
                )

    @staticmethod
    def _blocked(capability: str, request) -> None:
        del request
        raise NodeManV3CapabilityBlocked(f"NodeMan external capability is not closed: {capability}")
