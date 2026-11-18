# DataLink 中的 DorisJob 管理方案

**评审稿。** 一个 DataLink 可以挂载多个 Doris 周期 INSERT Job。metadata 保存任务定义和链路归属，Doris FE 负责调度、执行及保存执行记录。第一阶段评审配置模型和管理接口。APM 预计算用于检验设计能否表达实际需求，接入策略、业务 SQL、建表与上线另行交付。

## 组件放在哪里

现有 `DataLink.compose_configs()` 组装 BKBase 资源，`apply_data_link()` 负责下发和清理。现有组件基类的 `delete_config()` 面向 BKBase。建议在同一个 `metadata.models.data_link` 包增加独立 Django 模型 `DorisJobConfig`，通过外键直接关联 DataLink。在链路详情层把 Job 摘要与已有组件并列展示，返回类型标识 `DorisJob`。写操作从 Job 自身的管理入口进入。

| 入口或场景 | 对 DorisJob 的处理 |
| --- | --- |
| 查看链路配置 | 按链路取本地 Job 列表。无需连接 FE 即可展示名称、集群、数据库、周期和上下游组件 |
| 链路重新 apply、BKBase 资源同步、回收缺失组件 | 保持现有流程。Job 不注册到 BKBase kind 映射、策略组件清理列表或 DataBus sinks |
| 停用链路 | 现有 `delete_data_link()` 仅停止 DataBus 并保留关联。建议维持该语义，由管理员按业务窗口单独暂停 Job，允许处理已入库的数据 |
| 物理删除链路 | 有关联 Job 时由外键 PROTECT 阻止删除，先解除纳管或显式删除 Job |
| 一个 Job 汇总多个来源 | 选负责该任务生命周期的链路作为归属；上下游关系单独登记，允许引用同租户其他链路的表组件。启停权限仍由归属链路管理 |

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

## 上下游表关系

按 **源表组件 → DorisJob → 目标表组件** 记录直接依赖。一个 Job 可以有多个 source 和多个 target；同一张表也可以供多个 Job 读取，或由多个 Job 写入。链路归属回答“谁管理 Job”，表关系回答“它从哪里读、写到哪里”。上游数和下游数互相独立，查询经过 Job 节点，无须生成每一对源表和目标表的组合。

建议增加本地模型 `DorisJobTableRelation`，每行表示一个方向上的一个组件引用。

| 字段 | 类型 | 用途 |
| --- | --- | --- |
| job | ForeignKey(DorisJobConfig, CASCADE) | 配置移除时一并移除关系 |
| direction | CharField，source / target | 相对于 Job 的读写方向；同一表可以分别出现在两个方向 |
| result_table_config | ForeignKey(ResultTableConfig, CASCADE)，可空 | 引用逻辑结果表组件，例如需要从链路结果表详情反查生产者或消费者 |
| doris_binding | ForeignKey(DorisStorageBindingConfig, CASCADE)，可空 | 引用具体 DorisBinding，例如同一逻辑表在存储轮换前后有多个绑定，要区分任务实际使用哪一个 |

每条引用通过请求中的 `kind + id` 选择一个外键。声明逻辑依赖时选 ResultTable；依赖特定存储绑定时选 DorisBinding。一个方向可混用两类组件。服务从被引用对象读取名称、租户、namespace 等展示信息。Binding 的 `physical_tables` 可以包含多张物理表，因此 Binding 级引用只表示依赖该绑定；具体读写的物理表以任务 SQL 为准。尚未登记为这两类组件的物理表仍可出现在 SQL 中，组件拓扑只能展示已登记的关系。

例如，周期任务读取请求明细和服务维表，写入一张按天分区的汇总表。它可以声明两个 source（明细的 DorisBinding、维表的 ResultTable）和一个 target（汇总表的 DorisBinding）。如果目标表同时需要从逻辑结果表和实际绑定两个入口反查，可在 target 中显式登记这两个组件。这样有两条目标组件关系，实际写入仍是一张表。

**多个独立目标表。** 关系模型允许登记多个目标。执行层沿用一个配置对应一个 FE Job、一条 INSERT 的约定。若业务分别向服务汇总表、接口汇总表执行两条 INSERT，在同一 DataLink 下声明两个 DorisJob，各自挂真实的源表和目标表。这样既能从链路看到全部输出，又能按目标定位执行失败的 Job。若将来需要把多条 INSERT 当作一个可统一启停的任务，需另行设计对多个远端 Job 的编排和部分成功语义。

## 管理方法

以下是 metadata 服务方法的建议契约。调用方传入当前租户，服务按租户定位链路和 Job。配置或执行 SQL 仅面向具有相应集群管理权限的操作人，沿用已有 FE 连接配置。写接口提供具名动作，参数只接受该动作所需的字段。FE 账号须具备目标版本执行 Job DDL 的权限。

| 方法 | 输入与结果 | 对 Doris 的影响 |
| --- | --- | --- |
| save_config(link, fields, sources, targets, id=None) | 在同一 metadata 事务中保存草稿及两组组件引用，返回组件 ID | 无 |
| list_configs(link) | 返回配置摘要及按方向分组的组件引用 | 无 |
| set_table_relations(id, sources, targets) | 整体替换两组关系，空数组清空该方向。草稿和已接管 Job 均可单独修订拓扑 | 无 |
| list_jobs_by_table(kind, component_id, direction=None) | 反查直接引用该组件的 Job 及归属链路；source 查消费者，target 查生产者，省略方向则返回双方及各自方向 | 无 |
| create_job(id) | 发布草稿；成功后记录远端 Job ID 并返回运行状态 | 在指定库执行 CREATE JOB，随后按名取回 ID；新任务按 Doris 默认行为进入 RUNNING |
| adopt_job(link, cluster_id, database, remote_id, fields, sources, targets) | 将现有周期 INSERT Job 绑定到链路；先展示远端实际 SQL 和周期，仅支持能完整表达为本模型的任务 | 仅读取。由管理员指定已存在的 Job，核对名称、ID、库上下文、任务体和周期后记录实际定义，关联调用方提供的上下游组件。无法确定上下文时由管理员显式提供并核实 |
| get_status(id) | 返回当前远端状态、名称及可见的最近错误；区分草稿、远端缺失及查询错误 | 查 jobs("type"="insert")，精确定位 Job |
| list_tasks(id, page, page_size) | 返回开始/结束时间、执行结果及错误 | 复用现有 insert 类型任务查询，按当前远端 Job ID 分页 |
| pause_job(id) / resume_job(id) | 返回操作后的状态；已经处于目标状态时直接返回 | 调用 Doris PAUSE / RESUME。暂停可能影响正在执行的 Task |
| drop_job(id) | 删除受管远端 Job，成功后清空远端 ID，保留本地定义作为草稿 | 执行 DROP JOB。业务表和已写入的数据保留 |
| detach_config(id) | 删除本地配置和链路关联；可用于废弃草稿或移交已有任务 | 无。已发布 Job 继续按原计划运行 |

**关系维护。** 保存时按当前租户和调用人可见范围解析组件 ID。接管存量任务时允许两组关系为空，后续可补录。单独编辑关系只修改 metadata，SQL 和调度保持原样；修改 SQL 涉及读写表变化时，在保存新草稿时一并更新关系。删除远端 Job 并保留草稿时也保留上下游配置；解除纳管时随本地 Job 删除关系。组件本身被删除时只清理指向它的引用，远端 Job 继续运行；以新组件替换旧组件后通过关系编辑入口重新关联。

**修改 SQL 或周期。** 首期采用显式操作序列：暂停旧 Job，查看在途 Task 和最后成功窗口，保留旧配置以备恢复，然后删除旧 Job、编辑草稿并重新发布。重新创建会获得新的 Job ID，切换前可用旧 ID 查看仍保留的历史。新定义发布失败时草稿可继续修正，旧调度已经停止。恢复旧调度需用保留的旧定义重新发布。该流程不会自行补算切换期间的窗口，业务负责人应根据目标表写入语义决定是否补算。

**存量与重试。** 本地草稿遇到远端同名 Job 时返回冲突，展示远端 ID，由管理员选择接管；不覆盖同名对象。FE 创建成功而本地写入失败也走相同入口。接管属于已有草稿时绑定原记录。对已绑定记录的远端写操作先按名称定位实际 ID，遇到同名新对象则停止，避免误操作。删除返回超时后重新查询，只有能确认旧 Job 已不存在才清空绑定；连接或权限异常保留原配置。建议同一配置的管理写操作在服务层按记录串行执行，跨库失败按上述流程恢复。

## 链路详情示例

同一条 APM 入库链路可挂载按服务汇总和按接口汇总两个 Job，各自保存周期和 INSERT 定义。管理员从链路详情进入指定 Job，可以单独暂停接口汇总，查看上一次执行失败的原因；服务汇总与 DataBus 消费继续运行。链路重新下发时两个 Job 仍保留原 ID。这个例子只要求建立配置关联，组件本身无须理解 APM 指标名、分位数算法或维度。

## 实现时的验收点

1. 链路详情能列出多个 Job；跨租户查询和写操作遵循原有资源权限。普通链路列表和 BKBase apply 无需连接 FE。
2. 验证创建、启停、删除、解除纳管；重复提交、同名冲突、FE 请求超时分别返回可操作的结果。接管一条既有 Job 后远端 ID 和执行记录保持连续。
3. 验证停用链路、重建 BKBase 关系及清理缺失组件均不会意外删除 Job；显式删除一条 Job 后，其他 Job 和物理表仍可访问。
4. 用目标 Doris 版本实测 `jobs`、`tasks` 返回字段、名称大小写、调度周期展示、执行中的暂停行为和账号权限，再确定接管入口可直接回填的字段。
5. 一个 Job 声明两条 source 和两条 target，验证两个方向均能独立增删、按组件 ID 反查。覆盖同表既读又写、不同 Job 共享一张表、历史与当前 DorisBinding 同时存在、跨链路同租户引用。验证单独修改关系不会触发 FE DDL。

对应代码入口：[DataLink 编排](./data_link.py)、[BKBase 组件基类](./data_link_configs.py)、[已有集群 Job 与 Task 查询](../../../kernel_api/rpc/functions/admin/doris_jobs.py)。现有集群查询面向列表；运行详情需要增加按指定 ID 或名称精确过滤的查询，避免拉全量再筛选。
