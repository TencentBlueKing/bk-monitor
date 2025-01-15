/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

// 文档 相关的词条
export default {
  // 规范：仅首字母大写
  // 规范：中文精简
  /*
   #### 大段文本类
 - Description Text：描述文本，用于详细描述页面或模块的内容和功能，例如“该页面用于用户登录操作”、“该模块用于展示用户的订单信息”等。
 - Feedback Text：反馈文本，用于鼓励用户提供反馈或建议，例如“您对我们的产品有什么建议或意见，请告诉我们”等。
 - Docs Text：说明文档，主要是大段介绍功能，例如“指标策略指的是可以通过对时序数据进行数据查询和检测，更多请查看文档”
 */
  '自定义上报是一种最灵活和自由的方式上报数据。如果是通过HTTP上报，agent和插件都不需要安装；如果是通过SDK和命令行上报，依赖bkmonitorbeat采集器。':
    'Custom reporting is the most flexible and free way to report data. If it is reported through HTTP, neither agent nor plugin needs to be installed; if it is reported through SDK and command line, it depends on the bkmonitorbeat collector. ',
  '研发项目主要是满足日常的研发代码提交和构建， 在研发项目中提供了构建机监控、APM、自定义指标上报等功能。 研发项目与蓝盾项目直接建立绑定关系，新建研发项目会同步到蓝盾项目。':
    'The R&D project is mainly to meet the daily R&D code submission And construction, in the R&D project, it provides functions such as construction machine monitoring, APM, and custom metric reporting. The R&D project and the Blue Shield project directly establish a binding relationship, and the new R&D project will be synchronized to the Blue Shield project. ',
  '容器项目当前主要指 kubernetes，基于容器管理平台(TKEx-IEG), 接入容器项目后能够满足容器相关的监控和日志采集等。同时蓝盾的研发项目，可以直接开启容器项目能力':
    "The container project currently mainly refers to kubernetes, which is based on the container management platform (TKEx-IEG). After accessing the container project, it can meet container-related monitoring and log collection. At the same time, Blue Shield's research and development projects can directly open the container project capabilities",
  '容器项目当前主要指 kubernetes，基于容器管理平台(TKEx-IEG), 接入容器项目后能够满足容器相关的监控和日志采集等。同时蓝盾的研发项目，可以直接开启容器项目能力。':
    "The container project currently mainly refers to kubernetes, based on the container management platform (TKEx-IEG), which can satisfy container-related monitoring and log collection after accessing the container project. At the same time, Blue Shield's research and development projects can directly open the capacity of container projects. ",
  '整屏截取指截取整个仪表盘，按宽度800截取，方便快速创建一个仪表盘的邮件订阅，因为邮件有大小限制，为保证发送质量会进行长宽限制和切分。并且限制只有一个。':
    'Full-Screen capture refers to capture the entire dashboard, with a width of 800, which is convenient and quick to create a dashboard email subscription. Because emails have size restrictions, length and width restrictions and segmentation will be performed to ensure the quality of sending. And there is only one limit. ',
  '视图截图指从仪表盘中的视图中获取，可以将不同的仪表盘下的部分内容生成一份报表，而且格式简洁方便邮件的输出。':
    'View capture refers to getting from the view in the dashboard, you can Part of the content under different dashboards generates a report, and the format is concise and convenient for email output. ',
  支持数据的汇聚和实时查询: 'Support data aggregation and real-time querying',
  支持按拓扑节点动态变化进行采集: 'Support dynamic collection based on topology nodes',
  支持Prometheus的标准输出格式: 'Support standard output format of Prometheus',
  '支持多指标计算、兼容PromQL、各种函数、秒级监控等。':
    'Support multi-index calculation, compatible with PromQL, various functions, second-level monitoring, etc. . ',
  '支持JS正则匹配方式， 如子串前缀匹配go_，模糊匹配(.*?)_total':
    'Support JS regular matching methods, such as substring Prefix match go_, fuzzy match (.*?)_total',
  '支持HTTP(s)、TCP、UDP、ICMP协议': 'Support HTTP(s), TCP, UDP, ICMP protocols',
  支持快速进行数据查看和检验: 'Support for fast data viewing and verification',
  '（满意）- 应用响应时间低于或等于': '(Satisfied) - Application response time is less than or equal to',
  '（可容忍）- 应用响应时间大于 T，但同时小于或等于':
    ' (Tolerating) - the application response time is greater than T, but at the same time less than or equal to ',
  '（烦躁期）- 应用响应时间大于': '(Frustrated) - Application response time is greater than',
  '数据时间，精确到毫秒，非必需项': 'Data time, accurate to milliseconds, non-mandatory',
  '数据通道标识验证码，必需项': 'Data channel identification verification code, required',
  '数据通道标识，必需项': 'Data Channel Identifier, Required',
  '自定义维度，非必需项': 'Custom dimensions, not required',
  '维度(Dimension)': 'Dimension',
  '维度值, 字符串 ; 可选': 'Dimension Value, String; Optional',
  '维度名:主机字段名，如host_ip:bk_host_innerip': 'dimension name: Host field name, such as host_ip:bk_host_innerip',
  '维度名:实例标签名，如cluster_name:cluster_name':
    'Dimension name: instance tag name, such as cluster_name:cluster_name.',
  '维度（Dimension）': 'Dimension',
  'snmp trap 将默认搭建 snmp trap server 接收不同设备的发送的事件数据。默认端口为 162。注意选择对应的 snmp 版本, 本版本为 V2c。':
    'snmp trap will set up snmp trap server by default to receive event data sent by different devices. The default port is 162. Pay attention to select the corresponding snmp version, this version is V2c. ',
  'snmp trap 将默认搭建 snmp trap server 接收不同设备的发送的事件数据。默认端口为 162。注意选择对应的 snmp 版本, 本版本为 V3。':
    'snmp trap will set up snmp trap server by default to receive event data sent by different devices. The default port is 162. Pay attention to select the corresponding snmp version, this version is V3. ',
  'snmp trap 将默认搭建 snmp trap server 接收不同设备的发送的事件数据。默认端口为 162。注意选择对应的 snmp 版本,本版本为 V1。':
    'snmp trap will set up snmp trap server by default to receive event data sent by different devices. The default port is 162. Pay attention to select the corresponding snmp version, this version is V1. ',
  'trap服务启动时绑定的地址，默认为0.0.0.0，如果要指定网卡，需要使用CMDB变量来使用如：':
    'The address bound when the trap service starts, the default is 0.0.0.0, if you want to specify the network card, you need to use CMDB variables to use such as:',
  '第2步：前往仪表盘配置个性化视图': 'Step 2: Go to the dashboard to configure personalized views',
  '第二步：前往配置平台录入服务的完整信息':
    'Step 2: Go to the configuration platform to enter the complete information of the service.',
  '第1步：配置拨测节点': 'Step 1: Configure probe nodes',
  '第2步：创建拨测任务': 'Step 2: Create probe task',
  '第2步：查看主机列表': 'Step 2: View host list',
  '第一步：了解进程的配置方法': 'Step 1: Understand the configuration method of the process',
  Step需填写合法的整数值: 'Step needs to be filled with a valid integer value',
  '第{step}步， 共{total}步': 'Step {step}, total {total} steps',
  '第4步：开启主机基础进程端口告警': 'Step 4: Enable basic process port alarm for host',
  '第1步：创建对应的采集任务获取数据': 'Step 1: Create corresponding collection tasks to obtain data',
  '第3步：系统默认配置的全局告警策略': 'Step 3: Global alarm rule configured by default by the system',
  '第1步：给你的主机安装蓝鲸Agent': 'Step 1: Install BlueKing Agent on your host',
  '第三步：在主机监控页面查看服务进程状态': 'Step 3: Check the service process status on the host monitoring page',
  '第3步：配置监控策略，时刻保障服务正常运行':
    'Step 3: Configure the monitoring rule to ensure the normal operation of the service at all times',
  '汇聚是可以基于存储落地的数据按周期、维度（group by）、条件(where) 进行汇聚计算(MAX/AVG) 得到的结果再进行各种检测算法。所以汇聚至少有1个周期的等待，及时性会慢点，但功能强大。':
    'Aggregation is Various detection algorithms can be performed based on the results obtained by aggregate calculation (MAX/AVG) based on the stored data according to the cycle, dimension (group by), and condition (where). Therefore, there is at least one cycle of waiting for aggregation, and the timeliness will be slower, but the function is powerful. ',
  '1. 补充 headers，用于携带 token 信息。定义 Client 行为，由于 prometheus sdk 没有提供新增或者修改 Headers 的方法，所以需要实现 Do() interface，代码示例如下：':
    '1. Add headers to carry token information. Define the Client behavior, since the prometheus sdk does not provide a method to add or modify Headers, it is necessary to implement the Do() interface, the code example is as follows:',
  '1. 补充 headers，用于携带 token 信息。实现一个自定义的 handler。':
    '1. Add headers to carry token information. Implement a custom handler. ',
  '1、“脚本采集” 和 “自定义exporter”不支持直接迁移，请通过该页面进行 “导出” 操作，然后在 “监控配置” - “插件” 页面中手动导入':
    '1, "script acquisition" and "custom exporter" do not support direct migration, please perform the "export" operation through this page, and then Manually import on the "Monitoring Configuration" - "Plugins" page',
  '1） 来自日志平台的日志数据，通过ES Query语法查询的日志关键字告警能力。':
    '1) The log data from the log platform, and the log keyword alarm capability queried by ES Query syntax. ',
  '2. 填写上报端点，在 `push.New("$endpoint", name)` 里指定。然后需要将自定义的 client 传入到 `pusher.Client($bkClient{})` 里面。':
    '2. Fill in the reporting endpoint, in `push.New("$endpoint", name )` specified. Then you need to pass the custom client into `pusher.Client($bkClient{})`.',
  '2. 填写上报端点，在 `push_to_gateway("$endpoint", ...)` 里指定。然后将自定义的 handler 传入到函数里。':
    '2. Fill in the reporting endpoint and specify it in `push_to_gateway("$endpoint", ...)`. Then pass the custom handler into the function. ',
  '2、仅对迁移状态为“准备”或“失败”的配置项进行迁移，已经迁移成功的配置项将被忽略':
    '2. Only the migration status is "preparation" or "failed" configuration items to be migrated, configuration items that have been successfully migrated will be ignored',
  '2） 通过插件采集，在Client端进行日志关键字匹配产生事件进行上报。':
    '2) Through plugin collection, log keyword matching is performed on the client side to generate events for reporting. ',
  提供基于配置平台节点的动态扩缩容:
    'Provides dynamic capacity expansion and contraction based on configuration platform nodes',
  提供开箱即用的K8s服务组件的各种监控视角:
    'Provides a variety of monitoring perspectives for out-of-the-box K8s service components',
  提供本地拉取和均衡拉取的能力: 'Provides local pull and balanced pull capabilities',
  提供物理和容器环境的采集: 'Provides collection of physical and container environments',
  提供节点TOP和地图等图表: 'Provide charts such as node TOP and map',
  提供远程服务注册的方式: 'Provides a way to register services remotely',
  提供默认的主机和事件策略: 'Provide default host and event rules',
  '【服务拨测】作为比较贴近用户体验层的监控功能，能够模拟处于不同运营商网络的用户访问你的业务的质量，第一时间掌握用户端对产品业务体验的反馈。':
    "[Synthetic Monitoring] As a monitoring function that is relatively close to the user experience layer, it can simulate the quality of users accessing your business on different operator networks, and grasp the user's feedback on product service experience in the first place. ",
  '【服务监控】支持各类开源和自研的中间件、组件等服务接入，使用内置或自研的采集器捕获服务的数据，展示丰富的指标图表并配置完善的告警策略进行防护。':
    '[Service Monitoring] Support various open source and self-developed middleware, components and other service access, use built-in or self-developed collectors to capture service data, display rich metric charts and configure perfect alarm rules for protection. ',
  '【进程监控】进程是上承服务、下接OS的连接器，在关联分析模型中也起着重要的作用！蓝鲸监控基于配置平台服务模块对服务实例的管理，能够将服务的进程运行状态和相关服务实例更好的衔接监控起来。':
    '[Process Monitoring] A process is a connector that connects services upwards and OSes downwards, and also plays an important role in the correlation analysis model! Based on the management of service instances by the configuration platform service module, BlueKing Monitoring can better link and monitor the running status of service processes and related service instances. ',
  'BK-pull主要是解决那些只暴露了端口服务的数据源。 通过pull拉取目标的数据':
    'BK-pull mainly solves those data sources that only expose port services. Pull target data through pull',
  'Datadog的采集Agent，可以快速的转化为蓝鲸的插件。更多介绍':
    "Datadog's collection Agent can be quickly converted into a BK plugin. More introduction",
  'Exporter 类型插件参数默认值必须包含 ${host} 和 ${port} 变量模板':
    'Exporter type plugin parameter default value must contain ${host} and ${port} variable template',
  'Exporter是用于暴露第三方服务的metrics给Prometheus。是Prometheus中重要的一个组件。按蓝鲸监控插件的规范就可以将开源的Exporter插件变成蓝鲸监控的采集能力。 运行的Exporter是go的二进制程序，需要启动进程和占用端口':
    'Exporter is used to expose the metrics of third-party services to Prometheus. It is an important component in Prometheus. According to the specifications of the BKMonitor plugin, the open source Exporter plugin can be turned into the collection capability of BKMonitor. The running Exporter is a go binary program, which needs to start the process and occupy the port ',
  'Exporter的类型插件需要使用${host} ${port}来定义启动参数。 如 --listen=${host}:${port}':
    'Exporter type plugin needs to use ${ host} ${port} to define startup parameters. Such as --listen=${host}:${port}',
  'Prometheus Metrics 标准格式': 'Prometheus Metrics standard format',
  'Prometheus的Exporter采集组件，可以快速转化为蓝鲸的插件。 更多介绍':
    'The Exporter collection component of Prometheus can be quickly converted into a BK plugin. More introduction',
  'Script就是由用户自定义脚本进行Metrics采集。只要符合监控的标准格式就可以把数据采集上来。 支持的脚本有：':
    'Script is a user-defined script for Metrics collection. As long as it conforms to the standard format of monitoring, the data can be collected. Supported scripts are: ',
  'JMX可以采集任何开启了JMX服务端口的java进程的服务状态，通过jmx采集java进程的jvm信息，包括gc耗时、gc次数、gc吞吐、老年代使用率、新生代晋升大小、活跃线程数等信息':
    'JMX can collect the service status of any java process with the JMX service port enabled, and collect the jvm information of the java process through jmx, including gc time consumption, gc times, gc throughput, old generation usage rate, new generation promotion size, number of active threads, etc. Information',
  '对于开启了JMX的服务，可以方便进行配置制作自己的插件。更多介绍':
    'For services that have enabled JMX, you can easily configure and make your own plug-ins. More introduction',
  'Kubernetes Cluster概览，是以Kubernetes整体视角查看该业务下所有的集群的情况，目的是能快速了解整体情况并且快速进行问题的定位。':
    'Kubernetes Cluster Overview is to view all the clusters under the business from the overall perspective of Kubernetes. The purpose is to quickly understand the overall situation and quickly locate the problem. ',
  'Log主要是围绕日志相关的内容进行数据的采集，比如日志关键字等':
    'Log mainly collects data related to logs, such as log keywords.',
  '关联告警：可以基于告警事件/策略进行与或等，判断是否要再进行告警或者进行告警处理等。':
    'Associated alarms: based on alarm events/rules, you can perform AND or etc. to determine whether to issue an alarm or perform alarm processing. ',
  '什么是应用？': 'What is an application?',
  'APM即应用性能监控，通过Trace数据分析应用中各服务的运行情况，尤其是在微服务和云原生情况下非常依赖Trace数据的发现来解决接口级别的调用问题。':
    'APM is application performance monitoring. It uses Trace data to analyze the operation of each service in the application, especially in the case of microservices and cloud native, it is very dependent on the discovery of Trace data to solve the call problem at the interface level. ',
  '从技术方面来说应用是Trace数据的存储隔离，在同一个应用内的数据将进行统计和观测。更多请查看产品文档。':
    'From a technical point of view, the application is the storage isolation of Trace data, and the data in the same application will be counted and observed. For more information, please refer to the product documentation. ',
  'Apdex（Application Performance Index）是由 Apdex 联盟开发的用于评估应用性能的工业标准。Apdex 标准从用户的角度出发，将对应用响应时间的表现，转为用户对于应用性能的可量化范围为 0-1 的满意度评价。':
    "Apdex (Application Performance Index) is an industry standard developed by the Apdex Alliance for evaluating application performance. Starting from the user's point of view, the Apdex standard converts the performance of application response time into the user's satisfaction evaluation of application performance with a quantifiable range of 0-1. ",
  '业务屏蔽: 屏蔽告警中包含该业务的所有通知':
    'Business shielding: shield all notifications in the alarm that include this business.',
  '主机屏蔽: 屏蔽告警中包含该IP通知,包含对应的实例':
    'host shielding: shielding the IP notification in the shielding alarm, including the corresponding instance',
  '服务实例屏蔽: 屏蔽告警中包含该实例的通知':
    'Service instance shielding: shielding the notification of this instance in the shielding alarm',
  '节点屏蔽: 屏蔽告警中包含该节点下的所有IP和实例的通知':
    'node shielding: shielding the notification of this instance in the warning Notifications of all IPs and instances under this node',
  '屏蔽的是告警内容的这类事件，不仅仅当前的事件还包括后续屏蔽时间内产生的事件':
    'This type of event is blocked from the alarm content, not only the current event but also the event generated within the subsequent blocking time',
  '屏蔽的是告警内容的这类事件，不仅仅当前的事件还包括后续屏蔽时间内产生的事件。':
    'What is masked is the event of the alarm content, not only the current event but also the events generated within the subsequent masking time. ',
  '时间戳(ms)；可选': 'Timestamp (ms); Optional',
  '所有的Kubetnetes集群都是通过BCS服务进行托管，托管方式有两种： 第一种： 界面托管 第二种： 命令行托管':
    'All Kubetnetes clusters are hosted by BCS services. There are two hosting methods: The first one: interface hosting The second one: command line hosting',
  '内置的不够用？快速制作自己的插件！': 'Not enough built-in? Quickly create your own plugin!',
  '应用一般是拥有独立的站点，由多个Service共同组成，提供完整的产品功能，拥有独立的软件架构。 ':
    'Applications generally have independent sites, composed of multiple Services, providing a complete Product functions have an independent software architecture. ',
  '应用一般是拥有独立的站点，由多个Service共同组成，提供完整的产品功能，拥有独立的软件架构。 从技术方面来说应用是Trace数据的存储隔离，在同一个应用内的数据将进行统计和观测。更多请查看产品文档。':
    'The application generally has an independent site, which is composed of multiple services, provides complete product functions, and has an independent software architecture. From a technical point of view, the application is the storage isolation of Trace data, and the data in the same application will be counted and observed. For more information, please refer to the product documentation. ',
  '如何使用脚本进行服务监控？': 'How to use scripts for service monitoring?',
  '如何实现多实例采集？': 'How to implement multi-instance collection?',
  '如何对开源组件进行监控？': 'How to monitor open source components?',
  '基于Kubernetes的云原生场景，提供了围绕云平台本身及上的应用数据监控解决方案。兼容了Prometheus的使用并且解决了原本的一些短板问题。开启容器监控需要将Kubernetes接入到蓝鲸容器管理平台中。':
    'Based on the cloud-native scenario of Kubernetes, it provides a solution for monitoring application data around the cloud platform itself and on it. Compatible with the use of Prometheus and solved some of the original short board problems. To enable container monitoring, you need to connect Kubernetes to the BlueKing container management platform. ',
  '处理套餐说明： 通过告警策略可以触发处理套餐，处理套餐可以与周边系统打通完成复杂的功能，甚至是达到自愈的目的。':
    'Solution description: The alarm solution can be triggered through the alarm rule, and the alarm solution can be combined with Peripheral systems are connected to complete complex functions, and even achieve the purpose of self-healing. ',
  '处理经验可以与指标和维度进行绑定，可以追加多种处理经验方便经验的共享。':
    'processing experience can be bound with metrics and dimensions, and more can be added This kind of processing experience facilitates the sharing of experience. ',
  '处理经验是与指标绑定出现的，如果同一个指标有多种情况，可以追加多种处理经验方便经验的共享。':
    'Process Experience is bound to metrics. If there are multiple situations for the same metric, multiple processing experiences can be added to facilitate experience sharing. ',
  '大部分的处理套餐建议是可以做成可以反复执行并且风险可控的，常见的回调、发工单等甚至都不需要有额外的通知。':
    'Most of the alarm solution suggestions can be made to be executed repeatedly and the risks are controllable. Common callbacks, work orders, etc. do not even require additional notification. ',
  '套餐是业务运维设计制作的一套恢复故障的方案，可以复用于不同的告警，也可作为原子套餐用于制作组合套餐':
    'The solution is a set of failure recovery solutions designed and produced by business operation and maintenance , can be reused for different alarms, and can also be used as an atomic package to make a combined package',
  "在程序中直接获取环境变量中的变量如 os.getenv('PYTHONPATH')":
    "GET VARIABLES IN ENVIRONMENT VARIABLES DIRECTLY IN YOUR PROGRAM, SUCH AS OS.GETENV('PYTHONPATH')",
  "在程序中直接获取环境变量中的变量如 os.getenv(\\'PYTHONPATH\\')":
    "Get the variables in the environment variables directly in the program such as os.getenv(\\'PYTHONPATH\\')",
  '可以切换到{0}，根据条件筛选 Trace': 'Switch to {0} and filter Trace based on conditions',
  '可以制作插件、批量导出导入配置、可自定义数据采集':
    'Can create plugins, batch export and import configurations, and customize data collection.',
  '可以定义远程拉取的插件，如拉取pushgateway的数据。更多介绍':
    'You can define the plugin for remote pulling, such as pulling the data of pushgateway. More introduction',
  '可以批量导入插件,采集配置,策略配置等. 建议:导入的监控目标相同.':
    'Can import plug-ins, collection configurations, alert rules, etc. in batches. Suggestion: The imported monitoring targets are the same.',
  '可以批量导出采集配置,策略配置和相应的依赖. 注意:不包括监控目标.':
    'Can export collection configuration, rule and corresponding dependencies in batches. Note: monitoring targets are not included.',
  '可以改变查询方式避免单图数量过大。': 'The query method can be changed to avoid a large number of single graphs.',
  '可以通过制作各种监控插件满足数据采集的需求，该功能依赖服务器安装bkmonitorbeat采集器。':
    'You can meet the needs of data collection by making various monitoring plug-ins. This function relies on the server to install the bkmonitorbeat collector. ',
  '可批量导入, 导入策略请上传yaml配置，导入仪表盘请上传json配置':
    'can be imported in batches, please upload yaml configuration for import rule, and upload json configuration for dashboard import',
  '日志即通过日志关键字匹配的数量进行告警，主要有两种':
    'The log is used to alert based on the number of log keyword matches. There are two main types',
  '日志关键字插件，通过对于日志文件的关键匹配进行计数，并且存储最近一条原始日志内容。':
    'Log keyword plugin counts the key matches of log files , and store the latest original log content. ',
  '日志关键字：日志关键字能力有两种，日志平台基于ES存储判断的日志关键字和基于Agent端进行日志关键字匹配的事件。':
    'Log keyword: There are two kinds of log keyword capabilities, the log platform stores and judges the log keyword based on ES, and the event matches the log keyword based on the Agent side. ',
  'event_type 为非必须项，用于标记事件类型，默认为异常事件':
    'event_type is not required, used to mark the event type, the default is abnormal event',
  '蓝鲸监控 V3 使用了全新的数据链路，为了确保数据能够正常上报，需要更新以下主机的采集器与采集配置。点击右上角':
    'BlueKing Monitoring V3 uses a new data link, in order to ensure that the data can be reported normally, the collector and collection configuration of the following hosts need to be updated. Click the upper right corner',
  '蓝鲸监控3.2版本对大部分的功能进行了最新的设计，为了确保您获得平滑的使用体验，请通过本页面进行数据迁移的确认。':
    'BlueKing Monitoring 3.2 version has the latest design for most of the functions. In order to ensure you get a smooth experience, please confirm the data migration through this page . ',
  '蓝鲸监控也支持其他平台的主动对接方式，具体请联系平台管理员':
    'BlueKing Monitoring also supports the active docking method of other platforms. For details, please contact the platform administrator',
  '蓝鲸监控支持对市面上常见的类Unix和Windows操作系统进行监控（企业版支持AIX），包括OS的基础性能指标和系统事件告警。':
    'BlueKing Monitoring supports the monitoring of common Unix-like and Windows operating systems on the market (the enterprise version supports AIX), including OS basic performance metrics and system event alarms. ',
  '蓝鲸监控自有的JSON数据格式，创建完后有具体的格式说明':
    'BlueKing Monitor owns the JSON data format, and there is a specific format after creation Description',
  '各种监控场景能力，当前有主机监控、服务拨测、Kubernetes监控，还可以自定义观测场景':
    'Various monitoring scene capabilities, currently there are host monitoring, service dial test, Kubernetes monitoring, you can also customize observation scenarios',
  '指标（Metric）': 'Metric',
  '指标：指标数据即时序数据。数据来源有：监控采集，自定义上报，计算平台，日志平台。可以对数据进行多指标计算和相应的函数功能。':
    'Indicator: Indicator data in real-time order. Data sources include: monitoring collection, custom reporting, computing platform, and logging platform. Multiple indicator calculations and corresponding function functions can be performed on data.',
  '指的主机系统和硬件的层面. 如 CPU MEM 服务器硬件等.监控范围对应”CMDB-主机拓扑“,最小粒度为IP':
    ' refers to the level of the host system and hardware, such as CPU MEM server hardware, etc. The monitoring scope corresponds to "CMDB-host topology", and the minimum granularity is IP', // 明确这里 指的 前面是什么？
  '指的是运行在服务器操作系统之上的,如服务模块,组件等. 监控范围对应”CMDB-服务拓扑“,最小粒度为实例':
    'refers to running on the server operating system, such as service Modules, components, etc. The monitoring scope corresponds to "CMDB-service topology", the minimum granularity is instance', // 明确这里 指的 前面是什么？
  '没有部署BCS服务，所有被监控的Kubernetes集群需要先注册到BCS。请检查BCS服务是否已经部署，如果未部署请查看文档':
    'No BCS service is deployed, all are The monitored Kubernetes cluster needs to be registered with BCS first. Please check whether the BCS service has been deployed. If not, please refer to the document ',
  '注入的维度信息将追加进采集的指标数据中，基于配置平台的服务实例自定义标签及主机字段获取':
    'injected dimension information in Shell will be added to the collected metric data, and the custom label and service instance based on the configuration platform Host Field Acquisition',
  '插件类型是蓝鲸监控丰富支持采集能力的一种表现，插件的类型将越来越丰富。 往下具体介绍当前每种类型特点':
    'The plugin type is a manifestation of the rich support and collection capabilities of BlueKing Monitoring, and the types of plug-ins will become more and more abundant. The following describes the current characteristics of each type in detail ',
  '自定义是直接执行，不用解释器进行执行。 如 ./脚本':
    'Customization is executed directly, without the need for an interpreter. Such as, ./script.',
  'API频率限制 1000/min，单次上报Body最大为500KB':
    'API frequency limit is 1000/min, and the maximum single report body is 500KB.',
  '业务是最终服务的对象，业务可以理解是对外提供的一个站点、游戏、平台服务等。包含了各种资源，物理主机、容器集群、服务模块、业务程序、运营数据等等。所以也包含了不同的角色和不同的研发项目，站在业务的整体视角可以观测到方方面面。':
    'business is the ultimate service object, and business can be understood as a site, game, platform service, etc. provided to the outside world. Contains various resources, such as physical hosts, container clusters, service modules, business programs, operational data, and more. Therefore, it also includes different roles and different R&D projects, and all aspects can be observed from the overall perspective of the business. ',
  'prometheus sdk 库：https://prometheus.io/docs/instrumenting/clientlibs/':
    'prometheus sdk library: https://prometheus.io/docs/instrumenting/clientlibs/',
  '采集后的日志关键字数据可以在视图中查看变化趋势，也可以在策略里面配置告警规则。':
    'After the collected log keyword data, you can view the change trend in the view, and you can also configure alarm rules in the rule. ',
  '用户使用 prometheus 原始 SDK 上报即可，不过需要指定蓝鲸的上报端点（$host:$port）以及 HTTP Headers。':
    'Users can use the prometheus original SDK to report, but you need to specify the report endpoint ($host:$port) and HTTP of BlueKing Headers. ',
  '点击立即创建业务的拨测监控，化被动投诉为主动发现问题':
    'Click to create business dial test monitoring immediately, turn passive complaints into active problem discovery', // 中文有语法错误
  什么是指标和维度: 'What are metrics and dimensions',
  '检测算法支持：静态阈值、同环比、单指标异常智能检测、单指标预测能力。 ':
    'Detection algorithm support: static threshold, year-on-year comparison, single-index abnormal intelligent detection, single-index prediction ability. ',
  '根据官方提供的任务模板Excel，您可以快速批量导入多个拨测任务':
    'According to official information Task template Excel, you can quickly import multiple dial test tasks in batches',
  '服务拨测通过拨测节点向远程目标发送探测信息，来发现目标服务的状态情况。支持TCP HTTP(s) UDP ICMP。该功能依赖服务器安装bkmonitorbeat采集器。':
    'Service Dialing Test Send detection information to the remote target through the dial test node to discover the status of the target service. Support TCP HTTP(s) UDP ICMP. This function depends on the server to install the bkmonitorbeat collector. ',
  '自定义场景是除了平台自带的场景之外可以根据监控需求来自定义监控场景，平台提供了快速定义场景的能力，从数据源接入到数据可视化、关联功能联动都可以很快速的完成。':
    'In addition to the scenarios provided by the platform, you can customize monitoring scenarios based on monitoring requirements. The platform provides the ability to quickly define scenarios, including data source access, data visualization, and association functions.',
  '数据采集是通过下发监控插件或配置来实现数据采集，并且提供插件和配置的全生命周期管理，所以依赖服务器安装bkmonitorbeat采集器。':
    'Data collection is implemented by delivering monitoring plug-ins or configurations, and provides lifecycle management of plug-ins and configurations. Therefore, the bkmonitorbeat collector is installed on the server.',
  '精确匹配(支持AND、OR)：': 'Exact match (supports AND, OR):',
  '说明运行该插件的环境依赖，如运行在哪个版本上，只支持哪些版本的采集等':
    'Indicates the environment dependency of running this plugin, such as which version it is running on, Which versions of collection are only supported',
  '采集的数据为CMDB中服务模块下的服务实例数据，可以支持多实例的采集，如mysql redis。':
    'The collected data is the service instance data under the service module in CMDB, which can support the collection of multiple instances, such as mysql redis. ',
  '最常用的参数使用方式。如 --port 3306': 'The most commonly used parameter usage. Such as: --port 3306',
  插件制作快速入门: 'Plug-in making quick start',
  '说明采集的原理过程，可以更好的方便使用': 'Explain the collection process to facilitate better use.',
  "了解'快速接入'方法": "Learn about the 'Quick Access' Method",
  '5分钟快速上手“服务拨测”功能': "Get started with the 'Service Dialing' function in 5 minutes",
  '启用后将自动进行主机异常检测，也可在监控策略中配置此类告警':
    'After enabling it, the host anomaly detection will be performed automatically, and this can also be configured in the monitoring rule Type of alarm',
  '指标分类的定义影响指标检索的时候,如试图查看，仪表盘添加视图和添加监控策略时选择指标的分类。':
    'The definition of metric category affects metric retrieval. If you try to view it, Select the category of metrics when adding a view and adding a monitoring rule to the dashboard. ',
  '当前没有发现任何一个Kubernetes Cluster ，添加Cluster成功后，会自动的采集集群内的指标和事件数据，包含集群中所有的对象 Namespace Service Pod Deamset Deploymente Node 等，提供立体的监控数据。':
    'nothing found yet Any Kubernetes Cluster, after the cluster is successfully added, will automatically collect the metrics and event data in the cluster, including all objects in the cluster, such as Namespace Service Pod Deamset Deploymente Node, etc., to provide three-dimensional monitoring data. ',
  '兼容serviceMonitor、podMonitor的使用': 'Compatible with serviceMonitor and podMonitor',
  ' 根据应用的数据量情况进行设置，如果应用的trace数据量非常大，不仅影响程序的输出、网络的消耗，也需要更大的集群资源成本。 在这种情况下会考虑进行采集，注意错误的Span默认是会被采集不会被采样。':
    ' The amount is very large, which not only affects the output of the program and the consumption of the network, but also requires a greater cost of cluster resources. In this case, collection will be considered. Note that the wrong span will be collected but not sampled by default. ',
  '"单位可选类型: {unitStr}\n分组分隔方式(仅;分隔). \n导入时-表示不更新. 空单元格表示置空"':
    '"Unit Optional type: {unitStr}\n Group separation mode (only; Delimited). \n When imported - indicates no update. Empty cell indicates null"',
  'Trap服务端口： 是trap接收的端口，默认为 162': 'Trap service port: the port that trap receives, default is 162.',
  'Yaml配置文件：是通过命令行工具将mib文件转换的yaml配置文件。':
    ' Yaml configuration file: It is a yaml configuration file converted from a mib file through a command line tool. ',
  '提供了Events、Log、Metrics的采集方案': 'The collection scheme of Events, Log and Metrics is provided',
  '监控数据采集是通过下发监控插件来实现数据采集的全生命周期管理，该功能依赖服务器安装bkmonitorbeat采集器':
    'Monitoring data collection is to realize the whole life cycle management of data collection by issuing monitoring plug-ins. This function relies on the server to install bkmonitorbeat collector',
  '指标数据即时序数据。数据来源有：蓝鲸监控采集，自定义上报，计算平台，日志平台。':
    'metric data is sequence data. Data sources include: BlueKing monitoring and collection, custom reporting, computing platform, and log platform. ',
  '拨测是主动探测应用可用性的监控方式，通过拨测节点对目标进行周期性探测，通过可用性和响应时间来度量目标的状态。帮助业务主动发现问题和提升用户体验。':
    'Dial test is a monitoring method that actively detects the availability of applications, periodically probes the target through the dial test node, and measures the status of the target through availability and response time. Help businesses proactively identify problems and improve user experience.',
  '通过应用拓扑图，可以了解服务之间调用的关系和出现问题的节点':
    'By applying a topology map, you can understand the relationship of calls between services and the nodes that have problem',
  采集方式介绍: 'Introduction to collection method',
  采集的指标丰富多达100个指标和8种系统事件:
    'The collected metrics are enriched with up to 100 metrics and 8 system events',
  不同云区域Proxy信息: 'Proxy information in different BK-Network Area',
  不同云区域上报端点信息: 'Report endpoint information in different BK-Network Area',
  'BK-PULL插件': 'BK-PULL Plugin',
  '采集上来的数据可以满足跨集群使用满足告警策略和视图查看。还可以与同边系统进行联动实现自愈的目的，同样也可以通过智能异常检测等更有效的发现问题，甚至在计算平台中进行二次的计算和处理。':
    'The collected data can meet the cross-cluster use and meet the alarm rule and view view. It can also be linked with the same side system to achieve the purpose of self-healing. It can also find problems more effectively through intelligent anomaly detection, and even perform secondary calculation and processing on the computing platform. ',
  '采集器将定期访问 http://127.0.0.1/server-status 以获取Apache的指标数据':
    "collector will visit http://127.0.0.1/server-status regularly to obtain Apache's metrics Data",
  '基于参数传递的顺序进行变量的获取,由添加参数的顺序决定,如Shell中常见的echo $1':
    'Acquisition of variables is based on the order of parameter passing, which is determined by the order of adding parameters. Such as, the common echo $1',
  参数的填写也可以使用CMDB变量: 'CMDB variables can also be used to fill in parameters',
  '运行该插件需要进行哪些配置。如Apache的status的设置':
    "what configurations are required to run the plugin. Such as, Apache's status setting",
  '通过调用次数、耗时、错误率等指标可以了解服务本身的运行状况':
    'Metrics such as the number of calls, time taken, and error rate give you an idea of the health of the service itself',
  '采集的数据为主机操作系统相关的，如CPU NET。':
    'The collected data is related to the host operating system, such as CPU and NET.',
  'recovery:恢复事件，abnormal:异常事件': 'Recovery: Recovery event, Abnormal: Abnormal event',
  '就会得到关键字并和 moudle=de4x5 匹配的次数。':
    'The number of matches with the keyword and moudle=de4x5 will be obtained.',
  '由用户自定义脚本实现数据采集，标准输出监控的数据格式即可。 更多介绍':
    'Data collection is realized by user-defined scripts, and the standard output monitoring data format is sufficient. More introduction',
  关键字规则配置方法: 'Method for Configuring Keyword Rules',
  'Datadog是一个一站式云端性能监控平台，拥有丰富的采集能力。蓝鲸监控兼容了Datadog的采集能力，当前用户不能自定义插件。因为Datadog是由python编写，需要有python可运行环境，不需要占用端口':
    "Datadog is a one-stop cloud performance monitoring platform with rich collection capabilities. BlueKing Monitoring is compatible with Datadog's collection capabilities, and currently users cannot customize plug-ins. Because Datadog is written by python, it needs a python executable environment and does not need to occupy a port",
  '事件内容，必需项': 'Event content, required',
  '指标，必需项': 'Metrics, Required',
  '来源标识如IP，必需项': 'Source identification such as IP, required',
  '单个 trace 中 30 分钟没有 span 上报，会自动结束；单个 trace 最大时长 1 天':
    'If no span is reported for 30 minutes in a single trace, it will end automatically; the maximum duration of a single trace is 1 day',
  对非必采的部分按TraceID进行采样: 'Sampling non-essential parts according to TraceID',
  服务实例数: 'Number of service instances',
  无匹配数据: 'No matching data',
  时间段重复了: 'Time period repeated',
  '该服务所在 APM 应用未开启 指标 功能': 'The APM application of this service has not enabled the Metrics function',
  '暂未开启 指标 功能': 'The Metrics function has not been enabled yet',
  '已开启 指标 功能，请参考接入指引进行数据上报':
    'The Metrics function has been enabled, please refer to the access guide for data reporting',
  '暂无 指标 数据': 'No Metrics data',
};
