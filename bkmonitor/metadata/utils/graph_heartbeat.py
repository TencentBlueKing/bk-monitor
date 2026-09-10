"""Resolve the opt-in SurrealDB relation validity window in milliseconds."""


def resolve_graph_heartbeat_gap_ms(default, overrides, tenant_id, biz_id):
    """Select a tenant/business override without falling back to another tenant."""

    def validate(value):
        if value is not None and (type(value) is not int or value <= 0 or value > 86400000):
            raise ValueError("graph heartbeat gap must be an integer in [1, 86400000] milliseconds or None")
        return value

    validate(default)
    if not isinstance(overrides, dict):
        raise ValueError("graph heartbeat overrides must be a tenant-to-business mapping")
    for tenant, businesses in overrides.items():
        if not isinstance(tenant, str) or not tenant or not isinstance(businesses, dict):
            raise ValueError("graph heartbeat overrides require tenant names and business mappings")
        for business, value in businesses.items():
            if not isinstance(business, str) or not business.isdecimal():
                raise ValueError("graph heartbeat business keys must be decimal strings")
            validate(value)
    return overrides.get(tenant_id, {}).get(str(biz_id), default)
