class QueryStringCharacters:
    ES_RESERVED_CHARACTERS = [
        "\\",
        "+",
        "-",
        "=",
        "&&",
        "||",
        ">",
        "<",
        "!",
        "(",
        ")",
        "{",
        "}",
        "[",
        "]",
        "^",
        '"',
        "~",
        "*",
        "?",
        ":",
        "/",
        " ",
    ]
    # 不管是不是通配符查询，都必须要转义双引号
    MUST_ESCAPE_CHARACTERS = ['"']
    CAN_NOT_ESCAPE_RESERVED_CHARACTERS = [
        ">",
        "<",
    ]
    SUPPORTED_WILDCARDS_CHARACTERS = ["*", "?"]


class QueryStringLogicOperators:
    AND = "AND"
    OR = "OR"
    NOT = "NOT"


class QueryStringOperators:
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"
    EQUAL = "equal"
    NOT_EQUAL = "not_equal"
    INCLUDE = "include"
    NOT_INCLUDE = "not_include"
    GT = "gt"
    LT = "lt"
    GTE = "gte"
    LTE = "lte"
    BETWEEN = "between"

    # 需要处理通配符转义的操作符
    NEED_WILDCARD_OPERATORS = [INCLUDE, NOT_INCLUDE]
    NEED_ADD_DOUBLE_QUOTATION_OPERATORS = [EQUAL, NOT_EQUAL]

    OPERATOR_TEMPLATE_MAPPING = {
        EXISTS: "{field}: *",
        NOT_EXISTS: "NOT {field}: *",
        EQUAL: "{field}: {value}",
        NOT_EQUAL: "NOT {field}: {value}",
        INCLUDE: "{field}: {value}",
        NOT_INCLUDE: "NOT {field}: {value}",
        GT: "{field}: >{value}}",
        LT: "{field}: <{value}}",
        GTE: "{field}: >={value}",
        LTE: "{field}: <={value}",
        BETWEEN: "{field}: [{start_value} TO {end_value}]",
    }
