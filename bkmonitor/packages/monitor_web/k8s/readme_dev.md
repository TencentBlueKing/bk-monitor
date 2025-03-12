## 错误定义

### k8s.core.errors.K8sResourceNotFound

找不到对应的资源类型

### k8s.core.errors.MultiWorkloadError

不支持多个 workload 查询

## 过滤器定义

### k8s.core.filters.filter_options

全局字典，用于存储注册继承于 [ResourceFilter](#k8scorefiltersresourcefilterobject) 的 [过滤器子类](#过滤器子类)。
通过 `resource_type`，可以将不同类型的过滤器与它们对应的类关联起来。

### k8s.core.filters.ResourceFilter(object)

过滤器的基类

```python
def filter_uid(self):
    """
    返回一个唯一的标识符  
    由 resource_type + filter_field + value 构成
    """

def filter_dict(self) -> Dict:
    """
    过滤条件构建  
    根据 value 的长度和 fuzzy 标志，它构建相应的查询条件

    如果只有一个值且 fuzzy 为 True，则使用模糊匹配。  
    如果只有一个值且 fuzzy 为 False，则直接匹配。  
    如果有多个值，则使用 __in 进行查询。
    """

def filter_string(self) -> str:
    """
    用于PromQL条件生成

    根据 value 的长度和 fuzzy 标志，构建相应的查询字符串：
    如果 fuzzy 为 True => 'key=~"value1|value2|..."''
    如果只有一个值，构建简单的等式 => 'key=value'
    如果有多个值，构建正则表达式匹配 => 'key=~"^(value1|value2|...)$"''
    如果filter_dict有多个key => 'key1=value1, key2=value2'
    """
```

### 过滤器子类

| ClassName              | resource_type     | filter_field   |
|------------------------|-------------------|----------------|
| NamespaceFilter        | namespace         | namespace      |
| PodFilter              | pod               | pod_name       |
| WorkloadFilter         | workload          | workload       |
| ContainerFilter        | container         | container_name |
| DefaultContainerFilter | container_exclude | container_name |
| NodeFilter             | node              | node           |
| ClusterFilter          | bcs_cluster_id    | bcs_cluster_id |
| SpaceFilter            | bk_biz_id         | bk_biz_id      |
| IngressFilter          | ingress           | ingress        |
| ServiceFilter          | service           | service        |

### k8s.core.filters.register_filter(filter_cls)

一个装饰器
用于注册 [过滤器类 ResourceFilter](#过滤器子类)。

它接受一个过滤器类 `filter_cls:ResourceFilter` 作为参数，并将其 `resource_type` 属性和类本身存储在 [`filter_options`](#k8scorefiltersfilter_options) 字典中。这使得在需要时可以方便地查找和使用不同的过滤器。

### k8s.core.filters.load_resource_filter(resource_type: str, filter_value, fuzzy=False)

根据给定的资源类型、过滤值和模糊匹配标志来加载对应的资源过滤器

例如：当 `resource_type="pod"` 返回 `PodFilter()`

## 资源类定义

### k8s.core.meta.FilterCollection(object)

用于管理多个过滤条件，支持添加和移除[过滤器](#k8scorefiltersresourcefilterobject)。它可以用于构建复杂的查询

```python
class FilterCollection(object):
    """
    用于管理多个过滤条件，支持添加和移除过滤器。它可以用于构建复杂的查询
    过滤查询集合

    内部过滤条件是一个字典， 可以通过 add、remove 来增删过滤条件
    """
    def filter_queryset(self):
        """
        通过遍历 filters 中的每个过滤器对象，应用过滤条件，最终返回过滤后的 queryset
        """

    def transform_filter_dict(self, filter_obj) -> Dict:
        """
        将过滤器对象的过滤条件转换为适合ORM查询的格式
        """
        
    def filter_string(self, exclude="") -> str:
        """
        生成一个过滤条件的字符串。
        如果 exclude 参数指定，则跳过以该参数开头的过滤器。
        如果有多个 workload ID，则只取第一个进行查询。
        """
```

### k8s.core.meta.K8sResourceMeta(object)

资源元数据基类
定义了获取数据的来源有数据库和 prom 历史数据两个地方
根据不同的指标 `meta_prom_with_**` 通过构建 promql 查询语句来获取数据

```python
class K8sResourceMeta(object):
    """
    资源元数据基类
    """

    filter: FilterCollection = None
    resource_field = ""
    resource_class = None
    column_mapping = {}  # 数据库表字段映射
    only_fields = []  # 指定查询时只关注的字段。
    method = ""  # 聚合方法（如 sum、avg 等）。

    def __init__(self, bk_biz_id, bcs_cluster_id):
        """
        接收集群id 和 业务id
        设置默认过滤器 FilterCollection()
        初始化聚合间隔和方法
        """
    
    def setup_filter(self):
        """
        初始化过滤器，并添加初始过滤条件 bk_biz_id, bcs_cluster_id, container_exclude 
        """

    def set_agg_interval(self, start_time, end_time):
        """
        根据不同的聚合方法（如 count、sum 等）设置聚合查询的时间间隔。
        """
    
    def set_agg_method(self, method: Literal["max", "avg", "min", "sum", "count"] = "sum"):
        """
        设置聚合方法，并在方法为 count 时重置聚合间隔。
        """
    
    def get_form_meta(self):
        """
        资源数据获取方式
        
        通过ORM，从数据库获取
        """

    def get_from_promql(self, start_time, end_time, order_by="", page_size=20, method="sum"):
        """
        资源数据获取方式
        
        通过构建PromQL进行获取
        核心是通过 meta_prom_by_sort 生成对应指标的PromQL
        """
    def meta_prom_by_sort(self, order_by="", page_size=20) -> str:
        """
        调用 meta_prom_with_{order_by.strip("-")} 获取不同指标的PromQL
        并在PromQL最外层添加排序和查询数量设置
        """

    def meta_prom_with_xxx(self) -> str:
        """
        构建不同指标的PromQL
        """
```

### k8s 资源子类

| ClassName        | resource_field | resource_class | column_mapping                                               |
|------------------|----------------|----------------|--------------------------------------------------------------|
| K8sNodeMeta      |                |                |                                                              |
| K8sContainerMeta | container_name | BCSContainer   | {"workload_kind": "workload_type", "container_name": "name"} |
| K8sPodMeta       | pod_name       | BCSPod         | {"workload_kind": "workload_type", "pod_name": "name"}       |
| K8sWorkloadMeta  | workload_name  | BCSWorkload    | {"workload_kind": "type", "workload_name": "name"}           |
| K8sNamespaceMeta | namespace      | NameSpace      | {}                                                           |
| K8sIngressMeta   | ingress        | BCSIngress     | {"ingress": "name"}                                          |
| K8sServiceMeta   | service        | BCSService     | {"service": "name"}                                          |

### k8s.core.meta.load_resource_meta(resource_type,bk_biz_id,bcs_cluster_id)

根据给定的资源类型和其他参数加载对应[资源元信息类](#k8s-资源子类)的实例。

| resource_type  | ClassName        |
|----------------|------------------|
| node           | K8sNodeMeta      |
| container      | K8sContainerMeta |
| container_name | K8sContainerMeta |
| pod            | K8sPodMeta       |
| pod_name       | K8sPodMeta       |
| workload       | K8sWorkloadMeta  |
| namespace      | K8sNamespaceMeta |
| ingress        | K8sIngressMeta   |
| service        | K8sServiceMeta   |

e.g. 当  `resource_type = "container"`, 返回 `K8sContainerMeta(bk_biz_id, bcs_cluster_id)`

### k8s.core.meta.NetworkWithRelation

作为一个辅助类，用于网络场景，层级关联支持

```python
def label_join(self, filter_exclude=""):
    """
    聚合和链接 ingress 和 pod 相关的指标，计算出它们之间的关系并按特定标签进行聚合。
    """

def clean_metric_name(self, metric_name):
    """
    网络场景相关的指标名都是 `nw_` 开头的，需要将 `nw_` 去掉
    """
```
