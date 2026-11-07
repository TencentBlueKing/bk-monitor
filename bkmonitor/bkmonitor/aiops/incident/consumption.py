from contextvars import ContextVar


# Receipt completion must observe failures normally swallowed by legacy callers.
strict_incident_delivery = ContextVar("strict_incident_delivery", default=False)
