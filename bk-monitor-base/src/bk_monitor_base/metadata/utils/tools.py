import hashlib
import inspect
import logging

from bk_monitor_base.metadata.config import settings

logger = logging.getLogger("metadata")


def is_ipv6_biz(bk_biz_id: int) -> bool:
    """
    判断业务是否支持ipv6
    """
    return str(bk_biz_id) in {str(biz) for biz in settings.common.ipv6_support_biz_list}


def _count_md5(content):
    if content is None:
        return None
    m2 = hashlib.md5()
    if isinstance(content, str):
        m2.update(content.encode("utf8"))
    else:
        m2.update(content)
    return m2.hexdigest()


def count_md5(content, dict_sort=True, list_sort=True):
    if dict_sort and isinstance(content, dict):
        # dict的顺序受到hash的影响，所以这里先排序再计算MD5
        return count_md5(
            [(str(k), count_md5(content[k], dict_sort, list_sort)) for k in sorted(content.keys())],
            dict_sort,
            list_sort,
        )
    elif isinstance(content, list | tuple):
        content = (
            sorted([count_md5(k, dict_sort) for k in content])
            if list_sort
            else [count_md5(k, dict_sort, list_sort) for k in content]
        )
    elif callable(content):
        return make_callable_hash(content)
    return _count_md5(str(content))


def make_callable_hash(content):
    """
    计算callable的hash
    """
    if inspect.isclass(content):
        h = []
        for attr in [i for i in sorted(dir(content)) if not i.startswith("__")]:
            v = getattr(content, attr)
            h.append(count_md5(v))

        return _count_md5("".join(h))
    try:
        return _count_md5(content.__name__)
    except AttributeError:
        try:
            return _count_md5(content.func.__name__)
        except AttributeError:
            return _count_md5(str(content))


def gen_bk_data_rt_id_without_biz_id(table_id):
    """
    计算平台表名只能是50个字节，需要进行截断
    """
    if table_id.endswith("__default__"):
        table_id = table_id.split(".__default__")[0]
    rt_id = "{}_{}".format(settings.metadata.bk_data_rt_id_prefix, table_id.replace(".", "_"))[-32:].lower()
    return rt_id.strip("_")


def to_bk_data_rt_id(table_id, suffix=None):
    if not table_id:
        return

    prefix_list = [str(settings.metadata.bk_data_bk_biz_id), gen_bk_data_rt_id_without_biz_id(table_id)]
    if suffix:
        prefix_list.append(str(suffix))

    return "_".join(prefix_list)
