# -*- coding: utf-8 -*-
import base64
import json
import re
import string

import jieba_fast

from apps.log_clustering.handlers.dataflow.constants import OnlineTaskTrainingArgs

NUMBER_REGEX_LST = ['NUMBER', 'PERIOD', 'IP', 'CAPACITY']


def format_pattern(pattern):
    return ' %s' % ' '.join([f'#{o.name}#' if hasattr(o, 'name') else o for o in pattern]) if pattern else ''


def sort_func(elem):
    """对正则列表进行排序"""
    return 1 if elem[0] not in ('NUMBER', 'CHAR') else 0


def parse_regex(predefined_varibles=None):
    """解析设置的正则表达式

    :param predefined_varibles: 预先定义的模式
    :return: 把模式编码成字符串
    """
    if predefined_varibles is None:
        predefined_varibles = []

    def single_parse_regex(variable):
        parts = variable.split(':')
        if len(parts) <= 1:
            raise Exception('Invalid variable format')
        name = parts[0]
        wrapped_regex = ':'.join([str(i) for i in parts[1:]])
        return name, re.compile(wrapped_regex)

    variables = [single_parse_regex(variable) for variable in predefined_varibles]
    return variables


def is_contains_chinese(strs):
    """判断字符串是否包含中文."""
    for _char in strs:
        if '\u4e00' <= _char <= '\u9fa5':
            return True
    return False


def judge_chinese(strs):
    """判断是否有中文，是否全部中文."""
    r = ['\u4e00' <= _char <= '\u9fa5' for _char in strs]
    return any(r), all(r)


class Variable(object):
    def __init__(self, name, value):
        self.value = value
        self.name = name

    def __eq__(self, other):
        if isinstance(other, str):
            return self.name == other
        return self.name == other.name

    def __repr__(self):
        return "'%s'" % self.value

    def __str__(self):
        return self.value

    def __add__(self, other):
        return self.value + other

    def __radd__(self, other):
        return other + self.value

    def lower(self):
        return self.name


def match_text_and_tokenize(variables, content, delimeter, number_variables, is_chinese_cut=0):
    """分词和正则匹配(包含中文分词逻辑，用户选择是否启动中文分词).

    :param variables:
    :param content:
    :param delimeter:
    :param number_variables:
    :param is_chinese_cut:
    :return:
    """
    if not delimeter or len(variables) == 0:
        return [content]
    variable_dict = {}
    for name, regex in variables:
        try:
            re.compile(regex)
        except re.error as exc:
            raise ValueError(f"invalid regex: {regex} - {exc}")
        matched_object = re.search(regex, content)
        while matched_object is not None:
            s, e = matched_object.start(), matched_object.end()
            content = f"{content[:s]} {name.upper()} {content[e:]}"
            variable_dict.setdefault(name.upper(), []).append(matched_object.group())
            matched_object = re.search(regex, content)

    tokens = re.split(delimeter, content.strip())
    tokens = [w.strip(" '") for w in tokens if w is not None and len(w) > 0 and not (w in string.punctuation)]

    cate_tokens = []
    for t in tokens:
        match = False
        for k, v in variable_dict.items():
            if t == k and len(v) >= 1:
                cate_tokens.append(Variable(k, v[0]))
                v.pop(0)
                match = True
                break
        if not match:
            for name, regex in number_variables:
                matched_object = re.search(regex, t)
                if matched_object:
                    match = True
                    cate_tokens.append(Variable(name.upper(), t))
                    break
            if not match:
                if not is_chinese_cut or len(t) <= 1:
                    cate_tokens.append(t)
                    continue
                # 如果包含中文,则进行中文分词
                has_chinese, all_chinese = judge_chinese(t)
                if has_chinese and not all_chinese:
                    chinese_tokens = list(jieba_fast.cut(t, cut_all=False, HMM=True))
                    if len(chinese_tokens) <= 1:
                        cate_tokens.append(t)
                        continue

                    for tt in chinese_tokens:
                        if is_contains_chinese(tt):
                            continue
                        for name, regex in number_variables:
                            matched_object = re.search(regex, tt)
                            if matched_object is not None:
                                match = True
                                break
                        if match:
                            idx = chinese_tokens.index(tt)
                            if idx > 0:
                                cate_tokens.append(''.join(chinese_tokens[:idx]))
                            cate_tokens.append(Variable(name.upper(), tt))
                            if idx + 1 < len(chinese_tokens):
                                cate_tokens.append(''.join(chinese_tokens[idx + 1 :]))
                            break
                    if not match:
                        cate_tokens.append(t)
                else:
                    cate_tokens.append(t)
    return cate_tokens


def debug(
    log,
    predefined_variables=OnlineTaskTrainingArgs.PREDEFINED_VARIBLES,
    delimeter=OnlineTaskTrainingArgs.DELIMETER,
    max_log_length=OnlineTaskTrainingArgs.MAX_LOG_LENGTH,
):
    """
    正则调试
    """
    predefined_variables_list = json.loads(base64.b64decode(predefined_variables).decode('utf-8'))
    variables = parse_regex(predefined_variables_list)
    variables.sort(key=sort_func, reverse=True)
    # 和number有关/无关的正则
    number_variables = [(name, regex) for (name, regex) in variables if name in NUMBER_REGEX_LST]
    variables = [(name, regex) for (name, regex) in variables if name not in NUMBER_REGEX_LST]

    delimeter = json.loads(base64.b64decode(delimeter).decode('utf-8'))

    seq = match_text_and_tokenize(variables, log[: min(max_log_length, len(log))], delimeter, number_variables)
    return format_pattern(seq)
