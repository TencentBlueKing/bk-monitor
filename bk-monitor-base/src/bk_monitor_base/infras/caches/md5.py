import hashlib
from typing import Any


def _count_md5(content: str | bytes | None) -> str:
    if content is None:
        return ""
    m2 = hashlib.md5()
    if isinstance(content, str):
        m2.update(content.encode("utf8"))
    else:
        m2.update(content)
    return m2.hexdigest()


def count_md5(content: Any, dict_sort: bool = True) -> str:
    if dict_sort and isinstance(content, dict):
        # dict的顺序受到hash的影响，所以这里先排序再计算MD5
        return count_md5([(str(k), count_md5(content[k])) for k in sorted(content.keys())])
    elif isinstance(content, list | tuple):
        content = sorted([count_md5(k) for k in content])
    return _count_md5(str(content))


def get_md5(content: Any) -> str | list[str]:
    if isinstance(content, list):
        return [count_md5(c) for c in content]
    else:
        return count_md5(content)
