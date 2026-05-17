import os

if os.getenv("ENABLE_BK_MONITOR_BASE_PLUGIN", "false").lower() == "true":
    from .new import *  # noqa: F403
else:
    from .old import *  # noqa: F403
