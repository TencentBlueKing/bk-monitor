import base64
import json
import re
import string

import jieba_fast

from apps.log_clustering.handlers.dataflow.constants import OnlineTaskTrainingArgs

NUMBER_REGEX_LST = ["NUMBER", "PERIOD", "IP", "CAPACITY"]
PATTERN_GAP_REGEX = r"[\s\S]*?"
PATTERN_PLACEHOLDER_REGEX = re.compile(r"#([A-Za-z0-9_]+)#")
PATTERN_TOKEN_REGEX = re.compile(r"#([A-Za-z0-9_]+)#|\*")

RISK_REASON_NO_PLACEHOLDER = "no_placeholder"
RISK_REASON_UNKNOWN_PLACEHOLDER = "unknown_placeholder"
RISK_REASON_INSUFFICIENT_LITERAL_TOKENS = "insufficient_literal_tokens"
RISK_REASON_INSUFFICIENT_RIGHT_ANCHOR = "insufficient_right_anchor"
RISK_REASON_TRUNCATED_TAIL = "truncated_tail"
RISK_REASON_AMBIGUOUS_DUPLICATE_PLACEHOLDER = "ambiguous_duplicate_placeholder"


def format_pattern(pattern):
    return " {}".format(" ".join([f"#{o.name}#" if hasattr(o, "name") else o for o in pattern])) if pattern else ""


def sort_func(elem):
    """对正则列表进行排序"""
    return 1 if elem[0] not in ("NUMBER", "CHAR") else 0


def parse_regex(predefined_varibles=None):
    """解析设置的正则表达式

    :param predefined_varibles: 预先定义的模式
    :return: 把模式编码成字符串
    """
    if predefined_varibles is None:
        predefined_varibles = []

    def single_parse_regex(variable):
        parts = variable.split(":")
        if len(parts) <= 1:
            raise Exception("Invalid variable format")
        name = parts[0]
        wrapped_regex = ":".join([str(i) for i in parts[1:]])
        return name, re.compile(wrapped_regex)

    variables = [single_parse_regex(variable) for variable in predefined_varibles]
    return variables


def is_contains_chinese(strs):
    """判断字符串是否包含中文."""
    for _char in strs:
        if "\u4e00" <= _char <= "\u9fa5":
            return True
    return False


def judge_chinese(strs):
    """判断是否有中文，是否全部中文."""
    r = ["\u4e00" <= _char <= "\u9fa5" for _char in strs]
    return any(r), all(r)


class Variable:
    def __init__(self, name, value):
        self.value = value
        self.name = name

    def __eq__(self, other):
        if isinstance(other, str):
            return self.name == other
        return self.name == other.name

    def __repr__(self):
        return f"'{self.value}'"

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
    tokens = [w.strip(" '") for w in tokens if w is not None and len(w) > 0 and w not in string.punctuation]

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
                                cate_tokens.append("".join(chinese_tokens[:idx]))
                            cate_tokens.append(Variable(name.upper(), tt))
                            if idx + 1 < len(chinese_tokens):
                                cate_tokens.append("".join(chinese_tokens[idx + 1 :]))
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
    predefined_variables_list = json.loads(base64.b64decode(predefined_variables).decode("utf-8"))
    variables = parse_regex(predefined_variables_list)
    variables.sort(key=sort_func, reverse=True)
    # 和number有关/无关的正则
    number_variables = [(name, regex) for (name, regex) in variables if name in NUMBER_REGEX_LST]
    variables = [(name, regex) for (name, regex) in variables if name not in NUMBER_REGEX_LST]

    delimeter = json.loads(base64.b64decode(delimeter).decode("utf-8"))

    seq = match_text_and_tokenize(variables, log[: min(max_log_length, len(log))], delimeter, number_variables)
    return format_pattern(seq)


def _decode_predefined_variables(predefined_varibles) -> list[str]:
    """兼容列表、JSON 字符串和 base64(JSON) 三种配置形态。"""

    if not predefined_varibles:
        return []
    if isinstance(predefined_varibles, list):
        return predefined_varibles

    candidates = [predefined_varibles]
    try:
        candidates.append(base64.b64decode(predefined_varibles).decode("utf-8"))
    except Exception:  # pylint: disable=broad-except
        pass

    for candidate in candidates:
        if isinstance(candidate, list):
            return candidate
        if not isinstance(candidate, str):
            continue
        try:
            decoded = json.loads(candidate)
        except Exception:  # pylint: disable=broad-except
            continue
        if isinstance(decoded, list):
            return decoded
    return []


def _build_placeholder_regex_mapping(predefined_varibles=None) -> dict[str, str]:
    """把预定义占位符配置转成 NAME -> raw regex 的映射。"""

    regex_list = _decode_predefined_variables(predefined_varibles)
    regex_mapping = {}
    for name, compiled_regex in parse_regex(regex_list):
        regex_mapping[name.upper()] = compiled_regex.pattern
    return regex_mapping


def _normalize_capturing_groups(regex: str) -> str:
    """把普通捕获组转成非捕获组，避免占用 regexp_extract 的 group index。"""

    result = []
    cursor = 0
    escaped = False

    while cursor < len(regex):
        char = regex[cursor]

        if escaped:
            result.append(char)
            escaped = False
            cursor += 1
            continue

        if char == "\\":
            result.append(char)
            escaped = True
            cursor += 1
            continue

        if char == "(" and cursor + 1 < len(regex):
            if regex[cursor + 1] != "?":
                result.append("(?:")
                cursor += 1
                continue

        result.append(char)
        cursor += 1

    return "".join(result)


def _strip_outer_regex_anchors(regex: str) -> str:
    """去掉最外层 ^/$ 锚点，避免嵌入整条日志 regex 后失去匹配能力。"""

    if regex.startswith("^"):
        regex = regex[1:]
    if regex.endswith("$") and not regex.endswith(r"\$"):
        regex = regex[:-1]
    return regex


def parse_pattern_placeholders(pattern: str) -> list[dict]:
    """按出现顺序解析 pattern 中的占位符，不按名称去重。"""

    placeholders = []
    for index, match in enumerate(PATTERN_PLACEHOLDER_REGEX.finditer(pattern or "")):
        placeholders.append({"name": match.group(1).upper(), "index": index})
    return placeholders


def tokenize_pattern_dsl(pattern: str) -> list[dict]:
    """把展示 DSL 拆为 literal / placeholder / wildcard 三类 token。"""

    tokens = []
    placeholder_index = 0
    pattern = pattern or ""
    cursor = 0

    def append_literal_tokens(content: str):
        # 展示态 pattern 中的空白只作为分隔符，不保留字面空格语义。
        for literal in re.split(r"\s+", content):
            if literal:
                tokens.append({"token_type": "literal", "raw": literal, "value": literal, "index": None})

    for match in PATTERN_TOKEN_REGEX.finditer(pattern):
        append_literal_tokens(pattern[cursor : match.start()])
        token_value = match.group(0)
        if token_value == "*":
            tokens.append({"token_type": "wildcard", "raw": token_value, "value": token_value, "index": None})
        else:
            placeholder_name = match.group(1).upper()
            tokens.append(
                {
                    "token_type": "placeholder",
                    "raw": token_value,
                    "value": placeholder_name,
                    "index": placeholder_index,
                }
            )
            placeholder_index += 1
        cursor = match.end()

    append_literal_tokens(pattern[cursor:])
    return tokens


def evaluate_pattern_risk(
    pattern: str,
    placeholder_index: int,
    max_log_length: int,
    predefined_varibles=None,
) -> dict:
    """评估当前 pattern 的提取风险，尽量返回结果而不是前置失败。"""

    tokens = tokenize_pattern_dsl(pattern)
    placeholders = [token for token in tokens if token["token_type"] == "placeholder"]
    reasons = []

    if not placeholders:
        reasons.append(RISK_REASON_NO_PLACEHOLDER)
        return {"risk_level": "high", "reasons": reasons}

    target_placeholder = next((item for item in placeholders if item["index"] == placeholder_index), None)
    if target_placeholder is None:
        reasons.append(RISK_REASON_UNKNOWN_PLACEHOLDER)
        return {"risk_level": "high", "reasons": reasons}

    regex_mapping = _build_placeholder_regex_mapping(predefined_varibles)
    if target_placeholder["value"] not in regex_mapping:
        reasons.append(RISK_REASON_UNKNOWN_PLACEHOLDER)

    literal_tokens = [token for token in tokens if token["token_type"] == "literal"]
    if len(literal_tokens) < 2:
        reasons.append(RISK_REASON_INSUFFICIENT_LITERAL_TOKENS)

    same_name_count = sum(1 for item in placeholders if item["value"] == target_placeholder["value"])
    if same_name_count > 1:
        reasons.append(RISK_REASON_AMBIGUOUS_DUPLICATE_PLACEHOLDER)

    target_position = tokens.index(target_placeholder)
    right_tokens = tokens[target_position + 1 :]
    # 右侧缺少稳定 literal 时，regexp_extract 更容易因为截断或重复模式失真。
    if not any(token["token_type"] == "literal" for token in right_tokens):
        reasons.append(RISK_REASON_INSUFFICIENT_RIGHT_ANCHOR)
    if (
        not right_tokens
        or right_tokens[-1]["token_type"] != "literal"
        or len((pattern or "").strip()) >= max_log_length
    ):
        reasons.append(RISK_REASON_TRUNCATED_TAIL)

    risk_level = "low"
    if reasons:
        risk_level = (
            "high"
            if any(reason in reasons for reason in [RISK_REASON_NO_PLACEHOLDER, RISK_REASON_UNKNOWN_PLACEHOLDER])
            else "medium"
        )
    return {"risk_level": risk_level, "reasons": sorted(set(reasons))}


def build_doris_regexp(pattern: str, placeholder_index: int, predefined_varibles=None) -> str:
    """把展示 DSL 编译成 Doris regexp_extract 可用的 raw regex。"""

    tokens = tokenize_pattern_dsl(pattern)
    regex_mapping = _build_placeholder_regex_mapping(predefined_varibles)
    placeholder_indexes = {token["index"] for token in tokens if token["token_type"] == "placeholder"}

    if not placeholder_indexes:
        raise ValueError("pattern has no placeholders")
    if placeholder_index not in placeholder_indexes:
        raise ValueError(f"placeholder index out of range: {placeholder_index}")

    parts = []

    for token in tokens:
        part = ""
        if token["token_type"] == "literal":
            part = re.escape(token["value"])
        elif token["token_type"] == "wildcard":
            part = PATTERN_GAP_REGEX
        elif token["token_type"] == "placeholder":
            placeholder_regex = regex_mapping.get(token["value"])
            if not placeholder_regex:
                raise ValueError(f"placeholder regex not found: {token['value']}")
            placeholder_regex = _normalize_capturing_groups(placeholder_regex)
            placeholder_regex = _strip_outer_regex_anchors(placeholder_regex)
            # 只捕获当前点击的那个占位符，其余占位符仅参与定位。
            if token["index"] == placeholder_index:
                part = f"({placeholder_regex})"
            else:
                part = f"(?:{placeholder_regex})"

        if not part:
            continue
        if parts:
            parts.append(PATTERN_GAP_REGEX)
        parts.append(part)

    return "".join(parts)


def escape_sql_literal(value: str) -> str:
    """转义 SQL 单引号字符串中的反斜杠和单引号。"""

    return value.replace("\\", "\\\\").replace("'", "''")
