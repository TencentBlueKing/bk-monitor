# Kingeye Meta Core 模块

## 如何获取并操作资源模型

```python
# 首先，引入资源模型
from bk_monitor_base.infras.declaratives.v1alpha1 import CollectConfig

# list 方法参数与 ApiServer 提供的 API 参数一致
# 结果是 Collect 对象列表
collects = CollectConfig.store.list()
collects = CollectConfig.store.list(namespace="xxxx", page=2, page_size=30)
collects = CollectConfig.store.list(namespace="xxxx", label_filter={"key": "value"})

for collect in collects:
    ...
    # 直接对 collect 对象进行修改
    collect.store.apply()
```

ESStore 使用方式
```python
配置 store_class
Resource.store_class = "bk_monitor_base.infras.declaratives.store.es_db.ESStore"
```

在框架中，理论上支持多种 `store` 实现，当模块能够连接到 ApiServer 的配置数据库时，将直接读写 DB，否则走 ApiServer DB。