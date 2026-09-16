from bkmonitor.nodeman_integration.mode import is_nodeman_v3


class NodeManIntegrationBackend:
    """Process-bound NodeMan routing with implementation imports kept behind the facade."""

    @property
    def is_v3(self) -> bool:
        return is_nodeman_v3()

    @property
    def v3(self):
        if not self.is_v3:
            raise RuntimeError("NodeMan V3 backend is unavailable in a V2-only process")

        # V2 processes must not import any V3 implementation module.
        from bkmonitor.nodeman_integration.v3.backend import node_man_v3_backend

        return node_man_v3_backend


node_man_backend = NodeManIntegrationBackend()
