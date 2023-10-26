代码一：

- 主要目录：

    alarm_backends/service/access/data

- 主要代码：alarm_backends/service/access/data/token.py

- 描述：
    access模块令牌桶：对数据拉取耗时超预期的数据源进行降级。
    
- 实现方案：
    利用redis的key过期特性及decr的原子性，实现的滑动窗口令牌桶模型。
    
- 背景：
    access模块根据用户配置的监控策略，将数据源进行分组。每个strategy_group_key代表一个数据拉取任务。
    后台将周期发起数据拉起任务并给到celery worker执行。
    access下的时序数据源包含：监控自采数据（influxdb，ES），日志平台（ES），数据平台（tspider）。
    当其中某类数据源底层存储出现问题导致查询耗时过长时，会影响整个集群的worker的处理速度，
    导致任务队列堵塞，影响其他数据源的数据获取。同时没有降级能力，将加大问题存储的负载，出现雪崩效应。
    
- 实现：
    每个数据拉取任务都公平的被分配一定数量的token（值可配置）其中一个token表示1秒的时间，默认为每10分钟30s。
    token被记录在一个有着初始10分钟过期的key里。当token余额为正时，才能开启数据拉取任务，拉取结束后扣除对应拉取耗时的token。
    当token余额为负数时，后续在key有效期内，将被禁止再次执行拉取任务，同时追加对应比例的key过期时间补偿。
    例如：当前设置10分钟30s的滑动窗口。当token余额为-10的时候，将追加 600 / 30 * 10 = 200s 的过期时间。
    
- 管理工具：
    alarm_backends/management/commands/token.py
    展示当前被降级的策略、表名及被限制时间


=======

代码二：

- 主要目录：

    alarm_backends/core/storage

- 主要代码：alarm_backends/core/storage/redis_cluster.py
- 
- 背景描述：
    蓝鲸监控后台核心功能概括为：数据拉取，异常检测，告警事件生命周期管理。Redis在后台是一个核心依赖组件。每条策略在数据流处理中，均需要依赖redis缓存原始数据，异常检测结果及对应告警事件信息。随着集群接入业务量级的增大，需要考虑redis集群的水平扩展能力。
    
- 实现方案：
    1. 【未选择】gcs redis集群模式：基于TwemProxy的分片模式。
    2. 【未选择】redis cluster模式： 运维成本高，同时对客户端改造成本较高。
    3. 最终方案，基于业务特性，实现客户端分片，基于策略id进行分片路由。 

- 管理工具：
    alarm_backends/management/commands/cacherouter.py
    集群节点信息配置、策略路由配置及路由信息获取

=======
代码三：

- 主要目录：
  - core/drf_resource
  - api/monitor
  - api/metadata

- 主要代码：core/drf_resource/contrib/nested_api.py

- 代码描述：API嵌套调用
  在监控后台API服务中，除了提供底层api服务外，还暴露了SaaS的部分业务逻辑接口。这些逻辑接口完全复用自SaaS。SaaS逻辑中，有对监控后台的API调用，因此在后台API模式下，可能会出现循环调用的问题。基于APIResource进行的再次封装，用以解决循环调用的问题。

- drf_resource模块背景说明（整体框架实现在2019年底）:
  - 蓝鲸监控平台项目SaaS和后台API模块，基于drf，参考ModelView的设计，实现基于业务逻辑单元的ViewSet封装。基于drf_resource封装后的逻辑，配合自动发现能力，可以让代码逻辑实现基于Resource原子的组装和复用。
  - 主要定义：
    - Resource： 一段业务逻辑的资源定义。Resource下可以定义输入及输出对应的serializers(core/drf_resource/base.py)
    - ResourceViewSet： 基于drf的GenericAPIView封装，执行Resource

- 目录说明：
  - drf_resource/contrib目录：
    基于Resource类的功能扩展。(core/drf_resource/contrib)
      - CacheResource：附带缓存能力的Resource
      - APIResource：业务逻辑为请求蓝鲸esb或apigateway的Resource
  - api目录：
    针对drf_resource的应用，定义各模块api接口，供项目内调用
      - api/monitor: 定义监控平台SaaS侧逻辑接口
      - api/metadata: 定义监控平台数据链路侧接口