# 表达式解析器模块 (expression)

## 概述

`expression` 模块用于多告警关联策略的表达式解析和求值。表达式用于描述多个告警之间的逻辑关系，支持 AND、OR、NOT 等逻辑运算符。

## 表达式定义

### 支持的运算符

- `&&`：逻辑与（AND），取两个操作数的最小状态值
- `||`：逻辑或（OR），取两个操作数的最大状态值
- `!`：逻辑非（NOT），状态转换（异常↔正常，无数据保持不变）
- `()`：括号分组，用于改变运算优先级

### 运算符优先级

1. `!`（NOT）- 最高优先级，右结合
2. `&&`（AND）- 左结合
3. `||`（OR） - 左结合，最低优先级

### 表达式示例

```python
"A"                    # 单个变量
"A && B"               # 两个变量的 AND 操作
"A || B"               # 两个变量的 OR 操作
"!A"                   # NOT 操作
"A && (B || C)"        # 括号改变优先级
"!A && B"              # NOT 优先级高于 AND
"A && (B || C) && !D"  # 复杂组合
```

### 变量命名规则

- 变量名由字母、数字和下划线组成（`\w+`）
- 变量名大小写不敏感（求值时会自动转换为小写进行匹配）

## 状态值定义

表达式求值使用以下状态值：

```python
class AlertExpressionValue:
    ABNORMAL = 20  # 异常状态
    NORMAL = 10    # 正常状态
    NO_DATA = 0    # 无数据状态
```

### 状态值计算规则

1. **AND 操作** (`&&`)：取两个操作数的**最小值**
   ```python
   ABNORMAL && NORMAL = NORMAL (min(20, 10) = 10)
   ABNORMAL && NO_DATA = NO_DATA (min(20, 0) = 0)
   ```

2. **OR 操作** (`||`)：取两个操作数的**最大值**
   ```python
   ABNORMAL || NORMAL = ABNORMAL (max(20, 10) = 20)
   NORMAL || NO_DATA = NORMAL (max(10, 0) = 10)
   ```

3. **NOT 操作** (`!`)：状态转换
   ```python
   !ABNORMAL = NORMAL    # 异常 => 正常
   !NORMAL = ABNORMAL     # 正常 => 异常
   !NO_DATA = NO_DATA     # 无数据 => 无数据（保持不变）
   ```

## 使用方法

### 基本使用

```python
from bk_monitor_base.domains.strategy.expression import (
    AlertExpressionValue,
    parse_expression,
)

# 解析表达式
expr = parse_expression("A && B")

# 定义上下文（告警状态）
context = {
    "A": AlertExpressionValue.ABNORMAL,  # 异常
    "B": AlertExpressionValue.NORMAL,     # 正常
}

# 求值
result = expr.eval(context)
print(result)  # 输出: 10 (NORMAL，因为 min(20, 10) = 10)

# 或者使用可调用接口
result = expr(context)
print(result)  # 输出: 10
```

### 复杂表达式

```python
from bk_monitor_base.domains.strategy.expression import (
    AlertExpressionValue,
    parse_expression,
)

# 解析复杂表达式
expr = parse_expression("A && (B || C) && !D")

# 定义上下文
context = {
    "A": AlertExpressionValue.ABNORMAL,
    "B": AlertExpressionValue.NORMAL,
    "C": AlertExpressionValue.NO_DATA,
    "D": AlertExpressionValue.NORMAL,
}

# 求值
result = expr.eval(context)
print(result)  # 输出: 10 (NORMAL)
```

### 表达式翻译

```python
from bk_monitor_base.domains.strategy.expression import parse_expression

# 解析表达式
expr = parse_expression("A && (B || C)")

# 无上下文翻译（使用变量名）
translation = expr.translate()
print(translation)  # 输出: "A && (B || C)"

# 有上下文翻译（使用翻译后的名称）
translation_context = {
    "A": "CPU告警",
    "B": "内存告警",
    "C": "磁盘告警",
}
translation = expr.translate(translation_context)
print(translation)  # 输出: "CPU告警 && (内存告警 || 磁盘告警)"
```

### 错误处理

```python
from bk_monitor_base.domains.strategy.expression import parse_expression

# 语法错误
try:
    expr = parse_expression("A &&")  # 缺少右操作数
except ValueError as e:
    print(f"语法错误: {e}")

# 未定义变量
try:
    expr = parse_expression("A && B")
    result = expr.eval({"A": 20})  # B 未定义
except ValueError as e:
    print(f"变量未定义: {e}")  # 输出: "variable 'B' is not defined"
```
