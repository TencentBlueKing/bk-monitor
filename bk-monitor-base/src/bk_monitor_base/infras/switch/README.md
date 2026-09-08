# Base 模块调用开关

## 开关

通过 config 中的 `enable_base_compatible_switch` 配置项来控制 Base 模块的调用开关。


## 调用

在需要调用 Base 模块的地方，使用以下代码来检查开关状态：

```python
# 原来的写法

result: SaveStrategyApiResult = StrategyApi.save_alarm_strategy_v2(obj)


# 增加开关后的写法
from bk_monitor_base.infras.switch import base_switch
from bk_monitor_base.strategy import save_alarm_strategy

result: SaveStrategyApiResult = base_switch(legacy=StrategyApi.save_alarm_strategy_v2, current=save_alarm_strategy, params=(obj,))
```

有的地方包含一个复杂调用
```python
# 原来的写法
del_obj = DeleteStrategy(ids=[_bk_strategy_id], bk_biz_id=self.resource.metadata.labels.bk_biz_id)
del_res = StrategyApi.delete_alarm_strategy(del_obj).dict()

# 增加开关后的写法
from bk_monitor_base.infras.switch import base_switch
from bk_monitor_base.strategy import delete_alarm_strategy

del_obj = DeleteStrategy(ids=[_bk_strategy_id], bk_biz_id=self.resource.metadata.labels.bk_biz_id)
del_res = base_switch(legacy=StrategyApi.delete_alarm_strategy, current=delete_alarm_strategy, params=(del_obj,)).dict()
```

`base_switch` 函数的参数说明如下：
- `legacy`: 旧的 Base 模块调用函数
- `current`: 新的 Base 模块调用函数
- `params`: 传递给函数的参数，使用元组形式传递

如果开关打开，则调用 `current` 函数，否则调用 `legacy` 函数。

## 注意事项

可以看到 current 传入的新方法需要和 legacy 传入的旧方法参数保持一致，也就是在 domains 中需要额外实现一套兼容方法，可以和模块设计的新方法分开实现。
