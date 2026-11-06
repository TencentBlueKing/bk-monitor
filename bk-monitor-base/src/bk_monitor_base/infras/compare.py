from bk_monitor_base.infras.types import JSON_TYPE


def nested_equal(a: JSON_TYPE, b: JSON_TYPE) -> bool:
    """
    比较两个嵌套字典或列表是否相等
    """
    if isinstance(a, list):
        if not isinstance(b, list):
            return False

        # 长度不匹配
        if len(a) != len(b):
            return False

        # 递归比较列表中的每个元素
        for aa, bb in zip(a, b, strict=False):
            if not nested_equal(aa, bb):
                return False
        return True
    elif isinstance(a, dict):
        # 类型不匹配
        if not isinstance(b, dict):
            return False

        # 长度不匹配
        if len(a) != len(b):
            return False

        for key, value in a.items():
            # 键不存在
            if key not in b:
                return False

            # 递归比较字典中的每个值
            if not nested_equal(value, b[key]):
                return False
        return True
    else:
        return a == b
