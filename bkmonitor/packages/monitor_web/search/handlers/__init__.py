# -*- coding: utf-8 -*-

from .action import ActionSearchHandler
from .alert import AlertSearchHandler
from .apm import ApmSearchHandler
from .biz import BizSearchHandler
from .dashboard import DashboardSearchHandler
from .host import HostSearchHandler
from .kubernetes import K8sSearchHandler
from .strategy import StrategySearchHandler
from .uptimecheck import UptimecheckSearchHandler

INSTALLED_HANDLERS = (
    BizSearchHandler,
    HostSearchHandler,
    K8sSearchHandler,
    AlertSearchHandler,
    ActionSearchHandler,
    StrategySearchHandler,
    UptimecheckSearchHandler,
    DashboardSearchHandler,
    ApmSearchHandler,
)
