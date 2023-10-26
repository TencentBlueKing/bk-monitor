{% load doc_tags %}
{% autoescape off %}
### 功能描述

{{ api.description|mdnewline }}

### 请求方式
#### 请求地址
{{ config.path }}

#### 请求方法
{{ config.suggest_method }}

{% templatetag openvariable %} common_args_desc {% templatetag closevariable %}

#### 接口参数

| 字段   | 类型 | 必选 | 描述 |
|--------|------|------|------|
| object | dict | 否   | 对象 |

#### 嵌套参数
##### object

| 字段 | 类型   | 必选 | 描述 |
|------|--------|------|------|
| name | string | 是   | 名称 |

#### 请求示例
```json
{}
```

### 返回结果
#### 字段说明

| 字段 | 类型 | 描述   |
|------|------|--------|
| id   | int  | 对象ID |

#### 结果示例
```json
{}
```
{% endautoescape %}