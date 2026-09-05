from bkmonitor.nodeman_integration.v3.exceptions import NodeManV3AdapterPending

from .validation import NodeManV3CapabilityBlocked


class NodeManV3Orchestrator:
    def uninstall(self, **kwargs):
        del kwargs
        raise NodeManV3CapabilityBlocked(
            "policy uninstall awaits the DeployPolicy reverse protocol; resource Delete is already idempotent"
        )

    def stop(self, **kwargs):
        del kwargs
        raise NodeManV3CapabilityBlocked(
            "stop awaits the DeployPolicy reverse protocol; keep Scope unchanged while resources remain removed"
        )

    def start(self, **kwargs):
        del kwargs
        raise NodeManV3CapabilityBlocked("start awaits the DeployPolicy reverse protocol to restore the same Scope")

    def retry(self, **kwargs):
        self._adapter_pending("E1 retry workflow contract", kwargs)

    def revoke(self, **kwargs):
        self._adapter_pending("E1 terminate workflow contract", kwargs)

    def status(self, **kwargs):
        self._adapter_pending("E1-E3 status identity contract", kwargs)

    def instance_status(self, **kwargs):
        self._adapter_pending("E1-E3 instance status identity contract", kwargs)

    @staticmethod
    def _adapter_pending(capability: str, request) -> None:
        del request
        raise NodeManV3AdapterPending(f"NodeMan protocol is available but monitor adapter is pending: {capability}")
