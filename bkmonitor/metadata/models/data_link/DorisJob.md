# DataLink 中的 DorisJob 管理方案

**评审稿。** 一个 DataLink 可以挂载多个 Doris 周期 INSERT Job。metadata 保存任务定义和链路归属，Doris FE 负责调度、执行及保存执行记录。第一阶段评审配置模型和管理接口。APM 预计算用于检验设计能否表达实际需求，接入策略、业务 SQL、建表与上线另行交付。

## 组件放在哪里

现有 `DataLink.compose_configs()` 组装 BKBase 资源，`apply_data_link()` 负责下发和清理。现有组件基类的 `delete_config()` 面向 BKBase。建议在同一个 `metadata.models.data_link` 包增加独立 Django 模型 `DorisJobConfig`，通过外键直接关联 DataLink。在链路详情层把 Job 摘要与已有组件并列展示，返回类型标识 `DorisJob`。写操作从 Job 自身的管理入口进入。

| 入口或场景 | 对 DorisJob 的处理 |
| --- | --- |
| 查看链路配置 | 按链路取本地 Job 列表。无需连接 FE 即可展示名称、集群、数据库和周期 |
| 链路重新 apply、BKBase 资源同步、回收缺失组件 | 保持现有流程。Job 不注册到 BKBase kind 映射、策略组件清理列表或 DataBus sinks |
| 停用链路 | 现有 `delete_data_link()` 仅停止 DataBus 并保留关联。建议维持该语义，由管理员按业务窗口单独暂停 Job，允许处理已入库的数据 |
| 物理删除链路 | 有关联 Job 时由外键 PROTECT 阻止删除，先解除纳管或显式删除 Job |
| 一个 Job 汇总多个来源 | 选负责该任务生命周期的链路作为归属；SQL 可读取多张物理表。首期只表达一个归属，避免多个链路分别启停同一任务 |

## 建议字段

| 字段 | Django 类型 / 初值 | 用途及变更语义 |
| --- | --- | --- |
| id | BigAutoField | metadata 的组件 ID，管理接口使用此 ID |
| data_link | ForeignKey(DataLink, PROTECT)，related_name=doris_jobs | 指向主键 data_link_name。租户、namespace、DataID 均从所属链路读取 |
| cluster_id | IntegerField，必填 | 使用现有 ClusterInfo.cluster_id，按链路租户及 TYPE_DORIS 解析连接。凭据由 ClusterInfo 提供 |
| database | CharField(255)，必填 | 创建 Job 时使用的 Doris 数据库上下文。任务 SQL 建议显式写出源表、目标表的库名 |
| name | CharField(255)，必填 | Doris Job 原名；按集群管理名称。集群、库、名称在绑定后固定，迁移或改名作为新 Job 处理 |
| interval_minutes | PositiveIntegerField，必填 | 首期只支持正整数分钟周期，映射为 EVERY n MINUTE |
| insert_sql | TextField，必填 | 保存单条 INSERT 任务体。服务负责组装 CREATE JOB，时间窗口、聚合及目标表由任务定义表达 |
| doris_job_id | BigIntegerField，可空 | 创建成功或显式接管后保存 FE 返回的 Id；执行记录按此 ID 查询。空值表示本地草稿 |
| create_time / last_modify_time | DateTimeField，自动维护 | 本地配置创建和修改时间 |

列表通过外键索引查询。建议同一个 ClusterInfo 的 `(cluster_id, name)` 只能由一条配置占用，与 Doris 的 Job 名称唯一语义对应。共用物理 FE 的多个集群登记仍可能遇到远端重名，按创建冲突处理。运行状态与最近失败原因在查看运行详情时读取；Task 历史沿用 Doris 的保留策略。字段里无需复制状态、连接参数或 DataLink 身份字段。[Doris 3.x Job 定义](https://doris.apache.org/docs/3.x/sql-manual/sql-statements/job/CREATE-JOB/)

## 管理方法

以下是 metadata 服务方法的建议契约。调用方传入当前租户，服务按租户定位链路和 Job。配置或执行 SQL 仅面向具有相应集群管理权限的操作人，沿用已有 FE 连接配置。写接口提供具名动作，参数只接受该动作所需的字段。FE 账号须具备目标版本执行 Job DDL 的权限。

| 方法 | 输入与结果 | 对 Doris 的影响 |
| --- | --- | --- |
| save_config(link, fields, id=None) | 创建草稿或编辑尚未发布的定义，返回组件 ID | 无 |
| list_configs(link) | 返回该链路的本地配置摘要 | 无 |
| create_job(id) | 发布草稿；成功后记录远端 Job ID 并返回运行状态 | 在指定库执行 CREATE JOB，随后按名取回 ID；新任务按 Doris 默认行为进入 RUNNING |
| adopt_job(link, cluster_id, database, remote_id, fields) | 将现有周期 INSERT Job 绑定到链路；先展示远端实际 SQL 和周期，仅支持能完整表达为本模型的任务 | 仅读取。由管理员指定已存在的 Job，核对名称、ID、库上下文、任务体和周期后记录实际定义。无法确定上下文时由管理员显式提供并核实 |
| get_status(id) | 返回当前远端状态、名称及可见的最近错误；区分草稿、远端缺失及查询错误 | 查 jobs("type"="insert")，精确定位 Job |
| list_tasks(id, page, page_size) | 返回开始/结束时间、执行结果及错误 | 复用现有 insert 类型任务查询，按当前远端 Job ID 分页 |
| pause_job(id) / resume_job(id) | 返回操作后的状态；已经处于目标状态时直接返回 | 调用 Doris PAUSE / RESUME。暂停可能影响正在执行的 Task |
| drop_job(id) | 删除受管远端 Job，成功后清空远端 ID，保留本地定义作为草稿 | 执行 DROP JOB。业务表和已写入的数据保留 |
| detach_config(id) | 删除本地配置和链路关联；可用于废弃草稿或移交已有任务 | 无。已发布 Job 继续按原计划运行 |

**修改 SQL 或周期。** 首期采用显式操作序列：暂停旧 Job，查看在途 Task 和最后成功窗口，保留旧配置以备恢复，然后删除旧 Job、编辑草稿并重新发布。重新创建会获得新的 Job ID，切换前可用旧 ID 查看仍保留的历史。新定义发布失败时草稿可继续修正，旧调度已经停止。恢复旧调度需用保留的旧定义重新发布。该流程不会自行补算切换期间的窗口，业务负责人应根据目标表写入语义决定是否补算。

**存量与重试。** 本地草稿遇到远端同名 Job 时返回冲突，展示远端 ID，由管理员选择接管；不覆盖同名对象。FE 创建成功而本地写入失败也走相同入口。接管属于已有草稿时绑定原记录。对已绑定记录的远端写操作先按名称定位实际 ID，遇到同名新对象则停止，避免误操作。删除返回超时后重新查询，只有能确认旧 Job 已不存在才清空绑定；连接或权限异常保留原配置。建议同一配置的管理写操作在服务层按记录串行执行，跨库失败按上述流程恢复。

## 链路详情示例

同一条 APM 入库链路可挂载按服务汇总和按接口汇总两个 Job，各自保存周期和 INSERT 定义。管理员从链路详情进入指定 Job，可以单独暂停接口汇总，查看上一次执行失败的原因；服务汇总与 DataBus 消费继续运行。链路重新下发时两个 Job 仍保留原 ID。这个例子只要求建立配置关联，组件本身无须理解 APM 指标名、分位数算法或维度。

## 实现时的验收点

1. 链路详情能列出多个 Job；跨租户查询和写操作遵循原有资源权限。普通链路列表和 BKBase apply 无需连接 FE。
2. 验证创建、启停、删除、解除纳管；重复提交、同名冲突、FE 请求超时分别返回可操作的结果。接管一条既有 Job 后远端 ID 和执行记录保持连续。
3. 验证停用链路、重建 BKBase 关系及清理缺失组件均不会意外删除 Job；显式删除一条 Job 后，其他 Job 和物理表仍可访问。
4. 用目标 Doris 版本实测 `jobs`、`tasks` 返回字段、名称大小写、调度周期展示、执行中的暂停行为和账号权限，再确定接管入口可直接回填的字段。

对应代码入口：[DataLink 编排](./data_link.py)、[BKBase 组件基类](./data_link_configs.py)、[已有集群 Job 与 Task 查询](../../../kernel_api/rpc/functions/admin/doris_jobs.py)。现有集群查询面向列表；运行详情需要增加按指定 ID 或名称精确过滤的查询，避免拉全量再筛选。
