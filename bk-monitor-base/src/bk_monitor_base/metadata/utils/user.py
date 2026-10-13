from bk_monitor_base.metadata.utils.local import local
from bk_monitor_base.metadata.utils.request import get_request


def get_request_user():
    """
    获取请求中的用户对象
    :return:
    """
    request = get_request(peaceful=True)
    if request:
        return request.user


def get_request_username():
    """基于request获取用户信息（web）"""
    user = get_request_user()
    if user:
        return user.username


def get_local_username():
    """从local对象中获取用户信息（celery）"""
    for user_key in ["bk_username", "username", "operator"]:
        username = getattr(local, user_key, None)
        if username is not None:
            return username


def set_local_username(username):
    local.username = username
