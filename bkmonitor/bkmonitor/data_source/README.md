# DataSource

数据查询模块

## 设计目的

- 统一查询入口
- saas和告警后台等模块可以共用，不需要一个模块写一份
- 支持时序和日志类的查询   
    - 时序类的查询结果是聚合后的时序数据
    - 日志类的查询结果是聚合后的数量，也是时序数据
- 封装sql拼接的逻辑，提供类似DjangoORM的使用方式


## 设计思路

参考 `django/db/***` 目录下的模块设计

## 目录结构

```
data_source
├── README.md
├── __init__.py
├── backends              # 不同数据类型的backends
│   ├── __init__.py
│   ├── base
│   │   ├── __init__.py
│   │   ├── connection.py # 
│   │   └── operations.py
│   ├── log               #
│   │   ├── __init__.py
│   │   ├── compiler.py   # 编译成dsl语法的相关逻辑
│   │   ├── connection.py # 查询相关逻辑
│   │   └── operations.py # 区别于其他数据类型的不同操作
│   └── time_series
│       ├── __init__.py
│       ├── compiler.py
│       ├── connection.py
│       └── operations.py
├── data_structure.py     # 数据结构定义，DataPoint
├── models
│   ├── __init__.py
│   └── sql
│       ├── __init__.py
│       ├── compiler.py   # 编译成查询语句的相关逻辑，基类
│       └── query.py      # 用户查询入口
└── shortcuts.py
```


## 使用方式

```python
# 自己加载backend，得到Query然后执行
query_class = load_backend(using=(data_source_label, data_type_label))
query = query_class(table_name, select...)
data = query.data
data = query.Query()
data = list(query)
data = iter(query)

# 直接import Query，然后执行
import Query
query = Query(table_name, using=(..)).select(...).filter(...)
data = query.execute()

# 原始sql查询
import RawQuery
query = RawQuery(raw_sql, using=(..))
data = query.data
```