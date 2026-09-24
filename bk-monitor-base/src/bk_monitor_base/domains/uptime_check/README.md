# 拨测模块 (uptime_check)

## 概述

`uptime_check` 模块是 BlueKing Monitor 中用于网络拨测和服务可用性监控的核心模块。该模块提供了完整的拨测任务管理能力，包括任务创建、配置生成、节点管理、订阅管理、数据接入等功能。

## 核心设计理念

### 任务管理器 (TaskManager)

任务管理器采用**协调者模式**，负责编排拨测任务的完整生命周期，协调各服务组件完成部署、启动、停止、删除等操作。

**设计要点**：

1. **流程编排**：通过 `TaskManager` 统一编排任务部署的完整流程，包括数据接入、配置生成、订阅创建、状态更新等步骤
2. **服务协调**：持有并协调多个服务实例（`SubscriptionService`、`DataAccessService`）完成特定功能
3. **核心职责**：
   - `deploy()`：部署任务（申请DataID → 生成配置 → 创建/更新订阅 → 异步查询状态）
   - `start()`：启动任务（检查订阅 → 执行启动操作）
   - `stop()`：停止任务（执行停止操作）
   - `delete()`：删除任务（清理订阅 → 删除数据库记录）
4. **钩子机制**：支持 `on_deploy_success` 回调钩子，用于解耦基础层与SaaS层的业务逻辑（如指标缓存追加）
5. **职责边界**：TaskManager 专注于任务生命周期管理和流程编排，配置生成由 SubscriptionService 负责；订阅操作通过 nodeman API 完成

### 配置生成服务 (ConfigGeneratorService)

配置生成服务采用**模板方法模式**，负责将业务配置转换为 bkmonitorbeat 采集器配置。

**设计要点**：

1. **模板渲染**：使用 Jinja2 模板引擎，为不同协议（HTTP/TCP/UDP/ICMP）提供独立的配置模板
2. **协议适配**：根据协议类型自动选择合适的模板和处理逻辑
3. **配置转换**：
   - `generate_config()`：生成完整的 bkmonitorbeat 配置
   - `generate_sub_config()`：生成单个任务的子配置
   - `render_template()`：渲染指定协议的模板
4. **数据准备**：处理超时计算、字段编码、标签注入等数据预处理工作
5. **可扩展性**：支持自定义模板目录，便于协议扩展

### 订阅服务 (SubscriptionService)

订阅服务采用**外观模式**，封装了与节点管理系统的交互逻辑。

**设计要点**：

1. **配置生成** (`SubscriptionService`)：
   - 按业务分组节点（`_group_nodes_by_biz()`）
   - 构建订阅 Scope（`_build_scope()`）
   - 构建采集步骤（`_build_step()`）
   - 生成完整订阅配置（`generate_subscription_config()`）
2. **订阅管理**：在 `TaskManager` 中直接调用 nodeman API 进行订阅创建/更新/启停/卸载删除等操作
3. **协作关系**：SubscriptionService 负责配置生成，TaskManager 负责编排流程并触发订阅操作

### 数据接入服务 (DataAccessService)

数据接入服务负责管理拨测任务的数据源（DataID）和结果表。

**设计要点**：

1. **DataID 管理**：
   - `get_data_id()`：获取默认或自定义 DataID
   - `create_data_id()`：创建新的 DataID
   - `get_or_create_data_id()`：获取或创建 DataID（可重入）
2. **结果表管理**：
   - `access()`：创建结果表和数据链路
   - `use_custom_report()`：判断是否使用自定义上报
3. **数据源模式**：
   - 默认DataID：所有任务共享同一个DataID（按协议区分）
   - 独立DataID：每个任务使用独立的DataID
4. **可重入性**：支持重复调用，避免重复创建资源

**设计优势**：

- **职责分离**：TaskManager 负责流程编排，各服务负责具体实现，各司其职
- **可测试性**：每个服务都可以独立测试，便于单元测试和集成测试
- **可扩展性**：新增协议只需添加模板和适配逻辑，无需修改核心流程
- **解耦设计**：通过钩子机制实现基础层与SaaS层的解耦

## 支持的拨测协议

拨测模块支持以下四种协议：

### 1. HTTP/HTTPS 拨测

用于检测 Web 服务的可用性和性能，支持：

- 多种请求方法（GET/POST/PUT/DELETE/HEAD/OPTIONS/PATCH）
- 自定义请求头和请求体
- 认证方式（Basic Auth、Bearer Token）
- 响应验证（状态码、响应体内容）
- SSL 证书验证

**典型场景**：
- Web 服务健康检查
- API 接口可用性监控
- 页面响应时间监控

### 2. TCP 拨测

用于检测 TCP 端口的连通性和响应，支持：

- 端口连通性检测
- 自定义请求数据发送
- 响应内容验证
- 超时控制

**典型场景**：
- 数据库端口检测（MySQL/Redis/MongoDB）
- 消息队列端口检测（Kafka/RabbitMQ）
- 自定义 TCP 服务监控

### 3. UDP 拨测

用于检测 UDP 服务的可用性，支持：

- UDP 端口检测
- 自定义请求数据发送
- 响应内容验证
- 等待空响应模式

**典型场景**：
- DNS 服务监控
- NTP 服务监控
- 自定义 UDP 服务监控

### 4. ICMP 拨测

用于检测网络连通性（Ping），支持：

- ICMP Echo Request/Reply
- 数据包大小配置
- 最大往返时间（RTT）测量

**典型场景**：
- 主机存活检测
- 网络延迟监控
- 网络质量评估

## 拨测管理流程

### 任务配置管理

拨测任务的配置包含以下关键字段：

1. **基础配置**：
   - `name`：任务名称
   - `protocol`：协议类型（HTTP/TCP/UDP/ICMP）
   - `check_interval`：检测间隔（分钟）
   - `bk_biz_id`：业务ID

2. **协议配置** (`config` 字段)：
   - `period`：检测周期（秒）
   - `timeout`：超时时间（毫秒）
   - 协议特定配置（如 HTTP 的 URL、方法、请求头等）

3. **节点配置**：
   - 关联的拨测节点列表
   - 支持按分组管理节点

4. **高级配置**：
   - `labels`：自定义标签
   - `indepentent_dataid`：是否使用独立DataID
   - `location`：拨测节点位置配置

### 任务生命周期管理

拨测任务的生命周期包括以下状态：

```
┌─────────┐     deploy()     ┌──────────┐
│  NEW    │ ───────────────> │ STARTING │
└─────────┘                  └──────────┘
                                   │
                   update_task_running_status()
                                   │
                                   v
                             ┌──────────┐
                             │ RUNNING  │ <───┐
                             └──────────┘     │
                                   │          │
                              stop()│    start()
                                   │          │
                                   v          │
                             ┌──────────┐     │
                             │ STOPPED  │ ────┘
                             └──────────┘
                                   │
                              delete()
                                   │
                                   v
                             ┌──────────┐
                             │ DELETED  │
                             └──────────┘
```

**状态说明**：

- `NEW`：新创建，尚未部署
- `STARTING`：启动中，正在创建订阅并下发配置
- `RUNNING`：运行中，正常采集数据
- `STOPPED`：已停止，订阅已禁用
- `STOPING`：停止中，正在停止订阅
- `FAILED`：失败，部署或启动失败

### 核心方法

#### 1. 任务创建与部署

```python
from bk_monitor_base.uptime_check import UptimeCheckTaskModel, UptimeCheckNodeModel

# 创建任务
task = UptimeCheckTaskModel.objects.create(
    bk_biz_id=2,
    name="HTTP拨测示例",
    protocol="HTTP",
    check_interval=5,
    config={
        "period": 60,
        "timeout": 3000,
        "url": "http://example.com",
        "method": "GET",
        "response_code": "200",
    },
)

# 关联节点
nodes = UptimeCheckNodeModel.objects.filter(bk_biz_id=2, is_common=True)
task.nodes.set(nodes)

# 部署任务
result = task.deploy()
```

#### 2. 任务启动与停止

```python
# 启动任务
task.start()

# 停止任务
task.stop()
```

#### 3. 任务删除

```python
# 删除任务（会自动清理订阅）
task.delete()
```

#### 4. 使用 TaskManager（推荐）

```python
from bk_monitor_base.uptime_check import TaskManager, UptimeCheckTaskSubscription

# 创建任务管理器
manager = TaskManager(
    task=task,
    subscription_model=UptimeCheckTaskSubscription,
    on_deploy_success=my_callback_function,  # 可选的成功回调
)

# 部署任务
manager.deploy(enable_strategy=True)

# 启动任务
manager.start()

# 停止任务
manager.stop()

# 删除任务
manager.delete()
```

### 数据接入

拨测任务的数据需要上报到指定的数据源，目前支持两种数据源模式：

#### 1. 默认 DataID 模式

所有同协议的拨测任务共享同一个 DataID：

- `uptimecheck.http`：HTTP 协议
- `uptimecheck.tcp`：TCP 协议
- `uptimecheck.udp`：UDP 协议
- `uptimecheck.icmp`：ICMP 协议

**特点**：
- 资源利用率高
- 管理简单
- 适合大规模部署

#### 2. 独立 DataID 模式

每个拨测任务使用独立的 DataID。

**特点**：
- 数据隔离性强
- 便于按任务统计资源消耗
- 适合重要业务或需要数据隔离的场景

**使用方式**：

```python
task = UptimeCheckTaskModel.objects.create(
    bk_biz_id=2,
    name="重要业务HTTP拨测",
    protocol="HTTP",
    indepentent_dataid=True,  # 启用独立DataID
    config={...},
)
```

## 模块结构

```
uptime_check/
├── __init__.py                    # 模块入口
├── apps.py                        # Django 应用配置
├── constants.py                   # 常量定义（协议、状态、默认值等）
├── models.py                      # 数据模型定义
├── tasks.py                       # Celery 异步任务
├── services/                      # 服务层
│   ├── config_generator.py       # 配置生成服务
│   ├── http_helper.py            # HTTP 协议辅助函数
│   ├── subscription.py           # 订阅配置服务
│   ├── data_access.py            # 数据接入服务
│   └── task_manager.py           # 任务管理器
├── templates/                     # Jinja2 配置模板
│   ├── http.jinja2               # HTTP 协议模板
│   ├── tcp.jinja2                # TCP 协议模板
│   ├── udp.jinja2                # UDP 协议模板
│   └── icmp.jinja2               # ICMP 协议模板
└── migrations/                    # 数据库迁移（仅用于测试）
    └── 0001_initial.py
```

## 快速开始

### 推荐使用方式（通过模块入口）

```python
# ✅ 推荐：从模块入口导入
from bk_monitor_base.uptime_check import (
    UptimeCheckTaskModel,
    UptimeCheckNodeModel,
    UptimeCheckGroup,
    UptimeCheckProtocol,
    TaskManager,
)

# ❌ 不推荐：直接从 domains 导入
from bk_monitor_base.domains.uptime_check.models import UptimeCheckTaskModel
```

### 示例：创建 HTTP 拨测任务

```python
from bk_monitor_base.uptime_check import (
    UptimeCheckTaskModel,
    UptimeCheckNodeModel,
    UptimeCheckTaskSubscription,
    TaskManager,
)

# 1. 创建拨测节点
node = UptimeCheckNodeModel.objects.create(
    bk_biz_id=2,
    name="测试节点",
    ip="127.0.0.1",
    bk_cloud_id=0,
    bk_host_id=1,
    is_common=False,
)

# 2. 创建 HTTP 拨测任务
task = UptimeCheckTaskModel.objects.create(
    bk_biz_id=2,
    name="示例HTTP拨测",
    protocol=UptimeCheckTaskModel.Protocol.HTTP,
    check_interval=5,
    config={
        "period": 60,
        "timeout": 3000,
        "url_list": ["http://example.com"],
        "method": "GET",
        "response_code": "200",
        "headers": [
            {"name": "User-Agent", "value": "BkMonitor/1.0"},
        ],
        "authorize": {
            "auth_type": "none",
        },
    },
)

# 3. 关联节点
task.nodes.add(node)

# 4. 使用 TaskManager 部署任务
manager = TaskManager(
    task=task,
    subscription_model=UptimeCheckTaskSubscription,
)

result = manager.deploy()
print(f"部署结果: {result}")

# 5. 查询任务状态（异步任务会更新）
task.refresh_from_db()
print(f"任务状态: {task.status}")
```

### 示例：创建 TCP 拨测任务

```python
# 创建 TCP 拨测任务
task = UptimeCheckTaskModel.objects.create(
    bk_biz_id=2,
    name="Redis端口检测",
    protocol=UptimeCheckTaskModel.Protocol.TCP,
    check_interval=1,
    config={
        "period": 60,
        "timeout": 3000,
        "ip_list": ["127.0.0.1"],
        "port": 6379,
        "response": "PONG",
        "response_format": "in",
    },
)

task.nodes.set([node])
manager = TaskManager(task=task, subscription_model=UptimeCheckTaskSubscription)
manager.deploy()
```

## 异步任务

模块提供以下 Celery 异步任务：

### 1. update_task_running_status

更新拨测任务的运行状态。

```python
from bk_monitor_base.uptime_check.tasks import update_task_running_status

# 异步更新任务状态
update_task_running_status.delay(task_id=1)
```

**功能**：
- 查询节点管理订阅的实际运行状态
- 更新任务状态（STARTING → RUNNING 或 FAILED）
- 记录失败日志

### 2. check_single_task_status

检查单个订阅任务的状态。

```python
from bk_monitor_base.uptime_check.tasks import check_single_task_status

# 检查订阅状态
status = check_single_task_status(
    subscription_id=123,
    task_id=456,
)
```

**返回值**：
- `CollectStatus.RUNNING`：运行中
- `CollectStatus.STARTING`：启动中
- `CollectStatus.FAILED`：失败

## 测试

```bash
# 运行所有拨测模块测试
uv run pytest src/bk_monitor_base/tests/domains/uptime_check/ -v

# 运行特定测试文件
uv run pytest src/bk_monitor_base/tests/domains/uptime_check/test_uptime_check_models.py -v

# 运行特定测试类
uv run pytest src/bk_monitor_base/tests/domains/uptime_check/test_uptime_check_task.py::TestTaskManager -v

# 查看测试覆盖率
uv run pytest src/bk_monitor_base/tests/domains/uptime_check/ --cov=bk_monitor_base.domains.uptime_check --cov-report=html

# 运行测试并显示详细输出
uv run pytest src/bk_monitor_base/tests/domains/uptime_check/ -xvs
```

## 详细文档

完整的架构设计和数据流文档请参考：

- [拨测模块架构文档](../../../../docs/architecture/uptime_check.md)
- [拨测模块重构说明](../../../../docs/architecture/uptime_check_refactoring.md)
- [拨测数据流图](../../../../docs/architecture/uptime_check_data_flow.md)
- [拨测数据流说明](../../../../docs/architecture/uptime_check_data_flow_diagram.md)
