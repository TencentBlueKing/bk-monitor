from bk_monitor_base.config import get_config

from .bcs import api as bcs
from .bcs_cluster_manager import api as bcs_cluster_manager
from .bcs_storage import api as bcs_storage
from .bk_monitorv3 import api as bk_monitorv3
from .bk_paas import api as bk_paas
from .bkdata import api as bkdata
from .cmdb import api as cmdb
from .cmsi import api as cmsi
from .gse import api as gse
from .log_search import api as log_search
from .nodeman import api as node_man
from .unify_query import api as unify_query
from .user import api as user

if get_config().common.enable_base_metadata:
    from .metadata import resource_proxy as metadata
else:
    from .metadata import api as metadata

__all__ = [
    "bcs",
    "bcs_cluster_manager",
    "bcs_storage",
    "bk_monitorv3",
    "bk_paas",
    "bkdata",
    "cmdb",
    "cmsi",
    "gse",
    "log_search",
    "metadata",
    "node_man",
    "unify_query",
    "user",
]
