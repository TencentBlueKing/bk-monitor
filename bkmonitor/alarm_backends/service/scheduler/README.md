# scheduler

任务调度器

## 模块设计

调度采用celery的任务分发模式

## 任务

- 异步任务（包括，服务相关逻辑） 
- 定时任务（包括，配置刷新，缓存维护等）


## 使用方式

- 异步任务

各个模块如果需要使用到异步任务，可以将任务统一写到模块下的`tasks.py`文件中，celery会自动加载这个文件下的所有任务

- 定时任务

统一在conf下配置，写到`DEFAULT_CRONTAB`配置中
```python
DEFAULT_CRONTAB = [
    # eg:
    # (module_name, every) like: ("alarm_backends.core.cache.strategy", "* * * * *"),
]

# module_name or func_name, If module_name must have 'main' func
```