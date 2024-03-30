import codecs


def unicode_str_encode(s):
    """
    将字符串转换为unicode编码
    例如: \t -> \\t
    """
    return codecs.encode(s, "unicode_escape").decode("utf-8")


def unicode_str_decode(s):
    """
    将unicode编码的字符串转换为正常字符串
    例如: \\t -> \t
    """
    return codecs.decode(s, "unicode_escape")
