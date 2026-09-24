from collections.abc import Callable
from multiprocessing.pool import ApplyResult, ThreadPool
from typing import Any


def bulk_request(
    api_func: Callable[..., list[Any]],
    request_data_iterable: list[dict[str, Any]] | None = None,
    ignore_exceptions: bool = False,
) -> list[Any]:
    """
    基于多线程的批量并发请求
    """
    if not isinstance(request_data_iterable, list | tuple):
        raise TypeError("'request_data_iterable' object is not iterable")

    pool = ThreadPool()
    futures: list[ApplyResult[Any]] = []
    for request_data in request_data_iterable:
        futures.append(pool.apply_async(api_func, kwds=request_data))

    pool.close()
    pool.join()

    results: list[Any] = []
    exceptions: list[Exception] = []
    for future in futures:
        try:
            results.append(future.get())
        except Exception as e:
            # 判断是否忽略错误
            if not ignore_exceptions:
                raise e
            exceptions.append(e)
            results.append(None)

    # 如果全部报错，则必须抛出错误
    if exceptions and len(exceptions) == len(futures):
        raise exceptions[0]

    return results
