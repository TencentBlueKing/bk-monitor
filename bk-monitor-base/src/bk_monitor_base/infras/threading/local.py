import logging
import sys
from threading import local
from typing import Any

from bk_monitor_base.infras.constant import DEFAULT_TENANT_ID
from bk_monitor_base.infras.declaratives.constants import ThreadLocalKey
from bk_monitor_base.infras.threading.utils import ignored

logger = logging.getLogger(__name__)


_local = local()


def set_local_param(key: str, value: Any):
    """
    设置自定义线程变量
    """
    setattr(_local, key, value)


def get_local_param(key: str, default: Any = None) -> Any:
    """
    获取线程变量
    """
    return getattr(_local, key, default)


def get_request():
    """
    获取线程请求request
    """
    try:
        return _local.request
    except AttributeError:
        return None


def get_request_username():
    """
    获取线程请求中的 USERNAME，非线程请求返回空字符串
    # TODO: username 不如直接透传，暂时保留方法，后期将会去掉，新代码不要使用
    """
    username = ""
    try:
        username = _local.bk_username
        if not username and get_request():
            username = _local.request.user.username
    except AttributeError:
        # 如果没有设置 bk_username 或者 request.user.username，则返回空字符串
        pass

    # 如果在 celery 或 manage.py 中没有设置 username，则默认使用 "admin"
    if not username and ("celery" in sys.argv or "manage.py" in sys.argv[0]):
        username = "admin"

    return username


def del_local_param(key: str):
    """
    删除自定义线程变量
    """
    if hasattr(_local, key):
        delattr(_local, key)


def get_tenant_id() -> str:
    """
    获取当前租户ID
    """
    tenant_id = ""
    with ignored(Exception):
        tenant_id = get_local_param(ThreadLocalKey.BK_TENANT_ID)
    if not tenant_id:
        with ignored(Exception):
            set_local_param(ThreadLocalKey.BK_TENANT_ID, get_request().user.tenant_id)
            tenant_id = get_local_param(ThreadLocalKey.BK_TENANT_ID)
    return tenant_id or DEFAULT_TENANT_ID
