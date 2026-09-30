# SNMP 插件说明文档

## 一、总体介绍

### 什么是SNMP？

SNMP（Simple Network Management Protocol，简单网络管理协议）是用于网络设备管理的标准协议。它可以监控和管理网络设备（如路由器、交换机、服务器等）的性能、配置和状态信息。

### SNMP在蓝鲸监控平台中的作用

蓝鲸监控平台通过SNMP插件实现对网络设备的全面监控，提供两种不同的监控方式：

1. **`SNMP` 主动采集插件**：主动轮询网络设备获取性能指标。
2. **`SNMP Trap` 被动接收插件**：接收网络设备主动发送的告警事件。

### SNMP协议基础概念

#### OID（对象标识符）

OID是SNMP中用于唯一标识管理对象的层次化标识符，每个网络设备的每个指标都有对应的OID，格式是一段数字(如1.3.6.1.2.1.2.2.1.10)
，使用snmp协议并通过oid访问设备，即可获取对应oid下的设备信息，如启动时间等。

#### MIB库

MIB（Management Information Base，管理信息库）是SNMP协议的核心组成部分，它是各设备官方提供的设备oid描述文件，可以根据该文件得到能够用于监控的oid以及oid的内容描述信息。

#### generator

generator
是生成snmp.yml工具，通过使用该工具，能够解析MIB库，并将对应的指标组合成snmp.yml文件([使用文档](https://github.com/prometheus/snmp_exporter/tree/master/generator))

#### generator.yml

generator.yml 是generator的配置文件，用户需要在该配置文件中告诉generator需要采集哪些oid。

#### snmp.yml

snmp.yml 是snmp和snmp trap的yaml配置文件，由generator自动生成，也可根据一定规则手动写入，其内部包含所有将被采集的snmp指标信息。
- snmp插件是在配置插件时需要上传snmp.yml文件。
- snmp trap插件在监控平台是内置插件，在创建snmp trap 插件采集任务时，需要上传snmp.yml文件。

#### TRAP

snmp trap是一种事件类的snmp信息，当对应设备发生一些事件(如网卡离线)时，会向事先配置好的目标发送snmp trap报文。

#### SNMP版本

- **v1**：是最简单的snmp采集，基于团体名（Community）进行简单认证。
- **v2/v2c**：现阶段最普遍使用的snmp采集，基于团体名（Community）进行简单认证。
- **v3**：最新的snmp版本，认证相对复杂，增加了一系列安全参数，适合对安全性要求高的环境。
- 基于团体名（Community）认证说明：`snmp`主动采集使用团体名作为采集设备的认证，所以是必填的；`snmptrap`
  使用团体名作为trap数据的过滤措施，所以可以不填，不填时视为接收所有团体的trap,多个需要过滤的团体名可用逗号分隔。
- SNMP版本兼容说明：`snmp`主动采集，各插件只能采集自己版本的设备，如snmp v2版本插件只能采集snmp v2协议的设备；`snmp trap`
  采集，可以向下兼容，如snmp v3版本的任务，向其中发送snmp v2/v1的trap数据，也同样能够接收并告警,对应兼容效果，snmp
  v3的trap同样提供了团体名字段。

## 二、SNMP 插件

### 什么是SNMP主动采集？

SNMP主动采集插件是监控平台下发一个snmp_exporter(snmp插件包里的二进制程序),
snmp_exporter程序通过snmp协议远程主动向网络设备发起SNMP请求，定期获取设备性能指标并进行上报的监控方式。这种方式适用于需要持续监控设备运行状态的场景。

**SNMP主动采集流程：**

1. 采集触发：bkmonitorbeat按周期向snmp_exporter发起HTTP请求；
2. 协议转换：snmp_exporter将HTTP请求转换为SNMP协议请求；
3. 设备通信获取数据：snmp_exporter通过SNMP协议与目标设备通信，并从设备获取性能指标数据；
4. 数据处理：snmp_exporter将SNMP数据转换为标准格式；
5. 数据返回：通过HTTP响应将处理后的数据返回给bkmonitorbeat；
6. 平台上报数据：bkmonitorbeat将数据上报到监控平台进行存储和展示。

**snmp_exporter二进制程序的核心作用：**

- HTTP代理服务：提供标准的HTTP接口供bkmonitorbeat调用。
- SNMP协议转换器：在HTTP协议和SNMP协议之间进行转换。
- 配置执行器：根据snmp.yaml配置执行具体的SNMP采集逻辑。
- 数据处理器：对原始SNMP数据进行清洗，转换为标准格式。

**bkmonitorbeat的角色：**

- 采集调度器：按配置周期触发采集任务。
- HTTP客户端：向snmp_exporter发起采集请求。
- 数据中转站：接收处理后的数据并上报到监控平台。

**核心配置文件：**
跟插件包一起下发到监控Agent主机（运行bkmonitorbeat的主机）
- **snmp.yaml**：SNMP指标定义配置文件，定义需要采集的具体指标和OID映射关系，创建 snmp 主动采集插件时需要上传这个文件。
- `bkmonitorbeat_debug.yaml.tpl`：调试配置
- `config.yaml.tpl`：SNMP采集器主配置，包含认证参数和基础配置
- `env.yaml.tpl`：环境变量配置，包含日志路径和监听地址
- `meta.yaml`：插件元数据配置

### snmp.yaml配置文件详解

**snmp.yaml是SNMP插件的核心配置文件**，它定义了：

1. 指标定义：需要采集的SNMP指标列表
2. OID映射：SNMP OID与监控平台指标的对应关系
3. 维度提取：从SNMP响应中提取的维度信息
4. 指标分组：按功能或设备类型对指标进行分组管理

#### snmp插件配置文件snmp.yaml字段详细说明

**分组配置字段：**

- 分组名称（如`if_mib`、`system_mib`）：
- 作用：按功能或设备类型对指标进行分组管理
- 说明：每个分组对应一个MIB模块或功能类别，便于指标分类和维护
- 命名建议：使用MIB模块名称或功能描述性名称

**walk字段：**

- 作用：定义SNMP walk操作的起始OID
- 说明：用于批量获取某个OID子树下的所有指标，提高采集效率
- 格式：字符串数组，每个元素是一个OID字符串
- 示例：`walk: ["1.3.6.1.2.1.2.2.1.1"]`

**metrics字段（指标列表）：**

- 作用：定义需要采集的具体SNMP指标
- 说明：每个metric对象描述一个SNMP指标及其属性
- 格式：对象数组，每个对象包含完整的指标配置

**指标配置字段：**

- name字段：
    - 作用：指标在监控平台中的显示名称
    - 说明：用于在监控界面中标识指标，建议使用有意义的英文名称
    - 要求：必须唯一，不能包含特殊字符

- oid字段：
    - 作用：SNMP对象的唯一标识符
    - 说明：标准的SNMP OID格式，如`1.3.6.1.2.1.1.3.0`
    - 注意：必须以点号开头，遵循SNMP OID规范

- type字段：
    - 作用：定义指标的数据类型
    - 说明：正确设置类型有助于数据聚合和告警规则配置

- indexes字段：
    - 作用：定义从SNMP响应中提取的维度信息
    - 格式：对象数组，每个对象包含维度配置
    - 子字段：
        - `labelname`：维度名称，将作为监控平台的维度字段
        - `type`：维度数据类型，如`integer`、`string`等
    - 示例：接口索引`ifIndex`作为维度，用于区分不同接口

- help字段：
    - 作用：指标的描述信息
    - 说明：用于在监控界面中显示指标的详细说明
    - 要求：建议使用中文描述，便于理解指标含义

**其他可选字段：**

- lookups字段：
    - 作用：定义OID查找映射关系，将原始SNMP OID值转换为更有意义的名称或标签
    - 配置结构：
        - `labelname`：映射后的维度名称
        - `labels`：基于哪个维度进行查找（通常是indexes中的维度）
        - `oid`：查找表的OID
        - `type`：查找结果的数据类型
    - 工作原理：使用indexes维度值作为索引，查询指定的OID查找表，将结果作为新的维度添加到监控数据中
    - 适用场景：状态码映射、设备类型转换、错误码解释等需要将数值转换为可读名称的场景
    - 示例说明：将接口索引(ifIndex)映射为接口描述(ifDescr)，让监控数据更直观易读

- auth字段：
    - 作用：SNMP认证配置（v3版本）
    - 说明：包含用户名、密码、认证协议等安全参数
    - 注意：通常在分组级别配置，影响该分组下所有指标

**snmp.yaml配置示例：**

```yaml
# 接口监控分组
if_mib:                    
  walk:                    # walk操作配置
    - 1.3.6.1.2.1.2.2.1.1  # 从接口索引开始walk
  metrics:                 # 指标列表
    - name: ifInOctets     # 指标名称
      oid: 1.3.6.1.2.1.2.2.1.10  # SNMP OID
      type: counter        # 指标类型
      indexes:             # 维度提取配置
        - labelname: ifIndex  # 维度名称：接口索引
          type: integer    # 维度类型：整数
      help: "接口输入字节数统计"  # 指标描述

# 系统信息分组 
system_mib:
  metrics:
    - name: ifOperStatus   
      oid: 1.3.6.1.2.1.2.2.1.8
      type: gauge
      indexes:
        - labelname: ifIndex  
          type: integer
      lookups:              # OID查找映射配置
        - labelname: ifDescr  # 映射后的维度名称
          labels:
            - ifIndex       # 基于ifIndex维度进行查找
          oid: 1.3.6.1.2.1.2.2.1.2  # 查找表的OID（接口描述OID）
          type: DisplayString  # 查找结果的数据类型
      help: "接口操作状态（1=up, 2=down, 3=testing, 4=unknown, 5=dormant, 6=notPresent, 7=lowerLayerDown）"
```

**lookups字段工作流程说明：**

1. 基础数据采集：首先采集`ifOperStatus`指标值和`ifIndex`维度值
2. 查找映射：使用`ifIndex`的值作为索引，查询`1.3.6.1.2.1.2.2.1.2`对应的查找表
3. 维度生成：将查询结果作为新的维度`ifDescr`添加到监控数据中

**实际效果示例：**

- 原始数据：`ifIndex=1, ifOperStatus=1`
- 通过lookups映射后：`ifIndex=1, ifDescr="GigabitEthernet0/1", ifOperStatus=1`
- 最终监控数据更直观，显示接口名称(即GigabitEthernet0/1)而非索引编号(即1)

## 三、SNMP Trap 插件

### 什么是 SNMP Trap 插件？

SNMP Trap 插件是蓝鲸监控平台的内置插件，用于监控网络设备通过SNMP协议发送的Trap事件。
与传统的SNMP轮询采集不同，SNMP Trap采用事件驱动模式，当网络设备发生异常或状态变化时主动上报事件, 然后 SNMP Trap 插件处理SNMP
Trap消息，并生成相应的监控数据。

**核心特性**

- 事件驱动：被动接收设备主动上报的事件，无需轮询
- 实时性强：事件发生时立即上报，响应速度快
- 资源消耗低：相比轮询模式，对设备和网络资源消耗更小
- 内置插件：无需生成插件包部署，系统初始化时自动创建，用户无需手动创建，配置即用
    - 通过数据库迁移脚本在系统部署时自动创建3个版本插件
        - `snmp_v1`：支持SNMP v1协议
        - `snmp_v2c`：支持SNMP v2c协议
        - `snmp_v3`：支持SNMP v3协议

**SNMP Trap被动采集流程：**

1. 设备事件触发：网络设备（路由器、交换机、服务器等）发生异常或状态变化时，主动生成SNMP Trap事件；
2. Trap事件发送：设备通过SNMP协议将Trap事件发送到监控平台的指定端口（默认162）；
3. 监听服务接收：采集器bkmonitorbeat采集器的SNMP Trap监听服务在配置的端口接收Trap数据包；
4. 协议版本识别：采集器bkmonitorbeat根据SNMP报文头识别协议版本（v1/v2c/v3），并进行相应的认证验证；
5. 数据包解析：采集器bkmonitorbeat的SNMP Trap监听服务解析Trap报文内容，提取关键信息：

- 企业OID（Enterprise）：标识设备厂商和类型
- 通用Trap类型（Generic Trap）：标准事件分类（冷启动、链路故障等）
- 特定Trap代码（Specific Trap）：厂商自定义事件代码
- 变量绑定（VarBinds）：事件相关的具体参数值

6. 事件数据转换：采集器bkmonitorbeat将SNMP Trap原始数据转换为标准监控指标格式：

- 提取OID作为指标标识
- 封装标准维度信息（协议版本、团体名、设备地址等）
- 处理时间戳和事件计数

7. 数据上报平台：采集器bkmonitorbeat将处理后的监控指标数据上报到监控平台进行存储和展示。

**与SNMP主动采集的对比**

| 特性   | SNMP主动采集 | SNMP Trap被动采集 |
|------|----------|---------------|
| 采集模式 | 轮询       | 事件驱动          |
| 触发方式 | 采集器定时请求  | 设备主动上报        |
| 实时性  | 依赖采集周期   | 实时响应          |
| 资源消耗 | 采集器主动消耗  | 设备事件触发消耗      |
| 适用场景 | 性能指标监控   | 异常事件监控        |

**核心配置文件：**

snmp_trap.yaml：SNMP Trap插件的配置文件，定义需要采集的具体指标和OID映射关系，创建snmp trap 插件采集任务时需要上传这个文件。

### SNMP Trap插件配置文件snmp.yaml详解
**snmp.yaml是SNMP Trap插件的核心配置文件**，它定义了：
1. 事件指标定义：需要监控的SNMP Trap事件指标
2. OID映射：SNMP Trap OID与监控平台指标的对应关系
3. 维度提取：从Trap报文中提取的维度信息
4. 数据处理：特殊OID的处理方式和编码配置

#### snmp Trap插件配置文件snmp.yaml字段详细说明

**配置文件结构概览**

```yaml
default:
  metrics: []                    # 指标定义列表
  report_oid_dimensions: []      # 维度上报配置
  raw_byte_oids: []              # 原始字节处理配置
  encode: "utf-8"                # 编码格式
  hide_agent_port: true          # 代理端口隐藏
```

**metrics字段（指标列表）**

- 作用：定义需要监控的SNMP Trap事件指标
- 格式：对象数组，每个对象包含完整的指标配置
- 指标配置字段详解：
  - name字段: 指标在监控平台中的显示名称, 用于在监控界面中标识Trap事件类型，必须唯一，不能包含特殊字符
  - oid字段: SNMP Trap事件的唯一标识符, 标准的SNMP OID格式，标识特定的Trap事件类型
  - type字段: 指标的数据类型
  - help字段: 指标的描述信息

**report_oid_dimensions字段**
- 作用：定义需要作为维度上报的OID列表
- 说明：这些OID的值将作为维度信息附加到监控数据中，便于数据分类和筛选
- 格式：字符串数组，每个元素是一个OID字符串

**raw_byte_oids字段**

- 作用：定义需要以原始字节形式处理的OID列表
- 说明：这些OID的值不会进行常规编码转换，而是直接以字节数组形式处理
- 格式：字符串数组，每个元素是一个OID字符串
- 适用场景：
  - 二进制数据：MAC地址、IP地址等网络地址信息
  - 特殊编码数据：非标准编码或厂商自定义格式
  - 序列号信息：设备序列号、硬件标识码
  - 加密数据：安全相关的加密信息
- 处理流程：
  - 识别OID是否在raw_byte_oids列表中
  - 对于匹配的OID，直接获取原始字节数据
  - 将原始字节数据转换为Base64字符串进行传输
  - 监控平台接收后按需解析原始数据

**encode字段**
- 作用：定义SNMP Trap事件中的数据编码格式
- 说明：默认为UTF-8编码，如果需要处理其他编码格式的数据，请根据实际情况进行配置

**hide_agent_port字段**
- 作用：定义是否隐藏代理端口信息
- 说明：默认为true，表示隐藏代理端口信息，即在监控数据中不显示代理端口信息

**snmp.yaml配置示例：**

```yaml
default:
  metrics:
    - name: "sysUpTime"
      oid: "1.3.6.1.2.1.1.3.0"
      type: "GAUGE"
      help: "系统运行时间"
    - name: "ifPhysAddress"
      oid: "1.3.6.1.2.1.2.2.1.6"
      type: "OTHER"
      help: "接口物理地址（MAC地址）"
    - name: "sysContact"
      oid: "1.3.6.1.2.1.1.4.0"
      type: "OTHER"
      help: "系统联系人信息"
  
  report_oid_dimensions: 
    - "1.3.6.1.2.1.1.2.0"
    - "1.3.6.1.2.1.1.5.0"
  
  # 需要原始字节处理的OID
  raw_byte_oids: 
    - "1.3.6.1.2.1.2.2.1.6"      # ifPhysAddress - MAC地址（二进制格式）
    - "1.3.6.1.4.1.9.9.276.1.1.1.1.11"  # 设备序列号（可能包含特殊字符）
    - "1.3.6.1.4.1.2011.5.25.31.1.1.1.1.5"  # 设备硬件信息
  
  encode: "utf-8"
  hide_agent_port: true
```
