# core.drf_resource

`core.drf_resource` 是监控平台内部的一套轻量业务接口框架。它借鉴了 DRF 的 `serializer + viewset` 思路，但把“业务逻辑单元”单独抽象成了 `Resource`，从而让一段逻辑既可以被 HTTP 接口复用，也可以被项目内其他模块直接调用。

这套框架的核心目标有三点：

- 将参数校验、业务逻辑、HTTP 暴露解耦。
- 让业务逻辑可以像函数一样在项目内复用。
- 通过自动发现、动态路由和统一扩展能力，减少样板代码。

## 核心概念

### Resource

`Resource` 是最核心的抽象，代表“一段接收输入并返回输出的业务逻辑”。

- 输入校验：可选 `RequestSerializer`
- 输出校验：可选 `ResponseSerializer`
- 业务实现：必须实现 `perform_request`
- 调用入口：统一走 `request`

标准执行链路如下：

1. 接收请求参数。
2. 使用 `RequestSerializer` 校验并生成 `validated_request_data`。
3. 调用 `perform_request(validated_request_data)` 执行业务逻辑。
4. 使用 `ResponseSerializer` 校验并生成最终输出。
5. 返回结果，并在异常时统一记录 tracing / 错误信息。

对应实现见：

- `core/drf_resource/base.py`

### ResourceViewSet

`ResourceViewSet` 是对 DRF `GenericViewSet` 的封装，用于把一个或多个 `Resource` 映射成 HTTP 接口。

- 通过 `resource_routes` 描述接口路由
- 自动生成 `list/create/retrieve/update/...` 或自定义 action
- 自动挂接 swagger 描述
- 支持异步任务模式

对应实现见：

- `core/drf_resource/viewsets.py`
- `core/drf_resource/routers.py`

### 三类全局入口

框架启动后会自动构建三个全局访问入口：

- `resource`：项目内业务型 Resource
- `api`：封装远程 API 调用的 Resource
- `adapter`：按平台差异覆盖实现的 Resource

常见调用方式：

```python
from core.drf_resource import api, resource

api.metadata.get_label({"label_type": "source_label"})
resource.some_module.some_method({"foo": "bar"})
```

## 架构分层

整体推荐分层如下：

```text
serializers -> resources -> viewsets -> router/url
```

各层职责：

- `Serializer`：只做请求/响应的数据结构定义与校验
- `Resource`：只写业务逻辑
- `ViewSet`：负责把 Resource 暴露成接口
- `Router`：负责自动注册 viewset 路由

这意味着：

- 同一段逻辑既可以被 HTTP 调用，也可以在 Python 内部直接复用
- View 层通常非常薄，复杂逻辑集中在 Resource

## 启动与自动发现

### 启动时机

`core.drf_resource` 的 `AppConfig.ready()` 会调用 `setup()`，扫描项目中可注册的资源模块并完成挂载。

对应实现见：

- `core/drf_resource/apps.py`
- `core/drf_resource/management/root.py`

### 发现规则

框架会扫描：

- 各 Django app 目录
- `settings.RESOURCE_DIRS`
- `settings.API_DIR`

满足以下文件结构之一时会被识别：

- `xxx/resources.py`
- `api/xxx/default.py`
- `xxx/adapter/default.py`
- `xxx/adapter/<platform>/resources.py`

扫描逻辑见：

- `core/drf_resource/management/finder.py`

### 动态挂载规则

发现模块后，会被包装成 `ResourceShortcut`，并懒加载模块中的类或函数。

例如：

```text
api/metadata/default.py
```

中的：

```python
class GetLabelResource(...)
```

会被暴露为：

```python
api.metadata.get_label(...)
```

这里有两个关键点：

- 类名末尾的 `Resource` 会被去掉
- 类名会从驼峰转成下划线

另外，`ResourceShortcut` 挂到外部的是实例，但 `Resource.__call__()` 内部会重新创建一个临时实例执行请求，因此可以避免共享状态导致的线程安全问题。

## Resource 的执行细节

### 1. serializer 自动绑定

`Resource` 初始化时会尝试查找 `RequestSerializer` 和 `ResponseSerializer`。

优先级如下：

1. 直接在 Resource 类中显式定义
2. 如果配置了 `serializers_module`，按命名规则自动查找

### 2. 请求校验

`validate_request_data()` 会：

- 没有 `RequestSerializer` 时直接透传
- 有 `RequestSerializer` 时执行 `is_valid()`
- 失败时抛出 `CustomException`

### 3. 业务执行

业务代码只需要实现：

```python
def perform_request(self, validated_request_data):
    ...
```

### 4. 响应校验

`validate_response_data()` 与请求校验类似：

- 没有 `ResponseSerializer` 时直接透传
- 否则校验输出结构

### 5. tracing 与异常埋点

`request()` 内部已经统一接入：

- OpenTelemetry span
- 异常事件记录
- MCP 请求指标上报

因此绝大多数子类不需要重复做这些工作。

### 6. 异步调用

每个 `Resource` 都支持：

- `delay()`
- `apply_async()`

底层通过 celery 任务 `run_perform_request` 执行。任务过程中还支持 `update_state()` 上报步骤状态。

对应实现见：

- `core/drf_resource/tasks.py`

### 7. 批量并发调用

`bulk_request()` 提供了基于线程池的并发请求能力，适合多个相同 Resource 的并发拉取场景。

## 通过 ViewSet 暴露接口

最常见的写法如下：

```python
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from query_api.resources import GetTSDataResource


class GetTSDataViewSet(ResourceViewSet):
    resource_routes = [
        ResourceRoute("POST", GetTSDataResource),
    ]
```

之后通过 `ResourceRouter` 注册：

```python
from core.drf_resource.routers import ResourceRouter
from . import views

router = ResourceRouter()
router.register_module(views)
```

路由注册时，`ResourceRouter` 会先调用 `generate_endpoint()` 动态生成真实的 view 方法，因此一般不需要手写 `post/get` 逻辑。

### ResourceRoute 常用参数

- `method`：HTTP 方法
- `resource_class`：对应 Resource
- `endpoint`：自定义 action 名称；为空时走默认 REST 动作
- `pk_field`：detail 接口时，URL 主键写入请求参数的字段名
- `enable_paginate`：是否分页
- `content_encoding`：响应编码
- `decorators`：附加装饰器

## 常见扩展类

### CacheResource

`CacheResource` 为 `request()` 提供缓存包装能力。若配置了：

- `cache_type`
- `backend_cache_type`

则会在初始化时自动把 `request` 包装成带缓存的版本。

特点：

- 缓存的是整个 Resource 调用结果
- 子类可通过 `cache_write_trigger()` 控制是否写缓存

对应实现见：

- `core/drf_resource/contrib/cache.py`

### APIResource

`APIResource` 继承自 `CacheResource`，用于封装远程 HTTP API 调用，适用于 ESB / APIGW 场景。

子类通常只需声明：

- `module_name`
- `base_url`
- `action`
- `method`

它额外提供了：

- 自动补充用户身份与租户信息
- 统一构造 `x-bkapi-authorization`
- GET / POST / PUT / PATCH / DELETE 请求封装
- 标准 `{result, code, data}` 响应处理
- 统一错误转换与 API 指标上报
- 流式响应支持

对应实现见：

- `core/drf_resource/contrib/api.py`

### FaultTolerantResource

`FaultTolerantResource` 用于“允许执行失败但返回默认值”的场景。

行为特点：

- 参数校验阶段出错：仍然抛异常
- 参数校验成功后，若后续执行报错：吞掉异常并返回默认值

适合查询类、可降级类接口。

对应实现见：

- `core/drf_resource/contrib/exception.py`

### KernelAPIResource

`KernelAPIResource` 基于 `APIResource` 再做了一层“嵌套 API 调用优化”。

背景是：

- 后台 API 服务会复用 SaaS 的部分 Resource
- SaaS 逻辑内部又可能调用后台 API
- 如果仍然走 ESB / APIGW，就可能形成回环调用

因此：

- 在 `ROLE=api` 时，直接把 API 路径 resolve 到本地 view 执行
- 非 API 模式下，仍然按普通远程 API 调用

对应实现见：

- `core/drf_resource/contrib/nested_api.py`

## 最小示例

### 定义一个业务 Resource

```python
from rest_framework import serializers
from core.drf_resource import Resource


class DemoResource(Resource):
    class RequestSerializer(serializers.Serializer):
        name = serializers.CharField(required=True)

    class ResponseSerializer(serializers.Serializer):
        message = serializers.CharField()

    def perform_request(self, validated_request_data):
        return {"message": f"hello {validated_request_data['name']}"}
```

### 暴露成接口

```python
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class DemoViewSet(ResourceViewSet):
    resource_routes = [
        ResourceRoute("POST", DemoResource),
    ]
```

### 项目内直接调用

如果该 Resource 位于可自动发现的 `resources.py` 中，还可以被项目内部直接调用：

```python
resource.demo.demo({"name": "alice"})
```

## 一个真实项目示例

### Resource 定义

`query_api/resources.py` 中的 `GetTSDataResource`：

- 使用 `RequestSerializer` 声明 `sql`
- 在 `perform_request()` 中按 SQL 选择 driver 并查询

### ViewSet 暴露

`kernel_api/views/v3/query.py` 中的 `GetTSDataViewSet`：

- 只写了一条 `ResourceRoute("POST", GetTSDataResource)`
- 没有额外业务逻辑

这正是这套框架希望达到的状态：接口层尽量薄，业务逻辑集中在 Resource。

## 异常处理

框架提供了统一异常处理器：

- `core/drf_resource/exceptions.py`

主要行为：

- `Error` / `CustomException`：按平台统一错误格式返回
- DRF `APIException`：转换为统一错误结构
- `Http404`：转换为平台 404 格式
- 未知异常：兜底成统一错误响应

在 web 侧已通过 DRF settings 挂载。

## 设计上的几个约定

推荐遵循以下实践：

- Resource 中只写业务逻辑，不写 HTTP 细节
- 参数和返回结构尽量显式定义 Serializer
- ViewSet 只做路由编排，不写复杂逻辑
- 项目内跨模块复用逻辑时，优先调用 `resource.xxx` / `api.xxx`
- 远程 API 封装优先继承 `APIResource`
- 可缓存查询优先继承 `CacheResource`
- 可降级查询优先继承 `FaultTolerantResource`

## 适用场景

这套框架尤其适合以下场景：

- 一段逻辑既要提供 HTTP 接口，又要被 Python 内部复用
- 需要统一参数校验和错误处理
- 需要将远程 API 调用抽象成项目内可复用的方法
- 需要在不同模块之间以“资源原子”方式复用逻辑

## 相关目录

```text
core/drf_resource/
├── __init__.py
├── stubgen.py
├── apps.py
├── base.py
├── exceptions.py
├── routers.py
├── tasks.py
├── tools.py
├── viewsets.py
├── contrib/
│   ├── api.py
│   ├── cache.py
│   ├── exception.py
│   └── nested_api.py
└── management/
    ├── finder.py
    └── root.py
```

## 类型桩生成

为了让 `from core.drf_resource import resource, api` 这类动态入口在 IDE / 类型检查器中具备补全能力，模块内提供了一个 stub 生成器：

- `core/drf_resource/stubgen.py`

常见用法：

```python
from core.drf_resource.stubgen import generate_entrypoint_type_stubs

generate_entrypoint_type_stubs()
```

默认会生成：

- `typings/core/drf_resource/__init__.pyi`

该文件会为 `resource` / `api` 动态入口补出层级结构与调用签名。

如果 `Resource` 定义了 `RequestSerializer` / `ResponseSerializer`，生成器还会进一步把 serializer 结构转换成对应的 `TypedDict` 类型，并体现在方法入参和返回值中。

对于请求参数，生成的 typing 会同时支持两种调用形式：

- `resource.foo(request_data={...})`
- `resource.foo(field_a=..., field_b=...)`

但这两种形式在类型层面是互斥的，不支持混写。

## 参考入口

如果要继续阅读源码，建议按下面顺序：

1. `core/drf_resource/base.py`
2. `core/drf_resource/viewsets.py`
3. `core/drf_resource/routers.py`
4. `core/drf_resource/management/root.py`
5. `core/drf_resource/contrib/api.py`
6. `core/drf_resource/contrib/nested_api.py`
7. `core/drf_resource/stubgen.py`
