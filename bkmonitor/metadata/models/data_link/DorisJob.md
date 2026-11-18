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

## apply_data_link 与 DorisJob 怎么配合

**建议把一次联合发布拆成两个可独立重试的阶段。** 第一阶段仍由 DataLink 向 BKBase 申请 RT、Binding、DataBus；第二阶段由 metadata 在源表和目标表就绪后向 Doris FE 发布本次选中的 Job。调用人可以一次提交链路和 Job，链路详情分别展示两个阶段的结果。

### 在哪里接入

现有 `apply_data_link()` 先在 metadata 事务内 compose 本地组件，提交后合并远端配置，调用带重试的 BKBase apply，成功后清理缺失组件并更新本地状态。部分调用方随后才调用 `sync_metadata()` 回填表名和集群信息。BKBase 接受申请时，FE 中的表仍可能尚未创建。因此 Job DDL 要放在调用方完成链路下发及必要的元数据回填之后，并在实际物理表可用时执行。[链路主流程](./data_link.py) · [链路任务入口](../../task/datalink.py)

| 阶段 | 谁负责 | 行为 |
| --- | --- | --- |
| 选择本次发布内容 | 上层链路发布入口 | 普通 apply 沿用原入口。联合发布显式携带选中的 Job 草稿 ID；新增链路也可携带模板或自由配置，引用本次 compose 才创建的组件时，按输出的组件名称和 namespace 解析本地主键 |
| 申请链路 | 现有 DataLink 流程 | 执行 apply 和该入口所需的 sync。失败直接返回链路阶段错误，本次请求尚未登记待发布 Job。仅靠本地 compose 成功不能触发 Job |
| 登记 Job 发布 | 上层入口调用 metadata Job 服务 | 链路阶段成功后，在一个本地事务中保存本次 Job 定义、上下游关系及发布意图。事务提交后投递 Job 任务。若本地保存失败，返回“链路已下发、Job 配置保存失败”，已有链路可直接进入 Job 发布入口 |
| 等待依赖并创建 | Job 任务，按配置 ID 执行 | 使用该 Job 自己的源、目标和最终库表定位检查依赖。BKBase 管理的 DorisBinding 可通过其状态及物理表映射定位；跨链路的表同样按实际引用处理。对声明的物理库表在目标连接下确认可访问，再按保存的 SQL 执行 CREATE JOB。自由 SQL 中未声明的依赖由 FE 执行结果暴露 |
| 展示结果 | 链路详情 | 链路展示既有的申请/运行状态，每个 Job 单列发布状态、当前 FE 状态及异常原因。创建成功表示 FE 已登记调度，首轮 INSERT 是否成功以 Task 记录为准 |

这里的“就绪”只要求本 Job 所用的库表和绑定可用。DataBus 是否已有首批数据、其他 Job 是否成功、整个链路是否全部组件 OK，都不作为统一前置条件。例如两个输出中只有服务汇总表建好，可以先发布服务汇总 Job，接口汇总 Job 继续等待自己的目标表。

### 如何重试、停用和重新 apply

建议在 Job 配置上保存 `publish_status`（draft / pending / published / failed）和可空的 `publish_error`。这两个字段记录 metadata 的发布进度；运行或暂停仍从 FE 查询。独立“发布 Job”与联合发布复用同一个 `publish_jobs(link, job_ids)` 入口。已接管的 Job 直接记为 published，显式删除远端并保留配置时回到 draft。

| 情况 | 恢复行为 |
| --- | --- |
| 依赖正在创建、FE 短暂不可达 | 保留 pending，复用任务框架做有限次数的延迟重试。达到上限转 failed，记录具体库表或错误。事务提交后投递失败时保留 pending，可从同一入口再次投递 |
| 部分 Job 失败 | 对成功项保留远端 ID，只重试选中的失败项。依赖修复后直接重试 Job；无需再次申请 DataBus、RT 或 Binding |
| FE 创建成功但调用超时，或写回 ID 失败 | 先按名称查询。已绑定相同 ID 的记录直接返回；远端存在同名对象但本地缺少绑定时返回待接管原因，走显式接管流程 |
| 链路重复 apply 或模板更新 | 默认不发布草稿。显式重复发布已绑定 Job 时返回已有结果，保留远端 ID 和暂停状态。修改 SQL 或替换物理表时，显式保存并发布选中的新定义 |
| 等待期间修改草稿、删除表组件或停链 | pending 配置先撤销本次待发布操作再编辑。相关组件被移除时，待发布 Job 标为 failed 并记录缺失引用；停用归属链路时撤销尚未开始的发布。任务执行 DDL 前在同一 Job 写操作串行区重新读取发布状态。已开始的创建返回实际结果，已发布 Job 的启停仍由管理员决定 |

若调用进程在链路成功与登记 Job 之间退出，重新提交联合发布可复用现有组件；已有草稿也可直接从 Job 入口补发。首期沿用现有任务机制和逐 Job 重试，无须在 MySQL、BKBase 和 Doris 之间引入分布式事务。

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
| publish_status / publish_error | CharField，默认 draft / TextField，可空 | metadata 最近一次发布的进度和失败原因，供任务恢复和链路详情使用 |
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

## 两种配置入口

两种入口都生成前述 `DorisJobConfig` 草稿及其表关系，沿用相同的发布、启停和查询方法。

| 入口 | 调用方提供 | 保存结果 |
| --- | --- | --- |
| 模板配置 | 模板 key、按槽位命名的 `sources` 和 `targets`、本次参数，以及归属链路和执行集群等公共配置 | 按模板生成具体 INSERT、周期和直接表关系；每个输出返回独立草稿 ID |
| 自由配置 | Job 名称、数据库、周期、完整 `insert_sql`，以及显式声明的 `sources` 和 `targets` | 原样保存任务体，按声明记录表关系；适用于临时任务、已有任务接管和模板未覆盖的 SQL |

**模板定义。** 建议首期把模板随 metadata 代码维护，用稳定的 key 查找。每份模板声明源槽位、目标槽位、业务参数及默认值，以及每个输出对应的 INSERT 模板。一个输出声明任务名称后缀、使用哪些源槽位、写入哪个目标槽位。周期可以由模板给默认值，也可以在本次配置中指定。模板的管理与 Job 发布是两个独立动作。

**组件与物理表。** 槽位名如 `events` 或 `daily`，用于在 SQL 中引用输入。每个槽位可以同时携带组件引用和本次使用的物理库表。当已有 DorisBinding 提供唯一可用的物理表时可直接取用；有多个用途时由调用方选择对应物理表。只提供逻辑 ResultTable 且无法确定实际库表时，预览返回待补充的槽位。未登记为组件的库表也可以作为模板输入，此时预览显示物理表，拓扑只记录能够关联到组件的槽位。渲染由服务按库名、表名分别引用标识符，业务参数按模板声明的类型生成 SQL 字面值。

以下为配置请求示例，组件 ID、物理表和模板名称仅用于说明。

```json
{
  "template_key": "daily_rollup",
  "name": "request_rollup",
  "sources": {
    "events": {"kind": "DorisBinding", "id": 11, "database": "raw", "table": "requests"},
    "services": {"kind": "ResultTable", "id": 12, "database": "dim", "table": "services"}
  },
  "targets": {
    "by_service": {"kind": "DorisBinding", "id": 21, "database": "agg", "table": "requests_by_service"},
    "by_app": {"kind": "DorisBinding", "id": 22, "database": "agg", "table": "requests_by_app"}
  },
  "params": {"lookback_days": 1},
  "interval_minutes": 60
}
```

在该示例模板中，`by_service` 输出只读取 `events`，`by_app` 输出读取 `events` 和 `services`。一次保存生成 `request_rollup_by_service` 和 `request_rollup_by_app` 两份草稿，各有自己的 INSERT 和表关系。反查 `services` 只会找到后一个 Job。两份草稿在同一个本地事务中创建，随后可分别发布；查看运行状态或修复一次发布失败时，使用对应的 Job ID。

**模板实例的保存与编辑。** 建议在 Job 配置上增加两个可空字段：`template_key`（CharField）记录来源，`template_inputs`（JSONField）保留本次输出标识、槽位实参和业务参数，供回显和重新预览。自由配置时两个字段为空。已保存的 `insert_sql` 和周期是发布依据；更新模板只影响下一次渲染。修改已有实例时按组件 ID 选择草稿、重新预览并保存；对已发布的 Job 沿用显式替换流程。也可以将草稿切换为自由配置：保留渲染后的 SQL、周期和已有表关系，清除模板来源后直接编辑。单独修订拓扑只更新关系，模板回显的输入仍代表上次渲染；下次显式套用模板时应展示将被替换的 SQL 和表关系。

## 管理方法

以下是 metadata 服务方法的建议契约。调用方传入当前租户，服务按租户定位链路和 Job。配置或执行 SQL 仅面向具有相应集群管理权限的操作人，沿用已有 FE 连接配置。写接口提供具名动作，参数只接受该动作所需的字段。FE 账号须具备目标版本执行 Job DDL 的权限。

| 方法 | 输入与结果 | 对 Doris 的影响 |
| --- | --- | --- |
| list_templates() | 返回可用模板的 key、源和目标槽位、参数及周期默认值 | 无 |
| preview_template(link, template_key, sources, targets, params, options) | 返回各输出的名称、物理库表、渲染 SQL、周期和直接组件关系，供检查 | 无，不落库 |
| save_from_template(link, template_key, sources, targets, params, options) | 按预览相同的规则生成并一次保存各输出草稿，返回输出名到组件 ID 的映射；编辑时显式指定对应草稿 ID | 无 |
| save_config(link, fields, sources, targets, id=None) | 在同一 metadata 事务中保存草稿及两组组件引用，返回组件 ID | 无 |
| list_configs(link) | 返回配置摘要及按方向分组的组件引用 | 无 |
| set_table_relations(id, sources, targets) | 整体替换两组关系，空数组清空该方向。草稿和已接管 Job 均可单独修订拓扑 | 无 |
| list_jobs_by_table(kind, component_id, direction=None) | 反查直接引用该组件的 Job 及归属链路；source 查消费者，target 查生产者，省略方向则返回双方及各自方向 | 无 |
| publish_jobs(link, job_ids) | 显式提交选中 Job 的发布请求，返回每项发布状态 | 提交后由 Job 任务逐项等待依赖并调用 create_job |
| create_job(id) | 发布任务执行单个 pending 配置；成功后记录远端 Job ID 并返回运行状态 | 在指定库执行 CREATE JOB，随后按名取回 ID；新任务按 Doris 默认行为进入 RUNNING |
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
6. 用两源两目标模板预览并保存，核对各输出实际使用的源、目标与 SQL。更新模板后已存草稿及运行中 Job 保持原定义；已有草稿能重新渲染，也能切换为自由配置。验证自由配置可在没有模板的情况下独立保存和发布。
7. 验证 BKBase apply 失败、apply 成功但表未就绪、两个 Job 仅一个成功、停链时仍有 pending Job 四种情况。分别检查两个阶段的状态、FE 创建次数、单项重试及重新 apply 后已暂停 Job 的状态。

对应代码入口：[DataLink 编排](./data_link.py)、[BKBase 组件基类](./data_link_configs.py)、[已有集群 Job 与 Task 查询](../../../kernel_api/rpc/functions/admin/doris_jobs.py)。现有集群查询面向列表；运行详情需要增加按指定 ID 或名称精确过滤的查询，避免拉全量再筛选。
