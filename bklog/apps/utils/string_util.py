def is_positive_or_negative_integer(s: str) -> bool:
    """判断字符串是否为正整数或负整数"""
    if s.startswith('-'):
        return s[1:].isdigit()
    else:
        return s.isdigit()
