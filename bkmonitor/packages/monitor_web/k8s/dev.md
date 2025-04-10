
# 容器监控设计文档

## 设计思路
本模块为Kubernetes容器监控场景的核心实现，采用分层架构设计，主要包含以下核心模块：

1. **资源元数据管理(Core)**
   - 定义K8S资源模型（Pod/Workload/Namespace等）
   - 实现资源数据获取（ORM + PromQL双模式）
   - 提供资源过滤、聚合、排序等核心功能

2. **监控场景管理(Scenario)**
   - 性能场景（CPU/内存/网络）
   - 网络场景（流量/包量/错误率）
   - 支持场景指标的动态扩展

3. **API资源层(Resources)**
   - 提供RESTful API接口
   - 支持分页/过滤/排序
   - 实现数据聚合与格式转换

4. **过滤引擎(Filters)**
   - 支持多维度资源过滤
   - 提供精确匹配和模糊查询
   - 自动转换查询条件到ORM/PromQL

## 核心实现

### 1. 资源元数据系统
```python
class K8sResourceMeta:
    """
    资源元数据基类，核心功能包括：
    - 资源字段映射(column_mapping)
    - PromQL生成器(meta_prom_with_*)
    - 数据聚合方法(set_agg_method)
    - 过滤条件管理(add_filter)
    """
```

#### 典型资源实现：
- `K8sPodMeta`: 处理Pod资源，支持容器级指标
- `K8sWorkloadMeta`: 处理工作负载，支持Deployment/StatefulSet等
- `K8sNamespaceMeta`: 命名空间维度聚合

### 2. 场景化指标管理
```python
class Category:
    """
    指标分类（如CPU/内存）
    包含多个Metric定义
    """

class Metric:
    """
    指标元数据：
    - 指标ID（对应Prometheus指标）
    - 显示名称
    - 计量单位
    - 不支持资源类型列表
    """
```

### 3. 过滤引擎
```python
class ResourceFilter:
    """
    过滤器基类，实现：
    - 过滤条件构建(filter_dict)
    - PromQL条件生成(filter_string)
    - 多值/模糊查询支持
    """
```

### 4. API接口层
主要接口示例：
- **获取集群列表** `ListBCSCluster`
- **资源概览统计** `WorkloadOverview`
- **场景指标列表** `ScenarioMetricList`
- **资源详情查询** `GetResourceDetail`
- **时序数据获取** `ResourceTrendResource`

## 主要特性

1. **多维度监控**
   - 支持6种核心资源类型
   - 覆盖20+关键指标
   - 秒级数据粒度

2. **灵活查询**
```python
# 示例：带过滤的分页查询
ListK8SResources().perform_request({
    "resource_type": "pod",
    "filter_dict": {"namespace": "default"},
    "order_by": "-cpu_usage",
    "page_size": 20
})
```

3. **场景化指标**
```python
# 性能场景指标定义
Metric(
    id="container_cpu_usage_seconds_total",
    name="CPU使用量",
    unit="core",
    unsupported_resource=[]
)
```

4. **混合数据源**
   - 实时数据：Prometheus
   - 元数据：Django ORM
   - 自动选择最优数据源

5. **性能优化**
   - 查询结果缓存
   - PromQL生成优化
   - 批量数据获取

## 接口示例
```python
# 获取工作负载CPU使用趋势
ResourceTrendResource().perform_request({
    "resource_type": "workload",
    "column": "container_cpu_usage_seconds_total",
    "resource_list": ["Deployment:bk-monitor"],
    "start_time": 1672502400,
    "end_time": 1672588800
})
```

## 扩展性设计
1. **新增资源类型**
   - 继承K8sResourceMeta
   - 实现meta_prom_with_*系列属性
   - 注册到resource_meta_map

2. **新增监控场景**
   - 在scenario目录添加新场景模块
   - 实现get_metrics()函数
   - 更新ScenarioMetricList资源

3. **自定义指标**
```python
class CustomMetric(Metric):
    def get_metric_promql(self):
        # 实现自定义PromQL逻辑
        return "custom_metric_query"
```

