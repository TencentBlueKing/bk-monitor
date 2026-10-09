import threading
from collections.abc import Callable
from typing import Any

# 默认的批量大小
DEFAULT_BULK_SIZE = 50


def bulk_handle(
    handler: Callable, data: list[Any], bulk_size: int = DEFAULT_BULK_SIZE, is_wait_finish: bool | None = True
):
    """批量操作"""
    # 获取长度，用以进行分组
    count = len(data)
    chunk_size = count // bulk_size + 1 if count % bulk_size != 0 else int(count / bulk_size)
    # 分组
    chunks = [data[i : i + chunk_size] for i in range(0, count, chunk_size)]
    threads = []

    for chunk in chunks:
        t = threading.Thread(target=handler, args=(chunk,))
        t.start()
        threads.append(t)

    # 如果不需要等待，则直接返回
    if not is_wait_finish:
        return

    # 等待所有线程完成
    for t in threads:
        t.join()


def chunk_list(data: list, size: int) -> list[list]:
    """
    将一个 list 按固定大小切分成若干小 list
    """
    return [data[i : i + size] for i in range(0, len(data), size)]
