import functools
import time
from typing import Any

from django.core.cache import cache


def share_lock(ttl: int = 600, identify: str | None = None) -> Any:
    """
    装饰定时任务时需要放在periodic_task下面
    @periodic_task(run_every=crontab(minute="*/1"), queue="sync")
    # 不填参数需要带括号执行
    @share_lock()
    def demo():
        pass
    :param ttl:
    :param identify:
    :return:
    """

    def wrapper(func):
        @functools.wraps(func)
        def _inner(*args, **kwargs):
            token = str(time.time())
            # 防止函数重名导致方法失效，增加一个ID参数，可以通过ID参数屏蔽多模块函数名重复的问题
            # 例如，可以为`${module}_${method_used_for}`
            cache_key = f"celery_{func.__name__}" if identify is None else identify
            client = cache
            lock_success = client.set(cache_key, token, timeout=ttl, nx=True)  # pyright: ignore [reportCallIssue]
            if not lock_success:
                return

            try:
                return func(*args, **kwargs)
            finally:
                if client.get(cache_key) == token:
                    client.delete(cache_key)

        return _inner

    return wrapper
