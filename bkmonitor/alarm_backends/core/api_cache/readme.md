# 一、using_cache介绍

##using_cache模式

| 调用模式  | 错误名词    | 描述                         |
| --------- | ----------- | ---------------------------- |
| cached    | API请求错误 | API请求错误                  |
| refresh   | 刷新模式    | 会刷新当前接口缓存并返回值   |
| cacheless | 不使用缓存  | 不使用缓存，直接调用接口返回 |

## cache_key的设定

```python
'{}:{}:{}:{},{}[{}]'.format(
                self.key_prefix, # 固定
                self.using_cache_type.key, # 缓存类型
                self.func_key_generator(task_definition), # 缓存调用对象
                count_md5(to_sorted_str(args)), # 入参md5
                count_md5(to_sorted_str(kwargs)), # 入参md5
                self.username # 用户名，后端为backend
            )
```

## 缓存类型：

| 参数                | 描述                         |
| -------------------|--------------------------- |
| key                | API请求错误                  |
| timeout            | 会刷新当前接口缓存并返回值   |
| user_related       | 不使用缓存，直接调用接口返回 |
| label              | 类型描述                     |

```python
CacheTypeItem(key='biz', timeout=20,label="业务及人员相关", user_related=True)
```



# 二、使用方式

## 1、装饰器

```python
from bkmonitor.utils.cache import CacheType, using_cache
@using_cache(CacheType.DATA)
def test():
    pass
```

添加了装饰器的函数会缓存结果。

## 2、API缓存

```python
from core.drf_resource.contrib.cache import CacheResource
from bkmonitor.utils.cache import CacheType

class HostPerformanceResource(CacheResource):
    cache_type = CacheType.HOST
    backend_cache_type = CacheType.CC_BACKEND
```

继承了CacheResource的类会根据配置的两种cache_type和backend_cache_type来决定缓存类别：

**cache_type**：客户端使用，如果是用户相关的接口，会取cache_type作为缓存类别，并取当前接口使用的用户名。

**backend_cache_type**：服务端使用，如果SaaS调用用户无关接口，或者不存在用户名想要配置缓存，都可以取backend_cache_type作为缓存类别。

为什么要区分开来呢？因为后端缓存是定时刷新，供后端、部分前端的定时任务、部分用户不敏感的查询使用；前端对于部分信息的时效性要求较高，所以在这里将其分开缓存。

## 3、后端API缓存的实现方式

代码位置：```from alarm_backends.core.api_cache```

实现机制（celery_beat定时刷新）：

后台设置定时刷新接口任务，指定需要刷新的接口及入参，在主文件**library**文件中统一定义调用：

```python
from constants.data_source import LabelType
from core.drf_resource import api

get_label_api = {
    'api': api.metadata.get_label,
    'args': {},
    'kwargs': {'label_type': LabelType.ResultTableLabel, 'include_admin_only': True}
}

```

```python
from alarm_backends.core.api_cache.metadata import get_label_api

def get_label():
    call_obj = get_label_api['api']
    call_obj.request.refresh(get_label_api['args'], **get_label_api['kwargs'])


API_CRONTAB = [
    # (get_business, "*/1 * * * *"),
    (get_label, "*/5 * * * *")
]
```

后端API缓存是直接对原始的API调用的缓存，保证接口的原子性，接口类继承APIResource，APIResource继承CacheResource，在CacheResource中针对request进行缓存：

```python
        self.request = using_cache(
            cache_type=self.cache_type,
            backend_cache_type=self.backend_cache_type,
            user_related=self.cache_user_related,
            compress=self.cache_compress,
            is_cache_func=self.cache_write_trigger,
            func_key_generator=func_key_generator
        )(self.request)
```

# 三、缓存后端

目前缓存后端使用的是后台DB，后面可以根据默认后端的变化（如redis）实现自动切换，配置如下：

```python
CACHES = {
    'db': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'django_cache',
        'OPTIONS': {
            'MAX_ENTRIES': 10000,
            'CULL_FREQUENCY': 10
        }
    },
    'dummy': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    },
    'locmem': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    },
}

if 'redis' in CACHES:
    CACHES['default'] = CACHES['redis']
else:
    CACHES['default'] = CACHES['db']
```

在数据库路由中配置路由到后端数据库：

```python
if model._meta.app_label == 'django_cache':
    return 'monitor_api'
```

